# APE Observability Stack

This directory contains the configuration files for the APE (Agentic Protocol Engine) observability stack, providing comprehensive monitoring, logging, and alerting capabilities for load testing operations.

## Components

### Log Collection & Storage
- **Promtail**: Collects logs from Docker containers with structured parsing
- **Loki**: Stores and indexes logs with trace ID correlation
- **Configuration**: `promtail.yml`, `loki-config.yml`

### Metrics Collection & Storage
- **Prometheus**: Scrapes metrics from services and infrastructure
- **cAdvisor**: Provides container resource metrics
- **Node Exporter**: Provides host system metrics
- **Configuration**: `prometheus.yml`, `prometheus-rules.yml`

### Visualization & Alerting
- **Grafana**: Provides dashboards and alerting interface
- **Dashboards**: Pre-configured dashboards for APE monitoring
- **Configuration**: `grafana-datasources.yml`, `grafana-dashboards.yml`

## Quick Start

1. **Start the observability stack**:
   ```bash
   docker-compose -f config/observability.docker-compose.yml up -d
   ```

2. **Access the interfaces**:
   - Grafana: http://localhost:3000 (admin/ape-admin)
   - Prometheus: http://localhost:9090
   - Loki: http://localhost:3100

3. **View dashboards**:
   - APE Load Testing Overview
   - APE Agent Performance
   - APE Infrastructure Monitoring

## Dashboard Overview

### APE Load Testing Overview
- **Purpose**: High-level view of load testing performance
- **Key Metrics**:
  - Concurrent active agents
  - Successful stateful sessions percentage
  - Time to First Token (TTFT) latency
  - Mean Time Between Actions (MTBA)
  - Recent errors and warnings

### APE Agent Performance
- **Purpose**: Detailed agent behavior and performance analysis
- **Key Metrics**:
  - Agent request rates and error rates
  - Session duration and step counts
  - Trace ID correlation for debugging
- **Features**: Filter by agent ID and trace ID

### APE Infrastructure Monitoring
- **Purpose**: System resource monitoring and capacity planning
- **Key Metrics**:
  - Host CPU, memory, and disk usage
  - Container resource consumption
  - Network I/O patterns
  - Container health status

## Log Structure

### Agent Logs
```json
{
  "timestamp": "2024-01-15T10:30:25.123Z",
  "level": "INFO",
  "message": "Agent completed tool execution",
  "trace_id": "abc123-def456-ghi789",
  "session_id": "session-001",
  "agent_id": "agent-001",
  "tool_name": "tool_http_post",
  "goal": "complete purchase flow",
  "step": 3,
  "success": true,
  "ttft": 0.45,
  "tokens": 150
}
```

### MCP Gateway Logs
```json
{
  "timestamp": "2024-01-15T10:30:25.123Z",
  "level": "INFO",
  "message": "Request processed successfully",
  "trace_id": "abc123-def456-ghi789",
  "request_id": "req-001",
  "method": "POST",
  "path": "/api/login",
  "status_code": 200,
  "execution_time": 0.125,
  "target_service": "sut_api"
}
```

### Cerebras Proxy Logs
```json
{
  "timestamp": "2024-01-15T10:30:25.123Z",
  "level": "INFO",
  "message": "Inference completed",
  "trace_id": "abc123-def456-ghi789",
  "request_id": "req-001",
  "ttft": 0.45,
  "total_tokens": 150,
  "input_tokens": 100,
  "output_tokens": 50,
  "cost_estimate": 0.0015,
  "model": "llama-4-scout",
  "status_code": 200
}
```

## Alerting Rules

### Critical Alerts
- **ContainerDown**: APE service container unavailable
- **LowDiskSpace**: Disk space below 10%

### Warning Alerts
- **HighCPUUsage**: CPU usage above 80% for 2+ minutes
- **HighMemoryUsage**: Memory usage above 85% for 2+ minutes
- **HighAgentErrorRate**: Agent error rate above 10%
- **LowSuccessfulSessionRate**: Success rate below 70%
- **HighTTFT**: Time to First Token above 2 seconds
- **HighMTBA**: Mean Time Between Actions above 1 second
- **HighGatewayErrorRate**: MCP Gateway error rate above 5%
- **HighGatewayLatency**: Gateway response time above 5 seconds

## Trace Correlation

The observability stack supports end-to-end trace correlation using trace IDs:

1. **Trace ID Generation**: Each agent session generates a unique trace ID
2. **Propagation**: Trace IDs are passed through all service calls
3. **Log Correlation**: Use Grafana's derived fields to jump between related logs
4. **Debugging**: Filter logs by trace ID to follow a complete user journey

## Performance Targets

### Key Performance Indicators (KPIs)
- **MTBA (Mean Time Between Actions)**: < 1 second (95th percentile)
- **TTFT (Time to First Token)**: < 2 seconds (95th percentile)
- **Successful Stateful Sessions**: > 85%
- **Agent Error Rate**: < 5%
- **Gateway Error Rate**: < 2%

### Scaling Targets
- **Concurrent Agents**: Support up to 1000+ agents
- **Request Rate**: Handle 10,000+ requests per minute
- **Resource Usage**: CPU < 80%, Memory < 85%

## Troubleshooting

### Common Issues

1. **Missing Logs**:
   - Verify Docker logging driver configuration
   - Check Promtail container has access to Docker socket
   - Ensure containers have `logging=promtail` label

2. **Missing Metrics**:
   - Verify service metrics endpoints are exposed
   - Check Prometheus service discovery configuration
   - Ensure cAdvisor has proper permissions

3. **Dashboard Issues**:
   - Verify Grafana datasource configuration
   - Check dashboard JSON syntax
   - Ensure proper dashboard provisioning

### Log Queries

**Find errors by trace ID**:
```logql
{job=~"ape-.*"} | json | trace_id="abc123-def456-ghi789" | level="ERROR"
```

**Agent session analysis**:
```logql
{job="ape-agent"} | json | session_id="session-001" | line_format "{{.timestamp}} [{{.level}}] {{.message}}"
```

**Gateway performance issues**:
```logql
{job="mcp-gateway"} | json | status_code >= 400 | line_format "{{.method}} {{.path}} -> {{.status_code}} ({{.execution_time}}s)"
```

## Configuration Customization

### Adding Custom Metrics
1. Expose metrics endpoint in your service (port 8000-8002)
2. Add scrape configuration to `prometheus.yml`
3. Create custom dashboard panels in Grafana

### Custom Log Parsing
1. Update pipeline stages in `promtail.yml`
2. Add new JSON fields to extraction rules
3. Create corresponding labels for filtering

### Alert Customization
1. Modify thresholds in `prometheus-rules.yml`
2. Add new alert rules following existing patterns
3. Configure notification channels in Grafana

## Security Considerations

- **Default Credentials**: Change Grafana admin password in production
- **Network Access**: Restrict dashboard access to authorized users
- **Data Retention**: Configure appropriate log and metric retention policies
- **Resource Limits**: Set container resource limits to prevent resource exhaustion