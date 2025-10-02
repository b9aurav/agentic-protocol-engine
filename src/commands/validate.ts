import chalk from 'chalk';
import * as fs from 'fs-extra';
import * as path from 'path';
import { 
  validateConfiguration, 
  validateMCPConfiguration, 
  validateProjectStructure,
  formatValidationResults,
  ConfigValidationResult
} from '../utils/config-validator';
import { SetupAnswers } from './setup';
import { MCPGatewayConfig } from '../templates/mcp-gateway';
import { ApplicationType } from '../templates/application-types';

interface ValidateOptions {
  config?: string;
  mcp?: string;
  project?: string;
  fix?: boolean;
  verbose?: boolean;
}

export async function validateCommand(options: ValidateOptions = {}): Promise<void> {
  console.log(chalk.blue('🔍 APE Configuration Validator'));
  console.log(chalk.gray('Validating your APE configuration for production readiness...\n'));

  let hasErrors = false;

  try {
    // Validate project structure if project path is provided
    if (options.project) {
      console.log(chalk.cyan('📁 Validating project structure...'));
      const projectResult = await validateProjectStructure(options.project);
      displayValidationResult('Project Structure', projectResult);
      if (!projectResult.valid) hasErrors = true;
    }

    // Validate main configuration file
    if (options.config) {
      console.log(chalk.cyan('⚙️  Validating main configuration...'));
      const configResult = await validateConfigFile(options.config);
      displayValidationResult('Main Configuration', configResult);
      if (!configResult.valid) hasErrors = true;
    }

    // Validate MCP Gateway configuration
    if (options.mcp) {
      console.log(chalk.cyan('🌐 Validating MCP Gateway configuration...'));
      const mcpResult = await validateMCPConfigFile(options.mcp);
      displayValidationResult('MCP Gateway Configuration', mcpResult);
      if (!mcpResult.valid) hasErrors = true;
    }

    // Auto-detect and validate if no specific files provided
    if (!options.config && !options.mcp && !options.project) {
      console.log(chalk.cyan('🔍 Auto-detecting configuration files...'));
      await autoValidateCurrentDirectory(options);
    }

    // Summary
    console.log(chalk.blue('\n📊 Validation Summary'));
    if (hasErrors) {
      console.log(chalk.red('❌ Configuration validation failed'));
      console.log(chalk.yellow('💡 Fix the errors above before deploying to production'));
      process.exit(1);
    } else {
      console.log(chalk.green('✅ All validations passed'));
      console.log(chalk.gray('Your configuration is ready for production deployment'));
    }

  } catch (error) {
    console.error(chalk.red(`Validation failed: ${error instanceof Error ? error.message : 'Unknown error'}`));
    process.exit(1);
  }
}

async function validateConfigFile(configPath: string): Promise<ConfigValidationResult> {
  try {
    if (!await fs.pathExists(configPath)) {
      return {
        valid: false,
        errors: [{ field: 'file', message: `Configuration file not found: ${configPath}`, code: 'FILE_NOT_FOUND', severity: 'error' }],
        warnings: [],
        suggestions: []
      };
    }

    const configContent = await fs.readJSON(configPath);
    
    // Convert config to SetupAnswers format for validation
    const setupAnswers: SetupAnswers = {
      projectName: configContent.project?.name || 'unknown',
      targetUrl: configContent.target?.url || '',
      targetPort: configContent.target?.port || 80,
      authType: configContent.target?.auth?.type || 'none',
      authToken: configContent.target?.auth?.token,
      authUsername: configContent.target?.auth?.username,
      authPassword: configContent.target?.auth?.password,
      agentCount: configContent.agents?.count || 1,
      testDuration: configContent.test?.duration || 5,
      testGoal: configContent.agents?.goal || '',
      endpoints: configContent.target?.endpoints || [],
      customHeaders: configContent.target?.headers || {},
      applicationType: configContent.applicationType as ApplicationType
    };

    return validateConfiguration(setupAnswers, setupAnswers.applicationType);

  } catch (error) {
    return {
      valid: false,
      errors: [{ 
        field: 'file', 
        message: `Error reading configuration file: ${error instanceof Error ? error.message : 'Unknown error'}`, 
        code: 'FILE_READ_ERROR', 
        severity: 'error' 
      }],
      warnings: [],
      suggestions: []
    };
  }
}

