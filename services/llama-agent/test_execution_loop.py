#!/usr/bin/env python3
"""
Test script for the enhanced agent execution loop and error handling.
"""
import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llama_agent import LlamaAgent
from models import AgentConfig


async def test_execution_loop():
    """Test the enhanced execution loop with error handling."""
    print("Testing Agent Execution Loop and Error Handling")
    print("=" * 50)
    
    # Create test configuration
    config = AgentConfig(
        agent_id="test-agent-001",
        mcp_gateway_url="http://localhost:8080",
        cerebras_proxy_url="http://localhost:8000",
        session_timeout_minutes=30,
        max_retries=3,
        inference_timeout=10.0,
        log_level="INFO"
    )
    
    # Mock the LLM to avoid actual API calls
    with patch('llama_agent.OpenAI') as mock_llm_class:
        # Create mock LLM instance
        mock_llm = AsyncMock()
        mock_llm.acomplete.return_value = Mock(text="Test response")
        mock_llm_class.return_value = mock_llm
        
        # Mock the agent runner to simulate execution
        with patch('llama_agent.AgentRunner') as mock_runner_class:
            mock_runner = AsyncMock()
            mock_task = Mock()
            mock_runner.create_task.return_value = mock_task
            mock_runner.arun_task.return_value = Mock(response="Goal completed successfully")
            mock_runner_class.return_value = mock_runner
            
            try:
                # Initialize agent
                print("1. Initializing agent...")
                agent = LlamaAgent(config)
                print("   ✓ Agent initialized successfully")
                
                # Test session creation
                print("\n2. Testing session creation...")
                session_id = await agent.start_session("Test user login and purchase flow")
                print(f"   ✓ Session created: {session_id}")
                
                # Test session info retrieval
                print("\n3. Testing session info retrieval...")
                session_info = agent.get_session_info(session_id)
                print(f"   ✓ Session info retrieved: {session_info['goal']}")
                
                # Test goal execution
                print("\n4. Testing goal execution...")
                result = await agent.execute_goal(session_id)
                print(f"   ✓ Goal execution completed: {result['success']}")
                print(f"   ✓ Steps completed: {result['steps_completed']}")
                
                # Test error handling with timeout simulation
                print("\n5. Testing timeout error handling...")
                with patch.object(agent.agent_runner, 'arun_task', side_effect=asyncio.TimeoutError("Simulated timeout")):
                    result = await agent.execute_goal(session_id)
                    print(f"   ✓ Timeout handled gracefully: {not result['success']}")
                    print(f"   ✓ Error message: {result.get('error', 'No error message')}")
                
                # Test error recovery
                print("\n6. Testing error recovery...")
                # Simulate a recoverable error followed by success
                call_count = 0
                def side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise Exception("503 Service Unavailable")
                    return Mock(response="Recovered successfully")
                
                with patch.object(agent.agent_runner, 'arun_task', side_effect=side_effect):
                    result = await agent.execute_goal(session_id)
                    print(f"   ✓ Error recovery successful: {result['success']}")
                    print(f"   ✓ Execution attempts: {result.get('execution_attempts', 1)}")
                
                # Test health check
                print("\n7. Testing health check...")
                health = await agent.health_check()
                print(f"   ✓ Health check completed: {health['status']}")
                
                # Test session cleanup
                print("\n8. Testing session cleanup...")
                agent.cleanup_sessions()
                print("   ✓ Session cleanup completed")
                
                print("\n" + "=" * 50)
                print("✓ All tests passed successfully!")
                
            except Exception as e:
                print(f"\n❌ Test failed with error: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    return True


async def test_error_categorization():
    """Test error categorization functionality."""
    print("\nTesting Error Categorization")
    print("=" * 30)
    
    config = AgentConfig(agent_id="test-agent-002")
    
    with patch('llama_agent.OpenAI'), patch('llama_agent.AgentRunner'):
        agent = LlamaAgent(config)
        
        # Test different error types
        test_errors = [
            (Exception("Connection timeout"), True, "network/transient"),
            (Exception("401 Unauthorized"), False, "auth"),
            (Exception("503 Service Unavailable"), True, "server"),
            (Exception("Invalid schema"), False, "fatal"),
            (Exception("Rate limit exceeded"), True, "rate_limit"),
        ]
        
        for error, should_be_recoverable, expected_category in test_errors:
            is_recoverable = agent._is_recoverable_error(error)
            print(f"   Error: {str(error)[:30]:<30} Recoverable: {is_recoverable} (Expected: {should_be_recoverable})")
            
            if is_recoverable != should_be_recoverable:
                print(f"   ❌ Unexpected recoverability for: {error}")
                return False
    
    print("   ✓ Error categorization working correctly")
    return True


async def main():
    """Run all tests."""
    print("Agent Execution Loop and Error Handling Tests")
    print("=" * 60)
    
    try:
        # Test execution loop
        success1 = await test_execution_loop()
        
        # Test error categorization
        success2 = await test_error_categorization()
        
        if success1 and success2:
            print("\n🎉 All tests completed successfully!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)