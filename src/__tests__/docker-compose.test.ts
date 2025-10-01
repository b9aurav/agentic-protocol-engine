import { generateDockerCompose, validateDockerComposeConfig, generateDockerComposeWithEnvironment } from '../templates/docker-compose';
import { SetupAnswers } from '../commands/setup';

describe('Docker Compose Configuration Generation', () => {
  const mockConfig: SetupAnswers = {
    projectName: 'test-project',
    targetUrl: 'http://localhost:8080',
    targetPort: 8080,
    authType: 'none',
    agentCount: 10,
    testDuration: 5,
    testGoal: 'Test realistic user behavior',
    endpoints: ['/api/users', '/api/products'],
    customHeaders: { 'User-Agent': 'APE-Test-Agent' }
  };

  describe('generateDockerCompose', () => {
    it('should generate valid Docker Compose configuration', () => {
      const config = generateDockerCompose(mockConfig);
      
      expect(config.version).toBe('3.8');
      expect(config.services).toBeDefined();
      expect(config.networks).toBeDefined();
      expect(config.volumes).toBeDefined();
    });

    it('should include all required services', () => {
      const config = generateDockerCompose(mockConfig);
      
      const requiredServices = [
        'mcp_gateway',
        'cerebras_proxy', 
        'llama_agent',
        'prometheus',
        'grafana',
        'loki',
        'promtail',
        'cadvisor',
        'node_exporter'
      ];

      requiredServices.forEach(service => {
        expect(config.services[service]).toBeDefined();
      });
    });

    it('should configure agent scaling based on user input', () => {
      const config = generateDockerCompose(mockConfig);
      
      expect(config.services.llama_agent.deploy.replicas).toBe(mockConfig.agentCount);
      expect(config.services.llama_agent.environment.AGENT_GOAL).toBe(mockConfig.testGoal);
      expect(config.services.llama_agent.environment.TARGET_ENDPOINTS).toBe(mockConfig.endpoints.join(','));
    });

    it('should configure network with project-specific naming', () => {
      const config = generateDockerCompose(mockConfig);
      
      const networkName = `${mockConfig.projectName}_network`;
      expect(config.networks[networkName]).toBeDefined();
      expect(config.networks[networkName].name).toBe(`${mockConfig.projectName}_ape_network`);
    });

    it('should configure authentication when provided', () => {
      const configWithAuth: SetupAnswers = {
        ...mockConfig,
        authType: 'bearer',
        authToken: 'test-token-123'
      };

      const config = generateDockerCompose(configWithAuth);
      
      expect(config.services.llama_agent.environment.AUTH_TYPE).toBe('bearer');
      expect(config.services.llama_agent.environment.AUTH_TOKEN).toBe('test-token-123');
    });
  });

  describe('validateDockerComposeConfig', () => {
    it('should validate a correct configuration', () => {
      const config = generateDockerCompose(mockConfig);
      const validation = validateDockerComposeConfig(config);
      
      expect(validation.valid).toBe(true);
      expect(validation.errors).toHaveLength(0);
    });

    it('should detect missing required services', () => {
      const config = generateDockerCompose(mockConfig);
      delete config.services.mcp_gateway;
      
      const validation = validateDockerComposeConfig(config);
      
      expect(validation.valid).toBe(false);
      expect(validation.errors).toContain('Missing required service: mcp_gateway');
    });
  });

  describe('generateDockerComposeWithEnvironment', () => {
    it('should apply development configuration', () => {
      const config = generateDockerComposeWithEnvironment(mockConfig, 'development');
      
      // Check that debug logging is enabled
      expect(config.services.mcp_gateway.environment.LOG_LEVEL).toBe('debug');
    });

    it('should apply production configuration', () => {
      const config = generateDockerComposeWithEnvironment(mockConfig, 'production');
      
      // Check that production environment is set
      expect(config.services.mcp_gateway.environment.ENVIRONMENT).toBe('production');
      expect(config.services.mcp_gateway.security_opt).toContain('no-new-privileges:true');
    });
  });
});