#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { setupWizard } from './commands/setup';
import { version } from '../package.json';

const program = new Command();

program
  .name('create-ape-load')
  .description('Create and configure a new APE load test environment')
  .version(version);

// Main setup command - Requirements 5.1, 5.2
program
  .argument('[project-name]', 'Name of the test project directory')
  .option('-t, --template <type>', 'Template type (rest-api, graphql, web-app)', 'rest-api')
  .option('-y, --yes', 'Skip interactive prompts and use defaults')
  .option('-o, --output <path>', 'Output directory for generated files', '.')
  .description('Interactive setup wizard for APE load test configuration')
  .action(setupWizard);

// Error handling
program.on('command:*', () => {
  console.error(chalk.red(`Invalid command: ${program.args.join(' ')}`));
  console.log(chalk.yellow('See --help for a list of available commands.'));
  process.exit(1);
});

// Parse command line arguments
program.parse();

// Show help if no arguments provided
if (!process.argv.slice(2).length) {
  console.log(chalk.blue('🤖 Welcome to Agentic Protocol Engine Setup!'));
  console.log();
  program.outputHelp();
}