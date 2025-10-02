#!/usr/bin/env python3
"""
Example usage of HTTP operation tools for Llama Agents.
Demonstrates how the tools work together for stateful user journey simulation.
"""
import asyncio
from models import AgentConfig
from llama_agent import LlamaAgent


async def example_user_journey():
    """
    Example demonstrating a typical user journey using HTTP tools.
    This shows how an agent would use the tools for a login -> action -> logout flow.
    """
    
    # Initialize agent configuration
    config = AgentConfig(
        agent_id="example-agent-001",
        mcp_gateway_url="http://mcp_gateway:3000",
        cerebras_proxy_url="http://cerebras_proxy:8000"
    )
    
    # Create agent instance
    agent = LlamaAgent(config)
    
    # Start a session with a specific goal
    session_id = await agent.start_session(
        goal="Complete user login and perform account update"
    )
    
    print(f"Started session: {session_id}")
    
    # Example of how the agent would use tools in sequence:
    print("\n=== Example Tool Usage Sequence ===")
    
    # 1. HTTP GET - Check login page
    print("1. Agent would use http_get to fetch login page:")
    print("   http_get(api_name='webapp', path='/login')")
    
    # 2. HTTP POST - Submit login credentials
    print("2. Agent would use http_post to submit login:")
    print("   http_post(api_name='webapp', path='/auth/login', data={'username': 'user', 'password': 'pass'})")
    
    # 3. State Update - Store session token
    print("3. Agent would use state_update to store session data:")
    print("   state_update(session_id=session_id, session_data={'token': 'jwt_token_123', 'user_id': '456'})")
    
    # 4. HTTP GET - Access protected resource
    print("4. Agent would use http_get with session headers:")
    print("   http_get(api_name='webapp', path='/profile', headers={'Authorization': 'Bearer jwt_token_123'})")
    
    # 5. HTTP PUT - Update user profile
    print("5. Agent would use http_put to update data:")
    print("   http_put(api_name='webapp', path='/profile', data={'email': 'new@email.com'}, headers={'Authorization': 'Bearer jwt_token_123'})")
    
    # 6. HTTP POST - Logout
    print("6. Agent would use http_post to logout:")
    print("   http_post(api_name='webapp', path='/auth/logout', data={}, headers={'Authorization': 'Bearer jwt_token_123'})")
    
    # Get session information
    session_info = agent.get_session_info(session_id)
    print(f"\nSession Info: {session_info}")
    
    # Health check
    health = await agent.health_check()
    print(f"Agent Health: {health}")


def demonstrate_tool_features():
    """
    Demonstrate the key features of the HTTP operation tools.
    """
    print("\n=== HTTP Operation Tools Features ===")
    
    print("\n1. Tool_HTTP_GET:")
    print("   - Read-only operations (fetch data, check status)")
    print("   - Automatic session header extraction from responses")
    print("   - Trace ID generation for request correlation")
    print("   - Error handling with detailed error categorization")
    
    print("\n2. Tool_HTTP_POST:")
    print("   - Write operations (login, form submission, create resources)")
    print("   - Session data extraction from response body and headers")
    print("   - Support for JSON payloads and authentication headers")
    print("   - Automatic token/session ID detection in responses")
    
    print("\n3. Tool_HTTP_PUT:")
    print("   - Update operations (modify resources, update data)")
    print("   - Session header propagation for authenticated requests")
    print("   - Response processing and error handling")
    
    print("\n4. Tool_HTTP_DELETE:")
    print("   - Delete operations (remove resources, cancel transactions)")
    print("   - Minimal payload with session header support")
    print("   - Proper error categorization for different response codes")
    
    print("\n5. Tool_State_Update:")
    print("   - Internal session context management")
    print("   - Persistent storage of cookies, tokens, transaction IDs")
    print("   - Integration with agent worker for stateful behavior")
    print("   - Session validation and expiration handling")
    
    print("\n=== MCP Gateway Integration ===")
    print("- All HTTP tools use MCP-compliant JSON schemas")
    print("- Standardized request/response format via MCPToolCall model")
    print("- Automatic trace ID injection for observability")
    print("- Configurable routing through target_api_name parameter")
    
    print("\n=== Error Handling & Observability ===")
    print("- Comprehensive error categorization (2xx, 4xx, 5xx)")
    print("- Structured logging with trace correlation")
    print("- Execution time measurement for performance analysis")
    print("- Graceful degradation on network/service failures")


if __name__ == "__main__":
    print("HTTP Operation Tools - Example Usage")
    print("=" * 50)
    
    # Demonstrate tool features
    demonstrate_tool_features()
    
    # Note: The actual execution would require the full containerized environment
    print("\n" + "=" * 50)
    print("Note: Full execution requires containerized environment with:")
    print("- MCP Gateway service running")
    print("- Cerebras Proxy service running") 
    print("- Target application (System Under Test)")
    print("- Proper network configuration")
    
    print("\nTo run the actual agent:")
    print("1. Start the Docker Compose environment")
    print("2. Configure MCP Gateway routing")
    print("3. Run: python -m llama_agent")