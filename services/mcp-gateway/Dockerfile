# MCP Gateway Dockerfile - Optimized for Requirements 6.1, 6.3, 6.4
# Multi-stage build for optimized container size and startup time

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
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

# Create non-root user for security and resource isolation
RUN groupadd -r mcp-gateway && useradd -r -g mcp-gateway -u 1003 mcp-gateway \
    && mkdir -p /app/logs /app/tmp /app/config /home/mcp-gateway/.local \
    && chown -R mcp-gateway:mcp-gateway /app /home/mcp-gateway

# Copy Python packages from builder stage to user directory
COPY --from=builder --chown=mcp-gateway:mcp-gateway /root/.local /home/mcp-gateway/.local

# Ensure executable permissions on installed binaries
RUN chmod +x /home/mcp-gateway/.local/bin/*

# Copy application code
COPY --chown=mcp-gateway:mcp-gateway src/ ./src/
COPY --chown=mcp-gateway:mcp-gateway config/ ./config/

# Switch to non-root user
USER mcp-gateway

# Set environment variables for optimization
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/mcp-gateway/.local/bin:$PATH \
    # Memory optimization
    MALLOC_ARENA_MAX=2 \
    # MCP Gateway configuration
    MCP_GATEWAY_CONFIG=/app/config/mcp-gateway.json \
    # Uvicorn optimization for high concurrency
    UVICORN_BACKLOG=2048 \
    # Resource monitoring
    METRICS_ENABLED=true \
    METRICS_PORT=8001 \
    # Graceful shutdown
    GRACEFUL_SHUTDOWN_TIMEOUT=15

# Health check optimized for faster startup detection
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Expose ports
EXPOSE 3000 8001

# Use exec form with optimized uvicorn settings for high-concurrency load
CMD ["uvicorn", "src.gateway:app", "--host", "0.0.0.0", "--port", "3000", \
     "--backlog", "2048", "--access-log", "--log-level", "info", \
     "--timeout-keep-alive", "5"]