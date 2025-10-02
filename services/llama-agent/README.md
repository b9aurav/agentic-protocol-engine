# Llama Agent Service

This service implements the core Llama Agent using LlamaIndex with MCP tool integration and session context management.

## Features

- **CustomSimpleAgentWorker**: LlamaIndex-based agent with stateful behavior
- **Session Management**: Maintains context across multi-step transactions
- **MCP Tool Integration**: Standardized HTTP operations through MCP Gateway
- **Pydantic Validation**: Schema validation for all MCP tool calls
- **Error Handling**: Comprehensive error tracking and recovery
- **Observability**: Structured logging with trace ID correlation

## Architecture

### Core Components

1. **StatefulAgentWorker**: Custom LlamaIndex agent worker with session management
2. **LlamaAgent**: Main agent orchestrator class
3. **MCPToolCall**: Pydantic models for MCP-compliant requests
4. **AgentSessionContext**: Session state management for stateful behavior

### Session Management

Each agent session maintains:
- Unique session and trace IDs
- User journey goal
- Session data (cookies, tokens, transaction IDs)
- Execution history with timing metrics
- Step counting and timeout handling

## Configuration

Environment variables:
- `AGENT_ID`: Unique agent identifier
- `MCP_GATEWAY_URL`: MCP Gateway endpoint (default: http://mcp-gateway:8080)
- `CEREBRAS_PROXY_URL`: Cerebras Proxy endpoint (default: http://cerebras-proxy:8000)
- `CEREBRAS_API_KEY`: API key for Cerebras inference
- `SESSION_TIMEOUT_MINUTES`: Session timeout (default: 30)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `INFERENCE_TIMEOUT`: LLM inference timeout (default: 10.0)
- `LOG_LEVEL`: Logging level (default: INFO)

## Usage

The agent service runs as a containerized service and maintains sessions for stateful user journey simulation.

### Docker Build

```bash
docker build -t llama-agent .
```

### Docker Run

```bash
docker run -e CEREBRAS_API_KEY=your_key llama-agent
```

## Implementation Status

✅ **Task 4.1 Complete**: Base Llama Agent with LlamaIndex and session management
- CustomSimpleAgentWorker implementation
- Pydantic models for MCP tool calls
- Session context management for stateful behavior
- Agent configuration and initialization
- Health checks and error handling

🔄 **Next Tasks**:
- Task 4.2: Implement HTTP operation tools
- Task 4.3: Add execution loop and error handling