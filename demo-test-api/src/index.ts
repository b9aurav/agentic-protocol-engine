import express from 'express';
import session from 'express-session';
import cors from 'cors';
import helmet from 'helmet';
import { seedData } from './models/dataSeeder';
import productsRouter from './routes/products';
import categoriesRouter from './routes/categories';
import cartRouter from './routes/cart';
import { errorHandler, notFoundHandler } from './middleware/errorHandler';
import { 
  responseDelayMiddleware, 
  errorSimulationMiddleware, 
  errorSimulationInfoMiddleware,
  requestLoggingMiddleware
} from './middleware/errorSimulation';

const app = express();
const PORT = process.env.PORT || 3001;

// Security middleware
app.use(helmet());

// CORS configuration
app.use(cors({
  origin: true,
  credentials: true
}));

// Body parsing middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Session configuration
app.use(session({
  secret: process.env.SESSION_SECRET || 'demo-secret',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: false, // Set to true in production with HTTPS
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
  }
}));

// Request logging middleware (first to capture all requests)
app.use(requestLoggingMiddleware);

// Error simulation middleware (before routes)
app.use(errorSimulationInfoMiddleware);
app.use(responseDelayMiddleware);
app.use(errorSimulationMiddleware);

// API routes
app.use('/api/products', productsRouter);
app.use('/api/categories', categoriesRouter);
app.use('/api/cart', cartRouter);

// Health endpoints (fast, no error simulation)
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString()
  });
});

app.get('/api/status', (_req, res) => {
  res.json({
    status: 'running',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage()
  });
});

// API documentation route
app.get('/', (_req, res) => {
  res.json({
    message: 'Demo Test API is running',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    description: 'A lightweight API designed for testing the Agentic Protocol Engine (APE)',
    endpoints: {
      health: {
        'GET /api/health': 'Basic health check (always fast)',
        'GET /api/status': 'System status and information'
      },
      products: {
        'GET /api/products': 'List all products (supports pagination and filtering)',
        'GET /api/products/{id}': 'Get specific product details',
        'GET /api/categories': 'List all product categories'
      },
      cart: {
        'POST /api/cart': 'Add item to cart (requires productId and quantity)',
        'GET /api/cart': 'Get current cart contents',
        'DELETE /api/cart/{itemId}': 'Remove item from cart'
      }
    },
    configuration: {
      errorSimulation: {
        'ERROR_RATE_503': process.env.ERROR_RATE_503 || '0.05',
        'ERROR_RATE_500': process.env.ERROR_RATE_500 || '0.01'
      },
      responseDelay: {
        'RESPONSE_DELAY_MIN': process.env.RESPONSE_DELAY_MIN || '50',
        'RESPONSE_DELAY_MAX': process.env.RESPONSE_DELAY_MAX || '200'
      }
    },
    documentation: 'See README.md for detailed API documentation'
  });
});

// 404 handler for non-existent routes (must be after all routes)
app.use(notFoundHandler);

// Global error handling middleware (must be last)
app.use(errorHandler);

// Seed demo data on startup
seedData();

// Start server
app.listen(Number(PORT), '0.0.0.0', () => {
  console.log(`Demo Test API server running on http://0.0.0.0:${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

export default app;