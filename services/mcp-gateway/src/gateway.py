"""
FastAPI-based MCP Gateway HTTP server.
Implements Requirements 3.1, 3.2, 3.3 for standardized protocol mediation.
"""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .models import MCPRequest, MCPResponse, GatewayConfig
from .router import RequestRouter
from .logging_config import setup_logging
from .metrics import setup_metrics, track_request_metrics


# Global router instance
router: RequestRouter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global router
    
    # Load configuration
    config = load_gateway_config()
    
    # Setup logging
    setup_logging(config.logging)
    
    # Setup metrics
    setup_metrics(config.metrics)
    
    # Initialize router
    router = RequestRouter(config.routes)
    
    logger = logging.getLogger(__name__)
    logger.info(f"MCP Gateway started with {len(config.routes)} routes")
    
    yield
    
    # Cleanup
    if router:
        await router.close()
    logger.info("MCP Gateway shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="MCP Gateway",
    description="Model Context Protocol Gateway for Agentic Protocol Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_gateway_config() -> GatewayConfig:
    """
    Load gateway configuration from file or environment.
    Requirement 3.1: Basic routing logic based on configuration file.
    """
    config_path = os.getenv("MCP_GATEWAY_CONFIG", "/app/config/mcp-gateway.json")
    
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return GatewayConfig(**config_data)
    except FileNotFoundError:
        # Return default configuration if file not found
        logging.warning(f"Configuration file not found at {config_path}, using defaults")
        return GatewayConfig(routes={})
    except Exception as e:
        logging.error(f"Failed to load configuration: {str(e)}")
        raise


@app.middleware("http")
async def add_trace_id_middleware(request: Request, call_next):
    """
    Middleware to add trace ID to all requests and provide comprehensive logging.
    Requirement 4.2: Trace ID injection and propagation.
    Requirement 8.2: Structured logging for all requests and responses.
    """
    # Get or generate trace ID
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    
    # Add trace ID to request state
    request.state.trace_id = trace_id
    
    # Log incoming request
    logger = logging.getLogger(__name__)
    
    # Read request body for logging (if present and reasonable size)
    request_body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if len(body) < 10000:  # Only log bodies smaller than 10KB
                request_body = body.decode('utf-8') if body else None
        except Exception:
            request_body = "<unable to read body>"
    
    logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params) if request.query_params else None,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("User-Agent"),
            "request_headers": dict(request.headers),
            "request_body": request_body,
            "event_type": "request_start"
        }
    )
    
    # Process request
    start_time = time.time()
    response = await call_next(request)
    execution_time = time.time() - start_time
    
    # Add trace ID and other headers to response
    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-Execution-Time"] = str(execution_time)
    response.headers["X-Gateway-Version"] = "1.0.0"
    
    # Log response
    logger.info(
        f"Response sent: {request.method} {request.url.path}",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "execution_time": execution_time,
            "response_headers": dict(response.headers),
            "client_ip": request.client.host if request.client else None,
            "event_type": "request_complete"
        }
    )
    
    return response


@app.post("/mcp/request", response_model=MCPResponse)
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """
    Handle MCP-compliant requests from agents.
    
    Requirement 3.1: FastAPI-based HTTP server for request routing.
    Requirement 3.2: Request validation using Pydantic schemas.
    Requirement 3.3: Enforce MCP-compliant JSON output.
    """
    if not router:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    
    try:
        # Track metrics
        with track_request_metrics(request.api_name, request.method.value):
            response = await router.route_request(request)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error handling MCP request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns the health status of the gateway and its routes.
    """
    if not router:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "Gateway not initialized"}
        )
    
    # Check health of all routes
    route_health = {}
    for api_name in router.routes.keys():
        route_health[api_name] = await router.health_check(api_name)
    
    overall_healthy = all(route_health.values()) if route_health else True
    
    return JSONResponse(
        status_code=200 if overall_healthy else 503,
        content={
            "status": "healthy" if overall_healthy else "degraded",
            "routes": route_health,
            "timestamp": time.time()
        }
    )


@app.get("/routes")
async def list_routes():
    """
    List all configured routes.
    Useful for debugging and service discovery.
    """
    if not router:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    
    routes_info = {}
    for api_name, route_config in router.routes.items():
        routes_info[api_name] = {
            "name": route_config.name,
            "description": route_config.description,
            "base_url": route_config.base_url,
            "timeout": route_config.timeout,
            "health_check_enabled": route_config.health_check.enabled if route_config.health_check else False
        }
    
    return {"routes": routes_info}


@app.get("/metrics")
async def get_metrics():
    """
    Prometheus metrics endpoint.
    Requirement 4.4: Custom metrics endpoints for MCP Gateway performance.
    """
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    
    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with trace ID."""
    trace_id = getattr(request.state, 'trace_id', str(uuid.uuid4()))
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "trace_id": trace_id,
            "timestamp": time.time()
        },
        headers={"X-Trace-ID": trace_id}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unexpected errors."""
    trace_id = getattr(request.state, 'trace_id', str(uuid.uuid4()))
    
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {str(exc)}", extra={"trace_id": trace_id})
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "trace_id": trace_id,
            "timestamp": time.time()
        },
        headers={"X-Trace-ID": trace_id}
    )


def main():
    """Main entry point for the MCP Gateway server."""
    config = load_gateway_config()
    
    uvicorn.run(
        "gateway:app",
        host=config.gateway.host,
        port=config.gateway.port,
        log_level=config.logging.level.lower(),
        reload=False
    )


if __name__ == "__main__":
    main()