# APE Grafana Dashboards and Alerting

This document describes the comprehensive Grafana dashboards and alerting system implemented for the Agentic Protocol Engine (APE) load testing infrastructure.

## Overview

The APE monitoring system provides real-time visibility into:
- **Concurrent agent performance** and scaling metrics
- **Success rates** and error tracking across all services
- **End-to-end latency** analysis (TTFT, MTBA, Gateway latency)
- **Log correlation** with trace ID filtering
- **Critical threshold alerting** for proactive issue detection

## Dashboard Catalog

### 1. APE Load Testing Overview (`ape-overview`)
**Purpose:** High-level system overview with key performance indicators

**Key Panels:**
- Concurrent Active Agents (real-time count with scaling trends)
- Success Rate gauge with color-coded thresholds
- Overall Error Rate monitoring
- Comprehensive latency analysis (TTFT, MTBA, Gateway)
- Real-time throughput metrics (requests/sec, sessions/sec)
- Multi-service log correlation with trace ID filtering

**Variables:**
- `trace_id`: Text input for trace correlation
- `agent_id`: Multi-select agent filtering
- `service`: Multi-select service filtering

**Refresh Rate:** 5 seconds (live monitoring)

### 2. APE Real-Time Monitoring (`ape-realtime-monitoring`)
**Purpose:** Focused real-time metrics for operational monitoring

**Key Features:**
- **Status Cards:** Critical metrics at-a-glance with color-coded thresholds
- **Agent Scaling Trend:** Visual representation of concurrent agents vs. target limits
- **Success vs Error Rates:** Comparative analysis over time
- **Comprehensive Latency Analysis:** Multi-percentile latency tracking
- **Correlated Logs:** Trace-based log correlation panel

**Thresholds:**
- Concurrent Agents: Green < 500, Yellow < 900, Red ≥ 900
- Success Rate: Red < 70%, Yellow < 85%, Green ≥ 85%
- TTFT Latency: Green < 1s, Yellow < 2s, Red ≥ 2s
- Error Rate: Green < 5%, Yellow < 10%, Red ≥ 10%

### 3. APE Agent Performance (`ape-agent-performance`)
**Purpose:** Detailed agent-level performance analysis

**Enhanced Features:**
- Agent request rate and error tracking by agent ID
- Session duration and step analysis
- **Cross-Service Trace Correlation:** Multi-service log correlation by trace ID
- **Agent Error Logs:** Filtered error/warning logs by agent ID
- Advanced filtering with agent ID and trace ID variables

### 4. APE Infrastructure Monitoring (`ape-infrastructure`)
**Purpose:** System resource monitoring and container health

**Monitoring Areas:**
- Host CPU and memory usage
- Container-level resource consumption
- Network I/O monitoring
- Disk usage tracking

### 5. APE Critical Alerts Dashboard (`ape-alerts-critical`)
**Purpose:** Real-time alert status and threshold monitoring

**Alert Panels:**
- Error Rate (Alert > 10%)
- Success Rate (Alert < 70%)
- TTFT Latency (Alert > 2s)
- MTBA (Alert > 1s)
- CPU Usage (Alert > 80%)
- Memory Usage (Alert > 85%)
- Agent Count (Alert > 1000)
- Disk Usage (Alert > 90%)

**Features:**
- Color-coded status indicators
- Built-in alert conditions
- Real-time threshold monitoring

### 6. APE Trace Correlation Dashboard (`ape-trace-correlation`)
**Purpose:** Advanced log correlation and distributed tracing

**Key Capabilities:**
- **Trace ID Input:** Interactive trace ID filtering
- **Multi-Service Correlation:** Logs from all APE services correlated by trace ID
- **Service-Specific Views:** Dedicated panels for Agent, Gateway, and Cerebras logs
- **Error Correlation:** Trace-specific error and warning aggregation
- **Log Ingestion Health:** Monitoring of log correlation system health

**Usage Instructions:**
1. Enter a trace ID (UUID format) in the variable field
2. Select specific services to filter logs
3. View correlated logs across all APE components
4. Analyze error patterns within a specific trace

## Alerting System

### Alert Rules Configuration

**File:** `config/prometheus-rules.yml`

#### Infrastructure Alerts (`ape_infrastructure_alerts`)
- **HighCPUUsage:** CPU > 80% for 2 minutes
- **HighMemoryUsage:** Memory > 85% for 2 minutes
- **ContainerDown:** APE service container down for 1 minute
- **HighContainerRestartRate:** Container restart rate > 0.1/sec

#### Agent Performance Alerts (`ape_agent_alerts`)
- **HighAgentErrorRate:** Agent error rate > 10% for 2 minutes
- **LowSuccessfulSessionRate:** Success rate < 70% for 3 minutes
- **HighTTFT:** 95th percentile TTFT > 2s for 2 minutes
- **HighMTBA:** 95th percentile MTBA > 1s for 2 minutes
- **HighAgentSessionFailureRate:** Session failure rate > 30% for 3 minutes
- **HighToolCallFailureRate:** Tool call failure rate > 20% for 2 minutes

#### Gateway Alerts (`ape_gateway_alerts`)
- **HighGatewayErrorRate:** MCP Gateway error rate > 5% for 2 minutes
- **HighGatewayLatency:** 95th percentile latency > 5s for 2 minutes

#### System Alerts (`ape_system_alerts`)
- **TooManyConcurrentAgents:** Agent count > 1000 for 1 minute
- **LowDiskSpace:** Disk usage > 90% for 2 minutes

