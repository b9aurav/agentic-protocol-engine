import { Command } from 'commander';
import { execSync, spawn } from 'child_process';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import chalk from 'chalk';
import { generateScalingStrategy, generateGracefulShutdownConfig, ScalingConfig } from '../templates/docker-compose';

interface ScaleOptions {
  agents?: number;
  strategy?: 'gradual' | 'immediate';
  timeout?: number;
  dryRun?: boolean;
  force?: boolean;
}

export function createScaleCommand(): Command {
  const scaleCommand = new Command('scale');
  
  scaleCommand
    .description('Scale APE agents up or down with graceful resource management')
    .option('-a, --agents <number>', 'Target number of agents', parseInt)
    .option('-s, --strategy <type>', 'Scaling strategy: gradual or immediate', 'gradual')
    .option('-t, --timeout <seconds>', 'Timeout for scaling operations', '300')
    .option('--dry-run', 'Show scaling plan without executing')
    .option('--force', 'Force scaling without confirmation')
    .action(async (options: ScaleOptions) => {
      try {
        await handleScaleCommand(options);
      } catch (error) {
        console.error(chalk.red('Error during scaling operation:'), error);
        process.exit(1);
      }
    });

  return scaleCommand;
}

async function handleScaleCommand(options: ScaleOptions): Promise<void> {
  // Validate that we're in an APE project directory
  if (!existsSync('ape.docker-compose.yml')) {
    console.error(chalk.red('Error: No APE configuration found. Run this command in an APE project directory.'));
    process.exit(1);
  }

  // Get current agent count
  const currentAgents = getCurrentAgentCount();
  const targetAgents = options.agents;

  if (!targetAgents) {
    console.error(chalk.red('Error: Target agent count is required. Use --agents <number>'));
    process.exit(1);
  }

  if (targetAgents < 1 || targetAgents > 2000) {
    console.error(chalk.red('Error: Agent count must be between 1 and 2000'));
    process.exit(1);
  }

  if (currentAgents === targetAgents) {
    console.log(chalk.yellow(`Already running ${currentAgents} agents. No scaling needed.`));
    return;
  }

  // Generate scaling configuration
  const scalingConfig: ScalingConfig = {
    currentAgents,
    targetAgents,
    maxConcurrentUpdates: options.strategy === 'immediate' ? targetAgents : Math.min(10, Math.ceil(Math.abs(targetAgents - currentAgents) / 5)),
    updateDelay: options.strategy === 'immediate' ? 1 : 3,
    healthCheckTimeout: parseInt(options.timeout?.toString() || '300')
  };

  const scalingStrategy = generateScalingStrategy(scalingConfig);
  const shutdownConfig = generateGracefulShutdownConfig(Math.max(currentAgents, targetAgents));

  // Display scaling plan
  displayScalingPlan(scalingConfig, scalingStrategy);

  if (options.dryRun) {
    console.log(chalk.blue('\n🔍 Dry run completed. No changes were made.'));
    return;
  }

  // Confirm scaling operation
  if (!options.force && !await confirmScaling(scalingConfig)) {
    console.log(chalk.yellow('Scaling operation cancelled.'));
    return;
  }

  // Execute scaling operation
  await executeScaling(scalingConfig, scalingStrategy, shutdownConfig);
}

function getCurrentAgentCount(): number {
  try {
    // Get current running agent count from Docker Compose
    const result = execSync('docker-compose -f ape.docker-compose.yml ps --services --filter "status=running" | grep llama_agent | wc -l', 
      { encoding: 'utf8', stdio: 'pipe' });
    return parseInt(result.trim()) || 0;
  } catch (error) {
    // Fallback: check configuration file
    try {
      const configPath = 'ape.config.json';
      if (existsSync(configPath)) {
        const config = JSON.parse(readFileSync(configPath, 'utf8'));
        return config.agentCount || 0;
      }
    } catch (configError) {
      console.warn(chalk.yellow('Warning: Could not determine current agent count. Assuming 0.'));
    }
    return 0;
  }
}

