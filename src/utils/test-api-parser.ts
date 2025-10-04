#!/usr/bin/env ts-node

/**
 * Manual test utility for API Specification Parser
 * 
 * Usage: ts-node src/utils/test-api-parser.ts [path-to-spec-file]
 */

import * as path from 'path';
import { createAPISpecParser, APISpecParser } from './api-spec-parser';

async function main() {
  const args = process.argv.slice(2);
  const specPath = args[0] || path.join(__dirname, '../../demo-test-api/API_SPECIFICATION.md');

  console.log('🔍 Testing API Specification Parser');
  console.log(`📄 Spec file: ${specPath}`);

  // Check for API key
  const apiKey = process.env.CEREBRAS_API_KEY;
  if (!apiKey) {
    console.error('❌ CEREBRAS_API_KEY environment variable is required');
    console.log('💡 Set it with: export CEREBRAS_API_KEY=your-api-key');
    process.exit(1);
  }

  try {
    // Create parser
    console.log('🤖 Creating API parser...');
    const parser = createAPISpecParser();

    // Parse specification
    console.log('⚡ Parsing specification with Cerebras LLM...');
    const startTime = Date.now();
    const result = await parser.parseSpecification(specPath);
    const duration = Date.now() - startTime;

    // Display results
    console.log(`✅ Parsing completed in ${duration}ms`);
    console.log('\n📊 Summary:');
    console.log(APISpecParser.summarizeSpec(result));

    console.log('\n🔗 Endpoints found:');
    result.endpoints.forEach((endpoint, index) => {
      console.log(`  ${index + 1}. ${endpoint.method} ${endpoint.path}`);
      console.log(`     Purpose: ${endpoint.purpose}`);
      if (endpoint.sessionRequired) {
        console.log('     🔐 Session required');
      }
      if (endpoint.parameters?.query) {
        console.log(`     Query params: ${Object.keys(endpoint.parameters.query).join(', ')}`);
      }
      if (endpoint.parameters?.body) {
        console.log(`     Body params: ${Object.keys(endpoint.parameters.body).join(', ')}`);
      }
    });

    console.log('\n📋 Data Models:');
    if (result.dataModels && Object.keys(result.dataModels).length > 0) {
      Object.keys(result.dataModels).forEach(model => {
        console.log(`  - ${model}`);
      });
    } else {
      console.log('  No data models found');
    }

    console.log('\n🔄 Common Patterns:');
    if (result.commonPatterns.pagination) {
      console.log('  ✓ Pagination support detected');
    }
    if (result.commonPatterns.sessionManagement) {
      console.log('  ✓ Session management detected');
    }
    if (result.commonPatterns.errorHandling?.length) {
      console.log(`  ✓ Error handling patterns: ${result.commonPatterns.errorHandling.join(', ')}`);
    }

    // Save result for inspection
    const outputPath = path.join(__dirname, 'parsed-spec-output.json');
    const fs = await import('fs-extra');
    await fs.writeJSON(outputPath, result, { spaces: 2 });
    console.log(`\n💾 Full result saved to: ${outputPath}`);

  } catch (error: any) {
    console.error('❌ Parsing failed:', error.message);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}