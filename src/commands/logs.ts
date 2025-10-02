import chalk from 'chalk';
import * as fs from 'fs-extra';
import * as path from 'path';
import { DockerComposeManager } from '../utils/docker';

interface LogsOptions {
  follow?: boolean;
  service?: string;
  grep?: string;
  tail: string;
}

export async function logsCommand(options: LogsOptions): Promise<void> {
  try {
    const tailLines = parseInt(options.tail, 10);
    
    if (isNaN(tailLines) || tailLines <= 0) {
      console.error(chalk.red('Invalid tail value. Must be a positive number.'));
      process.exit(1);
    }

    console.log(chalk.blue('📋 APE Service Logs\n'));
    
    // Find the project directory and Docker Compose file
    const projectDir = await findProjectDirectory();
    if (!projectDir) {
      console.error(chalk.red('No APE project found in current directory or parent directories.'));
      console.log(chalk.yellow('💡 Run this command from within an APE project directory.'));
      process.exit(1);
    }

    const dockerManager = new DockerComposeManager(
      projectDir,
      'ape.docker-compose.yml',
      path.basename(projectDir)
    );

    // Check if services are running
    const status = await dockerManager.getStatus();
    if (!status.isRunning) {
      console.log(chalk.yellow('⚠️  No APE services are currently running.'));
      console.log(chalk.yellow('💡 Start the test with: ape-load start'));
      process.exit(0);
    }

    // Display available services if no specific service requested
    if (!options.service) {
      console.log(chalk.cyan('📋 Available services:'));
      status.services.forEach(service => {
        const statusIcon = service.status === 'running' ? '✅' : '❌';
        console.log(`  ${statusIcon} ${service.name}`);
      });
      console.log();
    }

    // Validate service name if provided - Requirements 5.3, 4.2
    if (options.service) {
      const serviceExists = status.services.some(s => s.name === options.service || s.name.includes(options.service || ''));
      if (!serviceExists) {
        console.error(chalk.red(`Service "${options.service}" not found.`));
        console.log(chalk.yellow('Available services:'));
        status.services.forEach(service => {
          console.log(chalk.yellow(`  - ${service.name}`));
        });
        process.exit(1);
      }
      console.log(chalk.yellow(`🔍 Filtering by service: ${options.service}`));
    }
    
    // Display filtering information
    if (options.grep) {
      console.log(chalk.yellow(`🔍 Filtering by pattern: ${options.grep}`));
      
      // Check if grep pattern looks like a trace ID (UUID format)
      const traceIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (traceIdPattern.test(options.grep)) {
        console.log(chalk.cyan(`🔍 Detected trace ID format - searching across all services`));
      }
    }
    
    console.log(chalk.yellow(`📄 Showing last ${tailLines} lines`));
    
    if (options.follow) {
      console.log(chalk.yellow('👀 Following logs... (Press Ctrl+C to exit)\n'));
    } else {
      console.log();
    }

    // Start log streaming - Requirements 5.3, 4.2
    const logProcess = await dockerManager.getLogs({
      service: options.service,
      follow: options.follow,
      tail: tailLines,
      grep: options.grep
    });

    // Handle log output with color coding and formatting
    logProcess.stdout?.on('data', (data) => {
      const lines = data.toString().split('\n');
      
      for (const line of lines) {
        if (line.trim()) {
          formatAndDisplayLogLine(line, options.grep);
        }
      }
    });

    logProcess.stderr?.on('data', (data) => {
      const errorLines = data.toString().split('\n');
      for (const line of errorLines) {
        if (line.trim()) {
          console.error(chalk.red(`ERROR: ${line}`));
        }
      }
    });

    // Handle process termination
    logProcess.on('close', (code) => {
      if (code !== 0 && code !== null) {
        console.error(chalk.red(`\nLog streaming ended with code ${code}`));
      } else {
        console.log(chalk.gray('\nLog streaming ended.'));
      }
    });

    logProcess.on('error', (error) => {
      console.error(chalk.red(`\nLog streaming error: ${error.message}`));
    });

    // Handle Ctrl+C gracefully
    process.on('SIGINT', () => {
      console.log(chalk.yellow('\n\n📋 Stopping log stream...'));
      logProcess.kill('SIGTERM');
      process.exit(0);
    });

    // If not following, wait for the process to complete
    if (!options.follow) {
      await new Promise<void>((resolve) => {
        logProcess.on('close', () => resolve());
      });
    }
    
  } catch (error) {
    console.error(chalk.red(`Failed to retrieve logs: ${error instanceof Error ? error.message : 'Unknown error'}`));
    
    // Provide helpful troubleshooting information
    console.log(chalk.red('\n🔧 Troubleshooting:'));
    console.log(chalk.red('  1. Ensure APE services are running: ape-load status'));
    console.log(chalk.red('  2. Check Docker is running: docker ps'));
    console.log(chalk.red('  3. Verify project directory contains ape.docker-compose.yml'));
    
    process.exit(1);
  }
}

/**
 * Format and display a log line with appropriate coloring and trace ID highlighting
 */
function formatAndDisplayLogLine(line: string, grepPattern?: string): void {
  // Extract timestamp, service name, and message from Docker Compose log format
  const dockerLogPattern = /^(\S+)\s+\|\s+(.+)$/;
  const match = line.match(dockerLogPattern);
  
  if (match) {
    const [, serviceName, message] = match;
    
    // Color code by service type
    const serviceColor = getServiceColor(serviceName);
    const formattedService = chalk.hex(serviceColor)(`[${serviceName}]`);
    
    // Highlight trace IDs in the message - Requirements 4.2
    const formattedMessage = highlightTraceIds(message);
    
    // Highlight grep pattern if specified
    const finalMessage = grepPattern ? highlightGrepPattern(formattedMessage, grepPattern) : formattedMessage;
    
    console.log(`${formattedService} ${finalMessage}`);
  } else {
    // Fallback for non-standard log formats
    const formattedLine = highlightTraceIds(line);
    const finalLine = grepPattern ? highlightGrepPattern(formattedLine, grepPattern) : formattedLine;
    console.log(finalLine);
  }
}

/**
 * Get color for service based on service type
 */
function getServiceColor(serviceName: string): string {
  if (serviceName.includes('llama_agent') || serviceName.includes('agent')) {
    return '#00ff00'; // Green for agents
  } else if (serviceName.includes('mcp_gateway') || serviceName.includes('gateway')) {
    return '#0099ff'; // Blue for gateway
  } else if (serviceName.includes('cerebras_proxy') || serviceName.includes('proxy')) {
    return '#ff6600'; // Orange for proxy
  } else if (serviceName.includes('prometheus') || serviceName.includes('grafana')) {
    return '#ff0099'; // Pink for monitoring
  } else if (serviceName.includes('loki') || serviceName.includes('promtail')) {
    return '#9900ff'; // Purple for logging
  } else {
    return '#666666'; // Gray for others
  }
}

/**
 * Highlight trace IDs in log messages - Requirements 4.2
 */
function highlightTraceIds(message: string): string {
  // Pattern to match UUIDs (trace IDs)
  const traceIdPattern = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
  
  return message.replace(traceIdPattern, (match) => {
    return chalk.bgYellow.black(match);
  });
}

/**
 * Highlight grep pattern in log messages
 */
function highlightGrepPattern(message: string, pattern: string): string {
  if (!pattern) return message;
  
  try {
    // Create case-insensitive regex for the pattern
    const regex = new RegExp(`(${pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    
    return message.replace(regex, (match) => {
      return chalk.bgRed.white(match);
    });
  } catch (error) {
    // If regex fails, return original message
    return message;
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