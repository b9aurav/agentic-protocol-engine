import { generateMCPGatewayConfig, generateMCPGatewayPackageJson } from '../templates/mcp-gateway';
import { SetupAnswers } from '../commands/setup';

describe('MCP Gateway Configuration Generation', () => {
  const mockSetupAnswers: SetupAnswers = {
    projectName: 'test-project',
    targetUrl: 'http://localhost:8080',
    targetPort: 8080,
    authType: 'none',
    agentCount: 10,
    testDuration: 5,
    testGoal: 'Test user interactions',
    endpoints: ['/api/users', '/api/products'],
    customHeaders: {}
  };

  describe('generateMCPGatewayConfig', () => {
    it('should generate basic MCP Gateway configuration with no authentication', () => {
      const config = generateMCPGatewayConfig(mockSetupAnswers);

      expect(config.gateway.name).toBe('test-project-mcp-gateway');
      expect(config.gateway.port).toBe(3000);
      expect(config.gateway.cors.enabled).toBe(true);
      expect(config.gateway.rateLimit.enabled).toBe(true);

      // Check SUT API route configuration
      expect(config.routes.sut_api).toBeDefined();
      expect(config.routes.sut_api.baseUrl).toBe('http://localhost:8080');
      expect(config.routes.sut_api.timeout).toBe(30000);
      expect(config.routes.sut_api.retryPolicy.maxRetries).toBe(3);
      expect(config.routes.sut_api.endpoints).toHaveLength(5); // 2 user + 3 common endpoints

      // Check Cerebras API route configuration
      expect(config.routes.cerebras_api).toBeDefined();
      expect(config.routes.cerebras_api.baseUrl).toBe('http://cerebras_proxy:8000');
      expect(config.routes.cerebras_api.timeout).toBe(10000);
      expect(config.routes.cerebras_api.endpoints).toHaveLength(3);

      // Check logging and metrics configuration
      expect(config.logging.tracing.enabled).toBe(true);
      expect(config.logging.tracing.headerName).toBe('X-Trace-ID');
      expect(config.metrics.enabled).toBe(true);
    });

    it('should configure Bearer token authentication correctly', () => {
      const bearerConfig: SetupAnswers = {
        ...mockSetupAnswers,
        authType: 'bearer',
        authToken: 'test-bearer-token'
      };

      const config = generateMCPGatewayConfig(bearerConfig);

      expect(config.routes.sut_api.auth).toBeDefined();
      expect(config.routes.sut_api.auth?.type).toBe('bearer');
      expect(config.routes.sut_api.auth?.headers?.['Authorization']).toBe('Bearer test-bearer-token');
      expect(config.routes.sut_api.auth?.credentials?.token).toBe('test-bearer-token');
    });

    it('should configure Basic authentication correctly', () => {
      const basicConfig: SetupAnswers = {
        ...mockSetupAnswers,
        authType: 'basic',
        authUsername: 'testuser',
        authPassword: 'testpass'
      };

      const config = generateMCPGatewayConfig(basicConfig);

      expect(config.routes.sut_api.auth).toBeDefined();
      expect(config.routes.sut_api.auth?.type).toBe('basic');
      expect(config.routes.sut_api.auth?.headers?.['Authorization']).toMatch(/^Basic /);
      expect(config.routes.sut_api.auth?.credentials?.username).toBe('testuser');
      expect(config.routes.sut_api.auth?.credentials?.password).toBe('testpass');
    });

    it('should configure session authentication correctly', () => {
      const sessionConfig: SetupAnswers = {
        ...mockSetupAnswers,
        authType: 'session'
      };

      const config = generateMCPGatewayConfig(sessionConfig);

      expect(config.routes.sut_api.auth).toBeDefined();
      expect(config.routes.sut_api.auth?.type).toBe('session');
      expect(config.routes.sut_api.auth?.headers?.['Content-Type']).toBe('application/json');
    });

    it('should include custom headers in SUT API configuration', () => {
      const customHeadersConfig: SetupAnswers = {
        ...mockSetupAnswers,
        customHeaders: {
          'User-Agent': 'APE-Test-Agent/1.0',
          'X-Custom-Header': 'custom-value'
        }
      };

      const config = generateMCPGatewayConfig(customHeadersConfig);

      expect(config.routes.sut_api.auth?.headers?.['User-Agent']).toBe('APE-Test-Agent/1.0');
      expect(config.routes.sut_api.auth?.headers?.['X-Custom-Header']).toBe('custom-value');
    });

    it('should generate endpoint configurations with rate limiting', () => {
      const config = generateMCPGatewayConfig(mockSetupAnswers);

      const userEndpoint = config.routes.sut_api.endpoints.find(ep => ep.path === '/api/users');
      expect(userEndpoint).toBeDefined();
      expect(userEndpoint?.methods).toEqual(['GET', 'POST', 'PUT', 'DELETE']);
      expect(userEndpoint?.rateLimit?.max).toBe(100);
      expect(userEndpoint?.rateLimit?.windowMs).toBe(60000);

      const healthEndpoint = config.routes.sut_api.endpoints.find(ep => ep.path === '/health');
      expect(healthEndpoint).toBeDefined();
      expect(healthEndpoint?.methods).toEqual(['GET']);
      expect(healthEndpoint?.rateLimit?.max).toBe(200);
    });

    it('should configure Cerebras API endpoints correctly', () => {
      const config = generateMCPGatewayConfig(mockSetupAnswers);

      const chatEndpoint = config.routes.cerebras_api.endpoints.find(
        ep => ep.path === '/v1/chat/completions'
      );
      expect(chatEndpoint).toBeDefined();
      expect(chatEndpoint?.methods).toEqual(['POST']);
      expect(chatEndpoint?.rateLimit?.max).toBe(1000);

      const healthEndpoint = config.routes.cerebras_api.endpoints.find(ep => ep.path === '/health');
      expect(healthEndpoint).toBeDefined();
      expect(healthEndpoint?.methods).toEqual(['GET']);
    });

    it('should handle HTTPS URLs correctly', () => {
      const httpsConfig: SetupAnswers = {
        ...mockSetupAnswers,
        targetUrl: 'https://api.example.com:443',
        targetPort: 443
      };

      const config = generateMCPGatewayConfig(httpsConfig);

      expect(config.routes.sut_api.baseUrl).toBe('https://api.example.com:443');
    });

    it('should not duplicate common endpoints if already specified', () => {
      const configWithHealth: SetupAnswers = {
        ...mockSetupAnswers,
        endpoints: ['/api/users', '/health', '/api/products']
      };

      const config = generateMCPGatewayConfig(configWithHealth);

      const healthEndpoints = config.routes.sut_api.endpoints.filter(ep => ep.path === '/health');
      expect(healthEndpoints).toHaveLength(1);
    });
  });

  describe('generateMCPGatewayPackageJson', () => {
    it('should generate correct package.json for MCP Gateway', () => {
      const packageJson = generateMCPGatewayPackageJson('test-project');

      expect(packageJson.name).toBe('test-project-mcp-gateway');
      expect(packageJson.version).toBe('1.0.0');
      expect(packageJson.main).toBe('src/gateway.js');
      expect(packageJson.scripts.start).toBe('node src/gateway.js');

      // Check essential dependencies
      expect(packageJson.dependencies.express).toBeDefined();
      expect(packageJson.dependencies['express-rate-limit']).toBeDefined();
      expect(packageJson.dependencies.cors).toBeDefined();
      expect(packageJson.dependencies.axios).toBeDefined();
      expect(packageJson.dependencies.winston).toBeDefined();
      expect(packageJson.dependencies['prom-client']).toBeDefined();

      // Check dev dependencies
      expect(packageJson.devDependencies.jest).toBeDefined();
      expect(packageJson.devDependencies.supertest).toBeDefined();

      expect(packageJson.engines.node).toBe('>=18.0.0');
    });
  });
});