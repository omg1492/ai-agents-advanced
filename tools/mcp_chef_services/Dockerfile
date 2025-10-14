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

# Copy manifests for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY main.py mock_data.py ./

# Default runtime env
ENV LOG_LEVEL=INFO \
    HOST=0.0.0.0 \
    PORT=8013

EXPOSE 8013

# Use main.py entrypoint which reads PORT env variable
CMD ["uv", "run", "python", "main.py"]
