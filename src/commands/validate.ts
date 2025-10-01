/**
 * Performance validation command for APE CLI
 * Implements task 10.2: Validate performance targets and KPIs
 */

import { Command } from 'commander';
import chalk from 'chalk';
import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import ora from 'ora';

interface ValidationOptions {
  maxAgents?: string;
  testDuration?: string;
  skipOptimization?: boolean;
  output?: string;
  project?: string;
  quick?: boolean;
}

export function createValidateCommand(): Command {
  const validateCmd = new Command('validate');
  
  validateCmd
    .description('Validate performance targets and KPIs')
    .option('-a, --max-agents <number>', 'Maximum number of agents to test', '1000')
    .option('-d, --test-duration <minutes>', 'Test duration in minutes', '30')
    .option('--skip-optimization', 'Skip KPI optimization analysis')
    .option('-o, --output <file>', 'Output file for validation report')
    .option('-p, --project <name>', 'Project name', 'ape')
    .option('-q, --quick', 'Run quick validation (reduced scope)')
    .action(validateCommand);
  
  return validateCmd;
}

export async function validateCommand(options: ValidationOptions): Promise<void> {
  console.log(chalk.blue.bold('\n🚀 APE Performance Validation\n'));
  
  try {
    // Adjust parameters for quick validation
    if (options.quick) {
      options.maxAgents = '100';
      options.testDuration = '10';
      options.skipOptimization = true;
      console.log(chalk.yellow('⚡ Quick validation mode enabled (reduced scope)\n'));
    }
    
    // Check prerequisites
    await checkPrerequisites();
    
    // Determine script path
    const scriptPath = path.join(process.cwd(), 'scripts', 'run-performance-tests.py');
    
    if (!fs.existsSync(scriptPath)) {
      throw new Error(`Performance validation script not found: ${scriptPath}`);
    }
    
    // Prepare command arguments
    const args = [
      scriptPath,
      '--max-agents', options.maxAgents || '1000',
      '--test-duration', options.testDuration || '30',
      '--project', options.project || 'ape'
    ];
    
    if (options.skipOptimization) {
      args.push('--skip-optimization');
    }
    
    if (options.output) {
      args.push('--output', options.output);
    }
    
    // Start validation
    const spinner = ora('Initializing performance validation...').start();
    
    console.log(chalk.gray(`Running: python ${args.join(' ')}\n`));
    
    const validationProcess = spawn('python', args, {
      stdio: ['inherit', 'pipe', 'pipe'],
      cwd: process.cwd()
    });
    
    let stdout = '';
    let stderr = '';
    
    validationProcess.stdout?.on('data', (data) => {
      const output = data.toString();
      stdout += output;
      
      // Update spinner with progress information
      if (output.includes('Starting comprehensive performance test suite')) {
        spinner.text = 'Starting comprehensive performance test suite...';
      } else if (output.includes('Performing pre-test system checks')) {
        spinner.text = 'Performing pre-test system checks...';
      } else if (output.includes('Running performance validation tests')) {
        spinner.text = 'Running performance validation tests...';
      } else if (output.includes('Testing scaling to')) {
        const match = output.match(/Testing scaling to (\d+) agents/);
        if (match) {
          spinner.text = `Testing scaling to ${match[1]} agents...`;
        }
      } else if (output.includes('Validating sustained load performance')) {
        spinner.text = 'Validating sustained load performance...';
      } else if (output.includes('Running KPI optimization analysis')) {
        spinner.text = 'Running KPI optimization analysis...';
      } else if (output.includes('Comprehensive performance tests completed')) {
        spinner.text = 'Finalizing test results...';
      }
      
      // Print real-time output for important messages
      if (output.includes('✅') || output.includes('❌') || output.includes('⚠️')) {
        spinner.stop();
        console.log(output.trim());
        spinner.start();
      }
    });
    
    validationProcess.stderr?.on('data', (data) => {
      stderr += data.toString();
    });
    
    const exitCode = await new Promise<number>((resolve) => {
      validationProcess.on('close', resolve);
    });
    
    spinner.stop();
    
    if (exitCode === 0) {
      console.log(chalk.green.bold('\n✅ Performance validation completed successfully!\n'));
      
      // Parse and display summary from stdout
      displayValidationSummary(stdout);
      
      if (options.output) {
        console.log(chalk.blue(`📄 Detailed report saved to: ${options.output}\n`));
      }
      
    } else {
      console.log(chalk.red.bold('\n❌ Performance validation failed!\n'));
      
      if (stderr) {
        console.log(chalk.red('Error details:'));
        console.log(stderr);
      }
      
      // Still try to display any summary information
      if (stdout) {
        displayValidationSummary(stdout);
      }
      
      process.exit(1);
    }
    
  } catch (error) {
    console.error(chalk.red.bold('\n❌ Performance validation failed:'));
    console.error(chalk.red(error instanceof Error ? error.message : String(error)));
    process.exit(1);
  }
}

