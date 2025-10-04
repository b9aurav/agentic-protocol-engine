# API Specification Parser

The API Specification Parser is a utility that uses Cerebras LLM to intelligently parse markdown API specification documents and extract structured endpoint information for APE load testing configuration.

## Features

- **Intelligent Parsing**: Uses Cerebras LLM to understand API documentation in natural language
- **Structured Output**: Extracts endpoints, data models, and common patterns
- **Validation**: Validates parsed results for correctness and completeness
- **Error Handling**: Graceful error handling with detailed error messages
- **TypeScript Support**: Full TypeScript support with type definitions

## Installation

The parser is included in the APE utils package. No additional installation required.

## Usage

### Basic Usage

```typescript
import { createAPISpecParser } from '../utils/api-spec-parser';

// Create parser (requires CEREBRAS_API_KEY environment variable)
const parser = createAPISpecParser();

// Parse API specification file
const parsedSpec = await parser.parseSpecification('path/to/api-spec.md');

console.log('Parsed endpoints:', parsedSpec.endpoints.length);
```

### Advanced Usage

```typescript
import { APISpecParser } from '../utils/api-spec-parser';

// Create parser with custom configuration
const parser = new APISpecParser({
  apiKey: 'your-cerebras-api-key',
  model: 'llama3.1-8b',
  maxTokens: 4000,
  temperature: 0.1
});

const parsedSpec = await parser.parseSpecification('api-spec.md');

// Get summary
const summary = APISpecParser.summarizeSpec(parsedSpec);
console.log(summary);
```

## Configuration

### Environment Variables

- `CEREBRAS_API_KEY`: Required. Your Cerebras API key for LLM access.

### Parser Options

```typescript
interface CerebrasConfig {
  apiKey: string;           // Required: Cerebras API key
  baseUrl?: string;         // Optional: API base URL (default: https://api.cerebras.ai)
  model?: string;           // Optional: Model name (default: llama3.1-8b)
  maxTokens?: number;       // Optional: Max response tokens (default: 4000)
  temperature?: number;     // Optional: Temperature for consistency (default: 0.1)
}
```

## Output Format

The parser returns a `ParsedAPISpec` object with the following structure:

```typescript
interface ParsedAPISpec {
  endpoints: ParsedEndpoint[];
  dataModels: Record<string, any>;
  baseUrl?: string;
  commonPatterns: {
    pagination?: boolean;
    sessionManagement?: boolean;
    errorHandling?: string[];
  };
}

interface ParsedEndpoint {
  path: string;                    // e.g., "/api/products"
  method: string;                  // e.g., "GET", "POST"
  purpose: string;                 // Brief description
  parameters?: {
    query?: Record<string, any>;   // Query parameters
    path?: Record<string, any>;    // Path parameters
    body?: Record<string, any>;    // Request body schema
  };
  responses: {
    success: Record<string, any>;  // Success response schema
    error?: Record<string, any>[]; // Error response schemas
  };
  sessionRequired?: boolean;       // Whether endpoint requires session
}
```

## Example

### Input (API Specification Markdown)

```markdown
# Demo API

## GET /api/products
**Purpose**: Browse product catalog with pagination
**Query Parameters**:
- `page` (optional): Page number
- `limit` (optional): Items per page

**Success Response (200)**:
```json
{
  "products": [...],
  "pagination": {...}
}
```

### Output (Parsed Structure)

```typescript
{
  endpoints: [
    {
      path: "/api/products",
      method: "GET",
      purpose: "Browse product catalog with pagination",
      parameters: {
        query: {
          page: "optional: Page number",
          limit: "optional: Items per page"
        }
      },
      responses: {
        success: {
          products: "array",
          pagination: "object"
        }
      },
      sessionRequired: false
    }
  ],
  dataModels: {
    Product: {
      id: "string",
      name: "string",
      price: "number"
    }
  },
  commonPatterns: {
    pagination: true,
    sessionManagement: false,
    errorHandling: ["400", "404", "500"]
  }
}
```

## Testing

### Unit Tests

```bash
# Run unit tests
npm test src/utils/__tests__/api-spec-parser.test.ts
```

### Integration Tests

```bash
# Set API key and run integration tests
export CEREBRAS_API_KEY=your-api-key
npm test src/utils/__tests__/api-spec-parser.integration.test.ts
```

### Manual Testing

```bash
# Test with demo API specification
export CEREBRAS_API_KEY=your-api-key
ts-node src/utils/test-api-parser.ts
```

## Error Handling

The parser handles various error scenarios:

- **File not found**: Clear error message with file path
- **Invalid file format**: Validation errors with specific issues
- **API errors**: Network and authentication errors
- **Parsing errors**: JSON validation and structure errors
- **LLM errors**: Timeout and response format errors

## Integration with APE

The parser is designed to integrate with the APE setup wizard:

1. User provides API specification file path
2. Parser extracts endpoint information
3. Setup wizard uses parsed data to generate configuration
4. Agents use configuration for realistic load testing

## Limitations

- Currently supports markdown format API specifications
- Requires Cerebras API key and internet connection
- Parsing quality depends on specification completeness
- Large specifications may hit token limits

## Contributing

When contributing to the parser:

1. Add tests for new functionality
2. Update type definitions
3. Document new configuration options
4. Test with various API specification formats