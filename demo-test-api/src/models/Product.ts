export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  inStock: boolean;
}

export interface Category {
  id: string;
  name: string;
  productCount: number;
}