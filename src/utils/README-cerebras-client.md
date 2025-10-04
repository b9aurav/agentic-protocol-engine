# Cerebras Client for Node.js

A TypeScript wrapper around Cerebras API functionality, providing secure API key handling, request management, timeout handling, and error handling for LLM requests.

## Features

- **Secure API Key Handling**: Environment variable support with validation
- **Request Management**: HTTP/HTTPS requests with proper headers and authentication
- **Timeout Handling**: Configurable request timeouts with automatic retries
- **Error Handling**: Comprehensive error handling with retry logic for server errors
- **TypeScript Support**: Full type definitions for all API interactions
- **Multiple Interfaces**: Simple completion, chat conversations, and raw API access

## Installation

The Cerebras client is included as part of the APE utilities:

```typescript
import { CerebrasClient, CerebrasError } from '../src/utils/cerebras-client';
```

## Quick Start

### Environment Setup

Set your Cerebras API key as an environment variable:

```bash
export CEREBRAS_API_KEY="your-api-key-here"
```

### Basic Usage

```typescript
import { CerebrasClient } from '../src/utils/cerebras-client';

// Create client from environment variables
const client = CerebrasClient.fromEnvironment();

// Simple completion
const response = await client.complete('What is load testing?', {
  model: 'llama3.1-8b',
  maxTokens: 200,
  temperature: 0.7
});

console.log(response);
```

## API Reference

### CerebrasClient

#### Constructor

```typescript
new CerebrasClient(options: CerebrasClientOptions)
```

**Options:**
- `apiKey` (string, required): Cerebras API key
- `baseUrl` (string, optional): API base URL (default: 'https://api.cerebras.ai')
- `timeout` (number, optional): Request timeout in milliseconds (default: 30000)
- `maxRetries` (number, optional): Maximum retry attempts (default: 3)
- `retryDelay` (number, optional): Delay between retries in milliseconds (default: 1000)

#### Methods

##### `complete(prompt: string, options?): Promise<string>`

Simple completion for single prompts.

```typescript
const response = await client.complete('Explain REST APIs', {
  model: 'llama3.1-8b',
  maxTokens: 300,
  temperature: 0.5
});
```

##### `chat(messages: CerebrasMessage[], options?): Promise<string>`

Chat with conversation history.

```typescript
const messages = [
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: 'What is API load testing?' }
];

const response = await client.chat(messages, {
  model: 'llama3.1-8b',
  maxTokens: 400
});
```

##### `createChatCompletion(request: CerebrasCompletionRequest): Promise<CerebrasCompletionResponse>`

Raw API access for advanced use cases.

```typescript
const request = {
  model: 'llama3.1-8b',
  messages: [{ role: 'user', content: 'Hello!' }],
  max_tokens: 100,
  temperature: 0.7
};

const response = await client.createChatCompletion(request);
```

#### Static Methods

##### `validateApiKey(apiKey: string): boolean`

Validate API key format.

```typescript
const isValid = CerebrasClient.validateApiKey('your-api-key');
```

##### `fromEnvironment(options?): CerebrasClient`

Create client from environment variables.

```typescript
const client = CerebrasClient.fromEnvironment({
  timeout: 15000,
  maxRetries: 2
});
```

## Error Handling

The client provides comprehensive error handling through the `CerebrasError` class:

```typescript
import { CerebrasError } from '../src/utils/cerebras-client';

try {
  const response = await client.complete('test prompt');
} catch (error) {
  if (error instanceof CerebrasError) {
    console.error('API Error:', error.message);
    console.error('Status Code:', error.statusCode);
    console.error('Response:', error.response);
  }
}
```

### Error Types

- **Authentication Errors**: Invalid or missing API key
- **Rate Limiting**: HTTP 429 responses (automatically retried)
- **Server Errors**: HTTP 5xx responses (automatically retried)
- **Timeout Errors**: Request timeout exceeded
- **Network Errors**: Connection failures
- **Parse Errors**: Invalid JSON responses

## Configuration

### Environment Variables

- `CEREBRAS_API_KEY`: Your Cerebras API key (required)
- `CEREBRAS_BASE_URL`: Custom API base URL (optional)

### Retry Logic

The client automatically retries requests for:
- Server errors (HTTP 5xx)
- Rate limiting (HTTP 429)
- Network timeouts

Retry behavior is configurable:
- `maxRetries`: Number of retry attempts (default: 3)
- `retryDelay`: Base delay between retries (default: 1000ms)
- Exponential backoff: Delay increases with each retry attempt

## Usage in APE

The Cerebras client is designed for use within the APE ecosystem, particularly for:

### API Specification Parsing

```typescript
const parsingPrompt = `
You are an API specification parser. Analyze the following API documentation...

API Specification:
${apiSpecContent}

Extract and return a JSON object with endpoints, data models, and common patterns.
Return only valid JSON without additional text.
`;

const parsedData = await client.complete(parsingPrompt, {
  model: 'llama3.1-8b',
  maxTokens: 1000,
  temperature: 0.3 // Lower temperature for structured output
});

const apiSpec = JSON.parse(parsedData);
```

### Agent Behavior Generation

```typescript
const behaviorPrompt = `
Generate realistic user behavior patterns for load testing a ${apiType} API.
Consider typical user workflows, error scenarios, and edge cases.
`;

const behaviors = await client.complete(behaviorPrompt);
```

## Examples

See `examples/cerebras-client-example.ts` for comprehensive usage examples including:
- Simple completions
- Chat conversations
- API specification parsing
- Error handling scenarios

## Testing

Run the test suite:

```bash
npm test -- src/utils/__tests__/cerebras-client.test.ts
```

The tests cover:
- Client initialization
- API key validation
- Environment variable handling
- Error scenarios
- Configuration options

## Security Considerations

- **API Key Protection**: Never log or expose API keys in code
- **Environment Variables**: Use environment variables for sensitive configuration
- **Request Validation**: All requests are validated before sending
- **Error Sanitization**: Error messages don't expose sensitive information
- **Timeout Protection**: Prevents hanging requests from blocking the application

## Performance

- **Connection Reuse**: HTTP connections are managed efficiently
- **Retry Logic**: Smart retry logic prevents unnecessary API calls
- **Timeout Management**: Configurable timeouts prevent resource exhaustion
- **Memory Efficiency**: Streaming responses for large completions (when supported)

## Troubleshooting

### Common Issues

1. **"API key is required" Error**
   - Ensure `CEREBRAS_API_KEY` environment variable is set
   - Verify API key format with `CerebrasClient.validateApiKey()`

2. **Timeout Errors**
   - Increase timeout value in client options
   - Check network connectivity
   - Verify Cerebras API status

3. **Rate Limiting**
   - Client automatically retries with exponential backoff
   - Consider reducing request frequency
   - Check API usage limits

4. **Parse Errors**
   - Verify response format from Cerebras API
   - Check for API changes or updates
   - Enable debug logging for raw responses

### Debug Mode

Enable detailed logging by setting environment variable:

```bash
export DEBUG=cerebras-client
```

This will log request/response details for troubleshooting.