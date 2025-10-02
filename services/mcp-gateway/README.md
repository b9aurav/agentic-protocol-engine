# MCP Gateway Service

The MCP Gateway is a FastAPI-based HTTP server that implements standardized protocol mediation for the Agentic Protocol Engine (APE). It serves as the central routing and translation service between AI agents and target applications.

## Features

- **FastAPI-based HTTP server** for high-performance request routing
- **Pydantic schema validation** for MCP-compliant JSON requests/responses
- **Trace ID injection and propagation** for request correlation
- **Structured JSON logging** for comprehensive observability
- **Retry logic with exponential backoff** for resilient target service communication
- **Prometheus metrics collection** for performance monitoring
- **Health checks** for service availability monitoring
- **Configurable routing** via JSON configuration files

## Requirements Implementation

This service implements the following APE requirements:

- **Requirement 3.1**: Central routing and protocol translation service
- **Requirement 3.2**: Standard HTTP/JSON format responses
- **Requirement 3.3**: Enforce MCP-compliant JSON schema validation
- **Requirement 3.5**: Pass session headers through the MCP Gateway
- **Requirement 4.2**: Trace ID injection and propagation
- **Requirement 8.2**: Structured logging for all requests and responses

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the gateway by editing `config/mcp-gateway.json`

3. Start the server:
```bash
python -m uvicorn src.gateway:app --host 0.0.0.0 --port 3000
```

## Configuration

The gateway is configured via a JSON file (default: `config/mcp-gateway.json`). Example configuration:

```json
{
  "gateway": {
    "name": "mcp-gateway",
    "port": 3000,
    "host": "0.0.0.0"
  },
  "routes": {
    "sut_api": {
      "name": "System Under Test API",
      "base_url": "http://localhost:8080",
      "timeout": 30,
      "retry_policy": {
        "max_retries": 3,
        "backoff_factor": 1.5,
        "retry_on": [502, 503, 504, 408, 429]
      }
    }
  },
  "logging": {
    "level": "INFO",
    "format": "json"
  }
}
```

## API Endpoints

### POST /mcp/request
Process MCP-compliant requests from agents.

**Request Body:**
```json
{
  "api_name": "sut_api",
  "method": "GET",
  "path": "/api/users",
  "headers": {"Authorization": "Bearer token"},
  "data": {"key": "value"},
  "trace_id": "optional-trace-id"
}
```

**Response:**
```json
{
  "status_code": 200,
  "headers": {"Content-Type": "application/json"},
  "body": {"result": "data"},
  "execution_time": 0.123,
  "trace_id": "trace-id-123"
}
```

### GET /health
Health check endpoint returning gateway and route status.

### GET /routes
List all configured routes and their settings.

### GET /metrics
Prometheus metrics endpoint for monitoring.

## Docker Deployment

Build the Docker image:
```bash
docker build -t mcp-gateway .
```

Run the container:
```bash
docker run -p 3000:3000 -v $(pwd)/config:/app/config mcp-gateway
```

## Testing

Run the test suite:
```bash
python test_gateway.py
```

## Logging

The gateway provides structured JSON logging with the following fields:

- `trace_id`: Unique identifier for request correlation
- `method`: HTTP method
- `path`: Request path
- `status_code`: Response status code
- `execution_time`: Request processing time
- `api_name`: Target API identifier
- `client_ip`: Client IP address

## Metrics

Prometheus metrics are available at `/metrics`:

- `mcp_gateway_requests_total`: Total requests processed
- `mcp_gateway_request_duration_seconds`: Request duration histogram
- `mcp_gateway_active_requests`: Active requests gauge
- `mcp_gateway_route_health`: Route health status
- `mcp_gateway_errors_total`: Error count by type
- `mcp_gateway_retries_total`: Retry attempts count

## Error Handling

The gateway implements comprehensive error handling:

- **Request validation errors**: Return 422 with validation details
- **Route not found**: Return 404 with error message
- **Target service errors**: Retry with exponential backoff
- **Timeout errors**: Return 502 with timeout information
- **All errors include trace ID** for correlation

## Development

For development, install additional dependencies:
```bash
pip install -r requirements-dev.txt
```

Run with auto-reload:
```bash
uvicorn src.gateway:app --reload --host 0.0.0.0 --port 3000
```