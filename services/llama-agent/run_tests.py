#!/usr/bin/env python3
"""
Test runner for Llama Agent unit tests.
Runs the core component tests that validate tool call generation, session management, and LLM mocking.
"""
import subprocess
import sys
import os


def run_tests():
    """Run the unit tests and return exit code."""
    print("Running Llama Agent Unit Tests")
    print("=" * 50)
    
    # Change to the correct directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(test_dir)
    
    try:
        # Run the core component tests
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "test_core_components.py", 
            "-v", 
            "--tb=short"
        ], capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n✅ All unit tests passed successfully!")
            print("\nTest Coverage Summary:")
            print("- ✅ MCP Tool Call generation and validation")
            print("- ✅ Agent Session Context management")
            print("- ✅ Session Success Tracking")
            print("- ✅ Mock LLM responses for deterministic testing")
            print("- ✅ Tool Execution validation and error handling")
            print("\nRequirements validated:")
            print("- ✅ Requirement 1.3: Tool integration and validation")
            print("- ✅ Requirement 7.5: Session context management")
        else:
            print(f"\n❌ Tests failed with exit code: {result.returncode}")
            
        return result.returncode
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)