async function validateMCPConfigFile(mcpConfigPath: string): Promise<ConfigValidationResult> {
  try {
    if (!await fs.pathExists(mcpConfigPath)) {
      return {
        valid: false,
        errors: [{ field: 'file', message: `MCP configuration file not found: ${mcpConfigPath}`, code: 'FILE_NOT_FOUND', severity: 'error' }],
        warnings: [],
        suggestions: []
      };
    }

    const mcpConfig: MCPGatewayConfig = await fs.readJSON(mcpConfigPath);
    return validateMCPConfiguration(mcpConfig);

  } catch (error) {
    return {
      valid: false,
      errors: [{ 
        field: 'file', 
        message: `Error reading MCP configuration file: ${error instanceof Error ? error.message : 'Unknown error'}`, 
        code: 'FILE_READ_ERROR', 
        severity: 'error' 
      }],
      warnings: [],
      suggestions: []
    };
  }
}

async function autoValidateCurrentDirectory(_options: ValidateOptions): Promise<void> {
  const currentDir = process.cwd();
  
  // Check for common APE configuration files
  const configFiles = [
    { path: 'ape.config.json', type: 'main' },
    { path: 'ape.mcp-gateway.json', type: 'mcp' },
    { path: '.', type: 'project' }
  ];

  let foundFiles = false;

  for (const configFile of configFiles) {
    const fullPath = path.join(currentDir, configFile.path);
    
    if (configFile.type === 'project' || await fs.pathExists(fullPath)) {
      foundFiles = true;
      
      console.log(chalk.gray(`Found ${configFile.type} configuration: ${configFile.path}`));
      
      let result: ConfigValidationResult;
      
      switch (configFile.type) {
        case 'main':
          result = await validateConfigFile(fullPath);
          displayValidationResult('Main Configuration', result);
          break;
        case 'mcp':
          result = await validateMCPConfigFile(fullPath);
          displayValidationResult('MCP Gateway Configuration', result);
          break;
        case 'project':
          result = await validateProjectStructure(currentDir);
          displayValidationResult('Project Structure', result);
          break;
      }
    }
  }

  if (!foundFiles) {
    console.log(chalk.yellow('⚠️  No APE configuration files found in current directory'));
    console.log(chalk.gray('Run "ape-test setup" to create a new configuration'));
  }
}

function displayValidationResult(title: string, result: ConfigValidationResult): void {
  console.log(chalk.bold(`\n${title}:`));
  
  if (result.valid) {
    console.log(chalk.green('  ✅ Valid'));
  } else {
    console.log(chalk.red('  ❌ Invalid'));
  }

  // Display errors
  if (result.errors.length > 0) {
    console.log(chalk.red('\n  🚨 Errors:'));
    result.errors.forEach(error => {
      console.log(chalk.red(`    • ${error.field}: ${error.message}`));
      if (error.code) {
        console.log(chalk.gray(`      Code: ${error.code}`));
      }
    });
  }

  // Display warnings
  if (result.warnings.length > 0) {
    console.log(chalk.yellow('\n  ⚠️  Warnings:'));
    result.warnings.forEach(warning => {
      console.log(chalk.yellow(`    • ${warning.field}: ${warning.message}`));
      if (warning.suggestion) {
        console.log(chalk.gray(`      💡 ${warning.suggestion}`));
      }
    });
  }

  // Display suggestions
  if (result.suggestions.length > 0) {
    console.log(chalk.cyan('\n  💡 Suggestions:'));
    result.suggestions.forEach(suggestion => {
      console.log(chalk.cyan(`    • ${suggestion.field}: ${suggestion.message}`));
      console.log(chalk.gray(`      Reason: ${suggestion.reason}`));
      if (suggestion.suggestedValue !== undefined) {
        console.log(chalk.gray(`      Suggested: ${JSON.stringify(suggestion.suggestedValue)}`));
      }
    });
  }
}

// Export validation utilities for use in other commands
export { validateConfiguration, validateMCPConfiguration, validateProjectStructure, formatValidationResults };