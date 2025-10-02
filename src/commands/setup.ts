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
        targetUrl: 'http://localhost:8080',
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
          default: 'http://localhost:8080',
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

      // API endpoints configuration
      const endpointAnswers = await inquirer.prompt([
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



      answers = {
        ...basicAnswers,
        ...cerebrasAnswers,
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

async function generateConfigFiles(projectPath: string, config: SetupAnswers): Promise<void> {
  // Generate APE configuration file with comprehensive settings
  const apeConfig: any = {
    project: {
      name: config.projectName,
      version: '1.0.0',
      created: new Date().toISOString()
    },
    target: {
      url: config.targetUrl,
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



  await fs.writeJSON(path.join(projectPath, 'ape.config.json'), apeConfig, { spaces: 2 });

  // Generate Docker Compose configuration - Requirements 5.4, 6.2, 6.3
  const dockerComposeConfig = generateDockerCompose(config);

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
    ? generateApplicationSpecificConfig(config, config.applicationType)
    : generateMCPGatewayConfig(config);
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
- **API Endpoints**: ${config.endpoints.join(', ')}

## Generated Files
- \`ape.config.json\` - Main APE configuration
- \`ape.docker-compose.yml\` - Docker Compose orchestration
- \`ape.mcp-gateway.json\` - MCP Gateway routing configuration
- \`config/\` - Observability stack configuration (Prometheus, Grafana, etc.)
- \`.env.template\` - Environment variables template

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
}