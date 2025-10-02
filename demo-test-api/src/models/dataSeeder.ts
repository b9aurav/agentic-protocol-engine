import { products, categories } from './data';
import { Product, Category } from './Product';

// In-memory storage for demo purposes
let productStore: Product[] = [];
let categoryStore: Category[] = [];

export function seedData(): void {
  console.log('Seeding demo data...');
  
  // Initialize product store with demo data
  productStore = [...products];
  categoryStore = [...categories];
  
  console.log(`Seeded ${productStore.length} products across ${categoryStore.length} categories`);
}

export function getProducts(): Product[] {
  return productStore;
}

export function getCategories(): Category[] {
  return categoryStore;
}

export function getProductById(id: string): Product | undefined {
  return productStore.find(product => product.id === id);
}

export function getProductsByCategory(categoryId: string): Product[] {
  return productStore.filter(product => product.category === categoryId);
}