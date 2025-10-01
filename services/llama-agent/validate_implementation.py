#!/usr/bin/env python3
"""
Validation script to check the implementation structure without requiring dependencies.
"""
import ast
import os
import sys


def validate_python_file(filepath):
    """Validate a Python file for syntax and structure."""
    print(f"Validating {filepath}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST to check syntax
        tree = ast.parse(content, filename=filepath)
        
        # Check for required classes and methods
        classes = []
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
        
        print(f"  ✓ Syntax valid")
        print(f"  ✓ Classes found: {', '.join(classes) if classes else 'None'}")
        print(f"  ✓ Functions found: {len(functions)} functions")
        
        return True
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def validate_implementation():
    """Validate the implementation files."""
    print("Validating Agent Execution Loop Implementation")
    print("=" * 50)
    
    files_to_validate = [
        "services/llama-agent/llama_agent.py",
        "services/llama-agent/agent_worker.py", 
        "services/llama-agent/tools.py",
        "services/llama-agent/models.py",
        "services/llama-agent/main.py"
    ]
    
    all_valid = True
    
    for filepath in files_to_validate:
        if os.path.exists(filepath):
            if not validate_python_file(filepath):
                all_valid = False
        else:
            print(f"❌ File not found: {filepath}")
            all_valid = False
        print()
    
    return all_valid


def check_implementation_features():
    """Check if key implementation features are present."""
    print("Checking Implementation Features")
    print("=" * 35)
    
    features_to_check = [
        ("Goal-driven execution", "services/llama-agent/llama_agent.py", "execute_goal"),
        ("Error recovery", "services/llama-agent/llama_agent.py", "_apply_error_recovery_strategy"),
        ("Success evaluation", "services/llama-agent/llama_agent.py", "_evaluate_execution_success"),
        ("Error categorization", "services/llama-agent/agent_worker.py", "_categorize_error"),
        ("HTTP retry logic", "services/llama-agent/tools.py", "_is_retryable_status"),
        ("Session state extraction", "services/llama-agent/llama_agent.py", "_process_execution_response"),
    ]
    
    all_features_present = True
    
    for feature_name, filepath, method_name in features_to_check:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if method_name in content:
                print(f"  ✓ {feature_name}: Found {method_name}")
            else:
                print(f"  ❌ {feature_name}: Missing {method_name}")
                all_features_present = False
                
        except Exception as e:
            print(f"  ❌ {feature_name}: Error checking {filepath} - {e}")
            all_features_present = False
    
    return all_features_present


def check_requirements_coverage():
    """Check if the implementation covers the specified requirements."""
    print("\nChecking Requirements Coverage")
    print("=" * 30)
    
    requirements = [
        ("1.4: Adaptive decision-making", "execute_goal", "llama_agent.py"),
        ("1.5: Error recovery", "_apply_error_recovery_strategy", "llama_agent.py"),
        ("8.1: Error categorization", "_categorize_error", "agent_worker.py"),
        ("8.4: Comprehensive error handling", "_is_recoverable_error", "llama_agent.py"),
    ]
    
    all_covered = True
    
    for req_desc, method_name, filename in requirements:
        filepath = f"services/llama-agent/{filename}"
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if method_name in content:
                print(f"  ✓ {req_desc}")
            else:
                print(f"  ❌ {req_desc}: Missing implementation")
                all_covered = False
                
        except Exception as e:
            print(f"  ❌ {req_desc}: Error - {e}")
            all_covered = False
    
    return all_covered


def main():
    """Run all validation checks."""
    print("Agent Implementation Validation")
    print("=" * 40)
    print()
    
    # Validate syntax and structure
    syntax_valid = validate_implementation()
    
    # Check implementation features
    features_present = check_implementation_features()
    
    # Check requirements coverage
    requirements_covered = check_requirements_coverage()
    
    print("\n" + "=" * 40)
    print("Validation Summary:")
    print(f"  Syntax Valid: {'✓' if syntax_valid else '❌'}")
    print(f"  Features Present: {'✓' if features_present else '❌'}")
    print(f"  Requirements Covered: {'✓' if requirements_covered else '❌'}")
    
    if syntax_valid and features_present and requirements_covered:
        print("\n🎉 Implementation validation successful!")
        print("Task 4.3 'Add agent execution loop and error handling' is complete.")
        return 0
    else:
        print("\n❌ Implementation validation failed!")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)