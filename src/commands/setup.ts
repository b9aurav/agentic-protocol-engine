import chalk from 'chalk';
import inquirer from 'inquirer';
import ora from 'ora';
import * as fs from 'fs-extra';
import * as path from 'path';
import * as yaml from 'yaml';
import { generateDockerCompose, generatePrometheusConfig, generatePromtailConfig } from '../templates/docker-compose';
import { generateProductionOverride, generateProductionEnv } from '../templates/docker-compose.production';
import { generateMCPGatewayConfig } from '../templates/mcp-gateway';
import {
  ApplicationType,
  APPLICATION_TEMPLATES,
  generateApplicationSpecificConfig,
  generateApplicationDockerOverride
} from '../templates/application-types';
import { APISpecParser, ParsedAPISpec, ParsedEndpoint, APISpecParsingError, validateAPISpecFile } from '../utils/api-spec-parser';
import { displayError, getRecommendedAction, isTemporaryError, isConfigurationError } from '../utils/error-handler';

/**
 * Transform localhost URLs for Docker environments
 */
function transformUrlForDocker(url: string): string {
  try {
    const urlObj = new URL(url);
    if (urlObj.hostname === 'localhost' || urlObj.hostname === '127.0.0.1') {
      // For Docker Desktop on Windows/Mac, use host.docker.internal
      // For Linux, this would need to be the host IP or --network host
      urlObj.hostname = 'host.docker.internal';
      const transformedUrl = urlObj.toString();
      console.log(chalk.yellow(`ℹ️  Transformed ${url} to ${transformedUrl} for Docker compatibility`));
      return transformedUrl;
    }
    return url;
  } catch (error) {
    // If URL parsing fails, return original
    return url;
  }
}


interface SetupOptions {
  template: string;
  yes?: boolean;
  output: string;
  applicationType?: ApplicationType;
  validate?: boolean;
}

export interface SetupAnswers {
  projectName: string;
  targetUrl: string;
  targetPort: number;
  cerebrasApiKey: string;
  agentCount: number;
  testDuration: number;
  testGoal: string;
  endpoints: string[];
  applicationType: ApplicationType;
  apiSpecFile?: string;
  parsedApiSpec?: ParsedAPISpec;
}

