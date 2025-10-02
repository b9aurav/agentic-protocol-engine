#!/usr/bin/env python3
"""
Comprehensive unit tests for MCP Gateway.
Tests Requirements 3.3, 8.4 - request routing, validation, error handling, and trace ID propagation.
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response, RequestError, TimeoutException
import time

from src.gateway import app, load_gateway_config
from src.models import (
    MCPRequest, MCPResponse, HTTPMethod, RouteConfig, RetryPolicy, 
    GatewayConfig, AuthConfig, HealthCheckConfig
)
from src.router import RequestRouter


class TestMCPGatewayValidation:
    """Test MCP request validation and schema compliance."""
    
    def setup_method(self):
        """Setup test client and mock configuration."""
        self.client = TestClient(app)
        
        # Mock configuration
        self.mock_config = GatewayConfig(
            routes={
                "test_api": RouteConfig(
                    name="Test API",
                    description="Test service for unit tests",
                    base_url="http://test-service:8080",
                    timeout=30,
                    retry_policy=RetryPolicy(max_retries=2, backoff_factor=1.5)
                ),
                "auth_api": RouteConfig(
                    name="Authenticated API",
                    description="API with authentication",
                    base_url="http://auth-service:8080",
                    timeout=15,
                    auth=AuthConfig(
                        type="bearer",
                        headers={"Authorization": "Bearer test-token"}
                    )
                )
            }
        )
    
    def test_valid_mcp_request_validation(self):
        """Test that valid MCP requests pass validation."""
        # Test GET request
        valid_request = MCPRequest(
            api_name="test_api",
            method=HTTPMethod.GET,
            path="/users",
            headers={"User-Agent": "test-agent"},
            trace_id="test-trace-123"
        )
        
        assert valid_request.api_name == "test_api"
        assert valid_request.method == HTTPMethod.GET
        assert valid_request.path == "/users"
        assert valid_request.headers["User-Agent"] == "test-agent"
        assert valid_request.trace_id == "test-trace-123"
    
    def test_path_validation_adds_slash(self):
        """Test that paths without leading slash are corrected."""
        request = MCPRequest(
            api_name="test_api",
            method=HTTPMethod.GET,
            path="users/123"  # No leading slash
        )
        
        assert request.path == "/users/123"
    
    def test_empty_api_name_validation(self):
        """Test that empty api_name raises validation error."""
        with pytest.raises(ValueError, match="api_name cannot be empty"):
            MCPRequest(
                api_name="",
                method=HTTPMethod.GET,
                path="/test"
            )
    
    def test_whitespace_api_name_validation(self):
        """Test that whitespace-only api_name raises validation error."""
        with pytest.raises(ValueError, match="api_name cannot be empty"):
            MCPRequest(
                api_name="   ",
                method=HTTPMethod.GET,
                path="/test"
            )
    
    def test_invalid_http_method_validation(self):
        """Test that invalid HTTP methods are rejected."""
        with pytest.raises(ValueError):
            MCPRequest(
                api_name="test_api",
                method="INVALID_METHOD",  # Invalid method
                path="/test"
            )
    
    def test_post_request_with_data_validation(self):
        """Test POST request with data payload validation."""
        request = MCPRequest(
            api_name="test_api",
            method=HTTPMethod.POST,
            path="/users",
            data={"name": "John Doe", "email": "john@example.com"},
            headers={"Content-Type": "application/json"}
        )
        
        assert request.data["name"] == "John Doe"
        assert request.data["email"] == "john@example.com"


class TestRequestRouter:
    """Test request routing functionality."""
    
    def setup_method(self):
        """Setup router with test configuration."""
        self.routes = {
            "test_api": RouteConfig(
                name="Test API",
                description="Test service",
                base_url="http://test-service:8080",
                timeout=30,
                retry_policy=RetryPolicy(max_retries=2, backoff_factor=1.5)
            ),
            "slow_api": RouteConfig(
                name="Slow API",
                description="API with retry configuration",
                base_url="http://slow-service:8080",
                timeout=5,
                retry_policy=RetryPolicy(
                    max_retries=3,
                    backoff_factor=2.0,
                    retry_on=[502, 503, 504, 408, 429]
                )
            )
        }
        self.router = RequestRouter(self.routes)
    
    @pytest.mark.asyncio
    async def test_successful_request_routing(self):
        """Test successful request routing to target service."""
        # Mock successful HTTP response
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"status": "success", "data": {"id": 123}}
        mock_response.content = b'{"status": "success", "data": {"id": 123}}'
        mock_response.text = '{"status": "success", "data": {"id": 123}}'
        
        with patch.object(self.router.http_client, 'request', return_value=mock_response) as mock_request:
            request = MCPRequest(
                api_name="test_api",
                method=HTTPMethod.GET,
                path="/users/123",
                headers={"User-Agent": "test-agent"},
                trace_id="test-trace-456"
            )
            
            response = await self.router.route_request(request)
            
            # Verify request was made correctly
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]['method'] == 'GET'
            assert call_args[1]['url'] == 'http://test-service:8080/users/123'
            assert call_args[1]['timeout'] == 30
            
            # Verify headers include trace ID and other required headers
            headers = call_args[1]['headers']
            assert headers['X-Trace-ID'] == 'test-trace-456'
            assert headers['X-API-Name'] == 'test_api'
            assert headers['X-MCP-Gateway'] == '1.0.0'
            assert headers['User-Agent'] == 'test-agent'
            
            # Verify response
            assert isinstance(response, MCPResponse)
            assert response.status_code == 200
            assert response.trace_id == "test-trace-456"
            assert response.body["status"] == "success"
            assert response.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_route_not_found_error(self):
        """Test error handling when route is not found."""
        request = MCPRequest(
            api_name="nonexistent_api",
            method=HTTPMethod.GET,
            path="/test"
        )
        
        with pytest.raises(Exception) as exc_info:
            await self.router.route_request(request)
        
        assert "Route 'nonexistent_api' not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_request_with_authentication_headers(self):
        """Test request routing with authentication headers."""
        # Add authenticated route
        auth_route = RouteConfig(
            name="Auth API",
            description="Authenticated API",
            base_url="http://auth-service:8080",
            auth=AuthConfig(
                type="bearer",
                headers={"Authorization": "Bearer secret-token"}
            )
        )
        self.router.routes["auth_api"] = auth_route
        
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"authenticated": True}
        mock_response.content = b'{"authenticated": true}'
        mock_response.text = '{"authenticated": true}'
        
        with patch.object(self.router.http_client, 'request', return_value=mock_response) as mock_request:
            request = MCPRequest(
                api_name="auth_api",
                method=HTTPMethod.GET,
                path="/protected",
                headers={"Session-Token": "user-session-123"}
            )
            
            await self.router.route_request(request)
            
            # Verify authentication headers were added
            headers = mock_request.call_args[1]['headers']
            assert headers['Authorization'] == 'Bearer secret-token'
            assert headers['Session-Token'] == 'user-session-123'  # Original headers preserved
    
    @pytest.mark.asyncio
    async def test_post_request_with_json_data(self):
        """Test POST request routing with JSON data."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 201
        mock_response.headers = {"Location": "/users/456"}
        mock_response.json.return_value = {"id": 456, "created": True}
        mock_response.content = b'{"id": 456, "created": true}'
        mock_response.text = '{"id": 456, "created": true}'
        
        with patch.object(self.router.http_client, 'request', return_value=mock_response) as mock_request:
            request = MCPRequest(
                api_name="test_api",
                method=HTTPMethod.POST,
                path="/users",
                data={"name": "Jane Doe", "email": "jane@example.com"},
                headers={"User-Agent": "test-agent"}
            )
            
            response = await self.router.route_request(request)
            
            # Verify JSON data was passed
            assert mock_request.call_args[1]['json'] == {"name": "Jane Doe", "email": "jane@example.com"}
            
            # Verify Content-Type header was added
            headers = mock_request.call_args[1]['headers']
            assert headers['Content-Type'] == 'application/json'
            
            # Verify response
            assert response.status_code == 201
            assert response.body["id"] == 456


