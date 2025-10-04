/**
 * Integration tests for API Specification Parser with real demo API spec
 */

import * as path from 'path';
import { APISpecParser, createAPISpecParser } from '../api-spec-parser';

describe('APISpecParser Integration', () => {
  // Skip these tests if no API key is available
  const apiKey = process.env.CEREBRAS_API_KEY;
  const skipTests = !apiKey;

  if (skipTests) {
    console.log('Skipping integration tests - CEREBRAS_API_KEY not set');
  }

  describe('with demo API specification', () => {
    let parser: APISpecParser;
    const demoSpecPath = path.join(__dirname, '../../../demo-test-api/API_SPECIFICATION.md');

    beforeEach(() => {
      if (skipTests) return;
      parser = createAPISpecParser(apiKey);
    });

    it('should parse demo API specification successfully', async () => {
      if (skipTests) {
        console.log('Skipping test - no API key');
        return;
      }

      const result = await parser.parseSpecification(demoSpecPath);

      // Verify basic structure
      expect(result).toBeDefined();
      expect(result.endpoints).toBeDefined();
      expect(Array.isArray(result.endpoints)).toBe(true);
      expect(result.endpoints.length).toBeGreaterThan(0);

      // Verify we found the expected endpoints
      const paths = result.endpoints.map(e => e.path);
      expect(paths).toContain('/api/products');
      expect(paths).toContain('/api/cart');

      // Verify endpoint details
      const productsEndpoint = result.endpoints.find(e => e.path === '/api/products' && e.method === 'GET');
      expect(productsEndpoint).toBeDefined();
      expect(productsEndpoint?.purpose).toBeDefined();
      expect(productsEndpoint?.responses.success).toBeDefined();

      // Verify session management detection
      const cartEndpoints = result.endpoints.filter(e => e.path.startsWith('/api/cart'));
      const sessionRequiredEndpoints = cartEndpoints.filter(e => e.sessionRequired);
      expect(sessionRequiredEndpoints.length).toBeGreaterThan(0);

      // Verify data models
      expect(result.dataModels).toBeDefined();
      expect(typeof result.dataModels).toBe('object');

      // Log summary for manual verification
      const summary = APISpecParser.summarizeSpec(result);
      console.log('Parsed specification summary:', summary);
    }, 30000); // 30 second timeout for API call

    it('should handle parsing errors gracefully', async () => {
      if (skipTests) {
        console.log('Skipping test - no API key');
        return;
      }

      // Test with non-existent file
      await expect(parser.parseSpecification('non-existent-file.md'))
        .rejects.toThrow('File not found');
    });
  });

  describe('createAPISpecParser convenience function', () => {
    it('should create parser from environment variable', () => {
      if (skipTests) {
        console.log('Skipping test - no API key');
        return;
      }

      const parser = createAPISpecParser();
      expect(parser).toBeInstanceOf(APISpecParser);
    });
  });
});