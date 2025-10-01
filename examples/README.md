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

### 2. GraphQL Template (`graphql-example.json`)

**Best for:** GraphQL APIs with complex queries and mutations

**Features:**
- Query complexity management
- Introspection support
- Batch operation handling
- Performance optimization for complex queries

**Use Cases:**
- Social media platforms
- Content aggregation services
- Real-time applications
- Mobile app backends

**Performance Targets:**
- Simple queries: < 300ms average, < 800ms P95
- Complex queries: < 1s average, < 2s P95
- Error rate: < 0.5%
- Throughput: 500+ operations/minute

### 3. Microservices Template (`microservices-example.json`)

**Best for:** Distributed microservices architectures

**Features:**
- Service discovery integration
- Circuit breaker patterns
- Distributed tracing
- Cross-service dependency testing

**Use Cases:**
- Banking and financial systems
- Enterprise applications
- Cloud-native architectures
- Service mesh deployments

**Performance Targets:**
- Critical path: < 300ms average, < 800ms P95
- Non-critical: < 1s average, < 2s P95
- Error rate: < 0.1% critical, < 1% non-critical
- Throughput: 2000+ requests/minute

## Quick Start

### 1. Choose Your Template

```bash
# Copy a template to get started
cp examples/rest-api-example.json my-config.json

# Or use the setup wizard with a specific template
npx create-ape-test --template rest-api
```

### 2. Customize Configuration

Edit the configuration file to match your application:

```json
{
  "config": {
    "projectName": "my-api-test",
    "targetUrl": "https://api.myapp.com",
    "authType": "bearer",
    "authToken": "your_token_here",
    "agentCount": 25,
    "testDuration": 15,
    "endpoints": ["/api/users", "/api/products"]
  }
}
```

### 3. Validate Configuration

```bash
# Validate your configuration
ape-test validate --config my-config.json

# Validate entire project
ape-test validate --project ./my-ape-test
```

### 4. Run Load Test

```bash
# Generate APE project from config
ape-test setup --config my-config.json

# Start load test
cd my-api-test
ape-test start --agents 25
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

### Authentication Fields

| Field | Type | Description |
|-------|------|-------------|
| `authType` | `none\|bearer\|basic\|session\|api-key` | Authentication method |
| `authToken` | `string` | Bearer token or API key |
| `authUsername` | `string` | Username for basic auth |
| `authPassword` | `string` | Password for basic auth |

### Optional Fields

| Field | Description | Default |
|-------|-------------|---------|
| `targetPort` | Target application port | Extracted from URL |
| `endpoints` | API endpoints to test | Template defaults |
| `customHeaders` | Additional HTTP headers | `{}` |

## Validation Rules

APE validates configurations against production best practices:

### Security Validation
- ✅ HTTPS for production URLs
- ✅ Secure authentication methods
- ✅ No hardcoded credentials in descriptions
- ⚠️ HTTP usage warnings for non-localhost

### Performance Validation
- ✅ Reasonable agent counts (1-1000)
- ✅ Appropriate test durations (1-1440 minutes)
- ✅ Endpoint format validation
- ⚠️ High-scale deployment warnings

### Application-Specific Validation
- ✅ Auth type compatibility with application type
- ✅ Required endpoints for application type
- ✅ Performance target alignment
- ⚠️ Scaling recommendations per application type

## Best Practices

### 1. Start Small, Scale Up

```bash
# Begin with fewer agents
ape-test start --agents 10

# Monitor performance and scale gradually
ape-test scale --agents 50
```

### 2. Use Appropriate Templates

- **REST API:** Standard web APIs, CRUD operations
- **GraphQL:** Complex data fetching, real-time apps
- **Microservices:** Distributed systems, service mesh
- **Custom:** Unique architectures requiring custom configuration

### 3. Monitor Key Metrics

- **Response Times:** Average, P95, P99 latencies
- **Error Rates:** 4xx client errors, 5xx server errors
- **Throughput:** Requests per second/minute
- **Resource Usage:** CPU, memory, network utilization

### 4. Validate Before Production

```bash
# Always validate configuration
ape-test validate --project ./my-test

# Check for warnings and suggestions
ape-test validate --verbose
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify token validity and format
   - Check auth type compatibility
   - Ensure proper header configuration

2. **Network Connectivity**
   - Use `host.docker.internal` instead of `localhost`
   - Verify firewall and security group settings
   - Check DNS resolution in containers

3. **Performance Issues**
   - Start with fewer agents and scale up
   - Monitor resource usage on test machine
   - Adjust timeouts for slow endpoints

4. **Configuration Errors**
   - Run `ape-test validate` for detailed error messages
   - Check endpoint format (must start with `/`)
   - Verify JSON syntax and required fields

### Getting Help

- **Validation:** `ape-test validate --verbose`
- **Documentation:** Check README.md in generated projects
- **Examples:** Review template files in this directory
- **Logs:** Use `ape-test logs --follow` for real-time debugging

## Advanced Configuration

### Custom Headers

```json
{
  "customHeaders": {
    "Content-Type": "application/json",
    "X-API-Version": "v1",
    "X-Client-ID": "load-test"
  }
}
```

### Environment-Specific Overrides

```bash
# Development environment
ape-test setup --template rest-api --env development

# Production environment with optimizations
ape-test setup --template rest-api --env production
```

### Application-Specific Docker Overrides

Generated projects include application-specific Docker Compose overrides:

- `ape.docker-compose.rest-api.yml`
- `ape.docker-compose.graphql.yml`
- `ape.docker-compose.microservices.yml`

These provide optimized container configurations for each application type.