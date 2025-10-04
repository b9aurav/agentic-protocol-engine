import { SetupAnswers } from '../commands/setup';
import { MCPGatewayConfig, RouteConfig, EndpointConfig } from './mcp-gateway';

export type ApplicationType = 'rest-api';

export interface ApplicationTemplate {
    type: ApplicationType;
    name: string;
    description: string;
    defaultEndpoints: string[];
    healthCheckPath: string;
    metricsPath?: string;
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

        ],

        healthCheckPath: '/api/health',
        metricsPath: '/api/metrics'
    },




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

    // If we have parsed API data, use enhanced configuration
    if (config.parsedApiSpec) {
        // Use parsed endpoints instead of template defaults
        const endpoints: EndpointConfig[] = config.parsedApiSpec.endpoints.map(endpoint => {
            const endpointConfig: EndpointConfig = {
                path: endpoint.path,
                methods: [endpoint.method.toUpperCase()],
                description: endpoint.purpose,
                rateLimit: generateSmartRateLimit(endpoint, applicationType),
                metadata: {
                    parameters: endpoint.parameters,
                    responses: endpoint.responses,
                    sessionRequired: endpoint.sessionRequired,
                    sampleData: generateSampleRequestData(endpoint),
                    requiredFields: extractRequiredFields(endpoint.parameters),
                    optionalFields: extractOptionalFields(endpoint.parameters),
                    validation: generateValidationRules(endpoint),
                    responseHandling: generateResponseHandling(endpoint)
                }
            };

            return endpointConfig;
        });

        // Build enhanced route configuration
        const routeConfig: RouteConfig = {
            name: `${template.name} - ${config.projectName} (AI-Enhanced)`,
            description: `${template.description} - Enhanced with parsed API specification`,
            base_url: config.targetUrl,
            timeout: getApplicationTimeout(applicationType),
            retry_policy: getApplicationRetryPolicy(applicationType),
            endpoints: endpoints,
            health_check: {
                enabled: true,
                path: template.healthCheckPath,
                interval: 30000
            }
        };

        // Add enhanced features based on parsed patterns
        if (config.parsedApiSpec.commonPatterns?.sessionManagement) {
            routeConfig.sessionHandling = {
                enabled: true,
                cookieSupport: true,
                headerSupport: true,
                tokenRefresh: true
            };
        }

        if (config.parsedApiSpec.commonPatterns?.pagination) {
            routeConfig.paginationHandling = {
                enabled: true,
                defaultPageSize: 20,
                maxPageSize: 100,
                pageParam: 'page',
                sizeParam: 'size'
            };
        }

        if (config.parsedApiSpec.dataModels) {
            routeConfig.dataModels = config.parsedApiSpec.dataModels;
        }

        if (config.parsedApiSpec.commonPatterns?.errorHandling) {
            routeConfig.errorHandling = {
                patterns: config.parsedApiSpec.commonPatterns.errorHandling,
                retryableErrors: [429, 502, 503, 504],
                nonRetryableErrors: [400, 401, 403, 404, 422]
            };
        }

        return buildMCPGatewayConfig(config, routeConfig, applicationType);
    }

    // Fallback to template-based configuration
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
        endpoints: endpoints,
        health_check: {
            enabled: true,
            path: template.healthCheckPath,
            interval: 30000
        }
    };

    return buildMCPGatewayConfig(config, routeConfig, applicationType);
}

// Determine appropriate HTTP methods for endpoint based on application type
function determineHttpMethods(endpoint: string, applicationType: ApplicationType): string[] {
    const path = endpoint.toLowerCase();

    // Health and metrics endpoints are typically GET only
    if (path.includes('health') || path.includes('metrics') || path.includes('status')) {
        return ['GET'];
    }



    // Default REST API endpoints support full CRUD
    return ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
}

