import asyncio
import hmac
import json
import logging
import math
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from src.api_protection import BodyLimitMiddleware, InMemoryRateLimiter
from src.model_integrity import verify_model_integrity
from src.val_predict import DNSPredictor

ROOT = Path(__file__).resolve().parents[1]

MODEL_PATH = ROOT / "models" / "logistic_regression_model.onnx"
HASH_PATH = ROOT / "config" / "model.sha256"
MANIFEST_PATH = ROOT / "data" / "ci" / "manifest.json"

MAX_ROWS = 10_000
MAX_BODY_BYTES = 2 * 1024 * 1024
EXPECTED_FEATURES = 31

PREDICTION_TIMEOUT_SECONDS = 10
PREDICTION_QUEUE_TIMEOUT_SECONDS = 1
MAX_CONCURRENT_PREDICTIONS = 2

# Structured JSON logging.
class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event_data = getattr(record, "event_data", None)
        if event_data:
            entry.update(event_data)

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

logger = logging.getLogger("dns_api")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False

# Prometheus metrics. Labels have bounded cardinality.
REQUESTS = Counter(
    "dns_api_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)

REQUEST_DURATION = Histogram(
    "dns_api_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
)

HTTP_ERRORS = Counter(
    "dns_api_http_errors_total",
    "HTTP errors",
    ["status_class"],
)

VALIDATION_FAILURES = Counter(
    "dns_api_validation_failures_total",
    "Input validation failures",
    ["status"],
)

RATE_LIMIT_FAILURES = Counter(
    "dns_api_rate_limit_rejections_total",
    "Requests rejected by rate limiting",
)

PREDICTIONS = Counter(
    "dns_api_predictions_total",
    "Successful prediction requests",
)

with MANIFEST_PATH.open(encoding="utf-8") as file:
    FEATURES = json.load(file)["features"]

if len(FEATURES) != EXPECTED_FEATURES:
    raise RuntimeError("Invalid feature schema in manifest")

state = {
    "predictor": None,
    "model_version": None,
    "ready": False,
}

rate_limiter = InMemoryRateLimiter(limit=20, window_seconds=60)
prediction_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PREDICTIONS)
active_prediction_tasks = set()


def release_prediction_slot(task):
    """Release capacity only after the underlying worker has finished."""
    active_prediction_tasks.discard(task)
    prediction_semaphore.release()

    # Retrieve background exceptions to avoid unobserved-task warnings.
    if not task.cancelled():
        task.exception()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["ready"] = False
    state["predictor"] = None
    state["model_version"] = None

    try:
        # Integrity verification happens before ONNX Runtime loading.
        model_hash = verify_model_integrity(MODEL_PATH, HASH_PATH)
        predictor = DNSPredictor(str(MODEL_PATH))

        state["predictor"] = predictor
        state["model_version"] = model_hash[:12]
        state["ready"] = True

        logger.info(
            "Model loaded",
            extra={
                "event_data": {
                    "model_version": state["model_version"]
                }
            },
        )
    except Exception:
        # Do not expose internal error details through /health.
        logger.exception("Model initialization failed")

    yield

    # Do not accept new predictions during shutdown.
    state["ready"] = False

    # Wait for already running inference workers to finish.
    if active_prediction_tasks:
        await asyncio.gather(
            *list(active_prediction_tasks),
            return_exceptions=True,
        )

    state["predictor"] = None


