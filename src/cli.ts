#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { startCommand } from './commands/start';
import { stopCommand } from './commands/stop';
import { statusCommand } from './commands/status';
import { logsCommand } from './commands/logs';
import { createScaleCommand } from './commands/scale';
import { validateCommand } from './commands/validate';
import { version } from '../package.json';

const program = new Command();

program
  .name('ape-test')
  .description('Agentic Protocol Engine - AI-driven load testing tool')
  .version(version);

// Start command - Requirements 5.3, 6.1, 6.4
program
  .command('start')
  .description('Start load test with specified number of agents')
  .option('-a, --agents <number>', 'Number of concurrent agents to deploy', '10')
  .option('-c, --config <path>', 'Path to configuration file', './ape.config.json')
  .option('-d, --duration <minutes>', 'Test duration in minutes', '5')
  .action(startCommand);

// Stop command - Requirements 5.3
program
  .command('stop')
  .description('Stop running load test and cleanup resources')
  .option('-f, --force', 'Force stop without graceful shutdown')
  .action(stopCommand);

// Status command - Requirements 5.3
program
  .command('status')
  .description('Show current test status and metrics')
  .option('-w, --watch', 'Watch mode for real-time updates')
  .action(statusCommand);

// Logs command - Requirements 5.3, 4.2
program
  .command('logs')
  .description('View logs from running services')
  .option('-f, --follow', 'Follow log output')
  .option('-s, --service <name>', 'Filter logs by service name')
  .option('-g, --grep <pattern>', 'Filter logs by pattern or trace ID')
  .option('-t, --tail <lines>', 'Number of lines to show from end', '100')
  .action(logsCommand);

// Scale command - Requirements 6.1, 6.4
program.addCommand(createScaleCommand());

// Validate command - Requirements 5.4, 8.4
program
  .command('validate')
  .description('Validate APE configuration files for production readiness')
  .option('-c, --config <path>', 'Path to main configuration file')
  .option('-m, --mcp <path>', 'Path to MCP Gateway configuration file')
  .option('-p, --project <path>', 'Path to project directory')
  .option('--fix', 'Attempt to fix common configuration issues')
  .option('-v, --verbose', 'Show detailed validation information')
  .action(validateCommand);

// Error handling
program.on('command:*', () => {
  console.error(chalk.red(`Invalid command: ${program.args.join(' ')}`));
  console.log(chalk.yellow('See --help for a list of available commands.'));
  process.exit(1);
});

// Parse command line arguments
program.parse();

// Show help if no command provided
if (!process.argv.slice(2).length) {
  program.outputHelp();
}