// Generate descriptive endpoint descriptions
function generateEndpointDescription(endpoint: string, applicationType: ApplicationType): string {
    const path = endpoint.toLowerCase();

    if (path.includes('health')) return 'Application health check endpoint';
    if (path.includes('metrics')) return 'Prometheus metrics endpoint';

    if (path.includes('users')) return 'User management API endpoint';
    if (path.includes('products')) return 'Product catalog API endpoint';
    if (path.includes('orders')) return 'Order management API endpoint';
    if (path.includes('notifications')) return 'Notification service endpoint';

    return `API endpoint: ${endpoint}`;
}

// Generate endpoint-specific rate limits
function generateEndpointRateLimit(endpoint: string, applicationType: ApplicationType): { windowMs: number; max: number } {
    const path = endpoint.toLowerCase();



    // Health checks can be more frequent
    if (path.includes('health') || path.includes('metrics')) {
        return { windowMs: 60000, max: 200 };
    }

    // Default rate limit
    return { windowMs: 60000, max: 100 };
}

// Get application-specific timeout values
function getApplicationTimeout(applicationType: ApplicationType): number {
    return 30000; // Standard REST API timeout
}

// Get application-specific retry policies
function getApplicationRetryPolicy(applicationType: ApplicationType): RouteConfig['retry_policy'] {
    return {
        max_retries: 3,
        backoff_factor: 1.5,
        retry_on: [502, 503, 504, 408, 429]
    };
}

// Get application-specific rate limits based on agent count
function getApplicationRateLimit(applicationType: ApplicationType, agentCount: number): number {
    return agentCount * 10; // 10 requests per agent per minute
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



    // Validate endpoints for application type
    if (config.endpoints.length === 0) {
        warnings.push('No endpoints specified. Using default endpoints for application type.');
    } else {
        // Validate endpoint formats
        for (const endpoint of config.endpoints) {
            if (!endpoint.startsWith('/')) {
                errors.push(`Endpoint '${endpoint}' must start with '/'`);
            }




        }
    }





    // Validate test duration
    if (config.testDuration < 1) {
        errors.push('Test duration must be at least 1 minute');
    } else if (config.testDuration > 1440) {
        errors.push('Test duration cannot exceed 24 hours (1440 minutes)');
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
            DEFAULT_ENDPOINTS: template.defaultEndpoints.join(',')
        }
    };







    return overrides;
}

// Helper functions for enhanced configuration

/**
 * Generate smart rate limits based on parsed endpoint data
 */
function generateSmartRateLimit(endpoint: any, applicationType: ApplicationType): { windowMs: number; max: number } {
    const method = endpoint.method.toUpperCase();
    const path = endpoint.path.toLowerCase();

    // Health and metrics endpoints
    if (path.includes('health') || path.includes('metrics')) {
        return { windowMs: 60000, max: 300 };
    }

    // Authentication endpoints
    if (path.includes('login') || path.includes('auth')) {
        return { windowMs: 60000, max: 20 }; // Strict limit for auth
    }

    // Session-required endpoints get lower limits
    if (endpoint.sessionRequired) {
        if (method === 'GET') {
            return { windowMs: 60000, max: 150 };
        } else {
            return { windowMs: 60000, max: 30 };
        }
    }

    // Method-based limits
    if (method === 'GET') {
        return { windowMs: 60000, max: 200 };
    } else if (['POST', 'PUT', 'PATCH'].includes(method)) {
        return { windowMs: 60000, max: 50 };
    } else if (method === 'DELETE') {
        return { windowMs: 60000, max: 20 };
    }

    return { windowMs: 60000, max: 100 };
}

/**
 * Generate sample request data for parsed endpoints
 */
function generateSampleRequestData(endpoint: any): Record<string, any> {
    const sampleData: Record<string, any> = {};

    if (endpoint.parameters?.body) {
        Object.entries(endpoint.parameters.body).forEach(([key, description]) => {
            sampleData[key] = generateSampleValue(key, description as string);
        });
    }

    if (endpoint.parameters?.query) {
        Object.entries(endpoint.parameters.query).forEach(([key, description]) => {
            sampleData[key] = generateSampleValue(key, description as string);
        });
    }

    return sampleData;
}

