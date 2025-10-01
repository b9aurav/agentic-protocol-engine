#!/usr/bin/env python3
"""
Simple test script for MCP Gateway functionality.
Tests Requirements 3.1, 3.2, 3.3 implementation.
"""

import asyncio
import json
import httpx
from src.models import MCPRequest, HTTPMethod


async def test_mcp_gateway():
    """Test MCP Gateway basic functionality."""
    
    # Test configuration
    gateway_url = "http://localhost:3000"
    
    async with httpx.AsyncClient() as client:
        print("Testing MCP Gateway...")
        
        # Test 1: Health check
        print("\n1. Testing health check...")
        try:
            response = await client.get(f"{gateway_url}/health")
            print(f"Health check status: {response.status_code}")
            print(f"Health response: {response.json()}")
        except Exception as e:
            print(f"Health check failed: {e}")
        
        # Test 2: Routes listing
        print("\n2. Testing routes listing...")
        try:
            response = await client.get(f"{gateway_url}/routes")
            print(f"Routes status: {response.status_code}")
            print(f"Routes: {response.json()}")
        except Exception as e:
            print(f"Routes listing failed: {e}")
        
        # Test 3: MCP request (will fail without target service, but tests validation)
        print("\n3. Testing MCP request validation...")
        try:
            mcp_request = MCPRequest(
                api_name="sut_api",
                method=HTTPMethod.GET,
                path="/health",
                headers={"User-Agent": "MCP-Gateway-Test"},
                trace_id="test-trace-123"
            )
            
            response = await client.post(
                f"{gateway_url}/mcp/request",
                json=mcp_request.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            print(f"MCP request status: {response.status_code}")
            print(f"MCP response: {response.json()}")
        except Exception as e:
            print(f"MCP request failed: {e}")
        
        # Test 4: Invalid MCP request
        print("\n4. Testing invalid MCP request...")
        try:
            invalid_request = {
                "api_name": "",  # Invalid empty api_name
                "method": "INVALID",  # Invalid method
                "path": "no-slash"  # Invalid path
            }
            
            response = await client.post(
                f"{gateway_url}/mcp/request",
                json=invalid_request,
                headers={"Content-Type": "application/json"}
            )
            print(f"Invalid request status: {response.status_code}")
            print(f"Invalid response: {response.json()}")
        except Exception as e:
            print(f"Invalid request test failed: {e}")
        
        # Test 5: Metrics endpoint
        print("\n5. Testing metrics endpoint...")
        try:
            response = await client.get(f"{gateway_url}/metrics")
            print(f"Metrics status: {response.status_code}")
            print(f"Metrics content type: {response.headers.get('content-type')}")
            print(f"Metrics sample: {response.text[:200]}...")
        except Exception as e:
            print(f"Metrics test failed: {e}")


if __name__ == "__main__":
    print("MCP Gateway Test Suite")
    print("=" * 50)
    print("Note: This test assumes the gateway is running on localhost:3000")
    print("Start the gateway with: python -m uvicorn src.gateway:app --host 0.0.0.0 --port 3000")
    print()
    
    asyncio.run(test_mcp_gateway())