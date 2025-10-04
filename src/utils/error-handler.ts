/**
 * Comprehensive error handling utilities for APE
 * 
 * Provides consistent error handling, user-friendly messages,
 * and recovery suggestions across the application.
 */

import chalk from 'chalk';
import { APISpecParsingError, getErrorRecoverySuggestions, isTemporaryError, isConfigurationError } from './api-spec-parser';

// Re-export utility functions for convenience
export { isTemporaryError, isConfigurationError } from './api-spec-parser';

/**
 * Display a comprehensive error message with suggestions and recovery options
 */
export function displayError(error: APISpecParsingError): void {
  console.log(chalk.red(`\n❌ ${error.message}`));

  // Show error code for debugging
  if (error.code) {
    console.log(chalk.gray(`   Error Code: ${error.code}`));
  }

  // Show suggestion if available
  if (error.suggestion) {
    console.log(chalk.yellow(`\n💡 Suggestion: ${error.suggestion}`));
  }

  // Show recovery suggestions
  const suggestions = getErrorRecoverySuggestions(error);
  if (suggestions.length > 0) {
    console.log(chalk.blue('\n🔧 Recovery Options:'));
    suggestions.forEach((suggestion, index) => {
      console.log(chalk.blue(`   ${index + 1}. ${suggestion}`));
    });
  }

  // Show additional context based on error type
  if (isTemporaryError(error)) {
    console.log(chalk.yellow('\n⏱️  This appears to be a temporary issue that may resolve itself.'));
  }

  if (isConfigurationError(error)) {
    console.log(chalk.yellow('\n⚙️  This appears to be a configuration issue that needs to be fixed.'));
  }

  // Show fallback option if error is recoverable
  if (error.isRecoverable) {
    console.log(chalk.green('\n✅ You can continue with manual configuration as a fallback.'));
  }
}

/**
 * Get a short error summary for logging or display
 */
export function getErrorSummary(error: APISpecParsingError): string {
  let summary = `${error.code}: ${error.message}`;
  
  if (error.suggestion) {
    summary += ` (Suggestion: ${error.suggestion})`;
  }
  
  return summary;
}

/**
 * Determine the appropriate user action based on error type
 */
export function getRecommendedAction(error: APISpecParsingError): 'retry' | 'fix_config' | 'manual_fallback' | 'abort' {
  if (isTemporaryError(error)) {
    return 'retry';
  }
  
  if (isConfigurationError(error)) {
    return 'fix_config';
  }
  
  if (error.isRecoverable) {
    return 'manual_fallback';
  }
  
  return 'abort';
}

/**
 * Create a user-friendly error report for support or debugging
 */
export function createErrorReport(error: APISpecParsingError, context?: Record<string, any>): Record<string, any> {
  return {
    timestamp: new Date().toISOString(),
    error: {
      name: error.name,
      message: error.message,
      code: error.code,
      isRecoverable: error.isRecoverable,
      suggestion: error.suggestion,
      metadata: error.metadata
    },
    context: context || {},
    recommendations: getErrorRecoverySuggestions(error),
    errorType: {
      isTemporary: isTemporaryError(error),
      isConfiguration: isConfigurationError(error)
    },
    recommendedAction: getRecommendedAction(error)
  };
}

/**
 * Log error details for debugging (without exposing sensitive information)
 */
export function logErrorDetails(error: APISpecParsingError, context?: Record<string, any>): void {
  const report = createErrorReport(error, context);
  
  // Remove sensitive information before logging
  const sanitizedReport = {
    ...report,
    error: {
      ...report.error,
      metadata: sanitizeMetadata(report.error.metadata)
    }
  };
  
  console.debug('Error Report:', JSON.stringify(sanitizedReport, null, 2));
}

/**
 * Remove sensitive information from error metadata
 */
function sanitizeMetadata(metadata: any): any {
  if (!metadata || typeof metadata !== 'object') {
    return metadata;
  }
  
  const sanitized = { ...metadata };
  
  // Remove potentially sensitive fields
  const sensitiveFields = ['apiKey', 'token', 'password', 'secret', 'auth'];
  sensitiveFields.forEach(field => {
    if (sanitized[field]) {
      sanitized[field] = '[REDACTED]';
    }
  });
  
  // Truncate long values
  Object.keys(sanitized).forEach(key => {
    if (typeof sanitized[key] === 'string' && sanitized[key].length > 200) {
      sanitized[key] = sanitized[key].substring(0, 200) + '... [TRUNCATED]';
    }
  });
  
  return sanitized;
}

/**
 * Validate that an error is an APISpecParsingError and handle it appropriately
 */
export function handleAPISpecError(error: any, context?: Record<string, any>): APISpecParsingError {
  if (error instanceof APISpecParsingError) {
    return error;
  }
  
  // Convert generic errors to APISpecParsingError
  return new APISpecParsingError(
    `Unexpected error: ${error.message || 'Unknown error'}`,
    'UNEXPECTED_ERROR',
    {
      suggestion: 'Please try again or contact support if the issue persists',
      originalError: error.name || 'Unknown',
      context
    }
  );
}