export async function setupWizard(projectName?: string, options?: SetupOptions): Promise<void> {
  console.log(chalk.blue('🤖 Welcome to APE Setup Wizard!'));
  console.log(chalk.gray('This wizard will help you configure your AI-driven load test.\n'));



  try {
    let answers: SetupAnswers;

    if (options?.yes) {
      // Use defaults when --yes flag is provided
      const cerebrasApiKey = process.env.CEREBRAS_API_KEY;
      if (!cerebrasApiKey) {
        console.error(chalk.red('❌ CEREBRAS_API_KEY environment variable is required when using --yes flag'));
        console.log(chalk.yellow('Set it with: export CEREBRAS_API_KEY=your_api_key_here'));
        process.exit(1);
      }

      answers = {
        projectName: projectName || 'my-ape-load',
        targetUrl: 'http://localhost:3001',
        targetPort: 8080,
        cerebrasApiKey,
        agentCount: 10,
        testDuration: 5,
        testGoal: 'Simulate realistic user browsing and interaction patterns',
        endpoints: ['/api/health', '/api/users'],
        applicationType: 'rest-api'
      };
    } else {
      // Interactive prompts - Requirements 5.1, 5.2
      const selectedTemplate = APPLICATION_TEMPLATES['rest-api'];

      const basicAnswers = await inquirer.prompt([
        {
          type: 'input',
          name: 'projectName',
          message: 'Project name:',
          default: projectName || 'my-ape-load',
          validate: (input: string) => {
            if (input.length === 0) return 'Project name is required';
            if (!/^[a-zA-Z0-9-_]+$/.test(input)) return 'Project name can only contain letters, numbers, hyphens, and underscores';
            return true;
          }
        },
        {
          type: 'input',
          name: 'targetUrl',
          message: 'Target application URL:',
          default: 'http://localhost:3001',
          validate: (input: string) => {
            try {
              const url = new URL(input);
              if (!['http:', 'https:'].includes(url.protocol)) {
                return 'URL must use http or https protocol';
              }
              return true;
            } catch {
              return 'Please enter a valid URL (e.g., http://localhost:8080)';
            }
          }
        },
        {
          type: 'number',
          name: 'targetPort',
          message: 'Target application port:',
          default: (answers: any) => {
            try {
              const url = new URL(answers.targetUrl);
              return url.port ? parseInt(url.port) : (url.protocol === 'https:' ? 443 : 80);
            } catch {
              return 8080;
            }
          },
          validate: (input: number) => {
            if (!Number.isInteger(input) || input <= 0 || input > 65535) {
              return 'Port must be a valid integer between 1 and 65535';
            }
            return true;
          }
        }
      ]);



      // Cerebras API key prompt
      const cerebrasAnswers = await inquirer.prompt([
        {
          type: 'password',
          name: 'cerebrasApiKey',
          message: 'Cerebras API key (required for AI agents):',
          validate: (input: string) => {
            if (input.length === 0) return 'Cerebras API key is required';
            if (input.length < 10) return 'Please enter a valid Cerebras API key';
            return true;
          },
          mask: '*'
        }
      ]);

      // API specification parsing step
      let apiSpecAnswers: { apiSpecFile?: string; parsedApiSpec?: ParsedAPISpec } = {};

      const useApiSpecAnswer = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'useApiSpec',
          message: 'Do you have an API specification file to parse for endpoint configuration?',
          default: false
        }
      ]);

      if (useApiSpecAnswer.useApiSpec) {
        const apiSpecFileAnswer = await inquirer.prompt([
          {
            type: 'input',
            name: 'apiSpecFile',
            message: 'Path to API specification file (markdown format):',
            validate: async (input: string) => {
              if (input.length === 0) return 'File path is required';

              try {
                // Use the enhanced validation function
                await validateAPISpecFile(input);
                return true;
              } catch (error: any) {
                if (error.name === 'APISpecParsingError') {
                  // Return user-friendly error message
                  let message = error.message;
                  if (error.suggestion) {
                    message += ` (${error.suggestion})`;
                  }
                  return message;
                } else {
                  return `Cannot access file: ${error.message}`;
                }
              }
            }
          }
        ]);

        if (apiSpecFileAnswer.apiSpecFile) {
          const parseSpinner = ora('Parsing API specification with Cerebras LLM...').start();

          try {
            const parser = new APISpecParser({ apiKey: cerebrasAnswers.cerebrasApiKey });
            const parsedSpec = await parser.parseSpecification(apiSpecFileAnswer.apiSpecFile);

            parseSpinner.succeed(`Successfully parsed API specification: ${parsedSpec.endpoints.length} endpoints found`);

            // Show summary of parsed endpoints
            console.log(chalk.blue('\n📋 Parsed Endpoints:'));
            parsedSpec.endpoints.forEach((endpoint, index) => {
              console.log(chalk.gray(`   ${index + 1}. ${endpoint.method} ${endpoint.path} - ${endpoint.purpose}`));
            });

            if (parsedSpec.commonPatterns?.sessionManagement) {
              console.log(chalk.yellow('   ⚠️  Session management detected - agents will handle authentication'));
            }

            if (parsedSpec.commonPatterns?.pagination) {
              console.log(chalk.blue('   📄 Pagination support detected'));
            }

            apiSpecAnswers = {
              apiSpecFile: apiSpecFileAnswer.apiSpecFile,
              parsedApiSpec: parsedSpec
            };

          } catch (error: any) {
            // Enhanced error handling with comprehensive error reporting
            const apiError = error instanceof APISpecParsingError ? error : 
              new APISpecParsingError(
                `Unexpected error: ${error.message}`,
                'UNEXPECTED_ERROR',
                { suggestion: 'Please try again or continue with manual configuration' }
              );

            parseSpinner.fail('Failed to parse API specification');
            
            // Display comprehensive error information
            displayError(apiError);

            // Determine the best course of action
            const recommendedAction = getRecommendedAction(apiError);
            
            let fallbackChoice: any = { fallbackAction: 'manual' }; // Default fallback

            if (recommendedAction === 'retry' && isTemporaryError(apiError)) {
              // For temporary errors, offer retry option
              fallbackChoice = await inquirer.prompt([
                {
                  type: 'list',
                  name: 'fallbackAction',
                  message: 'This appears to be a temporary issue. How would you like to proceed?',
                  choices: [
                    { name: 'Retry parsing the specification', value: 'retry' },
                    { name: 'Continue with manual configuration', value: 'manual' },
                    { name: 'Exit and fix the issue', value: 'exit' }
                  ],
                  default: 'retry'
                }
              ]);

              if (fallbackChoice.fallbackAction === 'retry') {
                console.log(chalk.blue('Retrying API specification parsing...'));
                // Recursive retry (with same parameters)
                try {
                  const parser = new APISpecParser({ apiKey: cerebrasAnswers.cerebrasApiKey });
                  const parsedSpec = await parser.parseSpecification(apiSpecFileAnswer.apiSpecFile);
                  
                  console.log(chalk.green(`✅ Successfully parsed API specification on retry: ${parsedSpec.endpoints.length} endpoints found`));
                  
                  apiSpecAnswers = {
                    apiSpecFile: apiSpecFileAnswer.apiSpecFile,
                    parsedApiSpec: parsedSpec
                  };
                  
                  // Skip the rest of error handling since retry succeeded
                  return;
                } catch (retryError) {
                  console.log(chalk.red('Retry failed. Continuing with manual configuration...'));
                }
              }
            } else if (recommendedAction === 'fix_config' && isConfigurationError(apiError)) {
              // For configuration errors, suggest fixing and restarting
              fallbackChoice = await inquirer.prompt([
                {
                  type: 'list',
                  name: 'fallbackAction',
                  message: 'This appears to be a configuration issue. How would you like to proceed?',
                  choices: [
                    { name: 'Exit and fix the configuration', value: 'exit' },
                    { name: 'Continue with manual configuration', value: 'manual' }
                  ],
                  default: 'exit'
                }
              ]);
            } else if (apiError.isRecoverable) {
              // For recoverable errors, offer standard options
              fallbackChoice = await inquirer.prompt([
                {
                  type: 'list',
                  name: 'fallbackAction',
                  message: 'How would you like to proceed?',
                  choices: [
                    { name: 'Continue with manual configuration', value: 'manual' },
                    { name: 'Exit and fix the issue', value: 'exit' }
                  ],
                  default: 'manual'
                }
              ]);
            }

            // Handle the chosen action
            if (fallbackChoice.fallbackAction === 'exit') {
              console.log(chalk.blue('Setup cancelled. Please fix the issue and run the setup again.'));
              process.exit(0);
            }

            console.log(chalk.yellow('Continuing with manual endpoint configuration...'));

            // Store the file path even if parsing failed (for potential retry)
            apiSpecAnswers = {
              apiSpecFile: apiSpecFileAnswer.apiSpecFile
            };
          }
        }
      }

      // Test parameters prompts
      const testAnswers = await inquirer.prompt([
        {
          type: 'number',
          name: 'agentCount',
          message: 'Number of concurrent agents:',
          default: 10,
          validate: (input: number) => {
            if (!Number.isInteger(input) || input <= 0 || input > 1000) {
              return 'Agent count must be between 1 and 1000';
            }
            return true;
          }
        },
        {
          type: 'number',
          name: 'testDuration',
          message: 'Test duration (minutes):',
          default: 5,
          validate: (input: number) => {
            if (!Number.isInteger(input) || input <= 0) {
              return 'Duration must be a positive integer';
            }
            if (input > 1440) {
              return 'Duration cannot exceed 24 hours (1440 minutes)';
            }
            return true;
          }
        },
        {
          type: 'input',
          name: 'testGoal',
          message: 'Agent goal description (what should agents accomplish):',
          default: 'Simulate realistic user browsing and interaction patterns',
          validate: (input: string) => {
            if (input.length === 0) return 'Goal description is required';
            if (input.length < 10) return 'Please provide a more detailed goal description (at least 10 characters)';
            return true;
          }
        }
      ]);

      // API endpoints configuration - use parsed data if available
      let endpointAnswers: { endpoints: string[] };

      if (apiSpecAnswers.parsedApiSpec) {
        // Use parsed endpoints
        const parsedEndpoints = apiSpecAnswers.parsedApiSpec.endpoints.map(e => e.path);

        const confirmEndpointsAnswer = await inquirer.prompt([
          {
            type: 'confirm',
            name: 'useParsedEndpoints',
            message: `Use all ${parsedEndpoints.length} parsed endpoints for testing?`,
            default: true
          }
        ]);

        if (confirmEndpointsAnswer.useParsedEndpoints) {
          endpointAnswers = { endpoints: parsedEndpoints };
        } else {
          // Allow manual selection of parsed endpoints
          const selectedEndpointsAnswer = await inquirer.prompt([
            {
              type: 'checkbox',
              name: 'endpoints',
              message: 'Select endpoints to test:',
              choices: apiSpecAnswers.parsedApiSpec.endpoints.map(endpoint => ({
                name: `${endpoint.method} ${endpoint.path} - ${endpoint.purpose}`,
                value: endpoint.path,
                checked: true
              })),
              validate: (input: string[]) => {
                if (input.length === 0) return 'At least one endpoint must be selected';
                return true;
              }
            }
          ]);

          endpointAnswers = selectedEndpointsAnswer;
        }
      } else {
        // Manual endpoint configuration (existing behavior)
        endpointAnswers = await inquirer.prompt([
          {
            type: 'input',
            name: 'endpoints',
            message: `API endpoints to test (comma-separated, defaults available for ${selectedTemplate.name}):`,
            default: selectedTemplate.defaultEndpoints.join(','),
            validate: (input: string | string[]) => {
              let endpoints: string[];
              if (Array.isArray(input)) {
                endpoints = input;
              } else {
                if (input.length === 0) return 'At least one endpoint is required';
                endpoints = input.split(',').map(e => e.trim());
              }

              if (endpoints.length === 0) return 'At least one endpoint is required';

              for (const endpoint of endpoints) {
                if (!endpoint.startsWith('/')) {
                  return `Endpoint "${endpoint}" must start with /`;
                }
              }
              return true;
            },
            filter: (input: string | string[]) => {
              if (Array.isArray(input)) return input;
              return input.split(',').map(e => e.trim()).filter(e => e.length > 0);
            }
          }
        ]);
      }



      answers = {
        ...basicAnswers,
        ...cerebrasAnswers,
        ...apiSpecAnswers,
        ...testAnswers,
        ...endpointAnswers,
        applicationType: 'rest-api'
      };
    }



    const spinner = ora('Generating configuration files...').start();

    // Create project directory
    const projectPath = path.join(options?.output || '.', answers.projectName);
    await fs.ensureDir(projectPath);

    // Generate configuration files - Requirements 5.4
    await generateConfigFiles(projectPath, answers);

    spinner.succeed('Configuration files generated successfully!');

    console.log(chalk.green('\n✅ APE test environment created!'));
    console.log(chalk.blue(`📁 Project directory: ${projectPath}`));
    console.log(chalk.yellow('\n🚀 Next steps:'));
    console.log(chalk.yellow(`   cd ${answers.projectName}`));
    console.log(chalk.yellow('   ape-load start'));
    console.log(chalk.gray('\n💡 Use "ape-load --help" for more commands'));

  } catch (error) {
    console.error(chalk.red(`Setup failed: ${error instanceof Error ? error.message : 'Unknown error'}`));
    process.exit(1);
  }
}

