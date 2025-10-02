import { SetupAnswers } from '../commands/setup';
import { ApplicationType, APPLICATION_TEMPLATES, validateApplicationConfig } from '../templates/application-types';
import { MCPGatewayConfig } from '../templates/mcp-gateway';
import * as fs from 'fs-extra';
import * as path from 'path';

export interface ConfigValidationResult {
  valid: boolean;
  errors: ConfigError[];
  warnings: ConfigWarning[];
  suggestions: ConfigSuggestion[];
}

export interface ConfigError {
  field: string;
  message: string;
  code: string;
  severity: 'error' | 'warning';
}

export interface ConfigWarning {
  field: string;
  message: string;
  code: string;
  suggestion?: string;
}

export interface ConfigSuggestion {
  field: string;
  message: string;
  suggestedValue?: any;
  reason: string;
}

// Comprehensive configuration validation - Requirements 8.4
export class ConfigValidator {
  private errors: ConfigError[] = [];
  private warnings: ConfigWarning[] = [];
  private suggestions: ConfigSuggestion[] = [];

  public validateSetupConfig(config: SetupAnswers, applicationType?: ApplicationType): ConfigValidationResult {
    this.reset();

    // Basic configuration validation
    this.validateBasicConfig(config);
    
    // Network and connectivity validation
    this.validateNetworkConfig(config);
    
    // Authentication validation
    this.validateAuthConfig(config);
    
    // Performance and scaling validation
    this.validatePerformanceConfig(config);
    
    // Application-specific validation
    if (applicationType) {
      this.validateApplicationSpecific(config, applicationType);
    }

    // Security validation
    this.validateSecurityConfig(config);

    return {
      valid: this.errors.length === 0,
      errors: this.errors,
      warnings: this.warnings,
      suggestions: this.suggestions
    };
  }

  public validateMCPGatewayConfig(config: MCPGatewayConfig): ConfigValidationResult {
    this.reset();

    // Validate gateway configuration
    this.validateGatewaySection(config.gateway);
    
    // Validate routes
    this.validateRoutesSection(config.routes);
    
    // Validate logging configuration
    this.validateLoggingSection(config.logging);

    return {
      valid: this.errors.length === 0,
      errors: this.errors,
      warnings: this.warnings,
      suggestions: this.suggestions
    };
  }

  public async validateProjectStructure(projectPath: string): Promise<ConfigValidationResult> {
    this.reset();

    const requiredFiles = [
      'ape.config.json',
      'ape.docker-compose.yml',
      'ape.mcp-gateway.json'
    ];

    const recommendedFiles = [
      '.env.template',
      'README.md',
      'config/prometheus.yml',
      'config/promtail.yml'
    ];

    // Check required files
    for (const file of requiredFiles) {
      const filePath = path.join(projectPath, file);
      if (!await fs.pathExists(filePath)) {
        this.addError('project_structure', `Required file missing: ${file}`, 'MISSING_REQUIRED_FILE');
      }
    }

    // Check recommended files
    for (const file of recommendedFiles) {
      const filePath = path.join(projectPath, file);
      if (!await fs.pathExists(filePath)) {
        this.addWarning('project_structure', `Recommended file missing: ${file}`, 'MISSING_RECOMMENDED_FILE', 
          `Consider creating ${file} for better project organization`);
      }
    }

    // Validate configuration file contents
    await this.validateConfigFileContents(projectPath);

    return {
      valid: this.errors.length === 0,
      errors: this.errors,
      warnings: this.warnings,
      suggestions: this.suggestions
    };
  }

  private reset(): void {
    this.errors = [];
    this.warnings = [];
    this.suggestions = [];
  }

