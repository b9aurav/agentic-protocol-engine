# APE Container Resource Optimization Guide

This document describes the container resource optimization features implemented for Requirements 6.1 and 6.4, enabling APE to scale to 1000+ concurrent agents with optimal resource utilization.

## Overview

APE implements a comprehensive resource optimization strategy that includes:

- **Multi-stage Docker builds** for minimal container size
- **Dynamic resource allocation** based on agent count
- **Graceful scaling procedures** with zero-downtime updates
- **Production-optimized configurations** for high-scale deployments
- **Real-time resource monitoring** and alerting

## Resource Optimization Features

### 1. Optimized Docker Images

#### Multi-Stage Builds
All service containers use multi-stage builds to minimize image size and startup time:

```dockerfile
# Builder stage - includes build dependencies
FROM python:3.11-slim as builder
RUN apt-get update && apt-get install -y gcc g++
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage - minimal runtime image
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
# ... rest of production configuration
```

#### Security and Performance Optimizations
- Non-root user execution for security
- Read-only containers with tmpfs for temporary files
- Optimized Python settings (`PYTHONOPTIMIZE=2`, `MALLOC_ARENA_MAX=2`)
- Health checks optimized for faster startup detection

### 2. Dynamic Resource Allocation

APE automatically adjusts resource limits based on the number of agents:

| Agent Count | Memory per Agent | CPU per Agent | Use Case |
|-------------|------------------|---------------|----------|
| 1-50        | 512MB           | 0.5 cores     | Development/Small tests |
| 51-100      | 384MB           | 0.35 cores    | Medium-scale testing |
| 101-200     | 256MB           | 0.25 cores    | Large-scale testing |
| 201-500     | 192MB           | 0.15 cores    | High-scale testing |
| 501-1000+   | 128MB           | 0.1 cores     | Ultra-high-scale testing |

### 3. Graceful Scaling Operations

#### Scaling Up
```bash
# Scale to 500 agents gradually
ape-load scale --agents 500 --strategy gradual

# Scale immediately for urgent testing
ape-load scale --agents 100 --strategy immediate --force
```

#### Scaling Down
```bash
# Scale down with graceful shutdown
ape-load scale --agents 50 --strategy gradual

# Check scaling plan without executing
ape-load scale --agents 200 --dry-run
```

#### Rolling Updates
- **Parallelism**: Updates maximum 10 agents simultaneously
- **Delay**: 3-second delay between batches
- **Health Checks**: 15-second monitoring window
- **Rollback**: Automatic rollback on failure

### 4. Production Optimizations

#### Environment Configuration
APE generates production-specific configurations:

```bash
# Use production configuration
COMPOSE_FILE=ape.docker-compose.yml:ape.docker-compose.production.yml
docker-compose up -d
```

#### Production Features
- **Resource Limits**: Strict memory and CPU limits
- **Security**: Read-only containers, no new privileges
- **Monitoring**: Enhanced metrics collection
- **Logging**: Compressed logs with rotation
- **Networking**: Optimized bridge configuration

### 5. Resource Monitoring

#### Real-Time Monitoring
```bash
# Start resource monitoring
python scripts/resource-monitor.py --project my-ape-load --interval 10

# Monitor with JSON output
python scripts/resource-monitor.py --output /tmp/ape-metrics.json --no-console
```

#### Monitoring Features
- **Container Metrics**: CPU, memory, network, disk I/O per container
- **System Metrics**: Overall system resource utilization
- **Service Breakdown**: Resource usage by service type
- **Alerting**: Automatic alerts for threshold violations
- **Health Status**: Overall system health assessment

#### Alert Thresholds
- **System Memory**: Alert at 85% usage
- **System CPU**: Alert at 80% usage
- **Disk Usage**: Alert at 90% usage
- **Container Memory**: Alert at 90% per container
- **Container Restarts**: Alert after 3+ restarts

## Performance Optimization Strategies

### 1. Startup Optimization

#### Staggered Deployment
```python
# Agents start with random delays to prevent thundering herd
AGENT_STARTUP_DELAY = random(0, 10)  # 0-10 second delay
```

#### Dependency Waiting
- Health check polling for MCP Gateway availability
- Exponential backoff for service dependencies
- Timeout handling with graceful degradation

### 2. Memory Optimization

#### Python Optimizations
```bash
PYTHONOPTIMIZE=2          # Enable optimizations
PYTHONDONTWRITEBYTECODE=1 # Skip .pyc files
MALLOC_ARENA_MAX=2        # Limit memory arenas
```

#### Container Optimizations
- Minimal base images (python:3.11-slim)
- Multi-stage builds to exclude build dependencies
- Tmpfs for temporary files to reduce disk I/O

### 3. Network Optimization

#### Connection Pooling
```python
# Optimized connection pools based on scale
HTTP_POOL_CONNECTIONS = min(10, agent_count / 10)
HTTP_POOL_MAXSIZE = min(20, agent_count / 5)
KEEP_ALIVE_CONNECTIONS = min(50, agent_count / 10)
```

#### Request Optimization
- HTTP/1.1 keep-alive connections
- Request batching for high-throughput scenarios
- Timeout optimization (30s request, 5s keep-alive)

## Scaling Best Practices

### 1. Pre-Scaling Checklist

