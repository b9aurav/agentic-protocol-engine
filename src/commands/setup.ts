import chalk from 'chalk';
import inquirer from 'inquirer';
import ora from 'ora';
import * as fs from 'fs-extra';
import * as path from 'path';
import * as yaml from 'yaml';
import { generateDockerCompose, generatePrometheusConfig, generatePromtailConfig } from '../templates/docker-compose';
import { generateProductionOverride, generateProductionEnv } from '../templates/docker-compose.production';
import { generateMCPGatewayConfig } from '../templates/mcp-gateway';

interface SetupOptions {
  template: string;
  yes?: boolean;
  output: string;
}

export interface SetupAnswers {
  projectName: string;
  targetUrl: string;
  targetPort: number;
  authType: string;
  authToken?: string;
  authUsername?: string;
  authPassword?: string;
  agentCount: number;
  testDuration: number;
  testGoal: string;
  endpoints: string[];
  customHeaders: Record<string, string>;
}

export async function setupWizard(projectName?: string, options?: SetupOptions): Promise<void> {
  console.log(chalk.blue('🤖 Welcome to APE Setup Wizard!'));
  console.log(chalk.gray('This wizard will help you configure your AI-driven load test.\n'));

  try {
    let answers: SetupAnswers;

    if (options?.yes) {
      // Use defaults when --yes flag is provided
      answers = {
        projectName: projectName || 'my-ape-test',
        targetUrl: 'http://localhost:8080',
        targetPort: 8080,
        authType: 'none',
        agentCount: 10,
        testDuration: 5,
        testGoal: 'Simulate realistic user browsing and interaction patterns',
        endpoints: ['/api/health', '/api/users'],
        customHeaders: {}
      };
    } else {
      // Interactive prompts - Requirements 5.1, 5.2
      const basicAnswers = await inquirer.prompt([
        {
          type: 'input',
          name: 'projectName',
          message: 'Project name:',
          default: projectName || 'my-ape-test',
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
        },
        {
          type: 'list',
          name: 'authType',
          message: 'Authentication type:',
          choices: [
            { name: 'None (public endpoints)', value: 'none' },
            { name: 'Bearer Token (JWT/API Key)', value: 'bearer' },
            { name: 'Basic Authentication', value: 'basic' },
            { name: 'Session Cookies (login flow)', value: 'session' }
          ],
          default: 'none'
        }
      ]);

      // Conditional authentication prompts
      let authAnswers = {};
      if (basicAnswers.authType === 'bearer') {
        authAnswers = await inquirer.prompt([
          {
            type: 'password',
            name: 'authToken',
            message: 'Bearer token (will be stored in config):',
            validate: (input: string) => input.length > 0 || 'Bearer token is required',
            mask: '*'
          }
        ]);
      } else if (basicAnswers.authType === 'basic') {
        authAnswers = await inquirer.prompt([
          {
            type: 'input',
            name: 'authUsername',
            message: 'Username:',
            validate: (input: string) => input.length > 0 || 'Username is required'
          },
          {
            type: 'password',
            name: 'authPassword',
            message: 'Password (will be stored in config):',
            validate: (input: string) => input.length > 0 || 'Password is required',
            mask: '*'
          }
        ]);
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

      // API endpoints configuration
      const endpointAnswers = await inquirer.prompt([
        {
          type: 'input',
          name: 'endpoints',
          message: 'API endpoints to test (comma-separated, e.g., /api/users,/api/products):',
          default: '/api/health,/api/users',
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

      // Custom headers configuration
      const headerAnswers = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'hasCustomHeaders',
          message: 'Add custom headers (e.g., Content-Type, User-Agent)?',
          default: false
        }
      ]);

      let customHeaders = {};
      if (headerAnswers.hasCustomHeaders) {
        const headerConfig = await inquirer.prompt([
          {
            type: 'input',
            name: 'headerPairs',
            message: 'Custom headers (format: "Key1:Value1,Key2:Value2"):',
            validate: (input: string) => {
              if (input.length === 0) return true; // Optional
              const pairs = input.split(',');
              for (const pair of pairs) {
                if (!pair.includes(':')) {
                  return 'Headers must be in format "Key:Value,Key2:Value2"';
                }
              }
              return true;
            },
            filter: (input: string) => {
              const headers: Record<string, string> = {};
              if (input.length > 0) {
                const pairs = input.split(',');
                for (const pair of pairs) {
                  const [key, ...valueParts] = pair.split(':');
                  if (key && valueParts.length > 0) {
                    headers[key.trim()] = valueParts.join(':').trim();
                  }
                }
              }
              return headers;
            }
          }
        ]);
        customHeaders = headerConfig.headerPairs;
      }

      answers = {
        ...basicAnswers,
        ...authAnswers,
        ...testAnswers,
        ...endpointAnswers,
        customHeaders
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
    console.log(chalk.yellow('   ape-test start --agents 10'));
    console.log(chalk.gray('\n💡 Use "ape-test --help" for more commands'));

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
      endpoints: config.endpoints,
      auth: {
        type: config.authType
      },
      headers: config.customHeaders
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

  // Add authentication details based on type
  if (config.authType === 'bearer' && config.authToken) {
    apeConfig.target.auth.token = config.authToken;
  } else if (config.authType === 'basic' && config.authUsername && config.authPassword) {
    apeConfig.target.auth.username = config.authUsername;
    apeConfig.target.auth.password = config.authPassword;
  }

  await fs.writeJSON(path.join(projectPath, 'ape.config.json'), apeConfig, { spaces: 2 });

  // Generate Docker Compose configuration - Requirements 5.4, 6.2, 6.3
  const dockerComposeConfig = generateDockerCompose(config);
  await fs.writeFile(
    path.join(projectPath, 'ape.docker-compose.yml'),
    yaml.stringify(dockerComposeConfig)
  );

  // Generate production-optimized Docker Compose override - Requirements 6.1, 6.4
  const productionOverride = generateProductionOverride(config);
  await fs.writeFile(
    path.join(projectPath, 'ape.docker-compose.production.yml'),
    yaml.stringify(productionOverride)
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

  // Generate environment file template
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
  const mcpGatewayConfig = generateMCPGatewayConfig(config);
  await fs.writeJSON(path.join(projectPath, 'ape.mcp-gateway.json'), mcpGatewayConfig, { spaces: 2 });

  // Create comprehensive README with instructions
  const readme = `# ${config.projectName}

APE (Agentic Protocol Engine) Load Test Configuration

## Overview
This project contains an AI-driven load testing setup that uses intelligent LLM agents to simulate realistic user behavior against your target application.

## Configuration Summary
- **Target Application**: ${config.targetUrl}
- **Authentication**: ${config.authType}
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
2. Cerebras API key (copy \`.env.template\` to \`.env\` and add your key)

## Quick Start
\`\`\`bash
# 1. Set up environment
cp .env.template .env
# Edit .env and add your CEREBRAS_API_KEY

# 2. Start the load test
ape-test start --agents ${config.agentCount}

# 3. Monitor in real-time
# - Grafana Dashboard: http://localhost:3001 (admin/ape-admin)
# - Prometheus Metrics: http://localhost:9090
# - Container Metrics: http://localhost:8080

# 4. View logs and traces
ape-test logs --follow
ape-test logs --grep "TRACE_ID_HERE"

# 5. Check status
ape-test status

# 6. Stop the test
ape-test stop
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
ape-test start --agents 50

# Maximum recommended: ${config.agentCount * 2} agents
\`\`\`

## Troubleshooting
- Check service health: \`docker-compose -f ape.docker-compose.yml ps\`
- View service logs: \`docker-compose -f ape.docker-compose.yml logs [service_name]\`
- Restart services: \`docker-compose -f ape.docker-compose.yml restart\`

For more information, visit: https://github.com/b9aurav/agentic-protocol-engine
`;

  await fs.writeFile(path.join(projectPath, 'README.md'), readme);
}