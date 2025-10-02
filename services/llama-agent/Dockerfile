# Multi-stage build for optimized container size and startup time
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

# Create non-root user for security and resource isolation
RUN groupadd -r agent && useradd -r -g agent -u 1001 agent \
    && mkdir -p /app/logs /app/tmp /home/agent/.local \
    && chown -R agent:agent /app /home/agent

# Copy Python packages from builder stage to user directory
COPY --from=builder --chown=agent:agent /root/.local /home/agent/.local

# Ensure executable permissions on installed binaries
RUN chmod +x /home/agent/.local/bin/*

# Copy application code
COPY --chown=agent:agent . .

# Switch to non-root user
USER agent

# Set environment variables for optimization
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/agent/.local/bin:$PATH \
    # Memory optimization
    MALLOC_ARENA_MAX=2 \
    # Agent-specific optimizations
    AGENT_STARTUP_TIMEOUT=30 \
    AGENT_GRACEFUL_SHUTDOWN_TIMEOUT=10 \
    # Resource monitoring
    METRICS_ENABLED=true \
    METRICS_PORT=8000

# Health check for container orchestration
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose metrics port
EXPOSE 8000

# Use optimized startup script for better resource management and graceful shutdown
CMD ["python", "-u", "startup.py"]