import { Request } from 'express';
import { Product } from '../models/Product';

export interface CartItem {
  id: string;
  productId: string;
  productName: string;
  price: number;
  quantity: number;
}

export interface Cart {
  items: CartItem[];
  total: number;
  itemCount: number;
}

// Extend Express Session interface to include cart
declare module 'express-session' {
  interface SessionData {
    cart?: CartItem[];
  }
}

export class CartService {
  /**
   * Get cart from session, initialize if doesn't exist
   */
  static getCart(req: Request): Cart {
    if (!req.session.cart) {
      req.session.cart = [];
    }

    const items = req.session.cart;
    const total = items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const itemCount = items.reduce((sum, item) => sum + item.quantity, 0);

    return {
      items,
      total: Math.round(total * 100) / 100, // Round to 2 decimal places
      itemCount
    };
  }

  /**
   * Add item to cart or update quantity if item already exists
   */
  static addToCart(req: Request, product: Product, quantity: number = 1): Cart {
    if (!req.session.cart) {
      req.session.cart = [];
    }

    const existingItemIndex = req.session.cart.findIndex(item => item.productId === product.id);

    if (existingItemIndex >= 0) {
      // Update quantity of existing item
      req.session.cart[existingItemIndex].quantity += quantity;
    } else {
      // Add new item to cart
      const cartItem: CartItem = {
        id: `cart_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        productId: product.id,
        productName: product.name,
        price: product.price,
        quantity
      };
      req.session.cart.push(cartItem);
    }

    return this.getCart(req);
  }

  /**
   * Remove item from cart by cart item ID
   */
  static removeFromCart(req: Request, itemId: string): Cart {
    if (!req.session.cart) {
      req.session.cart = [];
    }

    req.session.cart = req.session.cart.filter(item => item.id !== itemId);
    return this.getCart(req);
  }

  /**
   * Check if item exists in cart
   */
  static hasItem(req: Request, itemId: string): boolean {
    if (!req.session.cart) {
      return false;
    }
    return req.session.cart.some(item => item.id === itemId);
  }

  /**
   * Clear entire cart
   */
  static clearCart(req: Request): Cart {
    req.session.cart = [];
    return this.getCart(req);
  }
}