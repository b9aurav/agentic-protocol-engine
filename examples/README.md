# APE Configuration Templates

This directory contains production-ready configuration templates for different application types. These templates provide optimized settings, validation rules, and best practices for load testing various architectures.

## Available Templates

### 1. REST API Template (`rest-api-example.json`)

**Best for:** Traditional RESTful APIs with CRUD operations

**Features:**
- Standard HTTP methods (GET, POST, PUT, DELETE)
- Bearer token or basic authentication
- Comprehensive endpoint coverage
- Optimized for stateless operations

**Use Cases:**
- E-commerce APIs
- User management systems
- Content management APIs
- Microservice endpoints

**Performance Targets:**
- Average response time: < 200ms
- P95 response time: < 500ms
- Error rate: < 1%
- Throughput: 1000+ requests/minute



## Quick Start

### 1. Choose Your Template

```bash
# Copy a template to get started
cp examples/rest-api-example.json my-config.json

# Or use the setup wizard with a specific template
npx create-ape-load --template rest-api
```

### 2. Customize Configuration

Edit the configuration file to match your application:

```json
{
  "config": {
    "projectName": "my-api-test",
    "targetUrl": "https://api.myapp.com",
    "agentCount": 25,
    "testDuration": 15,
    "endpoints": ["/api/users", "/api/products"]
  }
}
```

### 3. Validate Configuration

```bash
# Validate your configuration
ape-load validate --config my-config.json

# Validate entire project
ape-load validate --project ./my-ape-load
```

### 4. Run Load Test

```bash
# Generate APE project from config
ape-load setup --config my-config.json

# Start load test
cd my-api-test
ape-load start --agents 25
```

## Configuration Fields

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `projectName` | Unique project identifier | `"ecommerce-api-test"` |
| `targetUrl` | Application URL to test | `"https://api.example.com"` |
| `agentCount` | Number of concurrent agents | `50` |
| `testDuration` | Test duration in minutes | `15` |
| `testGoal` | Agent behavior description | `"Simulate user purchases"` |



### Optional Fields

| Field | Description | Default |
|-------|-------------|---------|
| `targetPort` | Target application port | Extracted from URL |
| `endpoints` | API endpoints to test | Template defaults |

## Best Practices

### 1. Start Small, Scale Up

```bash
# Begin with fewer agents
ape-load start --agents 10

# Monitor performance and scale gradually
ape-load scale --agents 50
```

### 2. Use Appropriate Templates

- **REST API:** Standard web APIs, CRUD operations

### 3. Monitor Key Metrics

- **Response Times:** Average, P95, P99 latencies
- **Error Rates:** 4xx client errors, 5xx server errors
- **Throughput:** Requests per second/minute
- **Resource Usage:** CPU, memory, network utilization

### 4. Validate Before Production

```bash
# Always validate configuration
ape-load validate --project ./my-test

# Check for warnings and suggestions
ape-load validate --verbose
```