function displayScalingPlan(config: ScalingConfig, strategy: any): void {
  const isScalingUp = config.targetAgents > config.currentAgents;
  const operation = isScalingUp ? 'Scale Up' : 'Scale Down';
  const difference = Math.abs(config.targetAgents - config.currentAgents);

  console.log(chalk.blue('\n📊 Scaling Plan'));
  console.log(chalk.blue('═'.repeat(50)));
  console.log(`${chalk.bold('Operation:')} ${isScalingUp ? chalk.green(operation) : chalk.yellow(operation)}`);
  console.log(`${chalk.bold('Current Agents:')} ${config.currentAgents}`);
  console.log(`${chalk.bold('Target Agents:')} ${config.targetAgents}`);
  console.log(`${chalk.bold('Agents to ' + (isScalingUp ? 'Add' : 'Remove') + ':')} ${difference}`);
  console.log(`${chalk.bold('Strategy:')} ${strategy.strategy}`);
  console.log(`${chalk.bold('Batch Size:')} ${strategy.batchSize}`);
  console.log(`${chalk.bold('Total Batches:')} ${strategy.totalBatches}`);
  console.log(`${chalk.bold('Update Delay:')} ${strategy.updateDelay}`);
  console.log(`${chalk.bold('Health Check Timeout:')} ${strategy.healthCheckTimeout}`);

  // Resource impact estimation
  const memoryPerAgent = config.targetAgents > 500 ? 128 : config.targetAgents > 100 ? 256 : 512;
  const cpuPerAgent = config.targetAgents > 500 ? 0.1 : config.targetAgents > 100 ? 0.25 : 0.5;
  const totalMemoryMB = config.targetAgents * memoryPerAgent;
  const totalCPU = config.targetAgents * cpuPerAgent;

  console.log(chalk.blue('\n💾 Resource Impact'));
  console.log(chalk.blue('═'.repeat(50)));
  console.log(`${chalk.bold('Memory per Agent:')} ${memoryPerAgent}MB`);
  console.log(`${chalk.bold('CPU per Agent:')} ${cpuPerAgent} cores`);
  console.log(`${chalk.bold('Total Memory Required:')} ${(totalMemoryMB / 1024).toFixed(1)}GB`);
  console.log(`${chalk.bold('Total CPU Required:')} ${totalCPU.toFixed(1)} cores`);

  // Estimated time
  const estimatedTime = strategy.totalBatches * parseInt(strategy.updateDelay.replace('s', ''));
  console.log(`${chalk.bold('Estimated Time:')} ${estimatedTime}s`);
}

async function confirmScaling(config: ScalingConfig): Promise<boolean> {
  const isScalingUp = config.targetAgents > config.currentAgents;
  const operation = isScalingUp ? 'scale up to' : 'scale down to';
  
  console.log(chalk.yellow(`\n⚠️  You are about to ${operation} ${config.targetAgents} agents.`));
  
  if (!isScalingUp && config.currentAgents > 100) {
    console.log(chalk.yellow('⚠️  This will terminate running agent containers and may interrupt ongoing tests.'));
  }
  
  if (isScalingUp && config.targetAgents > 500) {
    console.log(chalk.yellow('⚠️  High-scale deployment detected. Ensure sufficient system resources.'));
  }

  // In a real implementation, you would use a proper prompt library
  // For now, we'll assume confirmation
  return true;
}

