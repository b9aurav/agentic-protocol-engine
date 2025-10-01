import chalk from 'chalk';
import ora from 'ora';
import * as fs from 'fs-extra';
import * as path from 'path';
import { DockerComposeManager } from '../utils/docker';

interface StopOptions {
  force?: boolean;
}

export async function stopCommand(options: StopOptions): Promise<void> {
  const spinner = ora('Stopping APE load test...').start();
  
  try {
    // Find the project directory
    const projectDir = await findProjectDirectory();
    if (!projectDir) {
      spinner.info('No APE project found in current directory or parent directories.');
      console.log(chalk.yellow('💡 Run this command from within an APE project directory.'));
      return;
    }

    const dockerManager = new DockerComposeManager(
      projectDir,
      'ape.docker-compose.yml',
      path.basename(projectDir)
    );

    // Check current status
    spinner.text = 'Checking current status...';
    const status = await dockerManager.getStatus();
    
    if (!status.isRunning) {
      spinner.info('No APE services are currently running.');
      console.log(chalk.yellow('💡 Services are already stopped.'));
      return;
    }

    // Display what will be stopped
    const runningServices = status.services.filter(s => s.status === 'running');
    console.log(chalk.cyan(`\n📋 Stopping ${runningServices.length} running services:`));
    runningServices.forEach(service => {
      console.log(chalk.cyan(`  🔄 ${service.name}`));
    });

    if (options.force) {
      spinner.text = 'Force stopping all services...';
      console.log(chalk.yellow('\n⚠️  Force stop will immediately kill all containers'));
    } else {
      spinner.text = 'Gracefully shutting down services...';
      console.log(chalk.blue('\n🔄 Graceful shutdown will allow containers to clean up properly'));
    }
    
    // Stop services - Requirements 5.3
    await dockerManager.stop(options.force);
    
    // Verify all services are stopped
    spinner.text = 'Verifying shutdown...';
    const finalStatus = await dockerManager.getStatus();
    const stillRunning = finalStatus.services.filter(s => s.status === 'running');
    
    if (stillRunning.length > 0) {
      spinner.warn(`${stillRunning.length} services are still running:`);
      stillRunning.forEach(service => {
        console.log(chalk.yellow(`  ⚠️  ${service.name} (${service.status})`));
      });
      
      if (!options.force) {
        console.log(chalk.yellow('\n💡 Use --force flag to forcefully stop remaining services'));
      }
    } else {
      spinner.succeed('All services stopped successfully');
    }
    
    console.log(chalk.green('\n✅ APE load test stopped!'));
    console.log(chalk.blue('🧹 All containers and resources have been cleaned up'));
    console.log(chalk.gray(`📁 Project: ${path.basename(projectDir)}`));
    
    // Display cleanup summary
    console.log(chalk.cyan('\n📊 Cleanup Summary:'));
    console.log(chalk.cyan(`  🛑 Stopped: ${runningServices.length} services`));
    console.log(chalk.cyan(`  🗑️  Method: ${options.force ? 'Force kill' : 'Graceful shutdown'}`));
    
    // Provide next steps
    console.log(chalk.yellow('\n💡 Next Steps:'));
    console.log(chalk.yellow('  📊 View final metrics: Check Grafana dashboard before it shuts down'));
    console.log(chalk.yellow('  🔄 Restart test: ape-test start'));
    console.log(chalk.yellow('  📋 Check status: ape-test status'));
    
  } catch (error) {
    spinner.fail(`Failed to stop load test: ${error instanceof Error ? error.message : 'Unknown error'}`);
    
    // Provide helpful troubleshooting information
    console.log(chalk.red('\n🔧 Troubleshooting:'));
    console.log(chalk.red('  1. Check Docker is running: docker ps'));
    console.log(chalk.red('  2. Try force stop: ape-test stop --force'));
    console.log(chalk.red('  3. Manual cleanup: docker compose -f ape.docker-compose.yml down'));
    
    process.exit(1);
  }
}

/**
 * Find the APE project directory by looking for ape.docker-compose.yml
 */
async function findProjectDirectory(): Promise<string | null> {
  let currentDir = process.cwd();
  const maxDepth = 5; // Prevent infinite loops
  let depth = 0;
  
  while (depth < maxDepth) {
    const composeFile = path.join(currentDir, 'ape.docker-compose.yml');
    
    if (await fs.pathExists(composeFile)) {
      return currentDir;
    }
    
    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) {
      // Reached filesystem root
      break;
    }
    
    currentDir = parentDir;
    depth++;
  }
  
  return null;
}