/**
 * Generate enhanced MCP Gateway configuration using parsed API specification data
 */
function generateEnhancedMCPGatewayConfig(config: SetupAnswers): any {
  const baseConfig = generateMCPGatewayConfig(config);

  // If we have parsed API specification data, enhance the configuration
  if (config.parsedApiSpec) {
    // Enhance the SUT API route with parsed endpoint data
    if (baseConfig.routes.sut_api) {
      const enhancedEndpoints = config.parsedApiSpec.endpoints.map(endpoint => {
        const endpointConfig: any = {
          path: endpoint.path,
          methods: [endpoint.method.toUpperCase()],
          description: endpoint.purpose
        };

        // Add rate limiting based on endpoint type and complexity
        if (endpoint.method.toUpperCase() === 'GET') {
          endpointConfig.rateLimit = {
            windowMs: 60000,
            max: endpoint.sessionRequired ? 150 : 200 // Lower limit for session-based endpoints
          };
        } else if (['POST', 'PUT', 'PATCH'].includes(endpoint.method.toUpperCase())) {
          endpointConfig.rateLimit = {
            windowMs: 60000,
            max: endpoint.sessionRequired ? 30 : 50 // Much lower for write operations with sessions
          };
        } else {
          endpointConfig.rateLimit = {
            windowMs: 60000,
            max: 100 // Default for other methods
          };
        }

        // Add comprehensive metadata for enhanced processing
        endpointConfig.metadata = {
          parameters: endpoint.parameters,
          responses: endpoint.responses,
          sessionRequired: endpoint.sessionRequired,
          sampleData: generateSampleRequestData(endpoint),
          requiredFields: extractRequiredFields(endpoint.parameters),
          optionalFields: extractOptionalFields(endpoint.parameters),
          // Add request validation rules
          validation: generateValidationRules(endpoint),
          // Add response handling patterns
          responseHandling: generateResponseHandling(endpoint)
        };

        return endpointConfig;
      });

      // Replace the endpoints in the SUT API route
      baseConfig.routes.sut_api.endpoints = enhancedEndpoints;

      // Add enhanced metadata to the route description
      let enhancedDescription = baseConfig.routes.sut_api.description;

      if (config.parsedApiSpec.commonPatterns?.sessionManagement) {
        enhancedDescription += ' (Session management enabled)';
        // Add session handling configuration
        baseConfig.routes.sut_api.sessionHandling = {
          enabled: true,
          cookieSupport: true,
          headerSupport: true,
          tokenRefresh: true
        };
      }

      if (config.parsedApiSpec.commonPatterns?.pagination) {
        enhancedDescription += ' (Pagination supported)';
        // Add pagination handling configuration
        baseConfig.routes.sut_api.paginationHandling = {
          enabled: true,
          defaultPageSize: 20,
          maxPageSize: 100,
          pageParam: 'page',
          sizeParam: 'size'
        };
      }

      baseConfig.routes.sut_api.description = enhancedDescription;

      // Add data models to the route configuration for reference
      if (config.parsedApiSpec.dataModels) {
        baseConfig.routes.sut_api.dataModels = config.parsedApiSpec.dataModels;
      }

      // Add common error handling patterns
      if (config.parsedApiSpec.commonPatterns?.errorHandling) {
        baseConfig.routes.sut_api.errorHandling = {
          patterns: config.parsedApiSpec.commonPatterns.errorHandling,
          retryableErrors: [429, 502, 503, 504],
          nonRetryableErrors: [400, 401, 403, 404, 422]
        };
      }
    }
  }

  return baseConfig;
}

/**
 * Generate sample request data based on parsed endpoint parameters
 */
