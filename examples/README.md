# APE Configuration Examples

This directory contains example configurations for different types of applications and use cases. Each example demonstrates best practices and common patterns for load testing with APE.

## Available Examples

### 1. REST API Example (`rest-api-example.json`)

**Use Case**: E-commerce REST API with authentication and shopping workflows

**Key Features**:
- Bearer token authentication with refresh
- Multi-step user journeys (browse → cart → checkout)
- Validation rules for critical endpoints
- Performance thresholds and success criteria

**Best For**:
- Traditional REST APIs
- E-commerce platforms
- CRUD applications
- APIs with session management

### 2. GraphQL Example (`graphql-example.json`)

**Use Case**: Social media platform with GraphQL API

**Key Features**:
- JWT authentication
- Complex queries and mutations
- Dynamic variable handling
- Schema introspection support

**Best For**:
- GraphQL APIs
- Social platforms
- Content management systems
- Real-time applications

### 3. Microservices Example (`microservices-example.json`)

**Use Case**: Distributed microservices architecture with service mesh

**Key Features**:
- Multiple service endpoints
- Service discovery integration
- Circuit breaker patterns
- Cross-service validation
- Distributed tracing

**Best For**:
- Microservices architectures
- Service mesh deployments
- Complex distributed systems
- API gateways

## Using the Examples

### Quick Start with an Example

```bash
# Copy an example to your project
cp examples/rest-api-example.json my-project/ape.config.json

# Customize the configuration
nano my-project/ape.config.json

# Run the test
cd my-project
ape-test start --config ape.config.json
```

### Customizing Examples

1. **Update target URL**: Change `baseUrl` to your application
2. **Configure authentication**: Update credentials and endpoints
3. **Adjust agent goals**: Modify to match your user journeys
4. **Set performance thresholds**: Define success criteria
5. **Customize monitoring**: Configure alerts and dashboards

## Configuration Patterns

### Authentication Patterns

#### API Key Authentication
```json
{
  "authentication": {
    "type": "apikey",
    "header": "X-API-Key",
    "value": "your-api-key-here"
  }
}
```

#### OAuth2 Flow
```json
{
  "authentication": {
    "type": "oauth2",
    "authUrl": "https://auth.example.com/oauth/authorize",
    "tokenUrl": "https://auth.example.com/oauth/token",
    "clientId": "your-client-id",
    "clientSecret": "your-client-secret",
    "scope": "read write"
  }
}
```

#### Custom Headers
```json
{
  "authentication": {
    "type": "custom",
    "headers": {
      "Authorization": "Custom ${TOKEN}",
      "X-User-ID": "${USER_ID}",
      "X-Session": "${SESSION_ID}"
    }
  }
}
```

### Agent Goal Patterns

#### Sequential Goals (Funnel Testing)
```json
{
  "goals": [
    "Visit homepage and browse featured products",
    "Search for specific product category",
    "View product details and read reviews", 
    "Add product to cart and proceed to checkout",
    "Complete purchase with payment processing"
  ]
}
```

#### Parallel Goals (Load Distribution)
```json
{
  "goals": [
    {
      "name": "Browser Users",
      "weight": 60,
      "actions": ["Browse catalog", "Search products", "View details"]
    },
    {
      "name": "Purchaser Users", 
      "weight": 30,
      "actions": ["Add to cart", "Checkout", "Payment"]
    },
    {
      "name": "Admin Users",
      "weight": 10, 
      "actions": ["Manage inventory", "View analytics", "Process orders"]
    }
  ]
}
```

### Validation Patterns

#### Response Time Validation
```json
{
  "validation": {
    "endpoints": [
      {
        "path": "/api/products",
        "maxResponseTime": 500,
        "percentile": 95
      },
      {
        "path": "/api/checkout",
        "maxResponseTime": 2000,
        "percentile": 99
      }
    ]
  }
}
```

