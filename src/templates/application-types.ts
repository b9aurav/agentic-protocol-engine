import { SetupAnswers } from '../commands/setup';
import { MCPGatewayConfig, RouteConfig, EndpointConfig } from './mcp-gateway';

export type ApplicationType = 'rest-api' | 'graphql' | 'microservices' | 'custom';

export interface ApplicationTemplate {
    type: ApplicationType;
    name: string;
    description: string;
    defaultEndpoints: string[];
    authTypes: string[];
    commonHeaders: Record<string, string>;
    healthCheckPath: string;
    metricsPath?: string;
    specialConfig?: any;
}

export interface ValidationResult {
    valid: boolean;
    errors: string[];
    warnings: string[];
}

// Production-ready application templates - Requirements 5.4, 8.4
export const APPLICATION_TEMPLATES: Record<ApplicationType, ApplicationTemplate> = {
    'rest-api': {
        type: 'rest-api',
        name: 'REST API Application',
        description: 'Standard RESTful API with CRUD operations',
        defaultEndpoints: [
            '/api/health',
            '/api/v1/users',
            '/api/v1/products',
            '/api/v1/orders',
            '/api/v1/auth/login',
            '/api/v1/auth/logout'
        ],
        authTypes: ['bearer', 'basic', 'session', 'api-key'],
        commonHeaders: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'APE-LoadTest/1.0'
        },
        healthCheckPath: '/api/health',
        metricsPath: '/api/metrics'
    },

    'graphql': {
        type: 'graphql',
        name: 'GraphQL API Application',
        description: 'GraphQL API with queries, mutations, and subscriptions',
        defaultEndpoints: [
            '/graphql',
            '/health',
            '/metrics'
        ],
        authTypes: ['bearer', 'session', 'api-key'],
        commonHeaders: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'APE-LoadTest/1.0'
        },
        healthCheckPath: '/health',
        metricsPath: '/metrics',
        specialConfig: {
            introspectionEnabled: true,
            playgroundEnabled: false, // Disabled in production
            maxQueryDepth: 10,
            maxQueryComplexity: 1000
        }
    },

    'microservices': {
        type: 'microservices',
        name: 'Microservices Architecture',
        description: 'Multiple interconnected microservices with service discovery',
        defaultEndpoints: [
            '/api/gateway/health',
            '/api/user-service/users',
            '/api/product-service/products',
            '/api/order-service/orders',
            '/api/auth-service/login',
            '/api/notification-service/notifications'
        ],
        authTypes: ['bearer', 'service-mesh', 'mutual-tls'],
        commonHeaders: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'APE-LoadTest/1.0',
            'X-Service-Name': 'ape-load-test'
        },
        healthCheckPath: '/api/gateway/health',
        metricsPath: '/api/gateway/metrics'
    },



    'custom': {
        type: 'custom',
        name: 'Custom Application',
        description: 'Custom application configuration',
        defaultEndpoints: ['/health'],
        authTypes: ['none', 'bearer', 'basic', 'session', 'api-key', 'oauth2', 'mutual-tls'],
        commonHeaders: {
            'User-Agent': 'APE-LoadTest/1.0'
        },
        healthCheckPath: '/health'
    }
};

