import { Router, Request, Response, NextFunction } from 'express';
import { getProducts, getProductsByCategory, getProductById } from '../models/dataSeeder';
import { AppError, asyncHandler } from '../middleware/errorHandler';

const router = Router();

// GET /api/products - List products with optional pagination and category filtering
router.get('/', asyncHandler(async (req: Request, res: Response, next: NextFunction) => {
  const { page = '1', limit = '10', category } = req.query;
  
  // Parse pagination parameters
  const pageNum = parseInt(page as string, 10);
  const limitNum = parseInt(limit as string, 10);
  
  // Validate pagination parameters
  if (isNaN(pageNum) || pageNum < 1) {
    throw new AppError('Page must be a positive integer', 400, 'INVALID_PARAMETER');
  }
  
  if (isNaN(limitNum) || limitNum < 1 || limitNum > 100) {
    throw new AppError('Limit must be between 1 and 100', 400, 'INVALID_PARAMETER');
  }
  
  // Get products (filtered by category if specified)
  let products = category ? getProductsByCategory(category as string) : getProducts();
  
  // Calculate pagination
  const startIndex = (pageNum - 1) * limitNum;
  const endIndex = startIndex + limitNum;
  const totalProducts = products.length;
  const totalPages = Math.ceil(totalProducts / limitNum);
  
  // Apply pagination
  const paginatedProducts = products.slice(startIndex, endIndex);
  
  // Return response
  res.json({
    products: paginatedProducts,
    pagination: {
      currentPage: pageNum,
      totalPages,
      totalProducts,
      hasNextPage: pageNum < totalPages,
      hasPreviousPage: pageNum > 1
    },
    filters: {
      category: category || null
    }
  });
}));

// GET /api/products/{id} - Get specific product by ID
router.get('/:id', asyncHandler(async (req: Request, res: Response, next: NextFunction) => {
  const { id } = req.params;
  
  // Validate ID parameter
  if (!id || id.trim() === '') {
    throw new AppError('Product ID is required', 400, 'INVALID_PARAMETER');
  }
  
  // Find product by ID
  const product = getProductById(id);
  
  if (!product) {
    throw new AppError(`Product with ID '${id}' not found`, 404, 'RESOURCE_NOT_FOUND');
  }
  
  // Return product details
  res.json({
    product
  });
}));

export default router;