/**
 * API Specification Parser Utility
 * 
 * Uses Cerebras LLM to parse markdown API specifications and extract
 * structured endpoint information for APE load testing configuration.
 */

import * as fs from 'fs-extra';
import * as path from 'path';

/**
 * Custom error class for API specification parsing errors
 */
export class APISpecParsingError extends Error {
  public readonly code: string;
  public readonly metadata?: Record<string, any>;
  public readonly suggestion?: string;
  public readonly isRecoverable: boolean;

  constructor(
    message: string, 
    code: string, 
    metadata?: Record<string, any> & { suggestion?: string }
  ) {
    super(message);
    this.name = 'APISpecParsingError';
    this.code = code;
    this.metadata = metadata;
    this.suggestion = metadata?.suggestion;
    
    // Determine if error is recoverable (can fallback to manual config)
    this.isRecoverable = this.determineRecoverability(code);
    
    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, APISpecParsingError);
    }
  }

  private determineRecoverability(code: string): boolean {
    const nonRecoverableErrors = [
      'MISSING_FILE_PATH',
      'INVALID_FILE_PATH_TYPE',
      'EMPTY_FILE_PATH',
      'INVALID_FILE_PATH_FORMAT'
    ];
    
    return !nonRecoverableErrors.includes(code);
  }

  /**
   * Get a user-friendly error message with suggestions
   */
  public getUserFriendlyMessage(): string {
    let message = this.message;
    
    if (this.suggestion) {
      message += `\n💡 Suggestion: ${this.suggestion}`;
    }
    
    if (this.isRecoverable) {
      message += '\n🔄 You can continue with manual endpoint configuration.';
    }
    
    return message;
  }

  /**
   * Get error details for logging
   */
  public getErrorDetails(): Record<string, any> {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      isRecoverable: this.isRecoverable,
      suggestion: this.suggestion,
      metadata: this.metadata,
      stack: this.stack
    };
  }
}

// Types for parsed API specification
export interface ParsedEndpoint {
  path: string;
  method: string;
  purpose: string;
  parameters?: {
    query?: Record<string, any>;
    path?: Record<string, any>;
    body?: Record<string, any>;
  };
  responses: {
    success: Record<string, any>;
    error?: Record<string, any>[];
  };
  sessionRequired?: boolean;
}

export interface ParsedAPISpec {
  endpoints: ParsedEndpoint[];
  dataModels: Record<string, any>;
  baseUrl?: string;
  commonPatterns: {
    pagination?: boolean;
    sessionManagement?: boolean;
    errorHandling?: string[];
  };
}

export interface CerebrasConfig {
  apiKey: string;
  baseUrl?: string;
  model?: string;
  maxTokens?: number;
  temperature?: number;
}

/**
 * API Specification Parser using Cerebras LLM
 */
export class APISpecParser {
  private config: CerebrasConfig;

  constructor(config: CerebrasConfig) {
    this.config = {
      baseUrl: 'https://api.cerebras.ai',
      model: 'llama3.1-8b',
      maxTokens: 4000,
      temperature: 0.1, // Low temperature for consistent parsing
      ...config
    };

    if (!this.config.apiKey) {
      throw new Error('Cerebras API key is required');
    }
  }

  /**
   * Parse an API specification file with comprehensive error handling
   */
  async parseSpecification(filePath: string): Promise<ParsedAPISpec> {
    try {
      // Validate file exists and is readable
      await this.validateFile(filePath);

      // Read the specification file
      const specContent = await this.readSpecificationFile(filePath);

      // Validate content before parsing
      this.validateSpecificationContent(specContent, filePath);

      // Parse using Cerebras LLM
      const parsedSpec = await this.parseWithLLM(specContent, filePath);

      // Validate the parsed result
      this.validateParsedSpec(parsedSpec);

      return parsedSpec;
    } catch (error: any) {
      if (error instanceof APISpecParsingError) {
        throw error;
      }
      
      // Wrap unexpected errors
      throw new APISpecParsingError(
        `Unexpected error during API specification parsing: ${error.message}`,
        'UNEXPECTED_ERROR',
        { 
          suggestion: 'Please check the file format and try again, or continue with manual configuration',
          originalError: error.name || 'Unknown',
          filePath
        }
      );
    }
  }

  /**
   * Read specification file with error handling
   */
  private async readSpecificationFile(filePath: string): Promise<string> {
    try {
      const content = await fs.readFile(path.resolve(filePath), 'utf-8');
      return content;
    } catch (error: any) {
      if (error.code === 'EISDIR') {
        throw new APISpecParsingError(
          `Path is a directory, not a file: ${filePath}`,
          'PATH_IS_DIRECTORY',
          { suggestion: 'Please provide a path to a file, not a directory' }
        );
      } else if (error.code === 'EACCES') {
        throw new APISpecParsingError(
          `Permission denied reading file: ${filePath}`,
          'READ_PERMISSION_DENIED',
          { suggestion: 'Please check file permissions or run with appropriate privileges' }
        );
      } else if (error.code === 'EMFILE' || error.code === 'ENFILE') {
        throw new APISpecParsingError(
          `Too many open files. Cannot read: ${filePath}`,
          'TOO_MANY_FILES',
          { suggestion: 'Please close other applications and try again' }
        );
      } else {
        throw new APISpecParsingError(
          `Failed to read specification file: ${error.message}`,
          'FILE_READ_ERROR',
          { 
            suggestion: 'Please check the file is accessible and not corrupted',
            originalError: error.code || error.name 
          }
        );
      }
    }
  }