function generateSampleRequestData(endpoint: ParsedEndpoint): Record<string, any> {
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
function extractRequiredFields(parameters: ParsedEndpoint['parameters']): string[] {
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
function extractOptionalFields(parameters: ParsedEndpoint['parameters']): string[] {
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
 * Generate sample values based on field name and description
 */
function generateSampleValue(fieldName: string, description: string): any {
  const lowerDesc = description.toLowerCase();
  const lowerField = fieldName.toLowerCase();

  // Type-based generation
  if (lowerDesc.includes('string') || lowerDesc.includes('text')) {
    if (lowerField.includes('email')) return 'user@example.com';
    if (lowerField.includes('name')) return 'Sample Name';
    if (lowerField.includes('id')) return 'sample-id-123';
    if (lowerField.includes('password')) return 'SecurePass123!';
    if (lowerField.includes('token')) return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
    return 'sample text';
  }

  if (lowerDesc.includes('number') || lowerDesc.includes('integer')) {
    if (lowerField.includes('price') || lowerField.includes('cost')) return 29.99;
    if (lowerField.includes('count') || lowerField.includes('quantity')) return 5;
    if (lowerField.includes('age')) return 25;
    if (lowerField.includes('year')) return new Date().getFullYear();
    return 42;
  }

  if (lowerDesc.includes('boolean')) {
    return true;
  }

  if (lowerDesc.includes('array')) {
    if (lowerField.includes('tags')) return ['tag1', 'tag2', 'tag3'];
    if (lowerField.includes('categories')) return ['category1', 'category2'];
    return ['sample', 'array', 'values'];
  }

  if (lowerDesc.includes('object')) {
    if (lowerField.includes('address')) {
      return {
        street: '123 Main St',
        city: 'Anytown',
        state: 'CA',
        zipCode: '12345'
      };
    }
    return { key: 'value' };
  }

  // Field name-based generation
  if (lowerField.includes('email')) return 'user@example.com';
  if (lowerField.includes('phone')) return '+1-555-0123';
  if (lowerField.includes('date')) return new Date().toISOString().split('T')[0];
  if (lowerField.includes('time')) return new Date().toISOString();
  if (lowerField.includes('url')) return 'https://example.com';
  if (lowerField.includes('uuid')) return '550e8400-e29b-41d4-a716-446655440000';
  if (lowerField.includes('status')) return 'active';

  return 'sample value';
}

/**
 * Generate validation rules based on endpoint parameters
 */
function generateValidationRules(endpoint: ParsedEndpoint): Record<string, any> {
  const rules: Record<string, any> = {};

  if (endpoint.parameters?.body) {
    Object.entries(endpoint.parameters.body).forEach(([key, description]) => {
      const rule: any = {};
      const lowerDesc = (description as string).toLowerCase();

      // Required/optional validation
      if (lowerDesc.includes('required')) {
        rule.required = true;
      }

      // Type validation
      if (lowerDesc.includes('string')) {
        rule.type = 'string';
        if (lowerDesc.includes('email')) rule.format = 'email';
        if (lowerDesc.includes('url')) rule.format = 'url';
        if (lowerDesc.includes('uuid')) rule.format = 'uuid';
      } else if (lowerDesc.includes('number') || lowerDesc.includes('integer')) {
        rule.type = 'number';
        if (lowerDesc.includes('positive')) rule.minimum = 0;
      } else if (lowerDesc.includes('boolean')) {
        rule.type = 'boolean';
      } else if (lowerDesc.includes('array')) {
        rule.type = 'array';
      }

      // Length constraints
      const minMatch = lowerDesc.match(/min(?:imum)?\s*(?:length\s*)?(\d+)/);
      const maxMatch = lowerDesc.match(/max(?:imum)?\s*(?:length\s*)?(\d+)/);
      if (minMatch) rule.minLength = parseInt(minMatch[1]);
      if (maxMatch) rule.maxLength = parseInt(maxMatch[1]);

      rules[key] = rule;
    });
  }

  return rules;
}

/**
 * Generate response handling patterns based on endpoint responses
 */
function generateResponseHandling(endpoint: ParsedEndpoint): Record<string, any> {
  const handling: Record<string, any> = {
    success: {
      expectedStatus: [200, 201, 202, 204],
      schema: endpoint.responses.success
    }
  };

  if (endpoint.responses.error && endpoint.responses.error.length > 0) {
    handling.error = endpoint.responses.error.map(error => ({
      status: error.code || 400,
      schema: error.example || error,
      retryable: [429, 502, 503, 504].includes(error.code || 400),
      handling: getErrorHandlingStrategy(error.code || 400)
    }));
  }

  // Add method-specific handling
  if (endpoint.method.toUpperCase() === 'POST') {
    handling.success.expectedStatus = [200, 201];
    handling.created = {
      status: 201,
      extractId: true, // Extract created resource ID from response
      followUp: endpoint.path.includes('login') ? 'session' : 'none'
    };
  } else if (endpoint.method.toUpperCase() === 'PUT') {
    handling.success.expectedStatus = [200, 204];
  } else if (endpoint.method.toUpperCase() === 'DELETE') {
    handling.success.expectedStatus = [200, 204];
    handling.deleted = {
      status: [200, 204],
      confirmDeletion: true
    };
  }

  return handling;
}

/**
 * Get error handling strategy based on status code
 */
function getErrorHandlingStrategy(statusCode: number): string {
  switch (statusCode) {
    case 400: return 'validate_request';
    case 401: return 'refresh_auth';
    case 403: return 'check_permissions';
    case 404: return 'resource_not_found';
    case 409: return 'handle_conflict';
    case 422: return 'validation_error';
    case 429: return 'rate_limit_backoff';
    case 500: return 'server_error_retry';
    case 502:
    case 503:
    case 504: return 'service_unavailable_retry';
    default: return 'generic_error';
  }
}

/**
 * Generate agent behavior configuration for an endpoint
 */
function generateAgentBehaviorConfig(endpoint: ParsedEndpoint): Record<string, any> {
  const behavior: Record<string, any> = {
    priority: getEndpointPriority(endpoint),
    frequency: getEndpointFrequency(endpoint),
    dependencies: getEndpointDependencies(endpoint),
    dataVariation: getDataVariationStrategy(endpoint)
  };

  // Add method-specific behaviors
  if (endpoint.method.toUpperCase() === 'GET') {
    behavior.caching = {
      enabled: true,
      ttl: 300, // 5 minutes
      varyByParams: true
    };
  } else if (['POST', 'PUT', 'PATCH'].includes(endpoint.method.toUpperCase())) {
    behavior.validation = {
      preValidate: true,
      postValidate: true,
      rollbackOnError: true
    };
  }

  // Add session-specific behaviors
  if (endpoint.sessionRequired) {
    behavior.session = {
      required: true,
      refreshOnExpiry: true,
      shareAcrossRequests: true
    };
  }

  return behavior;
}

/**
 * Generate test scenarios for an endpoint
 */
function generateTestScenarios(endpoint: ParsedEndpoint): Array<Record<string, any>> {
  const scenarios: Array<Record<string, any>> = [];

  // Happy path scenario
  scenarios.push({
    name: 'happy_path',
    description: `Successful ${endpoint.method} request to ${endpoint.path}`,
    weight: 70, // 70% of requests
    requestData: generateSampleRequestData(endpoint),
    expectedStatus: getSuccessStatusCodes(endpoint.method),
    followUp: getFollowUpActions(endpoint)
  });

  // Edge case scenarios
  if (endpoint.parameters?.body) {
    // Missing required fields
    scenarios.push({
      name: 'missing_required_fields',
      description: 'Request with missing required fields',
      weight: 10,
      requestData: generateIncompleteRequestData(endpoint),
      expectedStatus: [400, 422],
      followUp: 'retry_with_complete_data'
    });

    // Invalid data types
    scenarios.push({
      name: 'invalid_data_types',
      description: 'Request with invalid data types',
      weight: 5,
      requestData: generateInvalidRequestData(endpoint),
      expectedStatus: [400, 422],
      followUp: 'retry_with_valid_data'
    });
  }

  // Boundary testing
  scenarios.push({
    name: 'boundary_testing',
    description: 'Test with boundary values',
    weight: 10,
    requestData: generateBoundaryRequestData(endpoint),
    expectedStatus: [200, 201, 400],
    followUp: 'analyze_response'
  });

  // Large payload testing (for write operations)
  if (['POST', 'PUT', 'PATCH'].includes(endpoint.method.toUpperCase())) {
    scenarios.push({
      name: 'large_payload',
      description: 'Test with large request payload',
      weight: 5,
      requestData: generateLargeRequestData(endpoint),
      expectedStatus: [200, 201, 413],
      followUp: 'check_payload_limits'
    });
  }

  return scenarios;
}

/**
 * Generate agent workflows based on parsed endpoints
 */
function generateAgentWorkflows(endpoints: ParsedEndpoint[]): Array<Record<string, any>> {
  const workflows: Array<Record<string, any>> = [];

  // Authentication workflow (if login endpoint exists)
  const loginEndpoint = findLoginEndpoint(endpoints);
  if (loginEndpoint) {
    workflows.push({
      name: 'authentication_flow',
      description: 'User authentication and session management',
      steps: [
        {
          endpoint: loginEndpoint.path,
          method: loginEndpoint.method,
          purpose: 'authenticate_user',
          data: generateLoginData(),
          storeSession: true
        }
      ],
      frequency: 'session_start',
      priority: 'high'
    });
  }

  // CRUD workflow (if CRUD endpoints exist)
  const crudEndpoints = identifyCRUDEndpoints(endpoints);
  if (crudEndpoints.length > 0) {
    workflows.push({
      name: 'crud_operations',
      description: 'Complete CRUD operation workflow',
      steps: generateCRUDWorkflowSteps(crudEndpoints),
      frequency: 'regular',
      priority: 'medium'
    });
  }

  // Read-heavy workflow (for GET endpoints)
  const readEndpoints = endpoints.filter(e => e.method.toUpperCase() === 'GET');
  if (readEndpoints.length > 0) {
    workflows.push({
      name: 'data_browsing',
      description: 'User browsing and data retrieval patterns',
      steps: readEndpoints.map(endpoint => ({
        endpoint: endpoint.path,
        method: endpoint.method,
        purpose: 'browse_data',
        weight: getEndpointWeight(endpoint)
      })),
      frequency: 'high',
      priority: 'low'
    });
  }

  return workflows;
}

/**
 * Generate sample data sets for data models
 */
function generateSampleDataSets(dataModels: Record<string, any>): Record<string, any[]> {
  const dataSets: Record<string, any[]> = {};

  Object.entries(dataModels).forEach(([modelName, modelSchema]) => {
    dataSets[modelName] = generateModelSampleData(modelName, modelSchema, 10); // Generate 10 samples
  });

  return dataSets;
}

// Helper functions for the new configuration generation

function getEndpointPriority(endpoint: ParsedEndpoint): string {
  if (endpoint.path.includes('login') || endpoint.path.includes('auth')) return 'high';
  if (endpoint.path.includes('health') || endpoint.path.includes('status')) return 'low';
  if (endpoint.method.toUpperCase() === 'GET') return 'medium';
  return 'medium';
}

function getEndpointFrequency(endpoint: ParsedEndpoint): string {
  if (endpoint.method.toUpperCase() === 'GET') return 'high';
  if (endpoint.path.includes('health')) return 'high';
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(endpoint.method.toUpperCase())) return 'medium';
  return 'low';
}

function getEndpointDependencies(endpoint: ParsedEndpoint): string[] {
  const dependencies: string[] = [];
  
  if (endpoint.sessionRequired) {
    dependencies.push('authentication');
  }
  
  if (endpoint.path.includes('/{id}') || endpoint.path.includes('/:id')) {
    dependencies.push('resource_creation');
  }
  
  return dependencies;
}

function getDataVariationStrategy(endpoint: ParsedEndpoint): string {
  if (endpoint.method.toUpperCase() === 'GET') return 'parameter_variation';
  if (['POST', 'PUT', 'PATCH'].includes(endpoint.method.toUpperCase())) return 'payload_variation';
  return 'minimal_variation';
}

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

function getFollowUpActions(endpoint: ParsedEndpoint): string {
  if (endpoint.path.includes('login')) return 'store_session';
  if (endpoint.method.toUpperCase() === 'POST') return 'verify_creation';
  if (endpoint.method.toUpperCase() === 'DELETE') return 'verify_deletion';
  return 'continue';
}

function generateIncompleteRequestData(endpoint: ParsedEndpoint): Record<string, any> {
  const sampleData = generateSampleRequestData(endpoint);
  const requiredFields = extractRequiredFields(endpoint.parameters);
  
  // Remove one required field to create incomplete data
  if (requiredFields.length > 0) {
    delete sampleData[requiredFields[0]];
  }
  
  return sampleData;
}

function generateInvalidRequestData(endpoint: ParsedEndpoint): Record<string, any> {
  const sampleData = generateSampleRequestData(endpoint);
  
  // Corrupt some data types
  Object.keys(sampleData).forEach(key => {
    if (typeof sampleData[key] === 'string') {
      sampleData[key] = 12345; // Wrong type
    } else if (typeof sampleData[key] === 'number') {
      sampleData[key] = 'invalid_number'; // Wrong type
    }
  });
  
  return sampleData;
}

function generateBoundaryRequestData(endpoint: ParsedEndpoint): Record<string, any> {
  const sampleData = generateSampleRequestData(endpoint);
  
  // Apply boundary values
  Object.entries(sampleData).forEach(([key, value]) => {
    if (typeof value === 'string') {
      sampleData[key] = 'a'.repeat(255); // Long string
    } else if (typeof value === 'number') {
      sampleData[key] = Number.MAX_SAFE_INTEGER; // Large number
    }
  });
  
  return sampleData;
}

function generateLargeRequestData(endpoint: ParsedEndpoint): Record<string, any> {
  const sampleData = generateSampleRequestData(endpoint);
  
  // Add large data fields
  sampleData.largeTextField = 'x'.repeat(10000);
  sampleData.largeArray = Array(1000).fill('item');
  
  return sampleData;
}

function findLoginEndpoint(endpoints: ParsedEndpoint[]): ParsedEndpoint | null {
  return endpoints.find(e => 
    e.path.includes('login') || 
    e.path.includes('auth') || 
    e.path.includes('signin')
  ) || null;
}

function generateLoginData(): Record<string, any> {
  return {
    username: 'testuser@example.com',
    password: 'TestPassword123!',
    rememberMe: true
  };
}

function identifyCRUDEndpoints(endpoints: ParsedEndpoint[]): ParsedEndpoint[] {
  // Find endpoints that form CRUD operations
  const resourcePaths = new Set<string>();
  
  endpoints.forEach(endpoint => {
    const basePath = endpoint.path.replace(/\/\{[^}]+\}/g, '').replace(/\/:[^/]+/g, '');
    resourcePaths.add(basePath);
  });
  
  return endpoints.filter(endpoint => {
    const basePath = endpoint.path.replace(/\/\{[^}]+\}/g, '').replace(/\/:[^/]+/g, '');
    return resourcePaths.has(basePath) && !endpoint.path.includes('login') && !endpoint.path.includes('health');
  });
}

