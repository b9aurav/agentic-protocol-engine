# Demo Test API Specification

## API Endpoints

### 1. Product Catalog

#### GET /api/products
**Purpose**: Browse product catalog with optional filtering and pagination
**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page (1-100, default: 10)
- `category` (optional): Filter by category ID

**Success Response (200)**:
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
    "currentPage": 1,
    "totalPages": 2,
    "totalProducts": 20,
    "hasNextPage": true,
    "hasPreviousPage": false
  },
  "filters": {
    "category": null
  }
}
```

**Error Responses**:
- `400`: Invalid pagination parameters
- `500/503`: Random error simulation

#### GET /api/products/{id}
**Purpose**: Get detailed information for a specific product
**Path Parameters**:
- `id` (required): Product ID (string)

**Success Response (200)**:
```json
{
  "product": {
    "id": "1",
    "name": "Wireless Headphones",
    "description": "High-quality wireless headphones with noise cancellation",
    "price": 199.99,
    "category": "electronics",
    "inStock": true
  }
}
```

**Error Responses**:
- `400`: Missing or invalid product ID
- `404`: Product not found
- `500/503`: Random error simulation

#### GET /api/categories
**Purpose**: List all available product categories
**Success Response (200)**:
```json
{
  "categories": [
    {
      "id": "electronics",
      "name": "Electronics",
      "productCount": 8
    },
    {
      "id": "clothing",
      "name": "Clothing",
      "productCount": 6
    },
    {
      "id": "books",
      "name": "Books",
      "productCount": 4
    },
    {
      "id": "home",
      "name": "Home & Garden",
      "productCount": 2
    }
  ],
  "totalCategories": 4
}
```

### 2. Shopping Cart Operations

**Important**: All cart operations require session cookies. Ensure your HTTP client maintains cookies across requests.

#### GET /api/cart
**Purpose**: Retrieve current cart contents
**Session Required**: Yes
**Success Response (200)**:
```json
{
  "cart": {
    "items": [
      {
        "id": "cart_1759427912343_wm159etjg",
        "productId": "1",
        "productName": "Wireless Headphones",
        "price": 199.99,
        "quantity": 2
      }
    ],
    "total": 399.98,
    "itemCount": 2
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**Empty Cart Response (200)**:
```json
{
  "cart": {
    "items": [],
    "total": 0,
    "itemCount": 0
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### POST /api/cart
**Purpose**: Add item to shopping cart
**Session Required**: Yes
**Request Body**:
```json
{
  "productId": "1",
  "quantity": 2
}
```

**Success Response (200)**:
```json
{
  "message": "Item added to cart successfully",
  "cart": {
    "items": [
      {
        "id": "cart_1759427912343_wm159etjg",
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

**Error Responses**:
- `400`: Missing or invalid productId/quantity
- `404`: Product not found
- `400`: Product out of stock
- `500/503`: Random error simulation

#### DELETE /api/cart/{itemId}
**Purpose**: Remove specific item from cart
**Session Required**: Yes
**Path Parameters**:
- `itemId` (required): Cart item ID (from cart response)

**Success Response (200)**:
```json
{
  "message": "Item removed from cart successfully",
  "cart": {
    "items": [],
    "total": 0,
    "itemCount": 0
  }
}
```

**Error Responses**:
- `404`: Cart item not found
- `500/503`: Random error simulation

## Data Models

### Product
```json
{
  "id": "string",           // Unique identifier
  "name": "string",         // Product name
  "description": "string",  // Product description
  "price": "number",        // Price in USD
  "category": "string",     // Category ID
  "inStock": "boolean"      // Availability status
}
```

### Category
```json
{
  "id": "string",           // Unique identifier
  "name": "string",         // Display name
  "productCount": "number"  // Number of products in category
}
```

### Cart Item
```json
{
  "id": "string",           // Unique cart item ID
  "productId": "string",    // Reference to product
  "productName": "string",  // Product name (cached)
  "price": "number",        // Price per unit
  "quantity": "number"      // Quantity in cart
}
```

### Cart
```json
{
  "items": "CartItem[]",    // Array of cart items
  "total": "number",        // Total price
  "itemCount": "number"     // Total quantity of all items
}
```