  /**
   * Validate specification content before parsing
   */
  private validateSpecificationContent(content: string, filePath: string): void {
    if (!content || content.trim().length === 0) {
      throw new APISpecParsingError(
        `Specification file is empty: ${filePath}`,
        'EMPTY_SPECIFICATION',
        { suggestion: 'Please provide a non-empty API specification file' }
      );
    }

    // Check for minimum content length (reasonable API spec should have some content)
    if (content.trim().length < 50) {
      throw new APISpecParsingError(
        `Specification file appears to be too short (${content.length} characters): ${filePath}`,
        'SPECIFICATION_TOO_SHORT',
        { suggestion: 'Please ensure the file contains a complete API specification' }
      );
    }

    // Check for common API specification indicators
    const lowerContent = content.toLowerCase();
    const hasApiIndicators = [
      'api', 'endpoint', 'route', 'method', 'get', 'post', 'put', 'delete', 'patch',
      'request', 'response', 'parameter', 'header', 'body', 'json', 'http'
    ].some(indicator => lowerContent.includes(indicator));

    if (!hasApiIndicators) {
      console.warn(`Warning: File does not appear to contain API specification content: ${filePath}`);
      console.warn('The file will still be processed, but parsing may not be successful.');
    }

    // Check for binary content
    const hasBinaryContent = /[\x00-\x08\x0E-\x1F\x7F]/.test(content);
    if (hasBinaryContent) {
      throw new APISpecParsingError(
        `File appears to contain binary content: ${filePath}`,
        'BINARY_CONTENT',
        { suggestion: 'Please provide a text-based API specification file (markdown, JSON, YAML, etc.)' }
      );
    }
  }

  /**
   * Validate that the file exists and is readable with comprehensive checks
   */
  private async validateFile(filePath: string): Promise<void> {
    if (!filePath) {
      throw new APISpecParsingError('File path is required', 'MISSING_FILE_PATH');
    }

    if (typeof filePath !== 'string') {
      throw new APISpecParsingError('File path must be a string', 'INVALID_FILE_PATH_TYPE');
    }

    if (filePath.trim().length === 0) {
      throw new APISpecParsingError('File path cannot be empty', 'EMPTY_FILE_PATH');
    }

    // Validate file path format
    if (filePath.includes('\0')) {
      throw new APISpecParsingError('File path contains invalid null character', 'INVALID_FILE_PATH_FORMAT');
    }

    const resolvedPath = path.resolve(filePath);
    
    try {
      const stats = await fs.stat(resolvedPath);
      
      if (!stats.isFile()) {
        if (stats.isDirectory()) {
          throw new APISpecParsingError(
            `Path is a directory, not a file: ${filePath}`,
            'PATH_IS_DIRECTORY',
            { suggestion: 'Please provide a path to a file, not a directory' }
          );
        } else {
          throw new APISpecParsingError(
            `Path is not a regular file: ${filePath}`,
            'PATH_NOT_FILE',
            { suggestion: 'Please provide a path to a regular file' }
          );
        }
      }

      // Check file size (reasonable limits for API specs)
      const maxFileSize = 10 * 1024 * 1024; // 10MB
      if (stats.size > maxFileSize) {
        throw new APISpecParsingError(
          `File is too large: ${Math.round(stats.size / 1024 / 1024)}MB (max: 10MB)`,
          'FILE_TOO_LARGE',
          { suggestion: 'Please provide a smaller API specification file' }
        );
      }

      if (stats.size === 0) {
        throw new APISpecParsingError(
          `File is empty: ${filePath}`,
          'EMPTY_FILE',
          { suggestion: 'Please provide a non-empty API specification file' }
        );
      }

      // Check file permissions
      try {
        await fs.access(resolvedPath, fs.constants.R_OK);
      } catch (accessError) {
        throw new APISpecParsingError(
          `File is not readable: ${filePath}`,
          'FILE_NOT_READABLE',
          { suggestion: 'Please check file permissions and ensure the file is readable' }
        );
      }

      // Validate file extension (optional but helpful)
      const ext = path.extname(filePath).toLowerCase();
      const supportedExtensions = ['.md', '.markdown', '.txt', '.json', '.yaml', '.yml'];
      if (ext && !supportedExtensions.includes(ext)) {
        console.warn(`Warning: File extension '${ext}' is not commonly used for API specifications. Supported extensions: ${supportedExtensions.join(', ')}`);
      }

    } catch (error: any) {
      if (error instanceof APISpecParsingError) {
        throw error;
      }

      if (error.code === 'ENOENT') {
        throw new APISpecParsingError(
          `File not found: ${filePath}`,
          'FILE_NOT_FOUND',
          { 
            suggestion: 'Please check the file path and ensure the file exists',
            resolvedPath 
          }
        );
      } else if (error.code === 'EACCES') {
        throw new APISpecParsingError(
          `Permission denied accessing file: ${filePath}`,
          'PERMISSION_DENIED',
          { suggestion: 'Please check file permissions or run with appropriate privileges' }
        );
      } else if (error.code === 'EMFILE' || error.code === 'ENFILE') {
        throw new APISpecParsingError(
          `Too many open files. Cannot access: ${filePath}`,
          'TOO_MANY_FILES',
          { suggestion: 'Please close other applications and try again' }
        );
      } else if (error.code === 'ENOTDIR') {
        throw new APISpecParsingError(
          `Invalid path (directory component is not a directory): ${filePath}`,
          'INVALID_PATH',
          { suggestion: 'Please check the directory path components' }
        );
      } else {
        throw new APISpecParsingError(
          `Cannot access file: ${filePath} - ${error.message}`,
          'FILE_ACCESS_ERROR',
          { 
            suggestion: 'Please check the file path and permissions',
            originalError: error.code || error.name 
          }
        );
      }
    }
  }

