#!/usr/bin/env python3
"""
Simple test script for Cerebras Proxy service
"""

import asyncio
import json
import os
from typing import Dict, Any

import httpx


async def test_health_endpoint(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test health check endpoint"""
    try:
        response = await client.get(f"{base_url}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed: {data}")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False


async def test_models_endpoint(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test models list endpoint"""
    try:
        response = await client.get(f"{base_url}/v1/models")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Models endpoint passed: {len(data.get('data', []))} models")
            return True
        else:
            print(f"✗ Models endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Models endpoint error: {e}")
        return False


async def test_chat_completion(client: httpx.AsyncClient, base_url: str, api_key: str = None) -> bool:
    """Test chat completion endpoint"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    request_data = {
        "model": "llama3.1-8b",
        "messages": [
            {"role": "user", "content": "Say hello in exactly 5 words."}
        ],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    try:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=request_data,
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            print(f"✓ Chat completion passed:")
            print(f"  Response: {message}")
            print(f"  Tokens: {usage.get('total_tokens', 0)} total")
            return True
        else:
            print(f"✗ Chat completion failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Chat completion error: {e}")
        return False


async def test_metrics_endpoint(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test metrics endpoint"""
    try:
        response = await client.get(f"{base_url}/metrics")
        if response.status_code == 200:
            metrics = response.text
            lines = metrics.split('\n')
            metric_lines = [line for line in lines if line and not line.startswith('#')]
            print(f"✓ Metrics endpoint passed: {len(metric_lines)} metrics")
            return True
        else:
            print(f"✗ Metrics endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Metrics endpoint error: {e}")
        return False


async def main():
    """Run all tests"""
    base_url = os.getenv("CEREBRAS_PROXY_URL", "http://localhost:8000")
    api_key = os.getenv("APE_API_KEY")
    
    print(f"Testing Cerebras Proxy at {base_url}")
    print(f"API Key: {'Set' if api_key else 'Not set (development mode)'}")
    print("-" * 50)
    
    async with httpx.AsyncClient() as client:
        tests = [
            ("Health Check", test_health_endpoint(client, base_url)),
            ("Models List", test_models_endpoint(client, base_url)),
            ("Metrics", test_metrics_endpoint(client, base_url)),
        ]
        
        # Only test chat completion if we have a Cerebras API key
        if os.getenv("CEREBRAS_API_KEY"):
            tests.append(("Chat Completion", test_chat_completion(client, base_url, api_key)))
        else:
            print("⚠ Skipping chat completion test (CEREBRAS_API_KEY not set)")
        
        results = []
        for test_name, test_coro in tests:
            print(f"\nRunning {test_name}...")
            result = await test_coro
            results.append((test_name, result))
        
        print("\n" + "=" * 50)
        print("Test Results:")
        passed = 0
        for test_name, result in results:
            status = "PASS" if result else "FAIL"
            print(f"  {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\nPassed: {passed}/{len(results)} tests")
        
        if passed == len(results):
            print("🎉 All tests passed!")
            return 0
        else:
            print("❌ Some tests failed!")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())