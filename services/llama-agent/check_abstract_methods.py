#!/usr/bin/env python3
"""
Script to check what abstract methods are required by CustomLLM
"""

from llama_index.core.llms import CustomLLM
import inspect

def get_abstract_methods(cls):
    """Get all abstract methods from a class"""
    abstract_methods = []
    for name in dir(cls):
        method = getattr(cls, name)
        if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__:
            abstract_methods.append(name)
    return abstract_methods

if __name__ == "__main__":
    print("Abstract methods in CustomLLM:")
    abstract_methods = get_abstract_methods(CustomLLM)
    for method in abstract_methods:
        print(f"  - {method}")
    
    print(f"\nTotal abstract methods: {len(abstract_methods)}")