  /**
   * Parse API specification using Cerebras LLM with enhanced error handling
   */
  private async parseWithLLM(specContent: string, filePath?: string): Promise<ParsedAPISpec> {
    const prompt = this.buildParsingPrompt(specContent);

    try {
      const response = await this.callCerebrasAPI(prompt);
      return this.parseJSONResponse(response, filePath);
    } catch (error: any) {
      if (error instanceof APISpecParsingError) {
        throw error;
      }
      
      // Handle different types of LLM errors
      if (error.message.includes('Network error')) {
        throw new APISpecParsingError(
          'Unable to connect to Cerebras API for parsing',
          'NETWORK_ERROR',
          { 
            suggestion: 'Please check your internet connection and try again',
            isTemporary: true
          }
        );
      } else if (error.message.includes('HTTP 401')) {
        throw new APISpecParsingError(
          'Invalid Cerebras API key',
          'INVALID_API_KEY',
          { 
            suggestion: 'Please check your Cerebras API key and ensure it is valid',
            isConfigurationError: true
          }
        );
      } else if (error.message.includes('HTTP 429')) {
        throw new APISpecParsingError(
          'Cerebras API rate limit exceeded',
          'RATE_LIMIT_EXCEEDED',
          { 
            suggestion: 'Please wait a moment and try again, or upgrade your Cerebras API plan',
            isTemporary: true
          }
        );
      } else if (error.message.includes('HTTP 500') || error.message.includes('HTTP 502') || error.message.includes('HTTP 503')) {
        throw new APISpecParsingError(
          'Cerebras API service is temporarily unavailable',
          'SERVICE_UNAVAILABLE',
          { 
            suggestion: 'Please try again in a few minutes',
            isTemporary: true
          }
        );
      } else if (error.message.includes('timeout')) {
        throw new APISpecParsingError(
          'Parsing request timed out',
          'PARSING_TIMEOUT',
          { 
            suggestion: 'The specification file may be too large or complex. Try with a smaller file or continue with manual configuration',
            isTemporary: true
          }
        );
      } else {
        throw new APISpecParsingError(
          `LLM parsing failed: ${error.message}`,
          'LLM_PARSING_ERROR',
          { 
            suggestion: 'Please try again or continue with manual endpoint configuration',
            originalError: error.name || 'Unknown'
          }
        );
      }
    }
  }

  /**
   * Build structured prompt for API specification parsing
   */
  private buildParsingPrompt(specContent: string): string {
    return `You are an API specification parser. Analyze the following API documentation and extract structured information.

API Specification:
${specContent}

Extract and return a JSON object with the following structure:
{
  "endpoints": [
    {
      "path": "string (e.g., '/api/products')",
      "method": "string (e.g., 'GET', 'POST')",
      "purpose": "string (brief description)",
      "parameters": {
        "query": {"param_name": "description and type"},
        "path": {"param_name": "description and type"},
        "body": {"field_name": "description and type"}
      },
      "responses": {
        "success": {"example": "success response object"},
        "error": [{"code": 400, "example": "error response"}]
      },
      "sessionRequired": boolean
    }
  ],
  "dataModels": {
    "ModelName": {
      "field_name": "type and description"
    }
  },
  "commonPatterns": {
    "pagination": boolean,
    "sessionManagement": boolean,
    "errorHandling": ["pattern1", "pattern2"]
  }
}

Focus on:
- Accurate endpoint paths and HTTP methods
- Required vs optional parameters
- Request body schemas for POST/PUT/PATCH
- Response formats and error codes
- Session/cookie requirements
- Data relationships and workflows
- Common patterns like pagination

Return only valid JSON without additional text or markdown formatting.`;
  }