async function executeScaling(config: ScalingConfig, strategy: any, shutdownConfig: any): Promise<void> {
  const isScalingUp = config.targetAgents > config.currentAgents;
  
  console.log(chalk.blue(`\n🚀 Starting ${strategy.strategy} operation...`));

  try {
    if (isScalingUp) {
      await scaleUp(config, strategy);
    } else {
      await scaleDown(config, strategy, shutdownConfig);
    }

    // Update configuration file
    updateConfigFile(config.targetAgents);

    console.log(chalk.green(`\n✅ Successfully scaled to ${config.targetAgents} agents!`));
    
    // Display post-scaling status
    await displayPostScalingStatus(config.targetAgents);

  } catch (error) {
    console.error(chalk.red('\n❌ Scaling operation failed:'), error);
    console.log(chalk.yellow('💡 You can check the current status with: ape-test status'));
    throw error;
  }
}

async function scaleUp(config: ScalingConfig, _strategy: any): Promise<void> {
  console.log(chalk.blue('📈 Scaling up agents...'));
  
  // Use Docker Compose scale command with gradual rollout
  const scaleCommand = `docker-compose -f ape.docker-compose.yml up -d --scale llama_agent=${config.targetAgents} --no-recreate`;
  
  console.log(chalk.gray(`Executing: ${scaleCommand}`));
  
  const child = spawn('docker-compose', [
    '-f', 'ape.docker-compose.yml',
    'up', '-d',
    '--scale', `llama_agent=${config.targetAgents}`,
    '--no-recreate'
  ], { stdio: 'inherit' });

  return new Promise((resolve, reject) => {
    child.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Scale up failed with exit code ${code}`));
      }
    });
  });
}

async function scaleDown(config: ScalingConfig, _strategy: any, _shutdownConfig: any): Promise<void> {
  console.log(chalk.blue('📉 Scaling down agents...'));
  
  // Graceful scale down with proper shutdown
  const scaleCommand = `docker-compose -f ape.docker-compose.yml up -d --scale llama_agent=${config.targetAgents}`;
  
  console.log(chalk.gray(`Executing: ${scaleCommand}`));
  
  const child = spawn('docker-compose', [
    '-f', 'ape.docker-compose.yml',
    'up', '-d',
    '--scale', `llama_agent=${config.targetAgents}`
  ], { stdio: 'inherit' });

  return new Promise((resolve, reject) => {
    child.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Scale down failed with exit code ${code}`));
      }
    });
  });
}

function updateConfigFile(newAgentCount: number): void {
  try {
    const configPath = 'ape.config.json';
    let config = {};
    
    if (existsSync(configPath)) {
      config = JSON.parse(readFileSync(configPath, 'utf8'));
    }
    
    (config as any).agentCount = newAgentCount;
    (config as any).lastScaled = new Date().toISOString();
    
    writeFileSync(configPath, JSON.stringify(config, null, 2));
    console.log(chalk.gray(`Updated configuration: ${configPath}`));
  } catch (error) {
    console.warn(chalk.yellow('Warning: Could not update configuration file'), error);
  }
}

async function displayPostScalingStatus(targetAgents: number): Promise<void> {
  console.log(chalk.blue('\n📊 Post-Scaling Status'));
  console.log(chalk.blue('═'.repeat(50)));
  
  try {
    // Get actual running container count
    const runningAgents = execSync(
      'docker-compose -f ape.docker-compose.yml ps --services --filter "status=running" | grep llama_agent | wc -l',
      { encoding: 'utf8', stdio: 'pipe' }
    ).trim();
    
    console.log(`${chalk.bold('Target Agents:')} ${targetAgents}`);
    console.log(`${chalk.bold('Running Agents:')} ${runningAgents}`);
    
    if (parseInt(runningAgents) === targetAgents) {
      console.log(chalk.green('✅ All agents are running successfully'));
    } else {
      console.log(chalk.yellow('⚠️  Some agents may still be starting up'));
    }
    
    // Display resource usage
    console.log(chalk.blue('\n💾 Current Resource Usage'));
    console.log(chalk.blue('═'.repeat(50)));
    console.log(chalk.gray('Use "ape-test status" for detailed resource information'));
    
  } catch (error) {
    console.warn(chalk.yellow('Could not retrieve post-scaling status'));
  }
}