Before scaling to high agent counts:

1. **System Resources**: Ensure sufficient CPU, memory, and disk space
2. **Network Capacity**: Verify network bandwidth for target application
3. **Target Application**: Confirm target can handle expected load
4. **Monitoring**: Enable resource monitoring and alerting
5. **Backup Plan**: Have rollback strategy ready

### 2. Scaling Strategies

#### Gradual Scaling (Recommended)
- Start with small agent count (10-50)
- Monitor resource usage and performance
- Gradually increase in 50-100 agent increments
- Validate system stability at each level

#### Immediate Scaling
- Use for time-sensitive testing
- Ensure adequate system resources
- Monitor closely for resource exhaustion
- Have immediate rollback capability

### 3. Resource Planning

#### Memory Requirements
```bash
# Calculate total memory needed
agents = 500
memory_per_agent = 128  # MB for high-scale
total_agent_memory = agents * memory_per_agent  # 64GB

# Add overhead for services
mcp_gateway_memory = 1024  # MB
cerebras_proxy_memory = 1024  # MB
observability_memory = 4096  # MB (Prometheus, Grafana, Loki)

total_memory_needed = total_agent_memory + mcp_gateway_memory + cerebras_proxy_memory + observability_memory
# Total: ~70GB for 500 agents
```

#### CPU Requirements
```bash
# Calculate total CPU needed
cpu_per_agent = 0.1  # cores for high-scale
total_agent_cpu = agents * cpu_per_agent  # 50 cores

# Add overhead for services
service_cpu_overhead = 6  # cores

total_cpu_needed = total_agent_cpu + service_cpu_overhead
# Total: ~56 cores for 500 agents
```

## Troubleshooting

### Common Issues

#### 1. Out of Memory Errors
```bash
# Check memory usage
docker stats

# Scale down agents
ape-load scale --agents 100

# Check system memory
free -h
```

#### 2. Slow Startup Times
```bash
# Check container logs
ape-load logs --service llama_agent --tail 50

# Monitor resource usage during startup
python scripts/resource-monitor.py --interval 5
```

#### 3. High CPU Usage
```bash
# Check CPU usage by service
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Reduce agent count if needed
ape-load scale --agents 200
```

### Performance Tuning

#### 1. Memory Optimization
- Reduce agent memory limits for high-scale deployments
- Enable log compression for large deployments
- Use tmpfs for temporary files

#### 2. CPU Optimization
- Adjust CPU limits based on actual usage
- Use CPU affinity for better core utilization
- Monitor CPU wait times

#### 3. Network Optimization
- Increase connection pool sizes for high throughput
- Optimize keep-alive timeouts
- Monitor network bandwidth usage

## Monitoring and Alerting

### Grafana Dashboards

APE includes pre-configured Grafana dashboards for:

1. **System Overview**: Overall resource utilization
2. **Agent Performance**: Per-agent metrics and health
3. **Service Health**: MCP Gateway and Cerebras Proxy metrics
4. **Infrastructure**: Container and host system metrics

### Prometheus Metrics

Key metrics collected:

- `ape_agent_memory_usage_bytes`: Memory usage per agent
- `ape_agent_cpu_usage_percent`: CPU usage per agent
- `ape_concurrent_agents_total`: Number of running agents
- `ape_system_memory_percent`: System memory utilization
- `ape_system_cpu_percent`: System CPU utilization

### Alert Rules

Pre-configured alerts:

- **High Memory Usage**: System memory > 85%
- **High CPU Usage**: System CPU > 80%
- **Agent Failures**: Agent restart count > 3
- **Service Unavailable**: Health check failures
- **Resource Exhaustion**: Container resource limits exceeded

## Production Deployment

### Environment Setup

1. **Generate Production Configuration**:
   ```bash
   npx create-ape-load my-production-test
   # Configuration includes production optimizations automatically
   ```

2. **Set Environment Variables**:
   ```bash
   export COMPOSE_FILE=ape.docker-compose.yml:ape.docker-compose.production.yml
   export GRAFANA_ADMIN_PASSWORD=secure-password
   export CEREBRAS_API_KEY=your-api-key
   ```

3. **Deploy with Production Settings**:
   ```bash
   docker-compose --env-file .env.production up -d
   ```

### Security Considerations

- **Non-root Containers**: All containers run as non-root users
- **Read-only Filesystems**: Containers use read-only root filesystems
- **Network Isolation**: Services communicate through dedicated networks
- **Resource Limits**: Strict resource limits prevent resource exhaustion
- **Security Options**: `no-new-privileges` and other security hardening

### Maintenance

#### Regular Tasks
- Monitor resource usage trends
- Review and adjust resource limits
- Update container images for security patches
- Backup configuration and metrics data
- Test scaling procedures regularly

#### Capacity Planning
- Monitor growth in resource requirements
- Plan for peak load scenarios
- Evaluate infrastructure scaling needs
- Review cost optimization opportunities

## Conclusion

APE's resource optimization features enable efficient scaling to 1000+ concurrent agents while maintaining system stability and performance. The combination of optimized containers, dynamic resource allocation, graceful scaling, and comprehensive monitoring provides a robust foundation for large-scale AI-driven load testing.

For additional support or questions about optimization features, refer to the main APE documentation or open an issue in the project repository.