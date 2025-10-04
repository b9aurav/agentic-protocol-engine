import { SetupAnswers } from '../commands/setup';

export interface MCPGatewayConfig {
  gateway: {
    name: string;
    version: string;
    port: number;
    cors: {
      enabled: boolean;
      origins: string[];
    };
    rateLimit: {
      enabled: boolean;
      windowMs: number;
      max: number;
    };
  };
  routes: Record<string, RouteConfig>;
  logging: {
    level: string;
    format: string;
    tracing: {
      enabled: boolean;
      headerName: string;
    };
  };
  metrics: {
    enabled: boolean;
    endpoint: string;
  };
}

export interface RouteConfig {
  name: string;
  description: string;
  base_url: string;
  timeout: number;
  retry_policy: {
    max_retries: number;
    backoff_factor: number;
    retry_on: number[];
  };
  auth?: {
    type: string;
    headers?: Record<string, string>;
    credentials?: {
      username?: string;
      password?: string;
      token?: string;
    };
  };
  endpoints: EndpointConfig[];
  health_check?: {
    enabled: boolean;
    path: string;
    interval: number;
  };
  // Enhanced configuration for parsed API specifications
  sessionHandling?: {
    enabled: boolean;
    cookieSupport: boolean;
    headerSupport: boolean;
    tokenRefresh: boolean;
  };
  paginationHandling?: {
    enabled: boolean;
    defaultPageSize: number;
    maxPageSize: number;
    pageParam: string;
    sizeParam: string;
  };
  dataModels?: Record<string, any>;
  errorHandling?: {
    patterns: string[];
    retryableErrors: number[];
    nonRetryableErrors: number[];
  };
}

export interface EndpointConfig {
  path: string;
  methods: string[];
  description: string;
  rateLimit?: {
    windowMs: number;
    max: number;
  };
  // Enhanced metadata for parsed API specifications
  metadata?: {
    parameters?: any;
    responses?: any;
    sessionRequired?: boolean;
    sampleData?: Record<string, any>;
    requiredFields?: string[];
    optionalFields?: string[];
    validation?: Record<string, any>;
    responseHandling?: Record<string, any>;
  };
}

export function generateMCPGatewayConfig(config: SetupAnswers): MCPGatewayConfig {
  // Generate endpoint configurations from user input
  const endpoints: EndpointConfig[] = config.endpoints.map(endpoint => ({
    path: endpoint,
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
    description: `API endpoint: ${endpoint}`,
    rateLimit: {
      windowMs: 60000, // 1 minute
      max: 100 // requests per window
    }
  }));

  // Add common endpoints if not already specified
  const commonEndpoints = ['/health', '/status', '/metrics'];
  for (const commonEndpoint of commonEndpoints) {
    if (!config.endpoints.includes(commonEndpoint)) {
      endpoints.push({
        path: commonEndpoint,
        methods: ['GET'],
        description: `System endpoint: ${commonEndpoint}`,
        rateLimit: {
          windowMs: 60000,
          max: 200
        }
      });
    }
  }



  // Build the complete MCP Gateway configuration
  const mcpConfig: MCPGatewayConfig = {
    gateway: {
      name: `${config.projectName}-mcp-gateway`,
      version: '1.0.0',
      port: 3000,
      cors: {
        enabled: true,
        origins: ['*'] // Allow all origins for testing
      },
      rateLimit: {
        enabled: true,
        windowMs: 60000, // 1 minute
        max: 1000 // requests per window per IP
      }
    },
    routes: {
      // System Under Test (SUT) API route - Requirements 3.3, 3.4
      sut_api: {
        name: 'System Under Test API',
        description: `Target application API at ${config.targetUrl}`,
        base_url: config.targetUrl,
        timeout: 30, // 30 seconds
        retry_policy: {
          max_retries: 3,
          backoff_factor: 1.5,
          retry_on: [502, 503, 504, 408, 429] // Retry on server errors and timeouts
        },

        endpoints: endpoints,
        health_check: {
          enabled: true,
          path: '/health',
          interval: 30 // 30 seconds
        }
      },
      // Cerebras Proxy route for LLM inference - Requirements 2.1, 2.3
      cerebras_api: {
        name: 'Cerebras Inference API',
        description: 'High-speed LLM inference via Cerebras proxy',
        base_url: 'http://cerebras_proxy:8000',
        timeout: 10, // 10 seconds for fast inference
        retry_policy: {
          max_retries: 2,
          backoff_factor: 1.2,
          retry_on: [502, 503, 504, 408] // Don't retry on rate limits (429)
        },
        endpoints: [
          {
            path: '/v1/chat/completions',
            methods: ['POST'],
            description: 'OpenAI-compatible chat completions endpoint',
            rateLimit: {
              windowMs: 60000,
              max: 1000 // High limit for inference requests
            }
          },
          {
            path: '/health',
            methods: ['GET'],
            description: 'Health check endpoint'
          },
          {
            path: '/metrics',
            methods: ['GET'],
            description: 'Prometheus metrics endpoint'
          }
        ],
        health_check: {
          enabled: true,
          path: '/health',
          interval: 15 // 15 seconds
        }
      }
    },
    logging: {
      level: 'info',
      format: 'json',
      tracing: {
        enabled: true,
        headerName: 'X-Trace-ID'
      }
    },
    metrics: {
      enabled: true,
      endpoint: '/metrics'
    }
  };



  return mcpConfig;
}

export function generateMCPGatewayDockerfile(): string {
  return `# MCP Gateway Dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user
RUN addgroup -g 1001 -S nodejs
RUN adduser -S mcp-gateway -u 1001

# Set ownership
RUN chown -R mcp-gateway:nodejs /app
USER mcp-gateway

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
  CMD curl -f http://localhost:3000/health || exit 1

EXPOSE 3000

CMD ["node", "src/gateway.js"]
`;
}

export function generateMCPGatewayPackageJson(projectName: string): any {
  return {
    name: `${projectName}-mcp-gateway`,
    version: '1.0.0',
    description: 'MCP Gateway for Agentic Protocol Engine',
    main: 'src/gateway.js',
    scripts: {
      start: 'node src/gateway.js',
      dev: 'nodemon src/gateway.js',
      test: 'jest',
      'test:watch': 'jest --watch'
    },
    dependencies: {
      express: '^4.18.2',
      'express-rate-limit': '^6.10.0',
      cors: '^2.8.5',
      'http-proxy-middleware': '^2.0.6',
      axios: '^1.5.0',
      winston: '^3.10.0',
      'prom-client': '^14.2.0',
      uuid: '^9.0.0',
      helmet: '^7.0.0'
    },
    devDependencies: {
      nodemon: '^3.0.1',
      jest: '^29.7.0',
      supertest: '^6.3.3'
    },
    engines: {
      node: '>=18.0.0'
    }
  };
}