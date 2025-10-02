import { Product, Category } from './Product';

export const products: Product[] = [
  // Electronics (8 products)
  {
    id: "1",
    name: "Wireless Headphones",
    description: "High-quality wireless headphones with noise cancellation",
    price: 199.99,
    category: "electronics",
    inStock: true
  },
  {
    id: "2", 
    name: "Smartphone",
    description: "Latest model smartphone with advanced camera features",
    price: 799.99,
    category: "electronics",
    inStock: true
  },
  {
    id: "3",
    name: "Laptop Computer",
    description: "Powerful laptop for work and gaming",
    price: 1299.99,
    category: "electronics",
    inStock: false
  },
  {
    id: "4",
    name: "Bluetooth Speaker",
    description: "Portable wireless speaker with excellent sound quality",
    price: 89.99,
    category: "electronics",
    inStock: true
  },
  {
    id: "5",
    name: "Smart Watch",
    description: "Fitness tracking smartwatch with heart rate monitor",
    price: 299.99,
    category: "electronics",
    inStock: true
  },
  {
    id: "6",
    name: "Tablet",
    description: "10-inch tablet perfect for reading and entertainment",
    price: 449.99,
    category: "electronics",
    inStock: true
  },
  {
    id: "7",
    name: "Gaming Mouse",
    description: "High-precision gaming mouse with RGB lighting",
    price: 79.99,
    category: "electronics",
    inStock: false
  },
  {
    id: "8",
    name: "Wireless Charger",
    description: "Fast wireless charging pad for smartphones",
    price: 39.99,
    category: "electronics",
    inStock: true
  },

  // Clothing (6 products)
  {
    id: "9",
    name: "Cotton T-Shirt",
    description: "Comfortable 100% cotton t-shirt in various colors",
    price: 24.99,
    category: "clothing",
    inStock: true
  },
  {
    id: "10",
    name: "Denim Jeans",
    description: "Classic fit denim jeans with premium quality",
    price: 79.99,
    category: "clothing",
    inStock: true
  },
  {
    id: "11",
    name: "Winter Jacket",
    description: "Warm and stylish winter jacket with hood",
    price: 149.99,
    category: "clothing",
    inStock: false
  },
  {
    id: "12",
    name: "Running Shoes",
    description: "Lightweight running shoes with excellent cushioning",
    price: 119.99,
    category: "clothing",
    inStock: true
  },
  {
    id: "13",
    name: "Wool Sweater",
    description: "Cozy wool sweater perfect for cold weather",
    price: 89.99,
    category: "clothing",
    inStock: true
  },
  {
    id: "14",
    name: "Baseball Cap",
    description: "Adjustable baseball cap with embroidered logo",
    price: 29.99,
    category: "clothing",
    inStock: true
  },

  // Books (4 products)
  {
    id: "15",
    name: "Programming Guide",
    description: "Comprehensive guide to modern programming practices",
    price: 49.99,
    category: "books",
    inStock: true
  },
  {
    id: "16",
    name: "Science Fiction Novel",
    description: "Bestselling science fiction adventure story",
    price: 19.99,
    category: "books",
    inStock: true
  },
  {
    id: "17",
    name: "Cookbook",
    description: "Collection of healthy and delicious recipes",
    price: 34.99,
    category: "books",
    inStock: false
  },
  {
    id: "18",
    name: "History Book",
    description: "Fascinating exploration of world history",
    price: 39.99,
    category: "books",
    inStock: true
  },

  // Home & Garden (2 products)
  {
    id: "19",
    name: "Indoor Plant",
    description: "Beautiful low-maintenance indoor plant",
    price: 24.99,
    category: "home",
    inStock: true
  },
  {
    id: "20",
    name: "Coffee Maker",
    description: "Programmable coffee maker with thermal carafe",
    price: 129.99,
    category: "home",
    inStock: true
  }
];

export const categories: Category[] = [
  {
    id: "electronics",
    name: "Electronics",
    productCount: 8
  },
  {
    id: "clothing", 
    name: "Clothing",
    productCount: 6
  },
  {
    id: "books",
    name: "Books", 
    productCount: 4
  },
  {
    id: "home",
    name: "Home & Garden",
    productCount: 2
  }
];