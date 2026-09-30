# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home /app app

# Dependencies are installed from pyproject.toml alone (with a stub package and an empty
# README), so changes to code or docs do not invalidate these layers. Only editing
# pyproject.toml reinstalls dependencies. The pip cache mount keeps downloads between rebuilds.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py README.md

# GPU worker: torch wheels bundle CUDA, the host needs only the NVIDIA driver and
# nvidia-container-toolkit (on Windows: Docker Desktop with WSL 2). The CUDA major version of
# torch must be supported by the host driver: CUDA 12.x builds (cu126/cu128) run on 12.x drivers,
# CUDA 13 builds need a newer driver. Model weights go to the HF_HOME volume, not the image.
FROM base AS worker
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
ENV HF_HOME=/app/hf_cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install torch --index-url "${TORCH_INDEX_URL}" \
    && pip install ".[model]"
COPY README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir --no-deps . \
    && mkdir -p /app/storage/input /app/storage/output /app/storage/temp /app/hf_cache \
    && chown -R app:app /app
USER app
CMD ["python", "-m", "app.worker.worker"]

# Default (last) stage: lightweight image for api, bot, migrate and the mock worker.
FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install .
COPY README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir --no-deps . \
    && mkdir -p /app/storage/input /app/storage/output /app/storage/temp \
    && chown -R app:app /app
USER app

CMD ["python", "-m", "app.bot.bot"]
