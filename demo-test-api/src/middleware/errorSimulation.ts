import { Request, Response, NextFunction } from 'express';
import { AppError } from './errorHandler';

// Configuration from environment variables
const ERROR_RATE_503 = parseFloat(process.env.ERROR_RATE_503 || '0.05'); // 5% default
const ERROR_RATE_500 = parseFloat(process.env.ERROR_RATE_500 || '0.01'); // 1% default
const RESPONSE_DELAY_MIN = parseInt(process.env.RESPONSE_DELAY_MIN || '50'); // 50ms default
const RESPONSE_DELAY_MAX = parseInt(process.env.RESPONSE_DELAY_MAX || '200'); // 200ms default

// Health endpoints that should remain fast
const FAST_ENDPOINTS = ['/api/health', '/api/status'];

// Random delay simulation middleware
export const responseDelayMiddleware = (
  req: Request,
  _res: Response,
  next: NextFunction
): void => {
  // Skip delay for health endpoints
  if (FAST_ENDPOINTS.includes(req.path)) {
    return next();
  }

  // Calculate random delay between min and max
  const delay = Math.floor(Math.random() * (RESPONSE_DELAY_MAX - RESPONSE_DELAY_MIN + 1)) + RESPONSE_DELAY_MIN;
  
  setTimeout(() => {
    next();
  }, delay);
};

// Error simulation middleware
export const errorSimulationMiddleware = (
  req: Request,
  _res: Response,
  next: NextFunction
): void => {
  // Skip error simulation for health endpoints
  if (FAST_ENDPOINTS.includes(req.path)) {
    return next();
  }

  const random = Math.random();

  // Simulate 503 Service Unavailable
  if (random < ERROR_RATE_503) {
    const error = new AppError(
      'Service temporarily unavailable due to high load',
      503,
      'SERVICE_UNAVAILABLE'
    );
    return next(error);
  }

  // Simulate 500 Internal Server Error
  if (random < ERROR_RATE_503 + ERROR_RATE_500) {
    const error = new AppError(
      'An unexpected error occurred while processing your request',
      500,
      'INTERNAL_SERVER_ERROR'
    );
    return next(error);
  }

  // Continue with normal processing
  next();
};

// Request logging middleware to track APE agent activity
export const requestLoggingMiddleware = (
  req: Request,
  res: Response,
  next: NextFunction
): void => {
  const timestamp = new Date().toISOString();
  const userAgent = req.get('User-Agent') || 'Unknown';
  const sessionId = (req.session as any)?.id || 'No Session';
  const startTime = Date.now();
  
  // Log the incoming request
  console.log(`[${timestamp}] 📥 ${req.method} ${req.path} | User-Agent: ${userAgent} | Session: ${sessionId}`);
  
  // Log request body for POST/PUT requests (useful for cart operations)
  if ((req.method === 'POST' || req.method === 'PUT') && req.body) {
    console.log(`[${timestamp}] 📝 Request Body:`, JSON.stringify(req.body, null, 2));
  }
  
  // Log query parameters if present
  if (Object.keys(req.query).length > 0) {
    console.log(`[${timestamp}] 🔍 Query Params:`, JSON.stringify(req.query, null, 2));
  }
  
  // Override res.end to log response
  const originalEnd = res.end.bind(res);
  res.end = function(chunk?: any, encoding?: any, cb?: any) {
    const endTime = Date.now();
    const duration = endTime - startTime;
    const responseTimestamp = new Date().toISOString();
    
    console.log(`[${responseTimestamp}] 📤 ${req.method} ${req.path} | Status: ${res.statusCode} | Duration: ${duration}ms`);
    
    // Call original end method with proper return
    return originalEnd(chunk, encoding, cb);
  };
  
  next();
};

// Middleware to add error simulation info to response headers (for debugging)
export const errorSimulationInfoMiddleware = (
  _req: Request,
  res: Response,
  next: NextFunction
): void => {
  // Add configuration info to response headers for debugging
  res.set({
    'X-Error-Rate-503': ERROR_RATE_503.toString(),
    'X-Error-Rate-500': ERROR_RATE_500.toString(),
    'X-Response-Delay-Range': `${RESPONSE_DELAY_MIN}-${RESPONSE_DELAY_MAX}ms`
  });
  
  next();
};