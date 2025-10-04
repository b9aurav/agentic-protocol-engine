/**
 * Example usage of API Specification Parser
 */

import { createAPISpecParser, APISpecParser } from '../src/utils/api-spec-parser';
import * as path from 'path';

async function exampleUsage() {
  try {
    // Create parser (requires CEREBRAS_API_KEY environment variable)
    const parser = createAPISpecParser();

    // Parse the demo API specification
    const specPath = path.join(__dirname, '../demo-test-api/API_SPECIFICATION.md');
    console.log('Parsing API specification:', specPath);

    const parsedSpec = await parser.parseSpecification(specPath);

    // Display summary
    console.log('\nParsing Summary:');
    console.log(APISpecParser.summarizeSpec(parsedSpec));

    // Show endpoints
    console.log('\nEndpoints:');
    parsedSpec.endpoints.forEach(endpoint => {
      console.log(`- ${endpoint.method} ${endpoint.path}: ${endpoint.purpose}`);
      if (endpoint.sessionRequired) {
        console.log('  (requires session)');
      }
    });

    // Show data models
    console.log('\nData Models:');
    Object.keys(parsedSpec.dataModels || {}).forEach(model => {
      console.log(`- ${model}`);
    });

    return parsedSpec;

  } catch (error: any) {
    console.error('Error parsing API specification:', error.message);
    throw error;
  }
}

// Example of using parsed data for configuration generation
function generateConfigFromParsedSpec(parsedSpec: any) {
  const config = {
    target: {
      endpoints: parsedSpec.endpoints.map((endpoint: any) => ({
        path: endpoint.path,
        method: endpoint.method,
        purpose: endpoint.purpose,
        sessionRequired: endpoint.sessionRequired || false,
        sampleRequest: endpoint.parameters?.body || {},
        expectedResponse: endpoint.responses.success
      }))
    },
    sessionManagement: {
      enabled: parsedSpec.commonPatterns.sessionManagement || false,
      cookieHandling: true
    },
    dataModels: parsedSpec.dataModels || {}
  };

  return config;
}

// Run example if called directly
if (require.main === module) {
  exampleUsage()
    .then(parsedSpec => {
      console.log('\n--- Generated Configuration ---');
      const config = generateConfigFromParsedSpec(parsedSpec);
      console.log(JSON.stringify(config, null, 2));
    })
    .catch(console.error);
}

export { exampleUsage, generateConfigFromParsedSpec };