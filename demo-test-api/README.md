# Demo Test API

A lightweight Node.js/Express API designed specifically as a testing target for the Agentic Protocol Engine (APE). This API provides a minimal e-commerce-like interface with stateful shopping cart operations, product catalog, and various HTTP response scenarios to demonstrate APE's intelligent agent capabilities.

## Features

- **Product Catalog**: Browse 20 demo products across 4 categories
- **Shopping Cart**: Session-based stateful cart operations
- **Error Simulation**: Configurable error rates and response delays
- **Health Monitoring**: Health check and status endpoints
- **Request Logging**: Detailed logging for APE agent activity tracking

## Quick Start

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Build the project
npm run build

# Start the API
npm start
```

The API will be available at `http://localhost:3000`

### Development Mode

```bash
# Run in development mode with hot reload
npm run dev

# Build and watch for changes
npm run build:watch
```

## API Endpoints

### Product Catalog

#### GET /api/products
Returns a list of demo products with optional pagination and filtering.

**Query Parameters:**
- `page` (optional): Page number for pagination
- `limit` (optional): Number of products per page
- `category` (optional): Filter by category

**Example Response:**
```json
{
  "products": [
    {
      "id": "1",
      "name": "Wireless Headphones",
      "description": "High-quality wireless headphones with noise cancellation",
      "price": 199.99,
      "category": "electronics",
      "inStock": true
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 20,
    "totalPages": 2
  }
}
```

#### GET /api/products/{id}
Returns details for a specific product.

**Example Response:**
```json
{
  "id": "1",
  "name": "Wireless Headphones",
  "description": "High-quality wireless headphones with noise cancellation",
  "price": 199.99,
  "category": "electronics",
  "inStock": true
}
```

#### GET /api/categories
Returns available product categories.

**Example Response:**
```json
{
  "categories": [
    {
      "id": "electronics",
      "name": "Electronics",
      "productCount": 8
    }
  ]
}
```

### Shopping Cart

#### POST /api/cart
Adds an item to the shopping cart.

**Request Body:**
```json
{
  "productId": "1",
  "quantity": 2
}
```

**Example Response:**
```json
{
  "success": true,
  "message": "Item added to cart",
  "cart": {
    "items": [
      {
        "id": "cart-item-1",
        "productId": "1",
        "productName": "Wireless Headphones",
        "price": 199.99,
        "quantity": 2
      }
    ],
    "total": 399.98,
    "itemCount": 2
  }
}
```

#### GET /api/cart
Returns current cart contents.

**Example Response:**
```json
{
  "cart": {
    "items": [
      {
        "id": "cart-item-1",
        "productId": "1",
        "productName": "Wireless Headphones",
        "price": 199.99,
        "quantity": 2
      }
    ],
    "total": 399.98,
    "itemCount": 2
  }
}
```

#### DELETE /api/cart/{itemId}
Removes an item from the cart.

**Example Response:**
```json
{
  "success": true,
  "message": "Item removed from cart",
  "cart": {
    "items": [],
    "total": 0,
    "itemCount": 0
  }
}
```

### Health & Monitoring

#### GET /api/health
Basic health check endpoint (always fast, no error simulation).

**Example Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### GET /api/status
Returns system status and information.

**Example Response:**
```json
{
  "status": "running",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "uptime": 3600.5,
  "memory": {
    "rss": 45678592,
    "heapTotal": 20971520,
    "heapUsed": 15728640,
    "external": 1048576
  }
}
```

## Configuration

The API can be configured using environment variables:

### Server Configuration
- `PORT`: Server port (default: 3000)
- `NODE_ENV`: Environment mode (development/production)
- `SESSION_SECRET`: Session encryption key (default: 'demo-secret')

### Error Simulation
- `ERROR_RATE_503`: Probability of 503 Service Unavailable responses (default: 0.05 = 5%)
- `ERROR_RATE_500`: Probability of 500 Internal Server Error responses (default: 0.01 = 1%)

### Response Timing
- `RESPONSE_DELAY_MIN`: Minimum response delay in milliseconds (default: 50)
- `RESPONSE_DELAY_MAX`: Maximum response delay in milliseconds (default: 200)

### Example Configuration

```bash
# .env file
PORT=3000
NODE_ENV=development
SESSION_SECRET=your-secret-key
ERROR_RATE_503=0.05
ERROR_RATE_500=0.01
RESPONSE_DELAY_MIN=50
RESPONSE_DELAY_MAX=200
```

## Error Scenarios

The API simulates realistic error conditions for testing:

### HTTP Status Codes
- **404 Not Found**: Invalid product IDs, non-existent endpoints
- **400 Bad Request**: Malformed JSON, missing required fields
- **503 Service Unavailable**: Simulated high load (configurable rate)
- **500 Internal Server Error**: Simulated system errors (configurable rate)

### Response Times
- **Normal responses**: 50-200ms delay (configurable)
- **Error responses**: 100-500ms delay
- **Health endpoints**: <50ms (always fast)

## APE Integration

This API is specifically designed to work with the Agentic Protocol Engine:

### Stateful Behavior
- Session-based shopping cart maintains state across requests
- Agents can perform multi-step workflows: Browse → Add to Cart → View Cart → Remove Items

### Intelligent Decision Making
- Product selection based on availability and pricing
- Error recovery scenarios (404s, 503s)
- Adaptive behavior based on application responses

### Realistic Traffic Patterns
- Non-linear decision-making that mimics human users
- Configurable response delays simulate real-world latency
- Error rates provide realistic failure scenarios

## Development

### Project Structure
```
demo-test-api/
├── src/
│   ├── index.ts              # Main application entry point
│   ├── models/
│   │   ├── data.ts           # Data models and interfaces
│   │   └── dataSeeder.ts     # Demo data seeding
│   ├── routes/
│   │   ├── products.ts       # Product catalog routes
│   │   ├── categories.ts     # Category routes
│   │   └── cart.ts           # Shopping cart routes
│   ├── services/
│   │   └── cartService.ts    # Cart business logic
│   └── middleware/
│       ├── errorHandler.ts   # Global error handling
│       └── errorSimulation.ts # Error and delay simulation
├── dist/                     # Compiled JavaScript output
├── package.json
├── tsconfig.json
└── README.md
```

### Available Scripts

```bash
# Development
npm run dev          # Run with hot reload using ts-node
npm run build        # Compile TypeScript to JavaScript
npm run build:watch  # Compile and watch for changes

# Production
npm start            # Run compiled JavaScript (builds first)
npm run clean        # Remove dist/ directory

# Testing & Health Checks
npm run health       # Quick health check of running API
npm test             # Test all API endpoints
npm run test:endpoints # Same as npm test

# Utility Scripts
./start.sh           # Unix/Linux startup script
./start.bat          # Windows startup script
```

### Building and Testing

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Quick health check
npm run health

# Test all endpoints
npm test

# Manual API testing
curl http://localhost:3000/api/health
curl http://localhost:3000/api/products
```

### Quick Start Scripts

For easy deployment, use the provided startup scripts:

**Unix/Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```cmd
start.bat
```

These scripts will:
- Check Node.js version compatibility
- Install dependencies if needed
- Build the project
- Set default environment variables
- Start the API with configuration info

## Docker Support

The API is designed to be containerized for easy deployment with APE:

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## License

MIT License - see LICENSE file for details.

## Contributing

This API is part of the Agentic Protocol Engine project. For contributions and issues, please refer to the main APE repository.