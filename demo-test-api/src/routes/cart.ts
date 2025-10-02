import { Router, Request, Response, NextFunction } from 'express';
import { CartService } from '../services/cartService';
import { products } from '../models/data';
import { AppError, asyncHandler } from '../middleware/errorHandler';

const router = Router();

/**
 * POST /api/cart
 * Add item to cart
 */
router.post('/', asyncHandler(async (req: Request, res: Response, next: NextFunction) => {
  const { productId, quantity = 1 } = req.body;

  // Validate request body
  if (!productId) {
    throw new AppError('Product ID is required', 400, 'MISSING_PRODUCT_ID');
  }

  // Validate quantity
  if (quantity < 1 || !Number.isInteger(quantity)) {
    throw new AppError('Quantity must be a positive integer', 400, 'INVALID_QUANTITY');
  }

  // Find the product
  const product = products.find(p => p.id === productId);
  if (!product) {
    throw new AppError(`Product with ID '${productId}' not found`, 404, 'PRODUCT_NOT_FOUND');
  }

  // Check if product is in stock
  if (!product.inStock) {
    throw new AppError(`Product '${product.name}' is currently out of stock`, 400, 'PRODUCT_OUT_OF_STOCK');
  }

  // Add to cart
  const cart = CartService.addToCart(req, product, quantity);

  res.status(200).json({
    message: 'Item added to cart successfully',
    cart,
    timestamp: new Date().toISOString()
  });
}));

/**
 * GET /api/cart
 * Get current cart contents
 */
router.get('/', asyncHandler(async (req: Request, res: Response, next: NextFunction) => {
  const cart = CartService.getCart(req);

  res.status(200).json({
    cart,
    timestamp: new Date().toISOString()
  });
}));

/**
 * DELETE /api/cart/:itemId
 * Remove item from cart
 */
router.delete('/:itemId', asyncHandler(async (req: Request, res: Response, next: NextFunction) => {
  const { itemId } = req.params;

  // Validate itemId parameter
  if (!itemId) {
    throw new AppError('Item ID is required', 400, 'MISSING_ITEM_ID');
  }

  // Check if item exists in cart
  if (!CartService.hasItem(req, itemId)) {
    throw new AppError(`Cart item with ID '${itemId}' not found`, 404, 'CART_ITEM_NOT_FOUND');
  }

  // Remove item from cart
  const cart = CartService.removeFromCart(req, itemId);

  res.status(200).json({
    message: 'Item removed from cart successfully',
    cart,
    timestamp: new Date().toISOString()
  });
}));

export default router;