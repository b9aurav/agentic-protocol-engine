/**
 * Example usage of Cerebras Client
 * 
 * This example demonstrates how to use the CerebrasClient for API specification parsing
 * and other LLM tasks within the APE ecosystem.
 */

import { CerebrasClient, CerebrasError } from '../src/utils/cerebras-client';

async function demonstrateCerebrasClient() {
  try {
    // Create client from environment variables
    const client = CerebrasClient.fromEnvironment({
      timeout: 15000, // 15 seconds
      maxRetries: 2,
    });

    console.log('🤖 Cerebras Client initialized successfully');

    // Example 1: Simple completion
    console.log('\n📝 Example 1: Simple completion');
    const simplePrompt = 'What is load testing?';
    const simpleResponse = await client.complete(simplePrompt, {
      model: 'llama3.1-8b',
      maxTokens: 200,
      temperature: 0.7,
    });
    console.log('Response:', simpleResponse);

    // Example 2: Chat with conversation history
    console.log('\n💬 Example 2: Chat conversation');
    const chatMessages = [
      { role: 'system' as const, content: 'You are a helpful API documentation expert.' },
      { role: 'user' as const, content: 'Explain what REST API endpoints are.' },
    ];
    
    const chatResponse = await client.chat(chatMessages, {
      model: 'llama3.1-8b',
      maxTokens: 300,
      temperature: 0.5,
    });
    console.log('Chat Response:', chatResponse);

    // Example 3: API specification parsing prompt
    console.log('\n🔍 Example 3: API specification parsing');
    const apiSpecContent = `
# User API

## POST /api/users
Create a new user account.

**Request Body:**
- name (string, required): User's full name
- email (string, required): User's email address
- age (number, optional): User's age

**Response:**
- 201: User created successfully
- 400: Invalid input data
    `;

    const parsingPrompt = `
You are an API specification parser. Analyze the following API documentation and extract structured information.

API Specification:
${apiSpecContent}

Extract and return a JSON object with:
1. endpoints: Array of endpoint objects with path, method, purpose, parameters, and responses
2. dataModels: Object containing data model definitions

Focus on:
- Accurate endpoint paths and HTTP methods
- Required vs optional parameters
- Request body schemas
- Response formats and error codes

Return only valid JSON without additional text.
    `;

    const parsingResponse = await client.complete(parsingPrompt, {
      model: 'llama3.1-8b',
      maxTokens: 800,
      temperature: 0.3, // Lower temperature for more structured output
    });
    
    console.log('Parsed API Specification:');
    try {
      const parsedData = JSON.parse(parsingResponse);
      console.log(JSON.stringify(parsedData, null, 2));
    } catch (parseError) {
      console.log('Raw response (not valid JSON):', parsingResponse);
    }

  } catch (error) {
    if (error instanceof CerebrasError) {
      console.error('❌ Cerebras API Error:', error.message);
      if (error.statusCode) {
        console.error('Status Code:', error.statusCode);
      }
      if (error.response) {
        console.error('Response:', error.response);
      }
    } else {
      console.error('❌ Unexpected Error:', error);
    }
  }
}

// Example of error handling
async function demonstrateErrorHandling() {
  console.log('\n🚨 Error Handling Examples');

  // Example 1: Invalid API key
  try {
    const invalidClient = new CerebrasClient({ apiKey: 'invalid-key' });
    await invalidClient.complete('test prompt');
  } catch (error) {
    console.log('Expected error for invalid API key:', error.message);
  }

  // Example 2: Missing API key
  try {
    const originalKey = process.env.CEREBRAS_API_KEY;
    delete process.env.CEREBRAS_API_KEY;
    CerebrasClient.fromEnvironment();
    process.env.CEREBRAS_API_KEY = originalKey; // Restore
  } catch (error) {
    console.log('Expected error for missing API key:', error.message);
  }
}

// Run examples if this file is executed directly
if (require.main === module) {
  console.log('🚀 Starting Cerebras Client Examples...');
  
  demonstrateCerebrasClient()
    .then(() => demonstrateErrorHandling())
    .then(() => {
      console.log('\n✅ Examples completed successfully!');
      console.log('\n💡 To run this example:');
      console.log('1. Set CEREBRAS_API_KEY environment variable');
      console.log('2. Run: npx ts-node examples/cerebras-client-example.ts');
    })
    .catch((error) => {
      console.error('\n❌ Example failed:', error);
      process.exit(1);
    });
}

export { demonstrateCerebrasClient, demonstrateErrorHandling };