async function checkPrerequisites(): Promise<void> {
  const spinner = ora('Checking prerequisites...').start();
  
  try {
    // Check if Python is available
    await new Promise<void>((resolve, reject) => {
      const pythonCheck = spawn('python', ['--version'], { stdio: 'pipe' });
      pythonCheck.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error('Python is not available. Please install Python 3.7+'));
        }
      });
      pythonCheck.on('error', () => {
        reject(new Error('Python is not available. Please install Python 3.7+'));
      });
    });
    
    // Check if Docker is available
    await new Promise<void>((resolve, reject) => {
      const dockerCheck = spawn('docker', ['--version'], { stdio: 'pipe' });
      dockerCheck.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error('Docker is not available. Please install Docker'));
        }
      });
      dockerCheck.on('error', () => {
        reject(new Error('Docker is not available. Please install Docker'));
      });
    });
    
    // Check if compose file exists
    const composeFile = path.join(process.cwd(), 'ape.docker-compose.yml');
    if (!fs.existsSync(composeFile)) {
      throw new Error('Docker Compose file not found. Please run setup first.');
    }
    
    spinner.succeed('Prerequisites check passed');
    
  } catch (error) {
    spinner.fail('Prerequisites check failed');
    throw error;
  }
}

function displayValidationSummary(stdout: string): void {
  try {
    // Extract summary information from stdout
    const lines = stdout.split('\n');
    
    let inSummarySection = false;
    let summaryLines: string[] = [];
    
    for (const line of lines) {
      if (line.includes('APE COMPREHENSIVE PERFORMANCE TEST RESULTS')) {
        inSummarySection = true;
        continue;
      }
      
      if (inSummarySection) {
        if (line.includes('='.repeat(50)) && summaryLines.length > 0) {
          break; // End of summary section
        }
        
        if (line.trim()) {
          summaryLines.push(line);
        }
      }
    }
    
    if (summaryLines.length > 0) {
      console.log(chalk.cyan.bold('📊 Validation Summary:'));
      summaryLines.forEach(line => {
        if (line.includes('Overall Status:')) {
          if (line.includes('PASS')) {
            console.log(chalk.green(line));
          } else {
            console.log(chalk.red(line));
          }
        } else if (line.includes('✅')) {
          console.log(chalk.green(line));
        } else if (line.includes('❌')) {
          console.log(chalk.red(line));
        } else if (line.includes('⚠️')) {
          console.log(chalk.yellow(line));
        } else {
          console.log(line);
        }
      });
      console.log();
    }
    
    // Extract and display next steps
    let inNextStepsSection = false;
    let nextStepsLines: string[] = [];
    
    for (const line of lines) {
      if (line.includes('📋 Next Steps:')) {
        inNextStepsSection = true;
        continue;
      }
      
      if (inNextStepsSection) {
        if (line.includes('='.repeat(50))) {
          break;
        }
        
        if (line.trim() && line.includes('   ')) {
          nextStepsLines.push(line.trim());
        }
      }
    }
    
    if (nextStepsLines.length > 0) {
      console.log(chalk.cyan.bold('📋 Next Steps:'));
      nextStepsLines.forEach(line => {
        if (line.includes('✅')) {
          console.log(chalk.green(`  ${line}`));
        } else if (line.includes('❌')) {
          console.log(chalk.red(`  ${line}`));
        } else if (line.includes('🚨')) {
          console.log(chalk.red.bold(`  ${line}`));
        } else {
          console.log(chalk.blue(`  ${line}`));
        }
      });
      console.log();
    }
    
  } catch (error) {
    // If parsing fails, just show the raw output
    console.log(chalk.gray('Raw validation output:'));
    console.log(stdout);
  }
}

// Additional utility functions for validation
export async function quickValidate(): Promise<boolean> {
  try {
    await validateCommand({ 
      quick: true,
      maxAgents: '50',
      testDuration: '5',
      skipOptimization: true
    });
    return true;
  } catch {
    return false;
  }
}

export async function validateScaling(maxAgents: number): Promise<boolean> {
  try {
    await validateCommand({
      maxAgents: maxAgents.toString(),
      testDuration: '15',
      skipOptimization: true
    });
    return true;
  } catch {
    return false;
  }
}

export async function validateKPIs(): Promise<boolean> {
  try {
    await validateCommand({
      maxAgents: '100',
      testDuration: '20',
      skipOptimization: false
    });
    return true;
  } catch {
    return false;
  }
}