  /**
   * Call Cerebras API with the parsing prompt and comprehensive error handling
   */
  private async callCerebrasAPI(prompt: string): Promise<string> {
    // Validate API configuration
    if (!this.config.apiKey) {
      throw new APISpecParsingError(
        'Cerebras API key is not configured',
        'MISSING_API_KEY',
        { 
          suggestion: 'Please provide a valid Cerebras API key',
          isConfigurationError: true
        }
      );
    }

    // Validate prompt size
    if (prompt.length > 100000) { // ~100KB limit
      throw new APISpecParsingError(
        'API specification is too large for processing',
        'SPECIFICATION_TOO_LARGE',
        { 
          suggestion: 'Please provide a smaller API specification file or break it into sections',
          promptSize: prompt.length
        }
      );
    }

    const requestBody = {
      model: this.config.model,
      messages: [
        {
          role: 'user',
          content: prompt
        }
      ],
      max_tokens: this.config.maxTokens,
      temperature: this.config.temperature
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

    try {
      // Use Node.js built-in fetch (available in Node 18+)
      const response = await fetch(`${this.config.baseUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.config.apiKey}`,
          'User-Agent': 'APE-LoadTester/1.0'
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorText: string;
        try {
          errorText = await response.text();
        } catch {
          errorText = 'Unable to read error response';
        }

        // Handle specific HTTP status codes
        if (response.status === 401) {
          throw new APISpecParsingError(
            'Invalid or expired Cerebras API key',
            'INVALID_API_KEY',
            { 
              suggestion: 'Please check your Cerebras API key and ensure it is valid and not expired',
              httpStatus: response.status
            }
          );
        } else if (response.status === 403) {
          throw new APISpecParsingError(
            'Access forbidden - insufficient API permissions',
            'INSUFFICIENT_PERMISSIONS',
            { 
              suggestion: 'Please check your Cerebras API key permissions or upgrade your plan',
              httpStatus: response.status
            }
          );
        } else if (response.status === 429) {
          throw new APISpecParsingError(
            'Cerebras API rate limit exceeded',
            'RATE_LIMIT_EXCEEDED',
            { 
              suggestion: 'Please wait a moment and try again, or upgrade your Cerebras API plan',
              httpStatus: response.status,
              isTemporary: true
            }
          );
        } else if (response.status >= 500) {
          throw new APISpecParsingError(
            'Cerebras API service error',
            'SERVICE_ERROR',
            { 
              suggestion: 'The Cerebras API service is experiencing issues. Please try again later',
              httpStatus: response.status,
              isTemporary: true
            }
          );
        } else {
          throw new APISpecParsingError(
            `Cerebras API request failed: HTTP ${response.status}`,
            'API_REQUEST_FAILED',
            { 
              suggestion: 'Please check your request and try again',
              httpStatus: response.status,
              errorDetails: errorText
            }
          );
        }
      }

      let data: any;
      try {
        data = await response.json();
      } catch (parseError) {
        throw new APISpecParsingError(
          'Invalid JSON response from Cerebras API',
          'INVALID_API_RESPONSE',
          { 
            suggestion: 'The API returned an invalid response. Please try again',
            isTemporary: true
          }
        );
      }
      
      // Validate response structure
      if (!data) {
        throw new APISpecParsingError(
          'Empty response from Cerebras API',
          'EMPTY_API_RESPONSE',
          { suggestion: 'Please try again' }
        );
      }

      if (!data.choices || !Array.isArray(data.choices) || data.choices.length === 0) {
        throw new APISpecParsingError(
          'Invalid response format from Cerebras API - no choices',
          'INVALID_RESPONSE_FORMAT',
          { 
            suggestion: 'The API response format is unexpected. Please try again',
            responseStructure: Object.keys(data)
          }
        );
      }

      const choice = data.choices[0];
      if (!choice || !choice.message || typeof choice.message.content !== 'string') {
        throw new APISpecParsingError(
          'Invalid response format from Cerebras API - no message content',
          'INVALID_MESSAGE_FORMAT',
          { 
            suggestion: 'The API response format is unexpected. Please try again',
            choiceStructure: choice ? Object.keys(choice) : 'null'
          }
        );
      }

      const content = choice.message.content.trim();
      if (!content) {
        throw new APISpecParsingError(
          'Empty content in Cerebras API response',
          'EMPTY_RESPONSE_CONTENT',
          { suggestion: 'The API returned empty content. Please try again or check your specification file' }
        );
      }

      return content;

    } catch (error: any) {
      clearTimeout(timeoutId);
      
      if (error instanceof APISpecParsingError) {
        throw error;
      }

      // Handle fetch-specific errors
      if (error.name === 'AbortError') {
        throw new APISpecParsingError(
          'Request to Cerebras API timed out',
          'REQUEST_TIMEOUT',
          { 
            suggestion: 'The request took too long. Please try with a smaller specification file',
            timeout: '60 seconds',
            isTemporary: true
          }
        );
      } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
        throw new APISpecParsingError(
          'Network error: Unable to connect to Cerebras API',
          'NETWORK_ERROR',
          { 
            suggestion: 'Please check your internet connection and try again',
            isTemporary: true
          }
        );
      } else if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
        throw new APISpecParsingError(
          'Cannot connect to Cerebras API',
          'CONNECTION_FAILED',
          { 
            suggestion: 'Please check your internet connection and try again',
            isTemporary: true
          }
        );
      } else {
        throw new APISpecParsingError(
          `Unexpected error calling Cerebras API: ${error.message}`,
          'UNEXPECTED_API_ERROR',
          { 
            suggestion: 'Please try again or continue with manual configuration',
            originalError: error.name || 'Unknown'
          }
        );
      }
    }
  }

  /**
   * Parse and validate JSON response from LLM with comprehensive error handling
   */
  private parseJSONResponse(response: string, filePath?: string): ParsedAPISpec {
    if (!response || response.trim().length === 0) {
      throw new APISpecParsingError(
        'Empty response from LLM',
        'EMPTY_LLM_RESPONSE',
        { suggestion: 'Please try again or check your specification file format' }
      );
    }

    try {
      // Clean up response - remove any markdown formatting
      let cleanResponse = response.trim();
      
      // Remove markdown code blocks if present
      if (cleanResponse.startsWith('```json')) {
        cleanResponse = cleanResponse.replace(/^```json\s*/, '').replace(/\s*```$/, '');
      } else if (cleanResponse.startsWith('```')) {
        cleanResponse = cleanResponse.replace(/^```\s*/, '').replace(/\s*```$/, '');
      }

      // Remove any leading/trailing text that might not be JSON
      const jsonStart = cleanResponse.indexOf('{');
      const jsonEnd = cleanResponse.lastIndexOf('}');
      
      if (jsonStart === -1 || jsonEnd === -1 || jsonStart >= jsonEnd) {
        throw new APISpecParsingError(
          'No valid JSON found in LLM response',
          'NO_JSON_IN_RESPONSE',
          { 
            suggestion: 'The LLM did not return valid JSON. Please try again or check your specification file format',
            responsePreview: response.substring(0, 200)
          }
        );
      }

      cleanResponse = cleanResponse.substring(jsonStart, jsonEnd + 1);

      let parsed: any;
      try {
        parsed = JSON.parse(cleanResponse);
      } catch (jsonError: any) {
        // Try to provide more specific JSON parsing errors
        if (jsonError.message.includes('Unexpected token')) {
          throw new APISpecParsingError(
            'Invalid JSON format in LLM response',
            'INVALID_JSON_FORMAT',
            { 
              suggestion: 'The LLM returned malformed JSON. Please try again',
              jsonError: jsonError.message,
              responsePreview: cleanResponse.substring(0, 200)
            }
          );
        } else if (jsonError.message.includes('Unexpected end')) {
          throw new APISpecParsingError(
            'Incomplete JSON in LLM response',
            'INCOMPLETE_JSON',
            { 
              suggestion: 'The LLM response was cut off. Please try again',
              jsonError: jsonError.message
            }
          );
        } else {
          throw new APISpecParsingError(
            `JSON parsing error: ${jsonError.message}`,
            'JSON_PARSE_ERROR',
            { 
              suggestion: 'The LLM returned invalid JSON. Please try again',
              jsonError: jsonError.message,
              responsePreview: cleanResponse.substring(0, 200)
            }
          );
        }
      }

      // Validate that we got an object
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new APISpecParsingError(
          'LLM response is not a valid object',
          'INVALID_RESPONSE_TYPE',
          { 
            suggestion: 'Expected an object but got ' + (Array.isArray(parsed) ? 'array' : typeof parsed),
            responseType: Array.isArray(parsed) ? 'array' : typeof parsed
          }
        );
      }

      return parsed as ParsedAPISpec;

    } catch (error: any) {
      if (error instanceof APISpecParsingError) {
        throw error;
      }
      
      throw new APISpecParsingError(
        `Failed to parse LLM response: ${error.message}`,
        'RESPONSE_PARSING_ERROR',
        { 
          suggestion: 'The LLM response could not be processed. Please try again or continue with manual configuration',
          originalError: error.name || 'Unknown',
          responsePreview: response.substring(0, 200),
          filePath
        }
      );
    }
  }

  /**
   * Validate the parsed specification structure with comprehensive error messages
   */
  private validateParsedSpec(spec: ParsedAPISpec): void {
    if (!spec || typeof spec !== 'object') {
      throw new APISpecParsingError(
        'Parsed specification must be an object',
        'INVALID_SPEC_TYPE',
        { 
          suggestion: 'The LLM did not return a valid specification object. Please try again',
          actualType: typeof spec
        }
      );
    }

    // Validate endpoints array
    if (!spec.hasOwnProperty('endpoints')) {
      throw new APISpecParsingError(
        'Parsed specification is missing endpoints property',
        'MISSING_ENDPOINTS_PROPERTY',
        { 
          suggestion: 'The specification must contain an endpoints array',
          availableProperties: Object.keys(spec)
        }
      );
    }

    if (!Array.isArray(spec.endpoints)) {
      throw new APISpecParsingError(
        'Endpoints must be an array',
        'INVALID_ENDPOINTS_TYPE',
        { 
          suggestion: 'The endpoints property must be an array of endpoint objects',
          actualType: typeof spec.endpoints
        }
      );
    }

    if (spec.endpoints.length === 0) {
      throw new APISpecParsingError(
        'No endpoints found in specification',
        'NO_ENDPOINTS_FOUND',
        { 
          suggestion: 'The specification must contain at least one endpoint. Please check your API specification file format'
        }
      );
    }

    // Validate each endpoint with detailed error reporting
    for (let i = 0; i < spec.endpoints.length; i++) {
      try {
        this.validateEndpoint(spec.endpoints[i], i);
      } catch (error: any) {
        if (error instanceof APISpecParsingError) {
          // Create new error with endpoint index in metadata
          throw new APISpecParsingError(
            error.message,
            error.code,
            { ...error.metadata, endpointIndex: i }
          );
        }
        throw new APISpecParsingError(
          `Invalid endpoint at index ${i}: ${error.message}`,
          'INVALID_ENDPOINT',
          { 
            suggestion: 'Please check the endpoint structure in your specification',
            endpointIndex: i,
            endpoint: spec.endpoints[i]
          }
        );
      }
    }

    // Validate data models if present
    if (spec.dataModels !== undefined) {
      if (typeof spec.dataModels !== 'object' || Array.isArray(spec.dataModels)) {
        throw new APISpecParsingError(
          'Data models must be an object',
          'INVALID_DATA_MODELS_TYPE',
          { 
            suggestion: 'Data models should be an object with model names as keys',
            actualType: Array.isArray(spec.dataModels) ? 'array' : typeof spec.dataModels
          }
        );
      }
    }

    // Validate common patterns if present
    if (spec.commonPatterns !== undefined) {
      if (typeof spec.commonPatterns !== 'object' || Array.isArray(spec.commonPatterns)) {
        throw new APISpecParsingError(
          'Common patterns must be an object',
          'INVALID_COMMON_PATTERNS_TYPE',
          { 
            suggestion: 'Common patterns should be an object with pattern properties',
            actualType: Array.isArray(spec.commonPatterns) ? 'array' : typeof spec.commonPatterns
          }
        );
      }
    }

    // Additional validation for specification quality
    this.validateSpecificationQuality(spec);
  }

  /**
   * Validate specification quality and provide warnings
   */
  private validateSpecificationQuality(spec: ParsedAPISpec): void {
    const warnings: string[] = [];

    // Check for duplicate endpoints
    const endpointKeys = spec.endpoints.map(e => `${e.method.toUpperCase()} ${e.path}`);
    const duplicates = endpointKeys.filter((key, index) => endpointKeys.indexOf(key) !== index);
    if (duplicates.length > 0) {
      warnings.push(`Duplicate endpoints found: ${duplicates.join(', ')}`);
    }

    // Check for endpoints without proper HTTP methods
    const invalidMethods = spec.endpoints.filter(e => 
      !['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].includes(e.method.toUpperCase())
    );
    if (invalidMethods.length > 0) {
      warnings.push(`Endpoints with invalid HTTP methods: ${invalidMethods.map(e => e.path).join(', ')}`);
    }

    // Check for endpoints without descriptions
    const endpointsWithoutPurpose = spec.endpoints.filter(e => !e.purpose || e.purpose.trim().length < 5);
    if (endpointsWithoutPurpose.length > 0) {
      warnings.push(`${endpointsWithoutPurpose.length} endpoints have insufficient descriptions`);
    }

    // Log warnings if any
    if (warnings.length > 0) {
      console.warn('⚠️  Specification quality warnings:');
      warnings.forEach(warning => console.warn(`   - ${warning}`));
    }
  }

  /**
   * Validate individual endpoint structure with detailed error messages
   */
  private validateEndpoint(endpoint: ParsedEndpoint, index?: number): void {
    const endpointRef = index !== undefined ? `endpoint ${index}` : 'endpoint';

    // Validate endpoint is an object
    if (!endpoint || typeof endpoint !== 'object') {
      throw new APISpecParsingError(
        `${endpointRef} must be an object`,
        'INVALID_ENDPOINT_TYPE',
        { 
          suggestion: 'Each endpoint must be an object with path, method, purpose, and responses properties',
          actualType: typeof endpoint,
          endpointIndex: index
        }
      );
    }

    // Validate path
    if (!endpoint.hasOwnProperty('path')) {
      throw new APISpecParsingError(
        `${endpointRef} is missing path property`,
        'MISSING_ENDPOINT_PATH',
        { 
          suggestion: 'Each endpoint must have a path property (e.g., "/api/users")',
          endpointIndex: index,
          availableProperties: Object.keys(endpoint)
        }
      );
    }

    if (!endpoint.path || typeof endpoint.path !== 'string') {
      throw new APISpecParsingError(
        `${endpointRef} must have a valid path string`,
        'INVALID_ENDPOINT_PATH',
        { 
          suggestion: 'Path must be a non-empty string starting with "/" (e.g., "/api/users")',
          actualType: typeof endpoint.path,
          actualValue: endpoint.path,
          endpointIndex: index
        }
      );
    }

    if (!endpoint.path.startsWith('/')) {
      throw new APISpecParsingError(
        `${endpointRef} path must start with "/"`,
        'INVALID_PATH_FORMAT',
        { 
          suggestion: 'API paths should start with "/" (e.g., "/api/users" not "api/users")',
          actualPath: endpoint.path,
          endpointIndex: index
        }
      );
    }

    // Validate method
    if (!endpoint.hasOwnProperty('method')) {
      throw new APISpecParsingError(
        `${endpointRef} is missing method property`,
        'MISSING_ENDPOINT_METHOD',
        { 
          suggestion: 'Each endpoint must have a method property (e.g., "GET", "POST")',
          endpointIndex: index,
          availableProperties: Object.keys(endpoint)
        }
      );
    }

    if (!endpoint.method || typeof endpoint.method !== 'string') {
      throw new APISpecParsingError(
        `${endpointRef} must have a valid method string`,
        'INVALID_ENDPOINT_METHOD',
        { 
          suggestion: 'Method must be a valid HTTP method string (GET, POST, PUT, PATCH, DELETE, etc.)',
          actualType: typeof endpoint.method,
          actualValue: endpoint.method,
          endpointIndex: index
        }
      );
    }

    const validMethods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];
    if (!validMethods.includes(endpoint.method.toUpperCase())) {
      throw new APISpecParsingError(
        `Invalid HTTP method: ${endpoint.method}`,
        'UNSUPPORTED_HTTP_METHOD',
        { 
          suggestion: `Method must be one of: ${validMethods.join(', ')}`,
          actualMethod: endpoint.method,
          validMethods,
          endpointIndex: index
        }
      );
    }

    // Validate purpose
    if (!endpoint.hasOwnProperty('purpose')) {
      throw new APISpecParsingError(
        `${endpointRef} is missing purpose property`,
        'MISSING_ENDPOINT_PURPOSE',
        { 
          suggestion: 'Each endpoint must have a purpose description explaining what it does',
          endpointIndex: index,
          availableProperties: Object.keys(endpoint)
        }
      );
    }

    if (!endpoint.purpose || typeof endpoint.purpose !== 'string') {
      throw new APISpecParsingError(
        `${endpointRef} must have a purpose description`,
        'INVALID_ENDPOINT_PURPOSE',
        { 
          suggestion: 'Purpose must be a descriptive string explaining what the endpoint does',
          actualType: typeof endpoint.purpose,
          actualValue: endpoint.purpose,
          endpointIndex: index
        }
      );
    }

    if (endpoint.purpose.trim().length < 3) {
      throw new APISpecParsingError(
        `${endpointRef} purpose description is too short`,
        'PURPOSE_TOO_SHORT',
        { 
          suggestion: 'Purpose should be a meaningful description (at least 3 characters)',
          actualLength: endpoint.purpose.trim().length,
          endpointIndex: index
        }
      );
    }

    // Validate responses
    if (!endpoint.hasOwnProperty('responses')) {
      throw new APISpecParsingError(
        `${endpointRef} is missing responses property`,
        'MISSING_ENDPOINT_RESPONSES',
        { 
          suggestion: 'Each endpoint must have a responses object with at least a success response',
          endpointIndex: index,
          availableProperties: Object.keys(endpoint)
        }
      );
    }

    if (!endpoint.responses || typeof endpoint.responses !== 'object' || Array.isArray(endpoint.responses)) {
      throw new APISpecParsingError(
        `${endpointRef} must have responses object`,
        'INVALID_RESPONSES_TYPE',
        { 
          suggestion: 'Responses must be an object with success and optional error properties',
          actualType: Array.isArray(endpoint.responses) ? 'array' : typeof endpoint.responses,
          endpointIndex: index
        }
      );
    }

    if (!endpoint.responses.hasOwnProperty('success')) {
      throw new APISpecParsingError(
        `${endpointRef} is missing success response`,
        'MISSING_SUCCESS_RESPONSE',
        { 
          suggestion: 'Each endpoint must have a success response definition',
          endpointIndex: index,
          availableResponseTypes: Object.keys(endpoint.responses)
        }
      );
    }

    // Validate parameters if present
    if (endpoint.parameters !== undefined) {
      this.validateEndpointParameters(endpoint.parameters, endpointRef, index);
    }

    // Validate sessionRequired if present
    if (endpoint.sessionRequired !== undefined && typeof endpoint.sessionRequired !== 'boolean') {
      throw new APISpecParsingError(
        `${endpointRef} sessionRequired must be a boolean`,
        'INVALID_SESSION_REQUIRED_TYPE',
        { 
          suggestion: 'sessionRequired should be true or false',
          actualType: typeof endpoint.sessionRequired,
          endpointIndex: index
        }
      );
    }
  }

  /**
   * Validate endpoint parameters structure
   */
  private validateEndpointParameters(parameters: any, endpointRef: string, index?: number): void {
    if (typeof parameters !== 'object' || Array.isArray(parameters)) {
      throw new APISpecParsingError(
        `${endpointRef} parameters must be an object`,
        'INVALID_PARAMETERS_TYPE',
        { 
          suggestion: 'Parameters should be an object with query, path, and/or body properties',
          actualType: Array.isArray(parameters) ? 'array' : typeof parameters,
          endpointIndex: index
        }
      );
    }

    // Validate parameter types if present
    const validParameterTypes = ['query', 'path', 'body'];
    for (const [paramType, paramValue] of Object.entries(parameters)) {
      if (!validParameterTypes.includes(paramType)) {
        console.warn(`Warning: Unknown parameter type "${paramType}" in ${endpointRef}. Valid types: ${validParameterTypes.join(', ')}`);
      }

      if (paramValue !== null && (typeof paramValue !== 'object' || Array.isArray(paramValue))) {
        throw new APISpecParsingError(
          `${endpointRef} ${paramType} parameters must be an object`,
          'INVALID_PARAMETER_VALUE_TYPE',
          { 
            suggestion: `${paramType} parameters should be an object with parameter names as keys`,
            actualType: Array.isArray(paramValue) ? 'array' : typeof paramValue,
            parameterType: paramType,
            endpointIndex: index
          }
        );
      }
    }
  }

  /**
   * Get a summary of the parsed specification
   */
  static summarizeSpec(spec: ParsedAPISpec): string {
    const endpointCount = spec.endpoints.length;
    const methods = [...new Set(spec.endpoints.map(e => e.method))];
    const sessionRequired = spec.endpoints.filter(e => e.sessionRequired).length;
    const modelCount = spec.dataModels ? Object.keys(spec.dataModels).length : 0;

    return `Parsed ${endpointCount} endpoints (${methods.join(', ')}) with ${modelCount} data models. ${sessionRequired} endpoints require session management.`;
  }
}