#### Real-Time Performance Alerts (`ape_realtime_alerts`)
- **PerformanceDegradation:** Combined TTFT and MTBA threshold breach
- **AgentScalingIssue:** High agent count with elevated error rates
- **CriticalSessionFailureRate:** Success rate < 50% for 3 minutes
- **ResourceExhaustionPredicted:** Memory exhaustion predicted within 1 hour
- **GatewayLatencySpike:** Gateway latency > 10s for 1 minute
- **CerebrasInferenceFailure:** Cerebras error rate > 20% for 1 minute

### Notification Channels

**File:** `config/grafana-alerting.yml`

#### Webhook Notifications
- **Endpoint:** `http://localhost:3001/webhook/alerts`
- **Frequency:** 10 seconds
- **Format:** Structured JSON with alert details

#### Email Notifications
- **Recipients:** Configurable admin and ops email addresses
- **Frequency:** 5 minutes (to prevent spam)
- **Content:** Detailed alert information with dashboard links

## Log Correlation Features

### Trace ID Correlation
The system supports distributed tracing through trace ID correlation:

1. **Automatic Trace Propagation:** All APE services generate and propagate trace IDs
2. **Cross-Service Correlation:** Logs from different services can be correlated using trace IDs
3. **Interactive Filtering:** Dashboards provide trace ID input fields for real-time filtering
4. **Session Correlation:** Additional session ID correlation for agent-specific analysis

### Log Format Standards
All services use structured JSON logging with required fields:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (DEBUG, INFO, WARN, ERROR, CRITICAL)
- `service_name`: Service identifier
- `trace_id`: Distributed trace identifier
- `session_id`: Agent session identifier (where applicable)
- `agent_id`: Agent identifier (for agent services)
- `message`: Human-readable log message

### Derived Fields Configuration
Loki is configured with derived fields for automatic trace correlation:
- **TraceID Field:** Extracts trace IDs from log messages
- **SessionID Field:** Extracts session IDs for agent correlation
- **Clickable Links:** Trace and session IDs become clickable for navigation

## Usage Guidelines

### Real-Time Monitoring Workflow
1. **Start with Overview Dashboard:** Get system-wide health status
2. **Drill Down to Real-Time Dashboard:** Monitor specific metrics during load tests
3. **Use Agent Performance Dashboard:** Investigate agent-specific issues
4. **Leverage Trace Correlation:** Debug specific request flows

### Alert Response Procedures
1. **Critical Alerts:** Immediate investigation required
   - Session failure rate < 50%
   - Resource exhaustion predicted
   - Gateway latency > 10s

2. **Warning Alerts:** Monitor and prepare for intervention
   - Error rates > 10%
   - Success rates < 70%
   - Resource usage > 80%

3. **Scaling Alerts:** Capacity planning required
   - Agent count approaching 1000
   - Performance degradation under load

### Troubleshooting with Trace Correlation
1. **Identify Problem Trace:** Use error logs to find problematic trace IDs
2. **Open Trace Correlation Dashboard:** Enter trace ID in variable field
3. **Analyze Cross-Service Flow:** Review logs from all services for that trace
4. **Identify Bottlenecks:** Look for latency spikes or errors in specific services
5. **Correlate with Metrics:** Use performance dashboards to confirm patterns

## Configuration Files

### Dashboard Provisioning
- **Location:** `config/dashboards/`
- **Auto-Discovery:** Grafana automatically loads JSON dashboard files
- **Update Interval:** 10 seconds for configuration changes

### Alert Provisioning
- **Prometheus Rules:** `config/prometheus-rules.yml`
- **Grafana Alerting:** `config/grafana-alerting.yml`
- **Auto-Reload:** Configuration changes trigger automatic reload

### Data Source Configuration
- **Prometheus:** `http://prometheus:9090` (metrics)
- **Loki:** `http://loki:3100` (logs)
- **Refresh Intervals:** Optimized for real-time monitoring

## Performance Considerations

### Dashboard Refresh Rates
- **Real-Time Dashboards:** 5-second refresh for operational monitoring
- **Analysis Dashboards:** 15-second refresh for detailed investigation
- **Alert Dashboards:** 10-second refresh for immediate alert visibility

### Query Optimization
- **Time Ranges:** Optimized for 15-minute windows in real-time views
- **Rate Calculations:** 5-minute rate windows for smooth metrics
- **Log Queries:** Limited to 1000 lines to prevent performance issues

### Resource Usage
- **Grafana Memory:** Configured for high-frequency dashboard updates
- **Prometheus Retention:** 7-day retention for detailed analysis
- **Loki Storage:** Optimized for log correlation queries

## Maintenance

### Regular Tasks
1. **Dashboard Updates:** Review and update thresholds based on system performance
2. **Alert Tuning:** Adjust alert thresholds to reduce false positives
3. **Log Retention:** Monitor storage usage and adjust retention policies
4. **Performance Review:** Analyze dashboard query performance and optimize

### Backup and Recovery
- **Dashboard Export:** Regular export of dashboard configurations
- **Alert Rule Backup:** Version control for Prometheus rules
- **Data Source Configuration:** Backup of Grafana provisioning files

This comprehensive monitoring and alerting system provides complete visibility into the APE load testing infrastructure, enabling proactive issue detection and rapid troubleshooting through advanced log correlation capabilities.