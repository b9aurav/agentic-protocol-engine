"""
MCP Gateway routing logic for request forwarding to target services.
Implements Requirements 3.1, 3.2, 3.3 for standardized protocol mediation.
"""

import asyncio
import time
import uuid
from typing import Dict, Optional
import httpx
from fastapi import HTTPException
import logging

from .models import MCPRequest, MCPResponse, RouteConfig, RetryPolicy


logger = logging.getLogger(__name__)


class RequestRouter:
    """
    Handles routing of MCP requests to target services.
    Requirement 3.1: Central routing and protocol translation service.
    """
    
    def __init__(self, routes: Dict[str, RouteConfig]):
        """Initialize router with route configurations."""
        self.routes = routes
        self.http_client = httpx.AsyncClient()
        
    async def route_request(self, request: MCPRequest) -> MCPResponse:
        """
        Route an MCP request to the appropriate target service.
        
        Args:
            request: MCP-compliant request object
            
        Returns:
            MCPResponse: Standardized response object
            
        Raises:
            HTTPException: If routing fails or target service is unavailable
        """
        start_time = time.time()
        trace_id = request.trace_id or str(uuid.uuid4())
        
        # Validate route exists
        if request.api_name not in self.routes:
            execution_time = time.time() - start_time
            logger.error(f"Route not found: {request.api_name}", extra={"trace_id": trace_id})
            raise HTTPException(
                status_code=404,
                detail=f"Route '{request.api_name}' not found"
            )
        
        route_config = self.routes[request.api_name]
        
        # Build target URL
        target_url = f"{route_config.base_url.rstrip('/')}{request.path}"
        
        # Prepare headers
        headers = self._prepare_headers(request, route_config, trace_id)
        
        # Execute request with retry logic
        try:
            response = await self._execute_with_retry(
                method=request.method.value,
                url=target_url,
                headers=headers,
                json=request.data,
                route_config=route_config,
                trace_id=trace_id
            )
            
            execution_time = time.time() - start_time
            
            # Parse response body
            try:
                response_body = response.json() if response.content else None
            except Exception:
                response_body = {"raw_content": response.text} if response.text else None
            
            logger.info(
                f"Request routed successfully: {request.method} {target_url}",
                extra={
                    "trace_id": trace_id,
                    "status_code": response.status_code,
                    "execution_time": execution_time,
                    "api_name": request.api_name,
                    "method": request.method.value,
                    "path": request.path,
                    "target_url": target_url,
                    "response_size": len(response.content) if response.content else 0,
                    "request_headers": dict(headers),
                    "response_headers": dict(response.headers)
                }
            )
            
            return MCPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                execution_time=execution_time,
                trace_id=trace_id
            )
            
        except httpx.RequestError as e:
            execution_time = time.time() - start_time
            error_msg = f"Request failed: {str(e)}"
            
            logger.error(
                error_msg,
                extra={
                    "trace_id": trace_id,
                    "api_name": request.api_name,
                    "method": request.method.value,
                    "path": request.path,
                    "target_url": target_url,
                    "execution_time": execution_time,
                    "error_type": type(e).__name__,
                    "request_headers": dict(headers)
                }
            )
            
            raise HTTPException(
                status_code=502,
                detail=error_msg
            )
    
    def _prepare_headers(
        self, 
        request: MCPRequest, 
        route_config: RouteConfig, 
        trace_id: str
    ) -> Dict[str, str]:
        """
        Prepare headers for the target request.
        Requirement 3.5: Pass session headers through the MCP Gateway.
        Requirement 4.2: Trace ID injection and propagation.
        """
        headers = {}
        
        # Add request headers
        if request.headers:
            headers.update(request.headers)
        
        # Add authentication headers from route config
        if route_config.auth and route_config.auth.headers:
            headers.update(route_config.auth.headers)
        
        # Add trace ID header for correlation
        headers["X-Trace-ID"] = trace_id
        
        # Add API name for metrics tracking
        headers["X-API-Name"] = request.api_name
        
        # Add gateway identification
        headers["X-MCP-Gateway"] = "1.0.0"
        
        # Ensure content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"] and request.data:
            headers.setdefault("Content-Type", "application/json")
        
        # Add request timestamp for latency tracking
        headers["X-Request-Timestamp"] = str(time.time())
        
        return headers
    
    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json: Optional[Dict],
        route_config: RouteConfig,
        trace_id: str
    ) -> httpx.Response:
        """
        Execute HTTP request with retry logic.
        Requirement 3.2: Error handling and retry logic for target services.
        Requirement 4.2: Trace ID propagation and structured logging.
        """
        from .metrics import record_retry_attempt, record_error
        
        retry_policy = route_config.retry_policy
        last_exception = None
        
        for attempt in range(retry_policy.max_retries + 1):
            try:
                # Log request attempt
                logger.info(
                    f"Executing request attempt {attempt + 1}",
                    extra={
                        "trace_id": trace_id,
                        "method": method,
                        "url": url,
                        "attempt": attempt + 1,
                        "max_retries": retry_policy.max_retries + 1
                    }
                )
                
                response = await self.http_client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    timeout=route_config.timeout
                )
                
                # Log response details
                logger.info(
                    f"Received response: {response.status_code}",
                    extra={
                        "trace_id": trace_id,
                        "status_code": response.status_code,
                        "response_headers": dict(response.headers),
                        "attempt": attempt + 1
                    }
                )
                
                # Check if we should retry based on status code
                if attempt < retry_policy.max_retries and response.status_code in retry_policy.retry_on:
                    wait_time = retry_policy.backoff_factor ** attempt
                    
                    # Record retry attempt in metrics
                    record_retry_attempt(headers.get("X-API-Name", "unknown"), attempt + 1)
                    
                    logger.warning(
                        f"Request failed with status {response.status_code}, retrying in {wait_time}s",
                        extra={
                            "trace_id": trace_id,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "max_retries": retry_policy.max_retries,
                            "wait_time": wait_time,
                            "retry_reason": "status_code_retry"
                        }
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                return response
                
            except httpx.RequestError as e:
                last_exception = e
                
                # Record error in metrics
                record_error(type(e).__name__, headers.get("X-API-Name", "unknown"))
                
                if attempt < retry_policy.max_retries:
                    wait_time = retry_policy.backoff_factor ** attempt
                    
                    # Record retry attempt in metrics
                    record_retry_attempt(headers.get("X-API-Name", "unknown"), attempt + 1)
                    
                    logger.warning(
                        f"Request failed with error: {str(e)}, retrying in {wait_time}s",
                        extra={
                            "trace_id": trace_id,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "attempt": attempt + 1,
                            "max_retries": retry_policy.max_retries,
                            "wait_time": wait_time,
                            "retry_reason": "request_error"
                        }
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                # Final attempt failed, log and raise
                logger.error(
                    f"All retry attempts failed: {str(e)}",
                    extra={
                        "trace_id": trace_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "total_attempts": attempt + 1
                    }
                )
                raise e
        
        # If we get here, all retries failed due to status codes
        if last_exception:
            raise last_exception
        else:
            error_msg = f"All {retry_policy.max_retries} retry attempts failed"
            logger.error(error_msg, extra={"trace_id": trace_id})
            raise httpx.RequestError(error_msg)
    
    async def health_check(self, api_name: str) -> bool:
        """
        Perform health check for a specific route.
        
        Args:
            api_name: Name of the API route to check
            
        Returns:
            bool: True if service is healthy, False otherwise
        """
        if api_name not in self.routes:
            return False
        
        route_config = self.routes[api_name]
        
        if not route_config.health_check or not route_config.health_check.enabled:
            return True  # Assume healthy if health check is disabled
        
        health_url = f"{route_config.base_url.rstrip('/')}{route_config.health_check.path}"
        
        try:
            response = await self.http_client.get(
                health_url,
                timeout=5.0  # Short timeout for health checks
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for {api_name}: {str(e)}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()