class TestErrorHandlingAndRetry:
    """Test error handling and retry mechanisms."""
    
    def setup_method(self):
        """Setup router with retry configuration."""
        self.routes = {
            "retry_api": RouteConfig(
                name="Retry API",
                description="API with retry logic",
                base_url="http://retry-service:8080",
                timeout=5,
                retry_policy=RetryPolicy(
                    max_retries=2,
                    backoff_factor=1.5,
                    retry_on=[502, 503, 504, 408, 429]
                )
            )
        }
        self.router = RequestRouter(self.routes)
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Test retry mechanism on server errors."""
        # Mock responses: first two fail with 503, third succeeds
        mock_responses = [
            MagicMock(spec=Response, status_code=503),
            MagicMock(spec=Response, status_code=503),
            MagicMock(spec=Response, status_code=200)
        ]
        
        # Configure the successful response
        mock_responses[2].headers = {"Content-Type": "application/json"}
        mock_responses[2].json.return_value = {"status": "success"}
        mock_responses[2].content = b'{"status": "success"}'
        mock_responses[2].text = '{"status": "success"}'
        
        with patch.object(self.router.http_client, 'request', side_effect=mock_responses):
            with patch('asyncio.sleep') as mock_sleep:  # Mock sleep to speed up test
                request = MCPRequest(
                    api_name="retry_api",
                    method=HTTPMethod.GET,
                    path="/test",
                    trace_id="retry-test-123"
                )
                
                response = await self.router.route_request(request)
                
                # Verify final response is successful
                assert response.status_code == 200
                assert response.body["status"] == "success"
                
                # Verify sleep was called for backoff (2 retries)
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(1.5)  # First backoff
                mock_sleep.assert_any_call(2.25)  # Second backoff (1.5^2)
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion_failure(self):
        """Test behavior when all retry attempts are exhausted."""
        # Mock all responses to fail with 503
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 503
        
        with patch.object(self.router.http_client, 'request', return_value=mock_response):
            with patch('asyncio.sleep'):  # Mock sleep to speed up test
                request = MCPRequest(
                    api_name="retry_api",
                    method=HTTPMethod.GET,
                    path="/test"
                )
                
                # Should return the final failed response (not raise exception)
                response = await self.router.route_request(request)
                assert response.status_code == 503
    
    @pytest.mark.asyncio
    async def test_retry_on_request_error(self):
        """Test retry mechanism on request errors (network issues)."""
        # Mock request errors followed by success
        side_effects = [
            TimeoutException("Request timeout"),
            RequestError("Connection failed"),
            MagicMock(spec=Response, status_code=200)
        ]
        
        # Configure successful response
        side_effects[2].headers = {}
        side_effects[2].json.return_value = {"recovered": True}
        side_effects[2].content = b'{"recovered": true}'
        side_effects[2].text = '{"recovered": true}'
        
        with patch.object(self.router.http_client, 'request', side_effect=side_effects):
            with patch('asyncio.sleep'):  # Mock sleep to speed up test
                request = MCPRequest(
                    api_name="retry_api",
                    method=HTTPMethod.GET,
                    path="/test"
                )
                
                response = await self.router.route_request(request)
                
                # Verify recovery after network errors
                assert response.status_code == 200
                assert response.body["recovered"] is True
    
    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self):
        """Test that client errors (4xx) are not retried."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Not found"}
        mock_response.content = b'{"error": "Not found"}'
        mock_response.text = '{"error": "Not found"}'
        
        with patch.object(self.router.http_client, 'request', return_value=mock_response) as mock_request:
            with patch('asyncio.sleep') as mock_sleep:
                request = MCPRequest(
                    api_name="retry_api",
                    method=HTTPMethod.GET,
                    path="/nonexistent"
                )
                
                response = await self.router.route_request(request)
                
                # Verify no retries occurred
                assert mock_request.call_count == 1
                assert mock_sleep.call_count == 0
                assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_final_request_error_propagation(self):
        """Test that final request errors are properly propagated."""
        # All attempts fail with network error
        with patch.object(self.router.http_client, 'request', side_effect=RequestError("Network unreachable")):
            with patch('asyncio.sleep'):  # Mock sleep to speed up test
                request = MCPRequest(
                    api_name="retry_api",
                    method=HTTPMethod.GET,
                    path="/test"
                )
                
                with pytest.raises(Exception) as exc_info:
                    await self.router.route_request(request)
                
                assert "Request failed" in str(exc_info.value)