#### Business Logic Validation
```json
{
  "validation": {
    "businessRules": [
      {
        "name": "Cart Total Accuracy",
        "description": "Verify cart totals match item prices",
        "validation": "cart.total === cart.items.reduce((sum, item) => sum + item.price * item.quantity, 0)"
      },
      {
        "name": "Inventory Consistency", 
        "description": "Check inventory decreases after purchase",
        "validation": "post_purchase_inventory < pre_purchase_inventory"
      }
    ]
  }
}
```

## Environment-Specific Configurations

### Development Environment
```json
{
  "target": {
    "baseUrl": "http://localhost:3000"
  },
  "agents": {
    "count": 5,
    "duration": "2m"
  },
  "validation": {
    "successCriteria": {
      "successfulSessions": 70
    }
  }
}
```

### Staging Environment
```json
{
  "target": {
    "baseUrl": "https://staging.example.com"
  },
  "agents": {
    "count": 25,
    "duration": "10m"
  },
  "validation": {
    "successCriteria": {
      "successfulSessions": 85
    }
  }
}
```

### Production Environment
```json
{
  "target": {
    "baseUrl": "https://api.example.com"
  },
  "agents": {
    "count": 100,
    "duration": "30m"
  },
  "validation": {
    "successCriteria": {
      "successfulSessions": 95
    }
  }
}
```

## Advanced Patterns

### Multi-Region Testing
```json
{
  "regions": [
    {
      "name": "us-east-1",
      "baseUrl": "https://us-east.api.example.com",
      "agents": 50
    },
    {
      "name": "eu-west-1", 
      "baseUrl": "https://eu-west.api.example.com",
      "agents": 30
    },
    {
      "name": "ap-southeast-1",
      "baseUrl": "https://ap-southeast.api.example.com", 
      "agents": 20
    }
  ]
}
```

### Load Testing with Data Dependencies
```json
{
  "dataSetup": {
    "preTest": [
      "Create test user accounts",
      "Populate product catalog",
      "Set up payment methods"
    ],
    "postTest": [
      "Clean up test data",
      "Reset counters",
      "Archive test results"
    ]
  }
}
```

### Chaos Engineering Integration
```json
{
  "chaosEngineering": {
    "enabled": true,
    "scenarios": [
      {
        "name": "Service Failure",
        "probability": 0.1,
        "action": "simulate_service_down",
        "duration": "30s"
      },
      {
        "name": "Network Latency",
        "probability": 0.2, 
        "action": "add_latency",
        "latency": "500ms"
      }
    ]
  }
}
```

## Best Practices

### Configuration Management
1. **Use environment variables** for sensitive data
2. **Version control configurations** alongside code
3. **Validate configurations** before running tests
4. **Document custom settings** and their purposes

### Performance Optimization
1. **Start with small agent counts** and scale gradually
2. **Monitor resource usage** during tests
3. **Use realistic think times** between actions
4. **Set appropriate timeouts** for your application

### Monitoring and Alerting
1. **Define clear success criteria** upfront
2. **Set up alerts** for critical thresholds
3. **Monitor both APE and target** application metrics
4. **Correlate logs** using trace IDs

### Security Considerations
1. **Use test credentials** only
2. **Avoid production data** in load tests
3. **Secure API keys** and tokens
4. **Limit test scope** to prevent data corruption

## Contributing Examples

We welcome contributions of new examples! To add an example:

1. **Create a new JSON file** following the naming pattern
2. **Include comprehensive comments** explaining the configuration
3. **Add documentation** to this README
4. **Test the configuration** thoroughly
5. **Submit a pull request** with your example

### Example Template
```json
{
  "name": "Your Example Name",
  "description": "Brief description of the use case",
  "target": {
    "name": "example-app",
    "baseUrl": "https://example.com"
  },
  "agents": {
    "count": 10,
    "goals": ["Example goal"]
  },
  "validation": {
    "successCriteria": {
      "successfulSessions": 80
    }
  }
}
```