import { Router, Request, Response, NextFunction } from 'express';
import { getCategories } from '../models/dataSeeder';
import { asyncHandler } from '../middleware/errorHandler';

const router = Router();

// GET /api/categories - List all categories with product counts
router.get('/', asyncHandler(async (req: Request, res: Response, next: NextFunction) => {
  const categories = getCategories();
  
  res.json({
    categories,
    totalCategories: categories.length
  });
}));

export default router;