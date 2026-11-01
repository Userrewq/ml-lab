FROM python:3.10-slim-trixie@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get purge -y libc6-dev linux-libc-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --no-compile -r requirements.txt \
    && useradd --uid 10001 --create-home appuser

COPY src/val_predict.py src/docker_smoke.py ./src/
COPY models/logistic_regression_model.onnx ./models/
COPY data/ci/ ./data/ci/

ENV PYTHONPATH=/app/src

USER 10001:10001

CMD ["python", "src/docker_smoke.py"]
