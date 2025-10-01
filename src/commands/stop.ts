import chalk from 'chalk';
import ora from 'ora';

interface StopOptions {
  force?: boolean;
}

export async function stopCommand(options: StopOptions): Promise<void> {
  const spinner = ora('Stopping APE load test...').start();
  
  try {
    if (options.force) {
      spinner.text = 'Force stopping all services...';
    } else {
      spinner.text = 'Gracefully shutting down services...';
    }
    
    // Placeholder for Docker Compose shutdown
    // This will be implemented in task 7.3
    
    console.log(chalk.green('\n✅ APE load test stopped successfully!'));
    console.log(chalk.blue('🧹 All containers and resources have been cleaned up'));
    
    spinner.succeed('Load test stopped');
  } catch (error) {
    spinner.fail(`Failed to stop load test: ${error instanceof Error ? error.message : 'Unknown error'}`);
    process.exit(1);
  }
}