  private validateBasicConfig(config: SetupAnswers): void {
    // Project name validation
    if (!config.projectName || config.projectName.trim().length === 0) {
      this.addError('projectName', 'Project name is required', 'REQUIRED_FIELD');
    } else if (!/^[a-zA-Z0-9-_]+$/.test(config.projectName)) {
      this.addError('projectName', 'Project name can only contain letters, numbers, hyphens, and underscores', 'INVALID_FORMAT');
    } else if (config.projectName.length > 50) {
      this.addWarning('projectName', 'Project name is very long', 'LENGTH_WARNING', 
        'Consider using a shorter name for better readability');
    }

    // Test goal validation
    if (!config.testGoal || config.testGoal.trim().length === 0) {
      this.addError('testGoal', 'Test goal description is required', 'REQUIRED_FIELD');
    } else if (config.testGoal.length < 10) {
      this.addWarning('testGoal', 'Test goal description is very short', 'LENGTH_WARNING',
        'Provide a more detailed description for better agent behavior');
    } else if (config.testGoal.length > 500) {
      this.addWarning('testGoal', 'Test goal description is very long', 'LENGTH_WARNING',
        'Consider shortening the description for better LLM processing');
    }

    // Endpoints validation
    if (!config.endpoints || config.endpoints.length === 0) {
      this.addWarning('endpoints', 'No endpoints specified', 'EMPTY_ENDPOINTS',
        'Default endpoints will be used based on application type');
    } else {
      config.endpoints.forEach((endpoint, index) => {
        if (!endpoint.startsWith('/')) {
          this.addError(`endpoints[${index}]`, `Endpoint '${endpoint}' must start with '/'`, 'INVALID_ENDPOINT_FORMAT');
        }
        if (endpoint.includes(' ')) {
          this.addError(`endpoints[${index}]`, `Endpoint '${endpoint}' cannot contain spaces`, 'INVALID_ENDPOINT_FORMAT');
        }
        if (endpoint.length > 200) {
          this.addWarning(`endpoints[${index}]`, `Endpoint '${endpoint}' is very long`, 'LENGTH_WARNING');
        }
      });

      // Check for duplicate endpoints
      const duplicates = config.endpoints.filter((endpoint, index) => 
        config.endpoints.indexOf(endpoint) !== index
      );
      if (duplicates.length > 0) {
        this.addWarning('endpoints', `Duplicate endpoints found: ${duplicates.join(', ')}`, 'DUPLICATE_ENDPOINTS');
      }
    }
  }

  private validateNetworkConfig(config: SetupAnswers): void {
    // Target URL validation
    try {
      const url = new URL(config.targetUrl);
      
      if (!['http:', 'https:'].includes(url.protocol)) {
        this.addError('targetUrl', 'Target URL must use HTTP or HTTPS protocol', 'INVALID_PROTOCOL');
      }

      // Security warnings
      if (url.protocol === 'http:' && url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
        this.addWarning('targetUrl', 'Using HTTP for non-localhost URLs is insecure', 'SECURITY_WARNING',
          'Consider using HTTPS for production applications');
      }

      // Accessibility warnings
      if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
        this.addWarning('targetUrl', 'Localhost URLs may not work in containerized environments', 'NETWORK_WARNING',
          'Consider using host.docker.internal or the actual IP address');
      }

      // Port validation
      if (url.port) {
        const port = parseInt(url.port);
        if (port < 1 || port > 65535) {
          this.addError('targetUrl', 'Port must be between 1 and 65535', 'INVALID_PORT');
        }
        if (port < 1024 && url.hostname !== 'localhost') {
          this.addWarning('targetUrl', 'Using privileged ports (< 1024) may require special permissions', 'PORT_WARNING');
        }
      }

    } catch (error) {
      this.addError('targetUrl', `Invalid URL format: ${config.targetUrl}`, 'INVALID_URL_FORMAT');
    }

