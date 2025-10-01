# Multi-stage build for optimized container size
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Create non-root user for security
RUN groupadd -r cerebras && useradd -r -g cerebras -u 1002 cerebras \
    && mkdir -p /app/logs /app/tmp \
    && chown -R cerebras:cerebras /app

# Copy source code
COPY --chown=cerebras:cerebras src/ ./src/
COPY --chown=cerebras:cerebras config/ ./config/

# Switch to non-root user
USER cerebras

# Set environment variables for optimization
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH \
    # Memory optimization
    MALLOC_ARENA_MAX=2 \
    # Uvicorn optimization
    UVICORN_WORKERS=1 \
    UVICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker \
    # Resource monitoring
    METRICS_ENABLED=true \
    METRICS_PORT=8002

# Health check for container orchestration
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 8002

# Use exec form with optimized uvicorn settings for better performance
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-log", "--log-level", "info", "--no-server-header"]