function generateCRUDWorkflowSteps(crudEndpoints: ParsedEndpoint[]): Array<Record<string, any>> {
  const steps: Array<Record<string, any>> = [];
  
  // Create
  const createEndpoint = crudEndpoints.find(e => e.method.toUpperCase() === 'POST');
  if (createEndpoint) {
    steps.push({
      endpoint: createEndpoint.path,
      method: createEndpoint.method,
      purpose: 'create_resource',
      data: generateSampleRequestData(createEndpoint),
      storeResourceId: true
    });
  }
  
  // Read
  const readEndpoint = crudEndpoints.find(e => e.method.toUpperCase() === 'GET');
  if (readEndpoint) {
    steps.push({
      endpoint: readEndpoint.path,
      method: readEndpoint.method,
      purpose: 'read_resource',
      useStoredId: true
    });
  }
  
  // Update
  const updateEndpoint = crudEndpoints.find(e => ['PUT', 'PATCH'].includes(e.method.toUpperCase()));
  if (updateEndpoint) {
    steps.push({
      endpoint: updateEndpoint.path,
      method: updateEndpoint.method,
      purpose: 'update_resource',
      data: generateSampleRequestData(updateEndpoint),
      useStoredId: true
    });
  }
  
  // Delete
  const deleteEndpoint = crudEndpoints.find(e => e.method.toUpperCase() === 'DELETE');
  if (deleteEndpoint) {
    steps.push({
      endpoint: deleteEndpoint.path,
      method: deleteEndpoint.method,
      purpose: 'delete_resource',
      useStoredId: true
    });
  }
  
  return steps;
}

