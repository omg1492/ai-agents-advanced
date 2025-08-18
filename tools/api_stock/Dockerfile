# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_PYTHON=1 \
    PATH="/root/.local/bin:${PATH}"

# Install curl/ca-certificates and uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies (creates and uses a local .venv)
RUN uv sync --frozen --no-dev

# Copy application code
COPY main.py ./

EXPOSE 8011

# Defaults; can be overridden at runtime
ENV PORT=8011 \
    RELOAD=false \
    LOG_LEVEL=INFO

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