// Generate application-specific MCP Gateway configuration
export function generateApplicationSpecificConfig(
    config: SetupAnswers,
    applicationType: ApplicationType
): MCPGatewayConfig {
    const template = APPLICATION_TEMPLATES[applicationType];

    if (!template) {
        throw new Error(`Unknown application type: ${applicationType}`);
    }

    // Merge user endpoints with template defaults
    const allEndpoints = [...new Set([...template.defaultEndpoints, ...config.endpoints])];

    // Generate endpoint configurations based on application type
    const endpoints: EndpointConfig[] = allEndpoints.map(endpoint => {
        const endpointConfig: EndpointConfig = {
            path: endpoint,
            methods: determineHttpMethods(endpoint, applicationType),
            description: generateEndpointDescription(endpoint, applicationType),
            rateLimit: generateEndpointRateLimit(endpoint, applicationType)
        };

        return endpointConfig;
    });

    // Build route configuration with application-specific settings
    const routeConfig: RouteConfig = {
        name: `${template.name} - ${config.projectName}`,
        description: template.description,
        base_url: config.targetUrl,
        timeout: getApplicationTimeout(applicationType),
        retry_policy: getApplicationRetryPolicy(applicationType),
        auth: generateApplicationAuth(config, template),
        endpoints: endpoints,
        health_check: {
            enabled: true,
            path: template.healthCheckPath,
            interval: 30000
        }
    };

    // Create complete MCP Gateway configuration
    const mcpConfig: MCPGatewayConfig = {
        gateway: {
            name: `${config.projectName}-mcp-gateway`,
            version: '1.0.0',
            port: 3000,
            cors: {
                enabled: true,
                origins: ['*']
            },
            rateLimit: {
                enabled: true,
                windowMs: 60000,
                max: getApplicationRateLimit(applicationType, config.agentCount)
            }
        },
        routes: {
            sut_api: routeConfig,
            cerebras_api: {
                name: 'Cerebras Inference API',
                description: 'High-speed LLM inference via Cerebras proxy',
                base_url: 'http://cerebras_proxy:8000',
                timeout: 10000,
                retry_policy: {
                    max_retries: 2,
                    backoff_factor: 1.2,
                    retry_on: [502, 503, 504, 408]
                },
                endpoints: [
                    {
                        path: '/v1/chat/completions',
                        methods: ['POST'],
                        description: 'OpenAI-compatible chat completions endpoint',
                        rateLimit: { windowMs: 60000, max: 1000 }
                    },
                    {
                        path: '/health',
                        methods: ['GET'],
                        description: 'Health check endpoint'
                    }
                ],
                health_check: {
                    enabled: true,
                    path: '/health',
                    interval: 15000
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

    // Add application-specific headers
    const mergedHeaders = { ...template.commonHeaders, ...config.customHeaders };
    if (Object.keys(mergedHeaders).length > 0) {
        if (!mcpConfig.routes.sut_api.auth) {
            mcpConfig.routes.sut_api.auth = { type: 'none' };
        }
        if (!mcpConfig.routes.sut_api.auth.headers) {
            mcpConfig.routes.sut_api.auth.headers = {};
        }
        Object.assign(mcpConfig.routes.sut_api.auth.headers, mergedHeaders);
    }

    return mcpConfig;
}

// Determine appropriate HTTP methods for endpoint based on application type
function determineHttpMethods(endpoint: string, applicationType: ApplicationType): string[] {
    const path = endpoint.toLowerCase();

    // GraphQL typically uses POST for all operations
    if (applicationType === 'graphql') {
        return path.includes('graphql') ? ['POST'] : ['GET'];
    }

    // Health and metrics endpoints are typically GET only
    if (path.includes('health') || path.includes('metrics') || path.includes('status')) {
        return ['GET'];
    }

    // Authentication endpoints
    if (path.includes('login') || path.includes('auth') || path.includes('token')) {
        return ['POST'];
    }

    if (path.includes('logout')) {
        return ['POST', 'DELETE'];
    }



    // Default REST API endpoints support full CRUD
    return ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
}

// Generate descriptive endpoint descriptions
function generateEndpointDescription(endpoint: string, applicationType: ApplicationType): string {
    const path = endpoint.toLowerCase();

    if (applicationType === 'graphql' && path.includes('graphql')) {
        return 'GraphQL endpoint for queries, mutations, and subscriptions';
    }

    if (path.includes('health')) return 'Application health check endpoint';
    if (path.includes('metrics')) return 'Prometheus metrics endpoint';
    if (path.includes('login')) return 'User authentication endpoint';
    if (path.includes('logout')) return 'User logout endpoint';
    if (path.includes('users')) return 'User management API endpoint';
    if (path.includes('products')) return 'Product catalog API endpoint';
    if (path.includes('orders')) return 'Order management API endpoint';
    if (path.includes('notifications')) return 'Notification service endpoint';



    return `API endpoint: ${endpoint}`;
}

// Generate endpoint-specific rate limits
function generateEndpointRateLimit(endpoint: string, applicationType: ApplicationType): { windowMs: number; max: number } {
    const path = endpoint.toLowerCase();

    // Authentication endpoints need stricter rate limiting
    if (path.includes('login') || path.includes('auth')) {
        return { windowMs: 60000, max: 10 }; // 10 requests per minute
    }

    // Health checks can be more frequent
    if (path.includes('health') || path.includes('metrics')) {
        return { windowMs: 60000, max: 200 };
    }

    // GraphQL endpoints may need higher limits due to complex queries
    if (applicationType === 'graphql') {
        return { windowMs: 60000, max: 150 };
    }



    // Default rate limit
    return { windowMs: 60000, max: 100 };
}

// Get application-specific timeout values
function getApplicationTimeout(applicationType: ApplicationType): number {
    switch (applicationType) {
        case 'graphql':
            return 45000; // GraphQL queries can be complex
        case 'microservices':
            return 60000; // Service-to-service calls may take longer

        default:
            return 30000; // Standard REST API timeout
    }
}

// Get application-specific retry policies
function getApplicationRetryPolicy(applicationType: ApplicationType): RouteConfig['retry_policy'] {
    switch (applicationType) {
        case 'graphql':
            return {
                max_retries: 2, // GraphQL errors are often query-related, fewer retries
                backoff_factor: 1.5,
                retry_on: [502, 503, 504, 408]
            };
        case 'microservices':
            return {
                max_retries: 4, // Microservices may have transient failures
                backoff_factor: 2.0,
                retry_on: [502, 503, 504, 408, 429]
            };

        default:
            return {
                max_retries: 3,
                backoff_factor: 1.5,
                retry_on: [502, 503, 504, 408, 429]
            };
    }
}

// Get application-specific rate limits based on agent count
function getApplicationRateLimit(applicationType: ApplicationType, agentCount: number): number {
    const baseLimit = agentCount * 10; // 10 requests per agent per minute

    switch (applicationType) {
        case 'graphql':
            return Math.floor(baseLimit * 0.7); // GraphQL queries are more expensive
        case 'microservices':
            return Math.floor(baseLimit * 1.5); // Microservices may generate more traffic

        default:
            return baseLimit;
    }
}

// Generate application-specific authentication configuration
function generateApplicationAuth(config: SetupAnswers, template: ApplicationTemplate): RouteConfig['auth'] | undefined {
    if (config.authType === 'none') {
        return undefined;
    }

    // Validate that the auth type is supported by the application template
    if (!template.authTypes.includes(config.authType)) {
        throw new Error(
            `Authentication type '${config.authType}' is not supported for ${template.name}. ` +
            `Supported types: ${template.authTypes.join(', ')}`
        );
    }

    switch (config.authType) {
        case 'bearer':
            if (!config.authToken) {
                throw new Error('Bearer token is required for bearer authentication');
            }
            return {
                type: 'bearer',
                headers: {
                    'Authorization': `Bearer ${config.authToken}`
                },
                credentials: {
                    token: config.authToken
                }
            };

        case 'basic': {
            if (!config.authUsername || !config.authPassword) {
                throw new Error('Username and password are required for basic authentication');
            }
            const basicAuth = Buffer.from(`${config.authUsername}:${config.authPassword}`).toString('base64');
            return {
                type: 'basic',
                headers: {
                    'Authorization': `Basic ${basicAuth}`
                },
                credentials: {
                    username: config.authUsername,
                    password: config.authPassword
                }
            };
        }

        case 'session':
            return {
                type: 'session',
                headers: {
                    'Content-Type': 'application/json'
                }
            };

        case 'api-key':
            if (!config.authToken) {
                throw new Error('API key is required for API key authentication');
            }
            return {
                type: 'api-key',
                headers: {
                    'X-API-Key': config.authToken
                },
                credentials: {
                    token: config.authToken
                }
            };

        default:
            throw new Error(`Unsupported authentication type: ${config.authType}`);
    }
}

// Validate configuration for specific application type - Requirements 8.4
export function validateApplicationConfig(
    config: SetupAnswers,
    applicationType: ApplicationType
): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];
    const template = APPLICATION_TEMPLATES[applicationType];

    if (!template) {
        errors.push(`Unknown application type: ${applicationType}`);
        return { valid: false, errors, warnings };
    }

    // Validate URL format and accessibility
    try {
        const url = new URL(config.targetUrl);
        if (!['http:', 'https:'].includes(url.protocol)) {
            errors.push('Target URL must use HTTP or HTTPS protocol');
        }

        // Warn about localhost in production
        if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
            warnings.push('Using localhost may not work in containerized environments. Consider using host.docker.internal or the actual IP address.');
        }
    } catch (error) {
        errors.push(`Invalid target URL: ${config.targetUrl}`);
    }

    // Validate authentication configuration
    if (config.authType && config.authType !== 'none') {
        if (!template.authTypes.includes(config.authType)) {
            errors.push(
                `Authentication type '${config.authType}' is not supported for ${template.name}. ` +
                `Supported types: ${template.authTypes.join(', ')}`
            );
        }

        // Validate auth credentials
        switch (config.authType) {
            case 'bearer':
            case 'api-key':
                if (!config.authToken || config.authToken.trim().length === 0) {
                    errors.push(`${config.authType === 'bearer' ? 'Bearer token' : 'API key'} is required but not provided`);
                } else if (config.authToken.length < 10) {
                    warnings.push(`${config.authType === 'bearer' ? 'Bearer token' : 'API key'} seems too short. Ensure it's a valid token.`);
                }
                break;
            case 'basic':
                if (!config.authUsername || config.authUsername.trim().length === 0) {
                    errors.push('Username is required for basic authentication');
                }
                if (!config.authPassword || config.authPassword.trim().length === 0) {
                    errors.push('Password is required for basic authentication');
                }
                break;
        }
    }

    // Validate endpoints for application type
    if (config.endpoints.length === 0) {
        warnings.push('No endpoints specified. Using default endpoints for application type.');
    } else {
        // Validate endpoint formats
        for (const endpoint of config.endpoints) {
            if (!endpoint.startsWith('/')) {
                errors.push(`Endpoint '${endpoint}' must start with '/'`);
            }

            // Application-specific endpoint validation
            if (applicationType === 'graphql') {
                if (!config.endpoints.some(ep => ep.toLowerCase().includes('graphql'))) {
                    warnings.push('GraphQL applications typically need a /graphql endpoint');
                }
            }


        }
    }

    // Validate agent count for application type
    if (applicationType === 'graphql' && config.agentCount > 200) {
        warnings.push('GraphQL applications may not handle very high concurrent loads well. Consider starting with fewer agents.');
    }



    // Validate test duration
    if (config.testDuration < 1) {
        errors.push('Test duration must be at least 1 minute');
    } else if (config.testDuration > 1440) {
        errors.push('Test duration cannot exceed 24 hours (1440 minutes)');
    }

    // Application-specific warnings
    if (applicationType === 'microservices') {
        warnings.push('Microservices testing may require additional service discovery configuration. Ensure all service endpoints are accessible.');
    }

    if (applicationType === 'graphql' && !config.customHeaders['Content-Type']) {
        warnings.push('GraphQL applications typically require Content-Type: application/json header');
    }

    return {
        valid: errors.length === 0,
        errors,
        warnings
    };
}

// Generate application-specific Docker Compose overrides
export function generateApplicationDockerOverride(
    config: SetupAnswers,
    applicationType: ApplicationType
): any {
    const template = APPLICATION_TEMPLATES[applicationType];
    const overrides: any = {
        version: '3.8',
        services: {}
    };

    // Application-specific MCP Gateway configuration
    overrides.services.mcp_gateway = {
        environment: {
            APPLICATION_TYPE: applicationType,
            APPLICATION_NAME: template.name,
            HEALTH_CHECK_PATH: template.healthCheckPath,
            ...(template.metricsPath && { METRICS_PATH: template.metricsPath })
        }
    };

    // Application-specific agent configuration
    overrides.services.llama_agent = {
        environment: {
            APPLICATION_TYPE: applicationType,
            DEFAULT_ENDPOINTS: template.defaultEndpoints.join(','),
            SUPPORTED_AUTH_TYPES: template.authTypes.join(',')
        }
    };

    // GraphQL-specific configuration
    if (applicationType === 'graphql') {
        overrides.services.mcp_gateway.environment.GRAPHQL_INTROSPECTION = 'true';
        overrides.services.mcp_gateway.environment.GRAPHQL_MAX_DEPTH = '10';
        overrides.services.llama_agent.environment.GRAPHQL_MODE = 'true';
    }



    // Microservices-specific configuration
    if (applicationType === 'microservices') {
        overrides.services.mcp_gateway.environment.SERVICE_DISCOVERY = 'true';
        overrides.services.mcp_gateway.environment.CIRCUIT_BREAKER = 'true';
        overrides.services.llama_agent.environment.MICROSERVICES_MODE = 'true';
    }

    return overrides;
}