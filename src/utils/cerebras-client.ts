/**
 * Cerebras LLM Client for Node.js
 * TypeScript wrapper around Cerebras API functionality
 */

import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';

export interface CerebrasMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface CerebrasCompletionRequest {
  model: string;
  messages: CerebrasMessage[];
  max_tokens?: number;
  temperature?: number;
  top_p?: number;
  stream?: boolean;
}

export interface CerebrasChoice {
  index: number;
  message: {
    role: string;
    content: string;
  };
  finish_reason: string;
}

export interface CerebrasCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: CerebrasChoice[];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface CerebrasClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  retryDelay?: number;
}

export class CerebrasError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: any
  ) {
    super(message);
    this.name = 'CerebrasError';
  }
}

export class CerebrasClient {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;
  private maxRetries: number;
  private retryDelay: number;

  constructor(options: CerebrasClientOptions) {
    if (!options.apiKey) {
      throw new CerebrasError('API key is required');
    }

    this.apiKey = options.apiKey;
    this.baseUrl = options.baseUrl || 'https://api.cerebras.ai';
    this.timeout = options.timeout || 30000; // 30 seconds
    this.maxRetries = options.maxRetries || 3;
    this.retryDelay = options.retryDelay || 1000; // 1 second
  }

  /**
   * Create a chat completion
   */
  async createChatCompletion(
    request: CerebrasCompletionRequest
  ): Promise<CerebrasCompletionResponse> {
    return this.makeRequest('/v1/chat/completions', request);
  }

  /**
   * Simple completion method for single prompts
   */
  async complete(
    prompt: string,
    options: {
      model?: string;
      maxTokens?: number;
      temperature?: number;
    } = {}
  ): Promise<string> {
    const request: CerebrasCompletionRequest = {
      model: options.model || 'llama3.1-8b',
      messages: [{ role: 'user', content: prompt }],
      max_tokens: options.maxTokens || 1000,
      temperature: options.temperature || 0.7,
    };

    const response = await this.createChatCompletion(request);
    
    if (!response.choices || response.choices.length === 0) {
      throw new CerebrasError('No completion choices returned');
    }

    return response.choices[0].message.content;
  }

  /**
   * Chat with conversation history
   */
  async chat(
    messages: CerebrasMessage[],
    options: {
      model?: string;
      maxTokens?: number;
      temperature?: number;
    } = {}
  ): Promise<string> {
    const request: CerebrasCompletionRequest = {
      model: options.model || 'llama3.1-8b',
      messages,
      max_tokens: options.maxTokens || 1000,
      temperature: options.temperature || 0.7,
    };

    const response = await this.createChatCompletion(request);
    
    if (!response.choices || response.choices.length === 0) {
      throw new CerebrasError('No completion choices returned');
    }

    return response.choices[0].message.content;
  }

  /**
   * Make HTTP request with retry logic and error handling
   */
  private async makeRequest(
    endpoint: string,
    data: any,
    attempt: number = 1
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const url = new URL(endpoint, this.baseUrl);
      const isHttps = url.protocol === 'https:';
      const httpModule = isHttps ? https : http;

      const postData = JSON.stringify(data);

      const options = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + url.search,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData),
          'Authorization': `Bearer ${this.apiKey}`,
          'User-Agent': 'agentic-protocol-engine/1.0.0',
        },
        timeout: this.timeout,
      };

      const req = httpModule.request(options, (res) => {
        let responseData = '';

        res.on('data', (chunk) => {
          responseData += chunk;
        });

        res.on('end', () => {
          try {
            const parsedResponse = JSON.parse(responseData);

            const statusCode = res.statusCode || 0;
            
            if (statusCode >= 200 && statusCode < 300) {
              resolve(parsedResponse);
            } else {
              const error = new CerebrasError(
                parsedResponse.error?.message || `HTTP ${statusCode}`,
                statusCode,
                parsedResponse
              );
              
              // Retry on server errors (5xx) or rate limits (429)
              if (
                attempt < this.maxRetries &&
                (statusCode >= 500 || statusCode === 429)
              ) {
                setTimeout(() => {
                  this.makeRequest(endpoint, data, attempt + 1)
                    .then(resolve)
                    .catch(reject);
                }, this.retryDelay * attempt);
              } else {
                reject(error);
              }
            }
          } catch (parseError) {
            reject(new CerebrasError(
              `Failed to parse response: ${parseError}`,
              res.statusCode || 0,
              responseData
            ));
          }
        });
      });

      req.on('error', (error) => {
        if (attempt < this.maxRetries) {
          setTimeout(() => {
            this.makeRequest(endpoint, data, attempt + 1)
              .then(resolve)
              .catch(reject);
          }, this.retryDelay * attempt);
        } else {
          reject(new CerebrasError(`Request failed: ${error.message}`));
        }
      });

      req.on('timeout', () => {
        req.destroy();
        if (attempt < this.maxRetries) {
          setTimeout(() => {
            this.makeRequest(endpoint, data, attempt + 1)
              .then(resolve)
              .catch(reject);
          }, this.retryDelay * attempt);
        } else {
          reject(new CerebrasError('Request timeout'));
        }
      });

      req.write(postData);
      req.end();
    });
  }

  /**
   * Validate API key format
   */
  static validateApiKey(apiKey: string): boolean {
    return typeof apiKey === 'string' && apiKey.length > 0;
  }

  /**
   * Create client from environment variables
   */
  static fromEnvironment(options: Partial<CerebrasClientOptions> = {}): CerebrasClient {
    const apiKey = process.env.CEREBRAS_API_KEY;
    
    if (!apiKey) {
      throw new CerebrasError(
        'CEREBRAS_API_KEY environment variable is required'
      );
    }

    return new CerebrasClient({
      apiKey,
      baseUrl: process.env.CEREBRAS_BASE_URL,
      ...options,
    });
  }
}

/**
 * Default export for convenience
 */
export default CerebrasClient;