    // Target port validation
    if (config.targetPort) {
      if (!Number.isInteger(config.targetPort) || config.targetPort < 1 || config.targetPort > 65535) {
        this.addError('targetPort', 'Port must be a valid integer between 1 and 65535', 'INVALID_PORT');
      }
    }
  }

  private validateAuthConfig(config: SetupAnswers): void {
    if (!config.authType || config.authType === 'none') {
      this.addSuggestion('authType', 'No authentication configured', undefined,
        'Consider adding authentication for more realistic load testing');
      return;
    }

    switch (config.authType) {
      case 'bearer':
        if (!config.authToken) {
          this.addError('authToken', 'Bearer token is required for bearer authentication', 'REQUIRED_AUTH_FIELD');
        } else {
          if (config.authToken.length < 10) {
            this.addWarning('authToken', 'Bearer token seems too short', 'TOKEN_LENGTH_WARNING',
              'Ensure the token is valid and complete');
          }
          if (config.authToken.includes(' ')) {
            this.addWarning('authToken', 'Bearer token contains spaces', 'TOKEN_FORMAT_WARNING',
              'Tokens typically should not contain spaces');
          }
        }
        break;

      case 'basic':
        if (!config.authUsername) {
          this.addError('authUsername', 'Username is required for basic authentication', 'REQUIRED_AUTH_FIELD');
        }
        if (!config.authPassword) {
          this.addError('authPassword', 'Password is required for basic authentication', 'REQUIRED_AUTH_FIELD');
        } else if (config.authPassword.length < 6) {
          this.addWarning('authPassword', 'Password is very short', 'PASSWORD_LENGTH_WARNING',
            'Consider using a stronger password');
        }
        break;

      case 'session':
        this.addSuggestion('authType', 'Session authentication requires login flow', undefined,
          'Ensure your test goal includes login/logout steps for proper session management');
        break;

      default:
        this.addError('authType', `Unknown authentication type: ${config.authType}`, 'INVALID_AUTH_TYPE');
    }
  }

  private validatePerformanceConfig(config: SetupAnswers): void {
    // Agent count validation
    if (!Number.isInteger(config.agentCount) || config.agentCount < 1) {
      this.addError('agentCount', 'Agent count must be a positive integer', 'INVALID_AGENT_COUNT');
    } else {
      if (config.agentCount > 1000) {
        this.addWarning('agentCount', 'Very high agent count may require significant resources', 'PERFORMANCE_WARNING',
          'Ensure your system has sufficient CPU and memory');
      } else if (config.agentCount > 500) {
        this.addSuggestion('agentCount', 'High agent count detected', undefined,
          'Consider starting with fewer agents and scaling up gradually');
      }

      if (config.agentCount === 1) {
        this.addSuggestion('agentCount', 'Single agent may not provide meaningful load testing', 2,
          'Consider using at least 2-5 agents for basic load testing');
      }
    }

    // Test duration validation
    if (!Number.isInteger(config.testDuration) || config.testDuration < 1) {
      this.addError('testDuration', 'Test duration must be at least 1 minute', 'INVALID_DURATION');
    } else {
      if (config.testDuration > 1440) {
        this.addError('testDuration', 'Test duration cannot exceed 24 hours (1440 minutes)', 'DURATION_TOO_LONG');
      } else if (config.testDuration > 60) {
        this.addWarning('testDuration', 'Long test duration may consume significant resources', 'DURATION_WARNING',
          'Monitor resource usage during extended tests');
      }

      if (config.testDuration < 5) {
        this.addSuggestion('testDuration', 'Very short test duration', 5,
          'Consider running tests for at least 5 minutes for meaningful results');
      }
    }

    // Performance optimization suggestions
    if (config.agentCount > 100 && config.testDuration > 30) {
      this.addSuggestion('performance', 'High-scale, long-duration test detected', undefined,
        'Consider using production-optimized Docker Compose configuration');
    }
  }

  private validateApplicationSpecific(config: SetupAnswers, applicationType: ApplicationType): void {
    const appValidation = validateApplicationConfig(config, applicationType);
    
    // Convert application validation results to our format
    appValidation.errors.forEach(error => {
      this.addError('application', error, 'APPLICATION_VALIDATION_ERROR');
    });

    appValidation.warnings.forEach(warning => {
      this.addWarning('application', warning, 'APPLICATION_VALIDATION_WARNING');
    });

    // Application-specific suggestions
    const template = APPLICATION_TEMPLATES[applicationType];
    if (template) {
      // Suggest missing default endpoints
      const missingEndpoints = template.defaultEndpoints.filter(
        endpoint => !config.endpoints.includes(endpoint)
      );
      if (missingEndpoints.length > 0) {
        this.addSuggestion('endpoints', 
          `Consider adding common ${template.name} endpoints`, 
          missingEndpoints,
          'These endpoints are commonly used in this application type');
      }

      // Suggest appropriate authentication
      if (config.authType === 'none' && template.authTypes.length > 1) {
        this.addSuggestion('authType',
          `${template.name} typically uses authentication`,
          template.authTypes.filter(auth => auth !== 'none')[0],
          'Authentication provides more realistic load testing scenarios');
      }
    }
  }

  private validateSecurityConfig(config: SetupAnswers): void {
    // Check for potential security issues
    if (config.authType === 'basic' && config.targetUrl.startsWith('http:')) {
      this.addWarning('security', 'Basic authentication over HTTP is insecure', 'SECURITY_WARNING',
        'Credentials will be transmitted in plain text');
    }

    // Check for hardcoded credentials in project name or goal
    const sensitivePatterns = [
      /password/i, /secret/i, /key/i, /token/i, /credential/i
    ];

    sensitivePatterns.forEach(pattern => {
      if (pattern.test(config.projectName)) {
        this.addWarning('projectName', 'Project name may contain sensitive information', 'SECURITY_WARNING',
          'Avoid including credentials or sensitive data in project names');
      }
      if (pattern.test(config.testGoal)) {
        this.addWarning('testGoal', 'Test goal may contain sensitive information', 'SECURITY_WARNING',
          'Avoid including credentials or sensitive data in descriptions');
      }
    });

    // Custom headers security check
    if (config.customHeaders) {
      Object.keys(config.customHeaders).forEach(header => {
        if (header.toLowerCase().includes('authorization') || header.toLowerCase().includes('token')) {
          this.addWarning('customHeaders', `Custom header '${header}' may contain sensitive data`, 'SECURITY_WARNING',
            'Ensure sensitive headers are properly secured');
        }
      });
    }
  }

  private validateGatewaySection(gateway: any): void {
    if (!gateway.name) {
      this.addError('gateway.name', 'Gateway name is required', 'REQUIRED_FIELD');
    }

    if (!gateway.port || !Number.isInteger(gateway.port)) {
      this.addError('gateway.port', 'Gateway port must be a valid integer', 'INVALID_PORT');
    } else if (gateway.port < 1024 || gateway.port > 65535) {
      this.addWarning('gateway.port', 'Gateway port should be between 1024 and 65535', 'PORT_WARNING');
    }

    if (gateway.rateLimit && gateway.rateLimit.enabled) {
      if (!gateway.rateLimit.max || gateway.rateLimit.max < 1) {
        this.addError('gateway.rateLimit.max', 'Rate limit max must be a positive integer', 'INVALID_RATE_LIMIT');
      }
    }
  }

  private validateRoutesSection(routes: any): void {
    if (!routes || Object.keys(routes).length === 0) {
      this.addError('routes', 'At least one route must be configured', 'MISSING_ROUTES');
      return;
    }

    Object.entries(routes).forEach(([routeName, route]: [string, any]) => {
      if (!route.baseUrl) {
        this.addError(`routes.${routeName}.baseUrl`, 'Route base URL is required', 'REQUIRED_FIELD');
      } else {
        try {
          new URL(route.baseUrl);
        } catch {
          this.addError(`routes.${routeName}.baseUrl`, 'Invalid base URL format', 'INVALID_URL_FORMAT');
        }
      }

      if (!route.endpoints || route.endpoints.length === 0) {
        this.addWarning(`routes.${routeName}.endpoints`, 'No endpoints configured for route', 'MISSING_ENDPOINTS');
      }

      if (route.timeout && (route.timeout < 1000 || route.timeout > 300000)) {
        this.addWarning(`routes.${routeName}.timeout`, 'Timeout should be between 1 and 300 seconds', 'TIMEOUT_WARNING');
      }
    });
  }

  private validateLoggingSection(logging: any): void {
    const validLogLevels = ['error', 'warn', 'info', 'debug', 'trace'];
    if (logging.level && !validLogLevels.includes(logging.level)) {
      this.addError('logging.level', `Invalid log level. Must be one of: ${validLogLevels.join(', ')}`, 'INVALID_LOG_LEVEL');
    }

    const validFormats = ['json', 'text', 'simple'];
    if (logging.format && !validFormats.includes(logging.format)) {
      this.addWarning('logging.format', `Recommended log formats: ${validFormats.join(', ')}`, 'LOG_FORMAT_WARNING');
    }
  }

  private async validateConfigFileContents(projectPath: string): Promise<void> {
    try {
      // Validate ape.config.json
      const configPath = path.join(projectPath, 'ape.config.json');
      if (await fs.pathExists(configPath)) {
        const configContent = await fs.readJSON(configPath);
        if (!configContent.project || !configContent.target) {
          this.addError('ape.config.json', 'Invalid configuration file structure', 'INVALID_CONFIG_STRUCTURE');
        }
      }

      // Validate MCP Gateway config
      const mcpConfigPath = path.join(projectPath, 'ape.mcp-gateway.json');
      if (await fs.pathExists(mcpConfigPath)) {
        const mcpConfig = await fs.readJSON(mcpConfigPath);
        const mcpValidation = this.validateMCPGatewayConfig(mcpConfig);
        // Merge MCP validation results
        this.errors.push(...mcpValidation.errors);
        this.warnings.push(...mcpValidation.warnings);
      }

    } catch (error) {
      this.addError('config_files', `Error reading configuration files: ${error instanceof Error ? error.message : 'Unknown error'}`, 'CONFIG_READ_ERROR');
    }
  }

  private addError(field: string, message: string, code: string): void {
    this.errors.push({ field, message, code, severity: 'error' });
  }

  private addWarning(field: string, message: string, code: string, suggestion?: string): void {
    this.warnings.push({ field, message, code, suggestion });
  }

  private addSuggestion(field: string, message: string, suggestedValue: any, reason: string): void {
    this.suggestions.push({ field, message, suggestedValue, reason });
  }
}

