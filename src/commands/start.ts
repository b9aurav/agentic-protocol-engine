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
    // Check if configuration file exists first to read agent count
    const configPath = path.resolve(options.config);
    if (!await fs.pathExists(configPath)) {
      spinner.fail(`Configuration file not found: ${configPath}`);
      console.log(chalk.yellow('\n💡 Run "npx create-ape-load" to generate configuration files.'));
      process.exit(1);
    }

    // Read configuration to get default agent count if not specified via CLI
    let agentCount: number;
    if (options.agents === '10') { // Default value from CLI, check config file
      try {
        const config = await fs.readJson(configPath);
        agentCount = config.agents?.count || parseInt(options.agents, 10);
      } catch (error) {
        agentCount = parseInt(options.agents, 10);
      }
    } else {
      agentCount = parseInt(options.agents, 10);
    }
    
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

    // Validate Docker Compose file exists
    const projectDir = path.dirname(configPath);
    const composeFile = path.join(projectDir, 'ape.docker-compose.yml');
    
    const composeValidation = await validateComposeFile(composeFile);
    if (!composeValidation.valid) {
      spinner.fail(`Invalid Docker Compose configuration: ${composeValidation.error}`);
      console.log(chalk.yellow('\n💡 Run "npx create-ape-load" to regenerate configuration files.'));
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
      // Start observability stack first if it exists - Requirements 5.3, 6.1, 6.4
      const observabilityCompose = path.join(projectDir, 'config', 'observability.docker-compose.yml');
      if (await fs.pathExists(observabilityCompose)) {
        spinner.text = 'Starting observability stack...';
        
        const observabilityManager = new DockerComposeManager(
          path.join(projectDir, 'config'),
          'observability.docker-compose.yml',
          `${path.basename(projectDir)}-observability`
        );
        
        try {
          await observabilityManager.start({
            projectName: `${path.basename(projectDir)}-observability`,
            detach: true
          });
          
          // Wait a moment for observability services to start
          await new Promise(resolve => setTimeout(resolve, 3000));
        } catch (error) {
          spinner.warn('Observability stack failed to start, continuing with core services...');
        }
      }
      
      // Start core APE services with agent scaling
      spinner.text = `Starting APE services with ${agentCount} agents...`;
      
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
    console.log(chalk.cyan('  📋 View logs: ape-load logs'));
    console.log(chalk.cyan('  📊 Check status: ape-load status'));
    console.log(chalk.cyan('  ⏹️  Stop test: ape-load stop'));
    
    // Display scaling information if applicable
    if (agentCount !== runningAgents) {
      console.log(chalk.yellow(`\n⚠️  Note: ${runningAgents}/${agentCount} agents are currently running.`));
      console.log(chalk.yellow('   Some agents may still be starting up.'));
    }
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    spinner.fail(`Failed to start load test: ${errorMessage}`);
    
    // Provide specific troubleshooting based on error type
    console.log(chalk.red('\n🔧 Troubleshooting:'));
    
    if (errorMessage.includes('port') || errorMessage.includes('bind')) {
      console.log(chalk.red('  🔌 Port Conflict Detected:'));
      console.log(chalk.red('    - Another service may be using the same port'));
      console.log(chalk.red('    - Check running containers: docker ps'));
      console.log(chalk.red('    - Stop conflicting services or change ports in config'));
    } else if (errorMessage.includes('network') || errorMessage.includes('subnet')) {
      console.log(chalk.red('  🌐 Network Issue Detected:'));
      console.log(chalk.red('    - Clean up unused networks: docker network prune -f'));
      console.log(chalk.red('    - Check network conflicts: docker network ls'));
    } else if (errorMessage.includes('pull') || errorMessage.includes('image')) {
      console.log(chalk.red('  📦 Docker Image Issue:'));
      console.log(chalk.red('    - Images may not be available publicly yet'));
      console.log(chalk.red('    - This is expected for development versions'));
    } else if (errorMessage.includes('unhealthy') || errorMessage.includes('health')) {
      console.log(chalk.red('  🏥 Service Health Issue:'));
      console.log(chalk.red('    - Check service logs: docker logs <container_name>'));
      console.log(chalk.red('    - Services may need more time to start'));
    }
    
    console.log(chalk.red('\n  📋 General Steps:'));
    console.log(chalk.red('    1. Ensure Docker is running: docker --version'));
    console.log(chalk.red('    2. Check Docker Compose: docker compose version'));
    console.log(chalk.red('    3. Verify configuration: ape-load validate'));
    console.log(chalk.red('    4. Check logs: ape-load logs'));
    
    process.exit(1);
  }
}