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
  baseUrl: string;
  timeout: number;
  retryPolicy: {
    maxRetries: number;
    backoffFactor: number;
    retryOn: number[];
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
  healthCheck?: {
    enabled: boolean;
    path: string;
    interval: number;
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
}

export function generateMCPGatewayConfig(config: SetupAnswers): MCPGatewayConfig {
  const targetUrl = new URL(config.targetUrl);
  
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

  // Configure authentication based on setup answers
  let authConfig: RouteConfig['auth'] | undefined;
  if (config.authType === 'bearer' && config.authToken) {
    authConfig = {
      type: 'bearer',
      headers: {
        'Authorization': `Bearer ${config.authToken}`
      },
      credentials: {
        token: config.authToken
      }
    };
  } else if (config.authType === 'basic' && config.authUsername && config.authPassword) {
    const basicAuth = Buffer.from(`${config.authUsername}:${config.authPassword}`).toString('base64');
    authConfig = {
      type: 'basic',
      headers: {
        'Authorization': `Basic ${basicAuth}`
      },
      credentials: {
        username: config.authUsername,
        password: config.authPassword
      }
    };
  } else if (config.authType === 'session') {
    authConfig = {
      type: 'session',
      headers: {
        'Content-Type': 'application/json'
      }
    };
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
        baseUrl: config.targetUrl,
        timeout: 30000, // 30 seconds
        retryPolicy: {
          maxRetries: 3,
          backoffFactor: 1.5,
          retryOn: [502, 503, 504, 408, 429] // Retry on server errors and timeouts
        },
        auth: authConfig,
        endpoints: endpoints,
        healthCheck: {
          enabled: true,
          path: '/health',
          interval: 30000 // 30 seconds
        }
      },
      // Cerebras Proxy route for LLM inference - Requirements 2.1, 2.3
      cerebras_api: {
        name: 'Cerebras Inference API',
        description: 'High-speed LLM inference via Cerebras proxy',
        baseUrl: 'http://cerebras_proxy:8000',
        timeout: 10000, // 10 seconds for fast inference
        retryPolicy: {
          maxRetries: 2,
          backoffFactor: 1.2,
          retryOn: [502, 503, 504, 408] // Don't retry on rate limits (429)
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
        healthCheck: {
          enabled: true,
          path: '/health',
          interval: 15000 // 15 seconds
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

  // Add custom headers to SUT route if specified
  if (Object.keys(config.customHeaders).length > 0) {
    if (!mcpConfig.routes.sut_api.auth) {
      mcpConfig.routes.sut_api.auth = { type: 'none' };
    }
    if (!mcpConfig.routes.sut_api.auth.headers) {
      mcpConfig.routes.sut_api.auth.headers = {};
    }
    Object.assign(mcpConfig.routes.sut_api.auth.headers, config.customHeaders);
  }

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