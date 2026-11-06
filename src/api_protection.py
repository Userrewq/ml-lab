import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound the actual buffered request body for /predict."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/predict":
            await self.app(scope, receive, send)
            return

        headers = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]

        if len(headers) > 1:
            response = JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length"},
            )
            await response(scope, receive, send)
            return

        if headers:
            try:
                declared_size = int(headers[0])
                if declared_size < 0:
                    raise ValueError
            except ValueError:
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length"},
                )
                await response(scope, receive, send)
                return

            if declared_size > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
                await response(scope, receive, send)
                return

        body = bytearray()

        while True:
            message = await receive()

            if message["type"] == "http.disconnect":
                return

            if message["type"] != "http.request":
                continue

            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
                await response(scope, receive, send)
                return

            body.extend(chunk)

            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive():
            nonlocal replayed

            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": bytes(body),
                    "more_body": False,
                }

            return await receive()

        await self.app(scope, replay_receive, send)


class InMemoryRateLimiter:
    """Per-client sliding-window limiter for a single application process."""

    def __init__(self, limit: int = 20, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        timestamps = self.requests[key]

        while timestamps and now - timestamps[0] >= self.window_seconds:
            timestamps.popleft()

        if len(timestamps) >= self.limit:
            return False

        timestamps.append(now)

        if len(self.requests) > 10_000:
            expired = [
                client
                for client, values in self.requests.items()
                if not values or now - values[-1] >= self.window_seconds
            ]
            for client in expired:
                self.requests.pop(client, None)

        return True