/**
 * Convenience function to create parser with environment variables
 */
export function createAPISpecParser(apiKey?: string): APISpecParser {
  const key = apiKey || process.env.CEREBRAS_API_KEY;
  
  if (!key) {
    throw new Error('Cerebras API key must be provided either as parameter or CEREBRAS_API_KEY environment variable');
  }

  return new APISpecParser({ apiKey: key });
}

/**
 * Validate API specification file path without requiring API key
 * This is useful for pre-validation in setup wizards
 */
export async function validateAPISpecFile(filePath: string): Promise<void> {
  // Create a temporary parser instance just for validation
  const tempParser = new APISpecParser({ apiKey: 'temp-validation-key' });
  
  // Access the private validateFile method through type assertion
  await (tempParser as any).validateFile(filePath);
}

/**
 * Get recovery suggestions based on error type
 */
export function getErrorRecoverySuggestions(error: APISpecParsingError): string[] {
  const suggestions: string[] = [];

  switch (error.code) {
    case 'FILE_NOT_FOUND':
      suggestions.push('Check the file path for typos');
      suggestions.push('Ensure the file exists in the specified location');
      suggestions.push('Use an absolute path if relative path is not working');
      break;

    case 'PATH_IS_DIRECTORY':
      suggestions.push('Provide a path to a file, not a directory');
      suggestions.push('Add the filename to the end of the path');
      break;

    case 'FILE_TOO_LARGE':
      suggestions.push('Break the specification into smaller files');
      suggestions.push('Remove unnecessary documentation or examples');
      suggestions.push('Focus on core API endpoints only');
      break;

    case 'EMPTY_FILE':
    case 'EMPTY_SPECIFICATION':
      suggestions.push('Ensure the file contains API specification content');
      suggestions.push('Check if the file was saved properly');
      break;

    case 'BINARY_CONTENT':
      suggestions.push('Provide a text-based specification file');
      suggestions.push('Convert binary formats to markdown or JSON');
      break;

    case 'INVALID_API_KEY':
      suggestions.push('Verify your Cerebras API key is correct');
      suggestions.push('Check if the API key has expired');
      suggestions.push('Ensure the API key has proper permissions');
      break;

    case 'RATE_LIMIT_EXCEEDED':
      suggestions.push('Wait a few minutes before trying again');
      suggestions.push('Consider upgrading your Cerebras API plan');
      suggestions.push('Use a smaller specification file');
      break;

    case 'NETWORK_ERROR':
    case 'SERVICE_UNAVAILABLE':
      suggestions.push('Check your internet connection');
      suggestions.push('Try again in a few minutes');
      suggestions.push('Verify Cerebras API service status');
      break;

    case 'SPECIFICATION_TOO_LARGE':
      suggestions.push('Break the specification into smaller sections');
      suggestions.push('Remove detailed examples and focus on structure');
      suggestions.push('Use a more concise specification format');
      break;

    case 'NO_ENDPOINTS_FOUND':
      suggestions.push('Ensure your specification contains endpoint definitions');
      suggestions.push('Check the format matches expected API documentation');
      suggestions.push('Include HTTP methods and paths in your specification');
      break;

    default:
      suggestions.push('Try again with a different specification file');
      suggestions.push('Continue with manual endpoint configuration');
      suggestions.push('Check the file format and content');
      break;
  }

  return suggestions;
}

/**
 * Check if an error is likely temporary and worth retrying
 */
export function isTemporaryError(error: APISpecParsingError): boolean {
  const temporaryErrorCodes = [
    'NETWORK_ERROR',
    'SERVICE_UNAVAILABLE',
    'RATE_LIMIT_EXCEEDED',
    'REQUEST_TIMEOUT',
    'CONNECTION_FAILED',
    'SERVICE_ERROR'
  ];

  return temporaryErrorCodes.includes(error.code) || error.metadata?.isTemporary === true;
}

/**
 * Check if an error is related to configuration issues
 */
export function isConfigurationError(error: APISpecParsingError): boolean {
  const configErrorCodes = [
    'INVALID_API_KEY',
    'INSUFFICIENT_PERMISSIONS',
    'MISSING_API_KEY'
  ];

  return configErrorCodes.includes(error.code) || error.metadata?.isConfigurationError === true;
}