# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY main.py ./
COPY utils/ ./utils/

# Expose port (default 5003)
EXPOSE 5003

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Run the application using uv
CMD ["uv", "run", "python", "main.py"]