class TestTraceIDPropagation:
    """Test trace ID propagation functionality."""
    
    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)
    
    @patch('src.gateway.router')
    def test_trace_id_generation_when_missing(self, mock_router):
        """Test that trace ID is generated when not provided."""
        # Mock router to avoid initialization issues
        mock_router.route_request = AsyncMock(return_value=MCPResponse(
            status_code=200,
            headers={},
            body={"test": "response"},
            execution_time=0.1,
            trace_id="generated-trace-id"
        ))
        
        request_data = {
            "api_name": "test_api",
            "method": "GET",
            "path": "/test"
            # No trace_id provided
        }
        
        response = self.client.post("/mcp/request", json=request_data)
        
        # Verify trace ID was added to response headers
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Trace-ID"] != ""
    
    @patch('src.gateway.router')
    def test_trace_id_preservation_when_provided(self, mock_router):
        """Test that provided trace ID is preserved."""
        test_trace_id = "custom-trace-12345"
        
        # Mock router to return response with same trace ID
        mock_router.route_request = AsyncMock(return_value=MCPResponse(
            status_code=200,
            headers={},
            body={"test": "response"},
            execution_time=0.1,
            trace_id=test_trace_id
        ))
        
        request_data = {
            "api_name": "test_api",
            "method": "GET",
            "path": "/test",
            "trace_id": test_trace_id
        }
        
        response = self.client.post("/mcp/request", json=request_data)
        
        # Verify the same trace ID is returned
        assert response.headers["X-Trace-ID"] == test_trace_id
    
    @patch('src.gateway.router')
    def test_trace_id_in_error_responses(self, mock_router):
        """Test that trace ID is included in error responses."""
        test_trace_id = "error-trace-789"
        
        # Mock router to raise an exception
        mock_router.route_request = AsyncMock(side_effect=Exception("Test error"))
        
        request_data = {
            "api_name": "test_api",
            "method": "GET",
            "path": "/test",
            "trace_id": test_trace_id
        }
        
        response = self.client.post("/mcp/request", json=request_data)
        
        # Verify trace ID is in error response
        assert response.status_code == 500
        assert response.headers["X-Trace-ID"] == test_trace_id
        
        response_data = response.json()
        assert response_data["trace_id"] == test_trace_id


