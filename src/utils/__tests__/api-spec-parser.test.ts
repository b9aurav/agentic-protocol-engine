/**
 * Tests for API Specification Parser
 */

import * as fs from 'fs-extra';
import * as path from 'path';
import { APISpecParser, ParsedAPISpec, createAPISpecParser } from '../api-spec-parser';

// Mock fetch for testing
global.fetch = jest.fn();

describe('APISpecParser', () => {
  let parser: APISpecParser;
  const mockApiKey = 'test-api-key';

  beforeEach(() => {
    parser = new APISpecParser({ apiKey: mockApiKey });
    jest.clearAllMocks();
  });

  describe('constructor', () => {
    it('should create parser with valid config', () => {
      expect(parser).toBeInstanceOf(APISpecParser);
    });

    it('should throw error without API key', () => {
      expect(() => new APISpecParser({ apiKey: '' })).toThrow('Cerebras API key is required');
    });

    it('should use default config values', () => {
      const parser = new APISpecParser({ apiKey: 'test' });
      expect(parser).toBeInstanceOf(APISpecParser);
    });
  });

  describe('parseSpecification', () => {
    const mockSpecContent = `
# Test API

## GET /api/test
Purpose: Test endpoint
Response: {"success": true}
`;

    const mockParsedResponse = {
      endpoints: [
        {
          path: '/api/test',
          method: 'GET',
          purpose: 'Test endpoint',
          responses: {
            success: { success: true }
          }
        }
      ],
      dataModels: {},
      commonPatterns: {
        pagination: false,
        sessionManagement: false,
        errorHandling: []
      }
    };

    beforeEach(() => {
      // Mock fs operations
      jest.spyOn(fs, 'stat').mockResolvedValue({ isFile: () => true } as any);
      jest.spyOn(fs, 'readFile').mockResolvedValue(mockSpecContent);

      // Mock fetch response
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          choices: [
            {
              message: {
                content: JSON.stringify(mockParsedResponse)
              }
            }
          ]
        })
      });
    });

    it('should parse valid specification file', async () => {
      const result = await parser.parseSpecification('test-spec.md');
      
      expect(result).toEqual(mockParsedResponse);
      expect(fs.stat).toHaveBeenCalled();
      expect(fs.readFile).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalled();
    });

    it('should throw error for non-existent file', async () => {
      jest.spyOn(fs, 'stat').mockRejectedValue({ code: 'ENOENT' });

      await expect(parser.parseSpecification('non-existent.md'))
        .rejects.toThrow('File not found');
    });

    it('should throw error for invalid file path', async () => {
      jest.spyOn(fs, 'stat').mockResolvedValue({ isFile: () => false } as any);

      await expect(parser.parseSpecification('directory'))
        .rejects.toThrow('Path is not a file');
    });

    it('should handle API errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 401,
        text: () => Promise.resolve('Unauthorized')
      });

      await expect(parser.parseSpecification('test-spec.md'))
        .rejects.toThrow('HTTP 401: Unauthorized');
    });

    it('should handle invalid JSON response', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          choices: [
            {
              message: {
                content: 'invalid json'
              }
            }
          ]
        })
      });

      await expect(parser.parseSpecification('test-spec.md'))
        .rejects.toThrow('Failed to parse JSON response');
    });

    it('should handle markdown formatted JSON response', async () => {
      const markdownResponse = '```json\n' + JSON.stringify(mockParsedResponse) + '\n```';
      
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          choices: [
            {
              message: {
                content: markdownResponse
              }
            }
          ]
        })
      });

      const result = await parser.parseSpecification('test-spec.md');
      expect(result).toEqual(mockParsedResponse);
    });
  });

  describe('validation', () => {
    it('should validate endpoint structure', async () => {
      const invalidResponse = {
        endpoints: [
          {
            // Missing required fields
            path: '/api/test'
          }
        ],
        dataModels: {},
        commonPatterns: {}
      };

      jest.spyOn(fs, 'stat').mockResolvedValue({ isFile: () => true } as any);
      jest.spyOn(fs, 'readFile').mockResolvedValue('test content');
      
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          choices: [
            {
              message: {
                content: JSON.stringify(invalidResponse)
              }
            }
          ]
        })
      });

      await expect(parser.parseSpecification('test-spec.md'))
        .rejects.toThrow('Endpoint must have a valid method string');
    });

    it('should validate HTTP methods', async () => {
      const invalidResponse = {
        endpoints: [
          {
            path: '/api/test',
            method: 'INVALID',
            purpose: 'Test',
            responses: { success: {} }
          }
        ],
        dataModels: {},
        commonPatterns: {}
      };

      jest.spyOn(fs, 'stat').mockResolvedValue({ isFile: () => true } as any);
      jest.spyOn(fs, 'readFile').mockResolvedValue('test content');
      
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          choices: [
            {
              message: {
                content: JSON.stringify(invalidResponse)
              }
            }
          ]
        })
      });

      await expect(parser.parseSpecification('test-spec.md'))
        .rejects.toThrow('Invalid HTTP method: INVALID');
    });
  });

  describe('summarizeSpec', () => {
    it('should create summary of parsed spec', () => {
      const spec: ParsedAPISpec = {
        endpoints: [
          {
            path: '/api/test1',
            method: 'GET',
            purpose: 'Test 1',
            responses: { success: {} }
          },
          {
            path: '/api/test2',
            method: 'POST',
            purpose: 'Test 2',
            responses: { success: {} },
            sessionRequired: true
          }
        ],
        dataModels: {
          User: { id: 'string' },
          Product: { name: 'string' }
        },
        commonPatterns: {}
      };

      const summary = APISpecParser.summarizeSpec(spec);
      expect(summary).toContain('2 endpoints');
      expect(summary).toContain('GET, POST');
      expect(summary).toContain('2 data models');
      expect(summary).toContain('1 endpoints require session');
    });
  });

  describe('createAPISpecParser', () => {
    it('should create parser with provided API key', () => {
      const parser = createAPISpecParser('test-key');
      expect(parser).toBeInstanceOf(APISpecParser);
    });

    it('should use environment variable', () => {
      process.env.CEREBRAS_API_KEY = 'env-key';
      const parser = createAPISpecParser();
      expect(parser).toBeInstanceOf(APISpecParser);
      delete process.env.CEREBRAS_API_KEY;
    });

    it('should throw error without API key', () => {
      delete process.env.CEREBRAS_API_KEY;
      expect(() => createAPISpecParser()).toThrow('Cerebras API key must be provided');
    });
  });
});