app = FastAPI(
    title="DNS Tunneling Detection API",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(ROOT / "static" / "index.html")

app.add_middleware(
    BodyLimitMiddleware,
    max_bytes=MAX_BODY_BYTES,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request error",
            extra={
                "event_data": {
                    "request_id": request_id,
                    "route": "unmatched",
                }
            },
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    duration = time.perf_counter() - started
    status = response.status_code

    route_object = request.scope.get("route")
    route = getattr(route_object, "path", "unmatched")

    REQUESTS.labels(request.method, route, str(status)).inc()
    REQUEST_DURATION.labels(request.method, route).observe(duration)

    if 400 <= status < 500:
        HTTP_ERRORS.labels("4xx").inc()

    if status >= 500:
        HTTP_ERRORS.labels("5xx").inc()

    if status in (400, 413, 415, 422):
        VALIDATION_FAILURES.labels(str(status)).inc()

    if status == 429:
        RATE_LIMIT_FAILURES.inc()

    refusal_type = None
    if status == 401:
        refusal_type = "authentication"
    elif status == 429:
        refusal_type = "rate_limit"
    elif status in (400, 413, 415, 422):
        refusal_type = "validation"
    elif status >= 500:
        refusal_type = "server_error"

    logger.info(
        "HTTP request",
        extra={
            "event_data": {
                "request_id": request_id,
                "route": route,
                "method": request.method,
                "status": status,
                "duration_seconds": round(duration, 6),
                "model_version": state["model_version"],
                "refusal_type": refusal_type,
            }
        },
    )

    response.headers["X-Request-ID"] = request_id
    return response


def check_token(token: str | None):
    expected = os.getenv("API_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured",
        )

    if token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    if not state["ready"] or state["predictor"] is None:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )

    return {
        "status": "healthy",
        "model_version": state["model_version"],
    }


@app.get("/metrics")
async def metrics(
    x_api_token: str | None = Header(default=None),
):
    check_token(x_api_token)

    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


@app.post("/predict")
async def predict(
    request: Request,
    x_api_token: str | None = Header(default=None),
):
    check_token(x_api_token)

    if not state["ready"] or state["predictor"] is None:
        raise HTTPException(status_code=503, detail="Model is not ready")

    client_ip = request.client.host if request.client else "unknown"

    if not rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    content_type = request.headers.get("content-type", "")
    if content_type.split(";")[0].strip().lower() != "application/json":
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json",
        )

    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(payload, dict) or set(payload) != {"rows"}:
        raise HTTPException(
            status_code=422,
            detail="Expected an object containing only the 'rows' field",
        )

    rows = payload["rows"]

    if not isinstance(rows, list) or not rows:
        raise HTTPException(
            status_code=422,
            detail="'rows' must be a non-empty list",
        )

    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail="Too many rows")

    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FEATURES):
            raise HTTPException(
                status_code=422,
                detail="Feature names do not match the model schema",
            )

        for feature in FEATURES:
            value = row[feature]

            # bool is a subclass of int in Python, so reject it explicitly.
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(
                    status_code=422,
                    detail="Feature values must be numeric",
                )

            if not math.isfinite(value):
                raise HTTPException(
                    status_code=422,
                    detail="NaN and Inf are not allowed",
                )

            # The existing predictor converts input to float32.
            # Reject values that overflow during this conversion.
            if not np.isfinite(np.float32(value)):
                raise HTTPException(
                    status_code=422,
                    detail="Feature value is outside the supported range",
                )

    try:
        frame = pd.DataFrame(rows, columns=FEATURES).astype(np.float32)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(
            status_code=422,
            detail="Invalid feature values",
        )

    # Bound both queued and actively executing predictions.
    try:
        await asyncio.wait_for(
            prediction_semaphore.acquire(),
            timeout=PREDICTION_QUEUE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Prediction capacity is temporarily unavailable",
        )

    slot_transferred = False
    worker = None

    try:
        worker = asyncio.create_task(
            asyncio.to_thread(state["predictor"].predict, frame)
        )
        active_prediction_tasks.add(worker)

        try:
            predictions = await asyncio.wait_for(
                asyncio.shield(worker),
                timeout=PREDICTION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # The thread cannot be forcibly stopped safely.
            # Keep its semaphore slot until it really finishes.
            worker.add_done_callback(release_prediction_slot)
            slot_transferred = True

            raise HTTPException(
                status_code=504,
                detail="Prediction timed out",
            )

        PREDICTIONS.inc()

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Prediction failed",
            extra={
                "event_data": {
                    "request_id": request.state.request_id,
                    "model_version": state["model_version"],
                }
            },
        )
        raise HTTPException(status_code=500, detail="Prediction failed")
    finally:
        if not slot_transferred:
            if worker is not None:
                active_prediction_tasks.discard(worker)
            prediction_semaphore.release()

    return {
        "prediction": predictions,
        "model_version": state["model_version"],
        "request_id": request.state.request_id,
    }