/**
 * Extract required fields from endpoint parameters
 */
function extractRequiredFields(parameters: any): string[] {
    const required: string[] = [];

    if (parameters?.body) {
        Object.entries(parameters.body).forEach(([key, description]) => {
            if (typeof description === 'string' && description.toLowerCase().includes('required')) {
                required.push(key);
            }
        });
    }

    return required;
}

/**
 * Extract optional fields from endpoint parameters
 */
function extractOptionalFields(parameters: any): string[] {
    const optional: string[] = [];

    if (parameters?.body) {
        Object.entries(parameters.body).forEach(([key, description]) => {
            if (typeof description === 'string' && description.toLowerCase().includes('optional')) {
                optional.push(key);
            }
        });
    }

    return optional;
}

/**
 * Generate validation rules for endpoint parameters
 */
function generateValidationRules(endpoint: any): Record<string, any> {
    const rules: Record<string, any> = {};

    if (endpoint.parameters?.body) {
        Object.entries(endpoint.parameters.body).forEach(([key, description]) => {
            const rule: any = {};
            const lowerDesc = (description as string).toLowerCase();

            if (lowerDesc.includes('required')) rule.required = true;
            if (lowerDesc.includes('string')) rule.type = 'string';
            if (lowerDesc.includes('number')) rule.type = 'number';
            if (lowerDesc.includes('boolean')) rule.type = 'boolean';
            if (lowerDesc.includes('email')) rule.format = 'email';

            rules[key] = rule;
        });
    }

    return rules;
}

/**
 * Generate response handling configuration
 */
function generateResponseHandling(endpoint: any): Record<string, any> {
    const handling: Record<string, any> = {
        success: {
            expectedStatus: getSuccessStatusCodes(endpoint.method),
            schema: endpoint.responses.success
        }
    };

    if (endpoint.responses.error && endpoint.responses.error.length > 0) {
        handling.error = endpoint.responses.error.map((error: any) => ({
            status: error.code || 400,
            schema: error.example || error,
            retryable: [429, 502, 503, 504].includes(error.code || 400)
        }));
    }

    return handling;
}

/**
 * Get success status codes for HTTP method
 */
function getSuccessStatusCodes(method: string): number[] {
    switch (method.toUpperCase()) {
        case 'GET': return [200];
        case 'POST': return [200, 201];
        case 'PUT': return [200, 204];
        case 'PATCH': return [200, 204];
        case 'DELETE': return [200, 204];
        default: return [200];
    }
}

/**
 * Generate sample values based on field name and description
 */
function generateSampleValue(fieldName: string, description: string): any {
    const lowerDesc = description.toLowerCase();
    const lowerField = fieldName.toLowerCase();

    if (lowerDesc.includes('string') || lowerDesc.includes('text')) {
        if (lowerField.includes('email')) return 'user@example.com';
        if (lowerField.includes('name')) return 'Sample Name';
        if (lowerField.includes('id')) return 'sample-id-123';
        return 'sample text';
    }

    if (lowerDesc.includes('number') || lowerDesc.includes('integer')) {
        if (lowerField.includes('price')) return 29.99;
        if (lowerField.includes('count')) return 5;
        return 42;
    }

    if (lowerDesc.includes('boolean')) return true;
    if (lowerDesc.includes('array')) return ['sample', 'values'];
    if (lowerDesc.includes('object')) return { key: 'value' };

    // Field name-based generation
    if (lowerField.includes('email')) return 'user@example.com';
    if (lowerField.includes('phone')) return '+1-555-0123';
    if (lowerField.includes('date')) return new Date().toISOString().split('T')[0];

    return 'sample value';
}

/**
 * Build complete MCP Gateway configuration
 */
function buildMCPGatewayConfig(
    config: SetupAnswers, 
    routeConfig: RouteConfig, 
    applicationType: ApplicationType
): MCPGatewayConfig {
    return {
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
}