class TestHealthCheckAndRoutes:
    """Test health check and route listing functionality."""
    
    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)
    
    @patch('src.gateway.router')
    def test_health_check_when_router_initialized(self, mock_router):
        """Test health check when router is properly initialized."""
        # Mock router with health check results
        mock_router.routes = {"test_api": MagicMock(), "auth_api": MagicMock()}
        mock_router.health_check = AsyncMock(return_value=True)
        
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "routes" in data
        assert "timestamp" in data
    
    def test_health_check_when_router_not_initialized(self):
        """Test health check when router is not initialized."""
        with patch('src.gateway.router', None):
            response = self.client.get("/health")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["reason"] == "Gateway not initialized"
    
    @patch('src.gateway.router')
    def test_routes_listing(self, mock_router):
        """Test route listing endpoint."""
        # Mock router with route configurations
        mock_route_config = MagicMock()
        mock_route_config.name = "Test API"
        mock_route_config.description = "Test service"
        mock_route_config.base_url = "http://test-service:8080"
        mock_route_config.timeout = 30
        mock_route_config.health_check = None
        
        mock_router.routes = {"test_api": mock_route_config}
        
        response = self.client.get("/routes")
        
        assert response.status_code == 200
        data = response.json()
        assert "routes" in data
        assert "test_api" in data["routes"]
        
        route_info = data["routes"]["test_api"]
        assert route_info["name"] == "Test API"
        assert route_info["description"] == "Test service"
        assert route_info["base_url"] == "http://test-service:8080"
        assert route_info["timeout"] == 30
        assert route_info["health_check_enabled"] is False


class TestMetricsIntegration:
    """Test metrics collection integration."""
    
    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)
    
    def test_metrics_endpoint_availability(self):
        """Test that metrics endpoint is available."""
        response = self.client.get("/metrics")
        
        # Should return Prometheus metrics format
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
    
    @patch('src.gateway.router')
    @patch('src.metrics.track_request_metrics')
    def test_metrics_tracking_on_request(self, mock_track_metrics, mock_router):
        """Test that metrics are tracked for MCP requests."""
        # Mock successful response
        mock_router.route_request = AsyncMock(return_value=MCPResponse(
            status_code=200,
            headers={},
            body={"success": True},
            execution_time=0.5,
            trace_id="metrics-test-123"
        ))
        
        request_data = {
            "api_name": "test_api",
            "method": "POST",
            "path": "/test"
        }
        
        response = self.client.post("/mcp/request", json=request_data)
        
        assert response.status_code == 200
        
        # Verify metrics tracking was called
        mock_track_metrics.assert_called_once_with("test_api", "POST")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])