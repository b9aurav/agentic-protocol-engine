import chalk from 'chalk';
import ora from 'ora';
import * as fs from 'fs-extra';
import * as path from 'path';
import { DockerComposeManager, checkDockerAvailability, validateComposeFile } from '../utils/docker';

interface StartOptions {
  agents: string;
  config: string;
  duration: string;
}

export async function startCommand(options: StartOptions): Promise<void> {
  const spinner = ora('Starting APE load test...').start();
  
  try {
    const agentCount = parseInt(options.agents, 10);
    
    if (isNaN(agentCount) || agentCount <= 0) {
      spinner.fail('Invalid agent count. Must be a positive number.');
      process.exit(1);
    }

    // Validate agent count limits - Requirements 6.1, 6.4
    if (agentCount > 1000) {
      spinner.warn(`Warning: ${agentCount} agents is very high. Consider starting with fewer agents.`);
    }

    spinner.text = 'Checking Docker availability...';
    
    // Check Docker and Docker Compose availability - Requirements 5.3
    const dockerCheck = await checkDockerAvailability();
    if (!dockerCheck.docker) {
      spinner.fail('Docker is not installed or not running. Please install Docker and try again.');
      process.exit(1);
    }
    if (!dockerCheck.compose) {
      spinner.fail('Docker Compose is not available. Please install Docker Compose and try again.');
      process.exit(1);
    }

    spinner.text = 'Validating configuration...';
    
    // Check if configuration file exists
    const configPath = path.resolve(options.config);
    if (!await fs.pathExists(configPath)) {
      spinner.fail(`Configuration file not found: ${configPath}`);
      console.log(chalk.yellow('\n💡 Run "npx create-ape-test" to generate configuration files.'));
      process.exit(1);
    }

    // Validate Docker Compose file exists
    const projectDir = path.dirname(configPath);
    const composeFile = path.join(projectDir, 'ape.docker-compose.yml');
    
    const composeValidation = await validateComposeFile(composeFile);
    if (!composeValidation.valid) {
      spinner.fail(`Invalid Docker Compose configuration: ${composeValidation.error}`);
      console.log(chalk.yellow('\n💡 Run "npx create-ape-test" to regenerate configuration files.'));
      process.exit(1);
    }

    spinner.text = `Initializing ${agentCount} agents...`;
    
    // Initialize Docker Compose manager
    const dockerManager = new DockerComposeManager(
      projectDir,
      'ape.docker-compose.yml',
      path.basename(projectDir)
    );

    // Check if services are already running
    const currentStatus = await dockerManager.getStatus();
    if (currentStatus.isRunning) {
      spinner.info('Services are already running. Scaling agents...');
      
      // Scale the llama_agent service to the desired count
      spinner.text = `Scaling to ${agentCount} agents...`;
      await dockerManager.scale('llama_agent', agentCount);
    } else {
      // Start all services with agent scaling - Requirements 5.3, 6.1, 6.4
      spinner.text = 'Starting observability stack...';
      
      await dockerManager.start({
        projectName: path.basename(projectDir),
        detach: true,
        scale: {
          llama_agent: agentCount
        },
        env: {
          AGENT_COUNT: agentCount.toString(),
          TEST_DURATION: options.duration
        }
      });
    }

    // Wait for services to be healthy - Requirements 6.1, 6.4
    spinner.text = 'Waiting for services to be ready...';
    try {
      await dockerManager.waitForHealthy(120000); // 2 minute timeout
    } catch (error) {
      spinner.warn('Some services may not be fully healthy yet, but continuing...');
    }

    // Verify final status
    const finalStatus = await dockerManager.getStatus();
    const runningAgents = finalStatus.services.filter(s => 
      s.name.includes('llama_agent') && s.status === 'running'
    ).length;

    spinner.succeed('Load test started successfully!');
    
    console.log(chalk.green(`\n✅ APE load test is running!`));
    console.log(chalk.blue(`📊 Active Agents: ${runningAgents}/${agentCount}`));
    console.log(chalk.blue(`⏱️  Duration: ${options.duration} minutes`));
    console.log(chalk.blue(`📁 Config: ${options.config}`));
    console.log(chalk.blue(`🐳 Project: ${path.basename(projectDir)}`));
    
    // Display service status
    console.log(chalk.cyan('\n📋 Service Status:'));
    for (const service of finalStatus.services) {
      const statusIcon = service.status === 'running' ? '✅' : 
                        service.status === 'starting' ? '🔄' : '❌';
      const healthIcon = service.health === 'healthy' ? '💚' : 
                        service.health === 'starting' ? '🟡' : 
                        service.health === 'unhealthy' ? '❤️' : '';
      
      console.log(`  ${statusIcon} ${service.name} (${service.status}) ${healthIcon}`);
    }
    
    console.log(chalk.yellow('\n🔗 Access Points:'));
    console.log(chalk.yellow('  📊 Grafana Dashboard: http://localhost:3001 (admin/ape-admin)'));
    console.log(chalk.yellow('  📈 Prometheus Metrics: http://localhost:9090'));
    console.log(chalk.yellow('  🔍 MCP Gateway: http://localhost:3000'));
    
    console.log(chalk.cyan('\n📋 Management Commands:'));
    console.log(chalk.cyan('  📋 View logs: ape-test logs'));
    console.log(chalk.cyan('  📊 Check status: ape-test status'));
    console.log(chalk.cyan('  ⏹️  Stop test: ape-test stop'));
    
    // Display scaling information if applicable
    if (agentCount !== runningAgents) {
      console.log(chalk.yellow(`\n⚠️  Note: ${runningAgents}/${agentCount} agents are currently running.`));
      console.log(chalk.yellow('   Some agents may still be starting up.'));
    }
    
  } catch (error) {
    spinner.fail(`Failed to start load test: ${error instanceof Error ? error.message : 'Unknown error'}`);
    
    // Provide helpful troubleshooting information
    console.log(chalk.red('\n🔧 Troubleshooting:'));
    console.log(chalk.red('  1. Ensure Docker is running: docker --version'));
    console.log(chalk.red('  2. Check Docker Compose: docker compose version'));
    console.log(chalk.red('  3. Verify configuration: ape-test status'));
    console.log(chalk.red('  4. Check logs: ape-test logs'));
    
    process.exit(1);
  }
}