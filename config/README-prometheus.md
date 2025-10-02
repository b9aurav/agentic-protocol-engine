# Prometheus Configuration for APE

This document describes the Prometheus metrics collection setup for the Agentic Protocol Engine (APE).

## Overview

The APE Prometheus configuration implements comprehensive metrics collection across all system components:

- **cAdvisor**: Container resource metrics (CPU, memory, network, disk)
- **Node Exporter**: Host system metrics (CPU, memory, disk, network)
- **Custom Service Metrics**: Application-specific performance metrics

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   cAdvisor      │    │  Node Exporter   │    │ Service Metrics │
│ (Container      │    │ (Host System     │    │ (Application    │
│  Metrics)       │    │  Metrics)        │    │  Performance)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────────┐
                    │    Prometheus       │
                    │   (Metrics Store)   │
                    └─────────────────────┘
                                 │
                    ┌─────────────────────┐
                    │      Grafana        │
                    │  (Visualization)    │
                    └─────────────────────┘
```

## Metrics Collection Jobs

### 1. Infrastructure Metrics

#### cAdvisor (Container Metrics)
- **Job**: `cadvisor`
- **Target**: `cadvisor:8080`
- **Interval**: 15s
- **Metrics**: Container CPU, memory, network, disk I/O
- **Labels**: 
  - `ape_service`: Docker Compose service name
  - `ape_project`: Project identifier
  - `container_name`: Container name

#### Node Exporter (Host Metrics)
- **Job**: `node-exporter`
- **Target**: `node-exporter:9100`
- **Interval**: 15s
- **Metrics**: Host CPU, memory, disk, network, filesystem

### 2. Application Metrics

#### MCP Gateway
- **Job**: `mcp-gateway`
- **Target**: `mcp_gateway:8001`
- **Interval**: 5s
- **Custom Metrics**:
  - `mcp_gateway_requests_total`: Total requests processed
  - `mcp_gateway_request_duration_seconds`: Request latency histogram
  - `mcp_gateway_active_requests`: Current active requests
  - `mcp_gateway_errors_total`: Error count by type
  - `mcp_gateway_route_health`: Route health status

#### Cerebras Proxy
- **Job**: `cerebras-proxy`
- **Target**: `cerebras_proxy:8002`
- **Interval**: 5s
- **Custom Metrics**:
  - `cerebras_proxy_requests_total`: Total inference requests
  - `cerebras_proxy_ttft_seconds_*`: Time-to-First-Token metrics
  - `cerebras_proxy_tokens_total`: Total tokens processed
  - `cerebras_proxy_tokens_per_second`: Token processing rate
  - `cerebras_proxy_cost_total`: Estimated cost tracking

#### Llama Agents (Dynamic Discovery)
- **Job**: `ape-agents`
- **Discovery**: Docker service discovery
- **Target Pattern**: `llama-agent:8000`
- **Interval**: 5s
- **Custom Metrics**:
  - `ape_agent_sessions_total`: Total sessions started
  - `ape_successful_sessions_total`: Successful stateful sessions
  - `ape_agent_mtba_seconds`: Mean Time Between Actions
  - `ape_agent_requests_total`: HTTP requests by status
  - `ape_inference_ttft_seconds`: Inference latency
  - `ape_concurrent_agents_count`: Active agent count

## Key Performance Indicators (KPIs)

### Primary Success Metrics

1. **Successful Stateful Sessions (%)**
   ```promql
   rate(ape_successful_sessions_total[5m]) / rate(ape_agent_sessions_total[5m]) * 100
   ```

2. **Mean Time Between Actions (MTBA)**
   ```promql
   histogram_quantile(0.95, rate(ape_agent_mtba_seconds_bucket[5m]))
   ```

3. **Time-to-First-Token (TTFT)**
   ```promql
   histogram_quantile(0.95, rate(ape_inference_ttft_seconds_bucket[5m]))
   ```

### System Health Metrics

1. **Agent Error Rate**
   ```promql
   rate(ape_agent_errors_total[5m]) / rate(ape_agent_requests_total[5m])
   ```

2. **Gateway Latency**
   ```promql
   histogram_quantile(0.95, rate(mcp_gateway_request_duration_seconds_bucket[5m]))
   ```

3. **Container Resource Usage**
   ```promql
   rate(container_cpu_usage_seconds_total[5m]) * 100
   ```

## Alerting Rules

### Critical Alerts

- **HighAgentErrorRate**: Agent error rate > 10%
- **LowSuccessfulSessionRate**: Success rate < 70%
- **HighTTFT**: TTFT > 2 seconds
- **HighMTBA**: MTBA > 1 second

### Warning Alerts

- **HighCPUUsage**: CPU > 80%
- **HighMemoryUsage**: Memory > 85%
- **ContainerDown**: Service unavailable
- **HighGatewayLatency**: Gateway latency > 5s

## Configuration Files

### Main Configuration
- `config/prometheus.yml`: Main Prometheus configuration
- `config/prometheus-rules.yml`: Alerting rules
- `config/observability.docker-compose.yml`: Service definitions

### Service Discovery

The configuration uses Docker service discovery for dynamic agent scaling:

```yaml
docker_sd_configs:
  - host: unix:///var/run/docker.sock
    port: 8000
    refresh_interval: 15s
    filters:
      - name: label
        values: ["com.docker.compose.service=llama-agent"]
```

### Relabeling

Automatic label extraction for better metric organization:

```yaml
relabel_configs:
  - source_labels: [__meta_docker_container_name]
    regex: '.*_llama-agent_([0-9]+)'
    target_label: agent_id
    replacement: 'agent-${1}'
```

## Performance Optimization

### Scrape Intervals
- **Infrastructure**: 15s (cAdvisor, Node Exporter)
- **Applications**: 5s (Gateway, Proxy, Agents)
- **Self-monitoring**: 30s (Prometheus)

### Resource Limits
- **Retention**: 7 days (configurable)
- **Storage**: Persistent volumes for data durability
- **Memory**: Optimized for high-cardinality metrics

## Troubleshooting

### Common Issues

1. **Missing Agent Metrics**
   - Verify agent containers expose port 8000
   - Check Docker socket permissions
   - Validate service discovery filters

2. **High Cardinality**
   - Monitor label usage
   - Use recording rules for complex queries
   - Implement metric retention policies

3. **Scrape Failures**
   - Check network connectivity
   - Verify service health endpoints
   - Review timeout configurations

### Debugging Commands

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Validate configuration
docker exec ape-prometheus promtool check config /etc/prometheus/prometheus.yml

# Check service discovery
curl http://localhost:9090/api/v1/label/__name__/values
```

## Integration with Grafana

The metrics are automatically available in Grafana through the configured data source:

- **URL**: `http://prometheus:9090`
- **Dashboards**: Auto-provisioned from `config/dashboards/`
- **Alerts**: Integrated with Prometheus alerting

## Security Considerations

- **Network Isolation**: All metrics traffic within Docker network
- **Authentication**: Basic auth for Grafana (admin/ape-admin)
- **Firewall**: Only necessary ports exposed externally
- **Data Retention**: Configurable retention policies

## Scaling Considerations

The configuration supports scaling to 1000+ concurrent agents:

- **Dynamic Discovery**: Automatic agent detection
- **Resource Limits**: Per-container resource constraints
- **Efficient Queries**: Optimized PromQL for high load
- **Storage**: Persistent volumes for data durability