// Utility functions for validation
export function validateConfiguration(config: SetupAnswers, applicationType?: ApplicationType): ConfigValidationResult {
  const validator = new ConfigValidator();
  return validator.validateSetupConfig(config, applicationType);
}

export function validateMCPConfiguration(config: MCPGatewayConfig): ConfigValidationResult {
  const validator = new ConfigValidator();
  return validator.validateMCPGatewayConfig(config);
}

export async function validateProjectStructure(projectPath: string): Promise<ConfigValidationResult> {
  const validator = new ConfigValidator();
  return validator.validateProjectStructure(projectPath);
}

// Helper function to format validation results for display
export function formatValidationResults(result: ConfigValidationResult): string {
  const lines: string[] = [];

  if (result.valid) {
    lines.push('✅ Configuration validation passed');
  } else {
    lines.push('❌ Configuration validation failed');
  }

  if (result.errors.length > 0) {
    lines.push('\n🚨 Errors:');
    result.errors.forEach(error => {
      lines.push(`  • ${error.field}: ${error.message} (${error.code})`);
    });
  }

  if (result.warnings.length > 0) {
    lines.push('\n⚠️  Warnings:');
    result.warnings.forEach(warning => {
      lines.push(`  • ${warning.field}: ${warning.message}`);
      if (warning.suggestion) {
        lines.push(`    💡 ${warning.suggestion}`);
      }
    });
  }

  if (result.suggestions.length > 0) {
    lines.push('\n💡 Suggestions:');
    result.suggestions.forEach(suggestion => {
      lines.push(`  • ${suggestion.field}: ${suggestion.message}`);
      lines.push(`    Reason: ${suggestion.reason}`);
      if (suggestion.suggestedValue !== undefined) {
        lines.push(`    Suggested: ${JSON.stringify(suggestion.suggestedValue)}`);
      }
    });
  }

  return lines.join('\n');
}