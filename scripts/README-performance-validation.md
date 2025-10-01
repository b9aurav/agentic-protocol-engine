# APE Performance Validation Scripts

This directory contains comprehensive performance validation scripts for task 10.2: "Validate performance targets and KPIs".

## Overview

The performance validation suite validates that APE meets its performance targets:

- **MTBA < 1 second** under various load conditions (Requirement 2.2)
- **Successful scaling to 1000+ concurrent agents** (Requirement 6.4)  
- **Successful Stateful Sessions percentage optimization** (Requirement 8.3)

## Scripts

### 1. `performance-validation.py`

Main performance validation script that runs comprehensive tests across different load conditions.

**Usage:**
```bash
python scripts/performance-validation.py --max-agents 1000 --test-duration 30 --output validation-report.json
```

**Key Features:**
- Validates MTBA under normal and high load conditions
- Tests scaling from 10 to 1000+ concurrent agents
- Measures cognitive latency (TTFT) performance
- Validates Successful Stateful Sessions percentage
- Generates comprehensive validation report

### 2. `kpi-optimization.py`

KPI optimization analysis script that provides actionable recommendations for improving performance.

**Usage:**
```bash
python scripts/kpi-optimization.py --analysis-duration 15 --output optimization-report.json
```

**Key Features:**
- Analyzes current KPI performance gaps
- Generates specific optimization recommendations
- Estimates improvement potential
- Provides implementation guidance

### 3. `run-performance-tests.py`

Orchestration script that runs the complete performance validation suite.

**Usage:**
```bash
python scripts/run-performance-tests.py --max-agents 1000 --test-duration 30 --output comprehensive-report.json
```

**Key Features:**
- Runs complete validation and optimization analysis
- Performs pre-test system checks
- Generates executive summary and recommendations
- Provides production readiness assessment

## CLI Integration

The validation is integrated into the APE CLI:

```bash
# Full validation (recommended)
ape-test validate --max-agents 1000 --test-duration 30

# Quick validation for development
ape-test validate --quick

# Validation with custom parameters
ape-test validate --max-agents 500 --test-duration 15 --skip-optimization
```

## Performance Targets

### Primary Targets (Critical)

| Metric | Target | Description |
|--------|--------|-------------|
| MTBA (Normal Load) | < 1.0 seconds | Mean Time Between Actions under normal load |
| MTBA (High Load) | < 1.5 seconds | Mean Time Between Actions with 500+ agents |
| Cognitive Latency (TTFT) | < 2.0 seconds | Time-to-First-Token for inference |
| Successful Stateful Sessions | ≥ 85% | Percentage of successful multi-step sessions |
| Max Concurrent Agents | ≥ 1000 | Maximum supported concurrent agents |

### Secondary Targets (Optimization)

| Metric | Target | Description |
|--------|--------|-------------|
| Agent Startup Time | < 30 seconds | Average time for agent initialization |
| System Memory Efficiency | < 85% | Memory usage under maximum load |
| System CPU Efficiency | < 80% | CPU usage under maximum load |

## Dependencies

### Required Python Packages

```bash
pip install docker httpx psutil prometheus-client structlog
```

### System Requirements

- **Python 3.7+**
- **Docker and Docker Compose**
- **Minimum 8GB RAM** (for high-scale testing)
- **Minimum 4 CPU cores**
- **10GB free disk space**

## Usage Examples

### Basic Validation

```bash
# Run basic validation with default parameters
python scripts/performance-validation.py

# Quick validation for CI/CD
python scripts/performance-validation.py --max-agents 100 --test-duration 10
```

### Comprehensive Testing

```bash
# Full production readiness validation
python scripts/run-performance-tests.py \
  --max-agents 1000 \
  --test-duration 30 \
  --output production-validation-report.json

# Development validation
python scripts/run-performance-tests.py \
  --max-agents 200 \
  --test-duration 15 \
  --skip-optimization
```

### KPI Optimization

```bash
# Analyze current performance and get optimization recommendations
python scripts/kpi-optimization.py \
  --analysis-duration 15 \
  --output kpi-optimization-report.json
```

## Report Structure

### Validation Report

```json
{
  "validation_summary": {
    "overall_success": true,
    "passed_targets": 8,
    "failed_targets": 0,
    "critical_failures": 0
  },
  "performance_targets": {
    "mtba_validation": { "status": "PASS" },
    "cognitive_latency_validation": { "status": "PASS" }
  },
  "scaling_validation": {
    "max_achieved_agents": 1000,
    "status": "PASS"
  },
  "kpi_validation": {
    "successful_stateful_sessions": { "status": "PASS" }
  }
}
```

### Optimization Report

```json
{
  "current_kpis": {
    "successful_stateful_sessions_percentage": {
      "current_value": 75.0,
      "target_value": 85.0,
      "improvement_potential": 13.3
    }
  },
  "optimization_recommendations": [
    {
      "category": "Session Success",
      "priority": "high",
      "description": "Optimize agent decision-making",
      "expected_improvement": "Increase success rate by 13.3%"
    }
  ]
}
```

## Troubleshooting

### Common Issues

1. **Docker not available**
   ```bash
   # Install Docker and Docker Compose
   # Ensure Docker daemon is running
   docker --version
   ```

2. **Insufficient system resources**
   ```bash
   # Check available resources
   python -c "import psutil; print(f'Memory: {psutil.virtual_memory().available/1024**3:.1f}GB, CPU: {psutil.cpu_count()} cores')"
   ```

3. **Python dependencies missing**
   ```bash
   # Install required packages
   pip install -r requirements.txt
   ```

4. **APE services not running**
   ```bash
   # Start APE services first
   ape-test start --agents 10
   ```

### Performance Issues

1. **High MTBA values**
   - Check Cerebras API performance
   - Optimize agent prompt complexity
   - Review inference timeout settings

2. **Low session success rates**
   - Review agent error handling logic
   - Check target application stability
   - Validate session state management

3. **Scaling failures**
   - Increase system resources
   - Optimize container resource limits
   - Check Docker Compose configuration

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Performance Validation
on: [push, pull_request]

jobs:
  validate-performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run quick validation
        run: python scripts/performance-validation.py --max-agents 50 --test-duration 5
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    stages {
        stage('Performance Validation') {
            steps {
                sh 'python scripts/run-performance-tests.py --max-agents 500 --test-duration 20'
                archiveArtifacts artifacts: '*.json', fingerprint: true
            }
        }
    }
}
```

## Contributing

When adding new performance tests or optimizations:

1. **Add new metrics** to the appropriate `PerformanceTarget` definitions
2. **Update validation logic** in the respective scripts
3. **Add test cases** for new functionality
4. **Update documentation** with new targets or procedures
5. **Validate changes** with the full test suite

## Support

For issues with performance validation:

1. Check the troubleshooting section above
2. Review logs in `/tmp/ape-performance-*.log`
3. Run with increased verbosity for debugging
4. Open an issue with validation report attached

## References

- **Requirements 2.2**: High-Speed Inference Integration
- **Requirements 6.4**: Scalable Container Architecture  
- **Requirements 8.3**: Validation and Error Handling
- **Task 10.2**: Validate performance targets and KPIs