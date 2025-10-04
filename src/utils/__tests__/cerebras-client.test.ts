/**
 * Tests for Cerebras Client
 */

import { CerebrasClient, CerebrasError } from '../cerebras-client';

describe('CerebrasClient', () => {
  describe('constructor', () => {
    it('should create client with required API key', () => {
      const client = new CerebrasClient({ apiKey: 'test-key' });
      expect(client).toBeInstanceOf(CerebrasClient);
    });

    it('should throw error without API key', () => {
      expect(() => {
        new CerebrasClient({ apiKey: '' });
      }).toThrow(CerebrasError);
    });

    it('should use default values for optional parameters', () => {
      const client = new CerebrasClient({ apiKey: 'test-key' });
      expect(client).toBeInstanceOf(CerebrasClient);
    });

    it('should accept custom options', () => {
      const client = new CerebrasClient({
        apiKey: 'test-key',
        baseUrl: 'https://custom.api.com',
        timeout: 5000,
        maxRetries: 5,
        retryDelay: 2000,
      });
      expect(client).toBeInstanceOf(CerebrasClient);
    });
  });

  describe('validateApiKey', () => {
    it('should validate valid API key', () => {
      expect(CerebrasClient.validateApiKey('valid-key')).toBe(true);
    });

    it('should reject empty API key', () => {
      expect(CerebrasClient.validateApiKey('')).toBe(false);
    });

    it('should reject non-string API key', () => {
      expect(CerebrasClient.validateApiKey(null as any)).toBe(false);
      expect(CerebrasClient.validateApiKey(undefined as any)).toBe(false);
    });
  });

  describe('fromEnvironment', () => {
    const originalEnv = process.env;

    beforeEach(() => {
      jest.resetModules();
      process.env = { ...originalEnv };
    });

    afterAll(() => {
      process.env = originalEnv;
    });

    it('should create client from environment variables', () => {
      process.env.CEREBRAS_API_KEY = 'env-test-key';
      const client = CerebrasClient.fromEnvironment();
      expect(client).toBeInstanceOf(CerebrasClient);
    });

    it('should throw error when CEREBRAS_API_KEY is not set', () => {
      delete process.env.CEREBRAS_API_KEY;
      expect(() => {
        CerebrasClient.fromEnvironment();
      }).toThrow(CerebrasError);
    });

    it('should use custom base URL from environment', () => {
      process.env.CEREBRAS_API_KEY = 'env-test-key';
      process.env.CEREBRAS_BASE_URL = 'https://custom.env.com';
      const client = CerebrasClient.fromEnvironment();
      expect(client).toBeInstanceOf(CerebrasClient);
    });

    it('should override environment with provided options', () => {
      process.env.CEREBRAS_API_KEY = 'env-test-key';
      const client = CerebrasClient.fromEnvironment({
        timeout: 10000,
      });
      expect(client).toBeInstanceOf(CerebrasClient);
    });
  });

  describe('error handling', () => {
    it('should create CerebrasError with message', () => {
      const error = new CerebrasError('Test error');
      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(CerebrasError);
      expect(error.message).toBe('Test error');
      expect(error.name).toBe('CerebrasError');
    });

    it('should create CerebrasError with status code and response', () => {
      const response = { error: 'API error' };
      const error = new CerebrasError('Test error', 400, response);
      expect(error.statusCode).toBe(400);
      expect(error.response).toBe(response);
    });
  });
});