# MCP Gateway Dockerfile
# Implements containerized deployment for Requirements 6.1, 6.3

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user for security
RUN groupadd -r mcp-gateway && useradd -r -g mcp-gateway mcp-gateway
RUN chown -R mcp-gateway:mcp-gateway /app
USER mcp-gateway

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Expose port
EXPOSE 3000

# Set environment variables
ENV PYTHONPATH=/app
ENV MCP_GATEWAY_CONFIG=/app/config/mcp-gateway.json

# Start the gateway server
CMD ["python", "-m", "uvicorn", "src.gateway:app", "--host", "0.0.0.0", "--port", "3000"]