function getEndpointWeight(endpoint: ParsedEndpoint): number {
  if (endpoint.path.includes('health')) return 0.1;
  if (endpoint.method.toUpperCase() === 'GET') return 0.6;
  if (endpoint.method.toUpperCase() === 'POST') return 0.2;
  return 0.1;
}

function generateModelSampleData(modelName: string, modelSchema: any, count: number): any[] {
  const samples: any[] = [];
  
  for (let i = 0; i < count; i++) {
    const sample: any = {};
    
    if (typeof modelSchema === 'object') {
      Object.entries(modelSchema).forEach(([field, description]) => {
        sample[field] = generateSampleValue(field, description as string);
        
        // Add variation for different samples
        if (typeof sample[field] === 'string' && field.includes('name')) {
          sample[field] = `${sample[field]} ${i + 1}`;
        } else if (typeof sample[field] === 'number') {
          sample[field] = sample[field] + i;
        }
      });
    }
    
    samples.push(sample);
  }
  
  return samples;
}

async function generateConfigFiles(projectPath: string, config: SetupAnswers): Promise<void> {
  // Transform target URL for Docker compatibility
  const dockerCompatibleUrl = transformUrlForDocker(config.targetUrl);
  
  // Create config with Docker-compatible URL while preserving all other properties
  const dockerConfig: SetupAnswers = { ...config, targetUrl: dockerCompatibleUrl };
  
  // Generate APE configuration file with comprehensive settings
  const apeConfig: any = {
    project: {
      name: config.projectName,
      version: '1.0.0',
      created: new Date().toISOString()
    },
    target: {
      url: dockerCompatibleUrl,
      port: config.targetPort,
      endpoints: config.endpoints
    },
    agents: {
      count: config.agentCount,
      goal: config.testGoal,
      scaling: {
        min: 1,
        max: config.agentCount * 2
      }
    },
    test: {
      duration: config.testDuration,
      warmup: 30, // seconds
      cooldown: 30 // seconds
    },
    observability: {
      metrics: {
        enabled: true,
        interval: 10 // seconds
      },
      logging: {
        level: 'info',
        tracing: true
      }
    }
  };

  // Add parsed API specification data if available
  if (config.parsedApiSpec) {
    apeConfig.apiSpec = {
      source: config.apiSpecFile,
      parsed: config.parsedApiSpec,
      generatedAt: new Date().toISOString(),
      summary: {
        endpointCount: config.parsedApiSpec.endpoints.length,
        methods: [...new Set(config.parsedApiSpec.endpoints.map(e => e.method))],
        sessionRequired: config.parsedApiSpec.endpoints.filter(e => e.sessionRequired).length,
        dataModelCount: config.parsedApiSpec.dataModels ? Object.keys(config.parsedApiSpec.dataModels).length : 0
      }
    };

    // Enhance target configuration with parsed endpoint details
    apeConfig.target.endpointDetails = config.parsedApiSpec.endpoints.map(endpoint => ({
      path: endpoint.path,
      method: endpoint.method,
      purpose: endpoint.purpose,
      parameters: endpoint.parameters,
      responses: endpoint.responses,
      sessionRequired: endpoint.sessionRequired,
      // Add enhanced configuration for agents
      agentBehavior: generateAgentBehaviorConfig(endpoint),
      // Add realistic test scenarios
      testScenarios: generateTestScenarios(endpoint)
    }));

    // Add common patterns information with enhanced configuration
    if (config.parsedApiSpec.commonPatterns) {
      apeConfig.target.commonPatterns = {
        ...config.parsedApiSpec.commonPatterns,
        // Add configuration for how agents should handle these patterns
        agentHandling: {
          sessionManagement: config.parsedApiSpec.commonPatterns.sessionManagement ? {
            loginEndpoint: findLoginEndpoint(config.parsedApiSpec.endpoints),
            sessionDuration: 3600, // 1 hour default
            refreshStrategy: 'proactive'
          } : null,
          pagination: config.parsedApiSpec.commonPatterns.pagination ? {
            strategy: 'follow_links',
            maxPages: 10,
            pageSize: 20
          } : null,
          errorHandling: config.parsedApiSpec.commonPatterns.errorHandling ? {
            retryStrategy: 'exponential_backoff',
            maxRetries: 3,
            backoffMultiplier: 2
          } : null
        }
      };
    }

    // Add data models with enhanced schema information
    if (config.parsedApiSpec.dataModels) {
      apeConfig.target.dataModels = config.parsedApiSpec.dataModels;
      
      // Generate sample data sets for each model
      apeConfig.target.sampleDataSets = generateSampleDataSets(config.parsedApiSpec.dataModels);
    }

    // Add agent workflow configuration based on parsed endpoints
    apeConfig.agents.workflows = generateAgentWorkflows(config.parsedApiSpec.endpoints);
    
    // Add intelligent request generation configuration
    apeConfig.agents.requestGeneration = {
      useRealisticData: true,
      respectValidation: true,
      varyOptionalFields: true,
      sessionAware: config.parsedApiSpec.commonPatterns?.sessionManagement || false
    };
  }

  await fs.writeJSON(path.join(projectPath, 'ape.config.json'), apeConfig, { spaces: 2 });
  
  // Generate Docker Compose configuration - Requirements 5.4, 6.2, 6.3
  const dockerComposeConfig = generateDockerCompose(dockerConfig);

  // Fix environment variable syntax in YAML output - restore ${} format
  let dockerComposeYaml = yaml.stringify(dockerComposeConfig);

  // Fix environment variables (uppercase names with optional default values)
  dockerComposeYaml = dockerComposeYaml.replace(/\{([A-Z_][A-Z0-9_]*(?::-[^}]*)?)\}/g, '${$1}');

  // Fix Docker template variables that may have been corrupted
  dockerComposeYaml = dockerComposeYaml.replace(/\$?\{\{\.([^}]+)\}\}/g, '{{.$1}}');
  dockerComposeYaml = dockerComposeYaml.replace(/\$\{\.([^}]+)\}/g, '{{.$1}}');

  // Fix double-escaped environment variables ($${ -> ${)
  dockerComposeYaml = dockerComposeYaml.replace(/\$\$\{([A-Z_][A-Z0-9_]*)\}/g, '${$1}');

  await fs.writeFile(
    path.join(projectPath, 'ape.docker-compose.yml'),
    dockerComposeYaml
  );

  // Generate production-optimized Docker Compose override - Requirements 6.1, 6.4
  const productionOverride = generateProductionOverride(config);

  // Fix environment variable syntax in production YAML output - restore ${} format
  let productionOverrideYaml = yaml.stringify(productionOverride);

  // Fix environment variables (uppercase names with optional default values)
  productionOverrideYaml = productionOverrideYaml.replace(/\{([A-Z_][A-Z0-9_]*(?::-[^}]*)?)\}/g, '${$1}');

  // Fix Docker template variables that may have been corrupted
  productionOverrideYaml = productionOverrideYaml.replace(/\$?\{\{\.([^}]+)\}\}/g, '{{.$1}}');
  productionOverrideYaml = productionOverrideYaml.replace(/\$\{\.([^}]+)\}/g, '{{.$1}}');

  // Fix double-escaped environment variables ($${ -> ${)
  productionOverrideYaml = productionOverrideYaml.replace(/\$\$\{([A-Z_][A-Z0-9_]*)\}/g, '${$1}');

  await fs.writeFile(
    path.join(projectPath, 'ape.docker-compose.production.yml'),
    productionOverrideYaml
  );

  // Generate production environment file - Requirements 6.1, 6.4
  const productionEnv = generateProductionEnv(config);
  await fs.writeFile(
    path.join(projectPath, '.env.production'),
    productionEnv
  );

  // Create config directory for observability stack
  const configDir = path.join(projectPath, 'config');
  await fs.ensureDir(configDir);
  await fs.ensureDir(path.join(configDir, 'grafana', 'provisioning', 'datasources'));
  await fs.ensureDir(path.join(configDir, 'grafana', 'provisioning', 'dashboards'));
  await fs.ensureDir(path.join(configDir, 'grafana', 'dashboards'));

  // Generate Prometheus configuration
  const prometheusConfig = generatePrometheusConfig(config);
  await fs.writeFile(
    path.join(configDir, 'prometheus.yml'),
    yaml.stringify(prometheusConfig)
  );

  // Generate Promtail configuration
  const promtailConfig = generatePromtailConfig(config);
  await fs.writeFile(
    path.join(configDir, 'promtail.yml'),
    yaml.stringify(promtailConfig)
  );

  // Generate Grafana datasource configuration
  const grafanaDatasources = {
    apiVersion: 1,
    datasources: [
      {
        name: 'Prometheus',
        type: 'prometheus',
        access: 'proxy',
        url: 'http://prometheus:9090',
        isDefault: true
      },
      {
        name: 'Loki',
        type: 'loki',
        access: 'proxy',
        url: 'http://loki:3100'
      }
    ]
  };

  await fs.writeFile(
    path.join(configDir, 'grafana', 'provisioning', 'datasources', 'datasources.yml'),
    yaml.stringify(grafanaDatasources)
  );

  // Generate Grafana dashboard provisioning
  const grafanaDashboards = {
    apiVersion: 1,
    providers: [
      {
        name: 'APE Dashboards',
        orgId: 1,
        folder: '',
        type: 'file',
        disableDeletion: false,
        updateIntervalSeconds: 10,
        allowUiUpdates: true,
        options: {
          path: '/var/lib/grafana/dashboards'
        }
      }
    ]
  };

  await fs.writeFile(
    path.join(configDir, 'grafana', 'provisioning', 'dashboards', 'dashboards.yml'),
    yaml.stringify(grafanaDashboards)
  );

  // Generate environment file with actual API key
  const envFile = `# APE Environment Configuration
# Generated automatically with your configuration

# Cerebras API Configuration
CEREBRAS_API_KEY=${config.cerebrasApiKey}

# Optional: Custom configuration overrides
# AGENT_SCALING_MAX=${config.agentCount * 2}
# LOG_LEVEL=debug
# METRICS_RETENTION=7d
`;

  await fs.writeFile(path.join(projectPath, '.env'), envFile);

  // Also generate template for reference
  const envTemplate = `# APE Environment Configuration
# Copy this to .env and fill in your values

# Cerebras API Configuration
CEREBRAS_API_KEY=your_cerebras_api_key_here

# Optional: Custom configuration overrides
# AGENT_SCALING_MAX=${config.agentCount * 2}
# LOG_LEVEL=debug
# METRICS_RETENTION=7d
`;

  await fs.writeFile(path.join(projectPath, '.env.template'), envTemplate);

  // Generate MCP Gateway routing configuration - Requirements 3.3, 3.4, 5.4
  const mcpGatewayConfig = config.applicationType
    ? generateApplicationSpecificConfig(dockerConfig, config.applicationType)
    : generateEnhancedMCPGatewayConfig(dockerConfig);
  await fs.writeJSON(path.join(projectPath, 'ape.mcp-gateway.json'), mcpGatewayConfig, { spaces: 2 });

  // Generate application-specific Docker Compose override
  if (config.applicationType) {
    const appDockerOverride = generateApplicationDockerOverride(config, config.applicationType);
    await fs.writeFile(
      path.join(projectPath, `ape.docker-compose.${config.applicationType}.yml`),
      yaml.stringify(appDockerOverride)
    );
  }

  // Create comprehensive README with instructions
  const apiSpecSection = config.parsedApiSpec ? `
- **API Specification**: Parsed from ${config.apiSpecFile}
- **Parsed Endpoints**: ${config.parsedApiSpec.endpoints.length} endpoints with detailed schemas
- **Session Management**: ${config.parsedApiSpec.commonPatterns?.sessionManagement ? 'Enabled' : 'Disabled'}
- **Pagination Support**: ${config.parsedApiSpec.commonPatterns?.pagination ? 'Enabled' : 'Disabled'}` : '';

  const readme = `# ${config.projectName}

APE (Agentic Protocol Engine) Load Test Configuration

## Overview
This project contains an AI-driven load testing setup that uses intelligent LLM agents to simulate realistic user behavior against your target application.

## Configuration Summary
- **Target Application**: ${config.targetUrl}
- **Authentication**: None (public API)
- **Concurrent Agents**: ${config.agentCount}
- **Test Duration**: ${config.testDuration} minutes
- **Agent Goal**: ${config.testGoal}
- **API Endpoints**: ${config.endpoints.join(', ')}${apiSpecSection}

## Generated Files
- \`ape.config.json\` - Main APE configuration${config.parsedApiSpec ? ' (enhanced with parsed API data)' : ''}
- \`ape.docker-compose.yml\` - Docker Compose orchestration
- \`ape.mcp-gateway.json\` - MCP Gateway routing configuration${config.parsedApiSpec ? ' (with intelligent request/response handling)' : ''}
- \`config/\` - Observability stack configuration (Prometheus, Grafana, etc.)
- \`.env.template\` - Environment variables template${config.parsedApiSpec ? `

