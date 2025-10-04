/**
 * Integration tests for Cerebras Client
 * These tests verify the client works with actual HTTP requests (mocked)
 */

import * as http from 'http';
import { CerebrasClient, CerebrasError } from '../cerebras-client';

describe('CerebrasClient Integration', () => {
  let mockServer: http.Server;
  let serverPort: number;
  let client: CerebrasClient;

  beforeAll((done) => {
    // Create a mock HTTP server for testing
    mockServer = http.createServer((req, res) => {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk.toString();
      });

      req.on('end', () => {
        const requestData = JSON.parse(body);
        
        // Check authorization header
        const authHeader = req.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
          res.writeHead(401, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: { message: 'Unauthorized' } }));
          return;
        }

        // Mock successful response
        if (req.url === '/v1/chat/completions' && req.method === 'POST') {
          const mockResponse = {
            id: 'test-completion-id',
            object: 'chat.completion',
            created: Date.now(),
            model: requestData.model || 'llama3.1-8b',
            choices: [
              {
                index: 0,
                message: {
                  role: 'assistant',
                  content: `Mock response for: ${requestData.messages[requestData.messages.length - 1].content}`
                },
                finish_reason: 'stop'
              }
            ],
            usage: {
              prompt_tokens: 10,
              completion_tokens: 20,
              total_tokens: 30
            }
          };

          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(mockResponse));
        } else {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: { message: 'Not found' } }));
        }
      });
    });

    mockServer.listen(0, () => {
      const address = mockServer.address();
      if (address && typeof address === 'object') {
        serverPort = address.port;
        client = new CerebrasClient({
          apiKey: 'test-api-key',
          baseUrl: `http://localhost:${serverPort}`,
          timeout: 5000,
          maxRetries: 1,
          retryDelay: 100
        });
        done();
      }
    });
  });

  afterAll((done) => {
    if (mockServer) {
      mockServer.close(done);
    } else {
      done();
    }
  });

  describe('HTTP requests', () => {
    it('should make successful completion request', async () => {
      const response = await client.complete('Test prompt', {
        model: 'llama3.1-8b',
        maxTokens: 100,
        temperature: 0.7
      });

      expect(response).toBe('Mock response for: Test prompt');
    });

    it('should make successful chat request', async () => {
      const messages = [
        { role: 'system' as const, content: 'You are helpful.' },
        { role: 'user' as const, content: 'Hello there!' }
      ];

      const response = await client.chat(messages, {
        model: 'llama3.1-8b',
        maxTokens: 150
      });

      expect(response).toBe('Mock response for: Hello there!');
    });

    it('should handle authentication errors', async () => {
      const unauthorizedClient = new CerebrasClient({
        apiKey: '', // Invalid API key
        baseUrl: `http://localhost:${serverPort}`,
        timeout: 5000,
        maxRetries: 1
      });

      await expect(unauthorizedClient.complete('Test')).rejects.toThrow(CerebrasError);
    });

    it('should handle network timeouts', async () => {
      const timeoutClient = new CerebrasClient({
        apiKey: 'test-key',
        baseUrl: 'http://localhost:99999', // Non-existent server
        timeout: 1000,
        maxRetries: 1,
        retryDelay: 100
      });

      await expect(timeoutClient.complete('Test')).rejects.toThrow(CerebrasError);
    }, 10000); // Increase timeout for this test

    it('should make raw API request', async () => {
      const request = {
        model: 'llama3.1-8b',
        messages: [{ role: 'user' as const, content: 'Raw API test' }],
        max_tokens: 50,
        temperature: 0.5
      };

      const response = await client.createChatCompletion(request);

      expect(response.choices).toHaveLength(1);
      expect(response.choices[0].message.content).toBe('Mock response for: Raw API test');
      expect(response.model).toBe('llama3.1-8b');
      expect(response.usage.total_tokens).toBe(30);
    });
  });

  describe('error scenarios', () => {
    it('should handle server errors with retry', async () => {
      // Create a server that returns 500 error
      const errorServer = http.createServer((req, res) => {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: { message: 'Internal server error' } }));
      });

      await new Promise<void>((resolve) => {
        errorServer.listen(0, () => {
          const address = errorServer.address();
          if (address && typeof address === 'object') {
            const errorClient = new CerebrasClient({
              apiKey: 'test-key',
              baseUrl: `http://localhost:${address.port}`,
              timeout: 2000,
              maxRetries: 2,
              retryDelay: 100
            });

            errorClient.complete('Test').catch((error) => {
              expect(error).toBeInstanceOf(CerebrasError);
              expect(error.statusCode).toBe(500);
              errorServer.close(() => resolve());
            });
          }
        });
      });
    }, 10000);

    it('should handle malformed JSON responses', async () => {
      // Create a server that returns invalid JSON
      const malformedServer = http.createServer((req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('invalid json response');
      });

      await new Promise<void>((resolve) => {
        malformedServer.listen(0, () => {
          const address = malformedServer.address();
          if (address && typeof address === 'object') {
            const malformedClient = new CerebrasClient({
              apiKey: 'test-key',
              baseUrl: `http://localhost:${address.port}`,
              timeout: 2000,
              maxRetries: 1
            });

            malformedClient.complete('Test').catch((error) => {
              expect(error).toBeInstanceOf(CerebrasError);
              expect(error.message).toContain('Failed to parse response');
              malformedServer.close(() => resolve());
            });
          }
        });
      });
    }, 10000);
  });
});