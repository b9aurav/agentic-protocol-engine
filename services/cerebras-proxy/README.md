# Cerebras Proxy Service

AI-compatible API proxy for Cerebras llama3.1-8b inference engine. This service provides a standardized interface for AI agents to access high-speed inference while implementing comprehensive performance monitoring and authentication.

## Features

- **AI-Compatible API**: Implements `/v1/chat/completions` endpoint with full AI compatibility
- **High-Speed Inference**: Forwards requests to Cerebras llama3.1-8b for sub-second response times
- **Performance Monitoring**: Tracks Time-to-First-Token (TTFT), token usage, and cost metrics
- **Authentication**: API key-based authentication with configurable security
- **Structured Logging**: JSON-formatted logs with trace ID correlation for observability
- **Prometheus Metrics**: Built-in metrics endpoint for monitoring and alerting

## API Endpoints

### Chat Completions
```
POST /v1/chat/completions
```

AI-compatible chat completions endpoint. Accepts standard AI request format and returns compatible responses.

**Request Example:**
```json
{
  "model": "llama3.1-8b",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**Response Example:**
```json
{
  "id": "chatcmpl-1234567890",
  "object": "chat.completion",
  "created": 1699123456,
  "model": "llama3.1-8b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 15,
    "total_tokens": 27
  }
}
```

### Health Check
```
GET /health
```

Returns service health status.

### Models List
```
GET /v1/models
```

Returns available models (AI-compatible).

### Metrics
```
GET /metrics
```

Returns Prometheus-compatible metrics for monitoring.

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `CEREBRAS_API_KEY` | Cerebras API key for authentication | Yes | - |
| `CEREBRAS_BASE_URL` | Cerebras API base URL | No | `https://api.cerebras.ai` |
| `APE_API_KEY` | API key for client authentication | No | - |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No | `INFO` |
| `HOST` | Server host address | No | `0.0.0.0` |
| `PORT` | Server port | No | `8000` |

### Authentication

The service supports optional API key authentication:

- If `APE_API_KEY` is set, clients must provide `Authorization: Bearer <token>` header
- If `APE_API_KEY` is not set, all requests are allowed (development mode)

## Performance Metrics

The service tracks comprehensive performance metrics:

### Time-to-First-Token (TTFT)
- Measures latency from request to first response token
- Critical for maintaining realistic user interaction timing
- Target: Sub-second response times

### Token Usage Tracking
- Input tokens (prompt)
- Output tokens (completion)
- Total tokens processed
- Tokens per second throughput

### Cost Calculation
- Estimated costs based on token usage
- Configurable pricing models
- Total cost tracking

### Error Monitoring
- Request success/failure rates
- Error categorization and logging
- Performance degradation detection

## Logging

Structured JSON logging with the following fields:

```json
{
  "timestamp": "2024-01-15T10:30:25.123Z",
  "level": "info",
  "message": "Chat completion successful",
  "trace_id": "trace-1699123456789",
  "ttft_seconds": 0.245,
  "total_time_seconds": 0.892,
  "total_tokens": 127,
  "prompt_tokens": 45,
  "completion_tokens": 82,
  "model": "llama3.1-8b"
}
```

## Docker Usage

### Build Image
```bash
docker build -t cerebras-proxy .
```

### Run Container
```bash
docker run -d \
  --name cerebras-proxy \
  -p 8000:8000 \
  -e CEREBRAS_API_KEY=your_api_key \
  -e APE_API_KEY=your_ape_key \
  cerebras-proxy
```

### Docker Compose
```yaml
services:
  cerebras-proxy:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CEREBRAS_API_KEY=${CEREBRAS_API_KEY}
      - APE_API_KEY=${APE_API_KEY}
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Development

### Local Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export CEREBRAS_API_KEY=your_api_key
export APE_API_KEY=your_ape_key

# Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_ape_key" \
  -d '{
    "model": "llama3.1-8b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'

# View metrics
curl http://localhost:8000/metrics
```

## Integration with APE

The Cerebras Proxy integrates with the Agentic Protocol Engine (APE) architecture:

1. **Agent Layer**: Llama Agents make inference requests via MCP Gateway
2. **MCP Gateway**: Routes inference requests to Cerebras Proxy
3. **Cerebras Proxy**: Forwards to Cerebras API with performance tracking
4. **Observability**: Logs and metrics flow to Loki/Prometheus/Grafana stack

## Requirements Compliance

This implementation satisfies the following APE requirements:

- **Requirement 2.1**: Cerebras llama3.1-8b integration with sub-second response times
- **Requirement 2.2**: TTFT measurement for cognitive latency validation
- **Requirement 2.3**: AI-compatible interface for standardized access
- **Requirement 2.4**: Token usage tracking and cost calculation
- **Requirement 4.4**: Performance monitoring and structured logging