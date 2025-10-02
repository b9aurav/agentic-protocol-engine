import * as fs from 'fs-extra';
import * as path from 'path';
import * as os from 'os';
import { generateMCPGatewayConfig } from '../../templates/mcp-gateway';
import { SetupAnswers } from '../../commands/setup';

describe('MCP Gateway Integration Tests', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'ape-test-'));
  });

  afterEach(async () => {
    await fs.remove(tempDir);
  });

  it('should generate valid MCP Gateway configuration file', async () => {
    const mockConfig: SetupAnswers = {
      projectName: 'integration-test',
      targetUrl: 'https://api.example.com',
      targetPort: 443,
      authType: 'bearer',
      authToken: 'test-token-123',
      agentCount: 25,
      testDuration: 10,
      testGoal: 'Test API endpoints comprehensively',
      endpoints: ['/api/v1/users', '/api/v1/orders', '/api/v1/products'],
      customHeaders: {
        'User-Agent': 'APE-LoadTest/1.0',
        'X-API-Version': 'v1'
      }
    };

    // Generate the configuration
    const mcpConfig = generateMCPGatewayConfig(mockConfig);

    // Write to file
    const configPath = path.join(tempDir, 'ape.mcp-gateway.json');
    await fs.writeJSON(configPath, mcpConfig, { spaces: 2 });

    // Verify file exists and is valid JSON
    expect(await fs.pathExists(configPath)).toBe(true);
    
    const savedConfig = await fs.readJSON(configPath);
    expect(savedConfig).toEqual(mcpConfig);

    // Verify key configuration elements
    expect(savedConfig.gateway.name).toBe('integration-test-mcp-gateway');
    expect(savedConfig.routes.sut_api.baseUrl).toBe('https://api.example.com');
    expect(savedConfig.routes.sut_api.auth.type).toBe('bearer');
    expect(savedConfig.routes.sut_api.auth.headers['Authorization']).toBe('Bearer test-token-123');
    expect(savedConfig.routes.sut_api.auth.headers['User-Agent']).toBe('APE-LoadTest/1.0');
    expect(savedConfig.routes.sut_api.auth.headers['X-API-Version']).toBe('v1');

    // Verify endpoint configuration
    const userEndpoint = savedConfig.routes.sut_api.endpoints.find(
      (ep: any) => ep.path === '/api/v1/users'
    );
    expect(userEndpoint).toBeDefined();
    expect(userEndpoint.methods).toEqual(['GET', 'POST', 'PUT', 'DELETE']);

    // Verify Cerebras API configuration
    expect(savedConfig.routes.cerebras_api.baseUrl).toBe('http://cerebras_proxy:8000');
    expect(savedConfig.routes.cerebras_api.timeout).toBe(10000);

    // Verify observability configuration
    expect(savedConfig.logging.tracing.enabled).toBe(true);
    expect(savedConfig.metrics.enabled).toBe(true);
  });

  it('should handle complex authentication scenarios', async () => {
    const basicAuthConfig: SetupAnswers = {
      projectName: 'basic-auth-test',
      targetUrl: 'http://internal-api:8080',
      targetPort: 8080,
      authType: 'basic',
      authUsername: 'admin',
      authPassword: 'secret123',
      agentCount: 5,
      testDuration: 2,
      testGoal: 'Test basic auth endpoints',
      endpoints: ['/admin/users', '/admin/settings'],
      customHeaders: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    };

    const mcpConfig = generateMCPGatewayConfig(basicAuthConfig);

    // Verify Basic auth configuration
    expect(mcpConfig.routes.sut_api.auth?.type).toBe('basic');
    expect(mcpConfig.routes.sut_api.auth?.credentials?.username).toBe('admin');
    expect(mcpConfig.routes.sut_api.auth?.credentials?.password).toBe('secret123');
    
    // Verify Base64 encoding of credentials
    const authHeader = mcpConfig.routes.sut_api.auth?.headers?.['Authorization'];
    expect(authHeader).toMatch(/^Basic /);
    
    const encodedCredentials = authHeader?.replace('Basic ', '');
    const decodedCredentials = Buffer.from(encodedCredentials!, 'base64').toString();
    expect(decodedCredentials).toBe('admin:secret123');

    // Verify custom headers are preserved
    expect(mcpConfig.routes.sut_api.auth?.headers?.['Content-Type']).toBe('application/json');
    expect(mcpConfig.routes.sut_api.auth?.headers?.['Accept']).toBe('application/json');
  });

  it('should generate configuration with proper retry policies', async () => {
    const config: SetupAnswers = {
      projectName: 'retry-test',
      targetUrl: 'http://unreliable-service:3000',
      targetPort: 3000,
      authType: 'none',
      agentCount: 50,
      testDuration: 15,
      testGoal: 'Test retry behavior under load',
      endpoints: ['/api/flaky-endpoint'],
      customHeaders: {}
    };

    const mcpConfig = generateMCPGatewayConfig(config);

    // Verify SUT API retry policy
    expect(mcpConfig.routes.sut_api.retryPolicy.maxRetries).toBe(3);
    expect(mcpConfig.routes.sut_api.retryPolicy.backoffFactor).toBe(1.5);
    expect(mcpConfig.routes.sut_api.retryPolicy.retryOn).toEqual([502, 503, 504, 408, 429]);

    // Verify Cerebras API retry policy (different from SUT)
    expect(mcpConfig.routes.cerebras_api.retryPolicy.maxRetries).toBe(2);
    expect(mcpConfig.routes.cerebras_api.retryPolicy.backoffFactor).toBe(1.2);
    expect(mcpConfig.routes.cerebras_api.retryPolicy.retryOn).toEqual([502, 503, 504, 408]);
  });

  it('should validate configuration schema compliance', async () => {
    const config: SetupAnswers = {
      projectName: 'schema-test',
      targetUrl: 'https://api.production.com',
      targetPort: 443,
      authType: 'session',
      agentCount: 100,
      testDuration: 30,
      testGoal: 'Validate production-like load',
      endpoints: ['/api/auth/login', '/api/dashboard', '/api/logout'],
      customHeaders: {
        'X-Forwarded-For': '127.0.0.1',
        'X-Real-IP': '127.0.0.1'
      }
    };

    const mcpConfig = generateMCPGatewayConfig(config);

    // Validate required top-level properties
    expect(mcpConfig).toHaveProperty('gateway');
    expect(mcpConfig).toHaveProperty('routes');
    expect(mcpConfig).toHaveProperty('logging');
    expect(mcpConfig).toHaveProperty('metrics');

    // Validate gateway configuration
    expect(mcpConfig.gateway).toHaveProperty('name');
    expect(mcpConfig.gateway).toHaveProperty('version');
    expect(mcpConfig.gateway).toHaveProperty('port');
    expect(mcpConfig.gateway).toHaveProperty('cors');
    expect(mcpConfig.gateway).toHaveProperty('rateLimit');

    // Validate route configurations
    expect(mcpConfig.routes).toHaveProperty('sut_api');
    expect(mcpConfig.routes).toHaveProperty('cerebras_api');

    // Validate SUT API route structure
    const sutRoute = mcpConfig.routes.sut_api;
    expect(sutRoute).toHaveProperty('name');
    expect(sutRoute).toHaveProperty('baseUrl');
    expect(sutRoute).toHaveProperty('timeout');
    expect(sutRoute).toHaveProperty('retryPolicy');
    expect(sutRoute).toHaveProperty('endpoints');
    expect(sutRoute).toHaveProperty('healthCheck');

    // Validate endpoint structure
    sutRoute.endpoints.forEach(endpoint => {
      expect(endpoint).toHaveProperty('path');
      expect(endpoint).toHaveProperty('methods');
      expect(endpoint).toHaveProperty('description');
      expect(Array.isArray(endpoint.methods)).toBe(true);
    });

    // Validate logging configuration
    expect(mcpConfig.logging).toHaveProperty('level');
    expect(mcpConfig.logging).toHaveProperty('format');
    expect(mcpConfig.logging).toHaveProperty('tracing');
    expect(mcpConfig.logging.tracing).toHaveProperty('enabled');
    expect(mcpConfig.logging.tracing).toHaveProperty('headerName');
  });
});