### API Specification Enhancement
This configuration was enhanced using AI-powered parsing of your API specification file:
- **Source File**: \`${config.apiSpecFile}\`
- **Parsed Endpoints**: ${config.parsedApiSpec.endpoints.length} endpoints with detailed schemas
- **Sample Data Generation**: Realistic request payloads based on parsed schemas
- **Response Handling**: Intelligent error handling based on documented responses
- **Session Management**: ${config.parsedApiSpec.commonPatterns?.sessionManagement ? 'Automatic session handling enabled' : 'No session management required'}` : ''}

## Prerequisites
1. Docker and Docker Compose installed
2. Cerebras API key (already configured during setup)

## Quick Start
\`\`\`bash
# 1. Start the load test (API key already configured)
docker-compose -f ape.docker-compose.yml --env-file .env up -d

# 3. Monitor in real-time
# - Grafana Dashboard: http://localhost:3001 (admin/ape-admin)
# - Prometheus Metrics: http://localhost:9090
# - Container Metrics: http://localhost:8080

# 4. View logs and traces
ape-load logs --follow
ape-load logs --grep "TRACE_ID_HERE"

# 5. Check status
ape-load status

# 6. Stop the test
ape-load stop
\`\`\`

## Architecture
The system uses a three-tier architecture:
1. **Agent Layer**: Scalable LLM agents (${config.agentCount} instances)
2. **Protocol Mediation**: MCP Gateway + Cerebras Proxy
3. **Target Layer**: Your application + observability stack

## Monitoring & Observability
- **Grafana**: Real-time dashboards and alerting
- **Prometheus**: Metrics collection and storage
- **Loki**: Centralized log aggregation
- **Trace Correlation**: End-to-end request tracing

## Scaling
\`\`\`bash
# Scale agents dynamically
ape-load start --agents 50

# Maximum recommended: ${config.agentCount * 2} agents
\`\`\`

## Troubleshooting
- Check service health: \`docker-compose -f ape.docker-compose.yml ps\`
- View service logs: \`docker-compose -f ape.docker-compose.yml logs [service_name]\`
- Restart services: \`docker-compose -f ape.docker-compose.yml restart\`

For more information, visit: https://github.com/b9aurav/agentic-protocol-engine
`;

  await fs.writeFile(path.join(projectPath, 'README.md'), readme);

  // Copy services directory to project - Required for Docker builds
  const servicesSourcePath = path.join(__dirname, '..', '..', 'services');
  const servicesDestPath = path.join(projectPath, 'services');

  try {
    await fs.copy(servicesSourcePath, servicesDestPath, {
      overwrite: true,
      filter: (src) => {
        // Exclude Python cache files and other build artifacts
        const relativePath = path.relative(servicesSourcePath, src);
        return !relativePath.includes('__pycache__') &&
          !relativePath.includes('.pyc') &&
          !relativePath.includes('.pytest_cache') &&
          !relativePath.endsWith('.log');
      }
    });
  } catch (error) {
    console.warn(chalk.yellow('⚠️  Warning: Could not copy services directory. You may need to copy it manually.'));
    console.warn(chalk.gray(`   Services should be copied from the package installation to: ${servicesDestPath}`));
  }

  await fs.writeJSON(path.join(projectPath, 'services', 'llama-agent', 'ape.config.json'), apeConfig, { spaces: 2 });
}