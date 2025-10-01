import chalk from 'chalk';
import inquirer from 'inquirer';
import ora from 'ora';
import * as fs from 'fs-extra';
import * as path from 'path';

interface SetupOptions {
  template: string;
  yes?: boolean;
  output: string;
}

interface SetupAnswers {
  projectName: string;
  targetUrl: string;
  targetPort: number;
  authType: string;
  agentCount: number;
  testDuration: number;
  testGoal: string;
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
        testGoal: 'Simulate user browsing and interaction'
      };
    } else {
      // Interactive prompts - Requirements 5.1, 5.2
      answers = await inquirer.prompt([
        {
          type: 'input',
          name: 'projectName',
          message: 'Project name:',
          default: projectName || 'my-ape-test',
          validate: (input: string) => input.length > 0 || 'Project name is required'
        },
        {
          type: 'input',
          name: 'targetUrl',
          message: 'Target application URL:',
          default: 'http://localhost:8080',
          validate: (input: string) => {
            try {
              new URL(input);
              return true;
            } catch {
              return 'Please enter a valid URL';
            }
          }
        },
        {
          type: 'number',
          name: 'targetPort',
          message: 'Target application port:',
          default: 8080,
          validate: (input: number) => (input > 0 && input <= 65535) || 'Port must be between 1 and 65535'
        },
        {
          type: 'list',
          name: 'authType',
          message: 'Authentication type:',
          choices: [
            { name: 'None', value: 'none' },
            { name: 'Bearer Token', value: 'bearer' },
            { name: 'Basic Auth', value: 'basic' },
            { name: 'Session Cookies', value: 'session' }
          ],
          default: 'none'
        },
        {
          type: 'number',
          name: 'agentCount',
          message: 'Number of concurrent agents:',
          default: 10,
          validate: (input: number) => (input > 0 && input <= 1000) || 'Agent count must be between 1 and 1000'
        },
        {
          type: 'number',
          name: 'testDuration',
          message: 'Test duration (minutes):',
          default: 5,
          validate: (input: number) => input > 0 || 'Duration must be greater than 0'
        },
        {
          type: 'input',
          name: 'testGoal',
          message: 'Agent goal description:',
          default: 'Simulate user browsing and interaction',
          validate: (input: string) => input.length > 0 || 'Goal description is required'
        }
      ]);
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
  // Generate APE configuration file
  const apeConfig = {
    project: {
      name: config.projectName,
      version: '1.0.0'
    },
    target: {
      url: config.targetUrl,
      port: config.targetPort,
      auth: {
        type: config.authType
      }
    },
    agents: {
      count: config.agentCount,
      goal: config.testGoal
    },
    test: {
      duration: config.testDuration
    }
  };

  await fs.writeJSON(path.join(projectPath, 'ape.config.json'), apeConfig, { spaces: 2 });

  // Placeholder files for Docker Compose and MCP Gateway config
  // These will be implemented in task 2.2 and 2.3
  await fs.writeFile(
    path.join(projectPath, 'ape.docker-compose.yml'),
    '# Docker Compose configuration will be generated here\n# Implementation in task 2.2\n'
  );

  await fs.writeFile(
    path.join(projectPath, 'ape.mcp-gateway.json'),
    '# MCP Gateway routing configuration will be generated here\n# Implementation in task 2.3\n'
  );

  // Create README with instructions
  const readme = `# ${config.projectName}

APE Load Test Configuration

## Configuration
- Target: ${config.targetUrl}
- Agents: ${config.agentCount}
- Duration: ${config.testDuration} minutes
- Goal: ${config.testGoal}

## Commands
\`\`\`bash
# Start load test
ape-test start --agents ${config.agentCount}

# View status
ape-test status

# View logs
ape-test logs --follow

# Stop test
ape-test stop
\`\`\`
`;

  await fs.writeFile(path.join(projectPath, 'README.md'), readme);
}