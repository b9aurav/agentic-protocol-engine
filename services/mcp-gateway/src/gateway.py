"""
FastAPI-based MCP Gateway HTTP server.
Implements Requirements 3.1, 3.2, 3.3 for standardized protocol mediation.
"""

import json
import asyncio
from fastapi.responses import JSONResponse
from .models import MCPRequest
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

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
    logger.info(f"MCP Gateway started with {len(config.routes)} routes.")
    
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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger = logging.getLogger(__name__)
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
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


# Manually import necessary components for the middleware workaround
from fastapi.responses import JSONResponse
from .models import MCPRequest

@app.middleware("http")
async def add_trace_id_middleware(request: Request, call_next):
    """
    Middleware to add trace ID, provide comprehensive logging, and apply a
    workaround for a suspected bug in FastAPI's internal processing for /mcp/request.
    """
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    logger = logging.getLogger(__name__)
    start_time = time.time()

    # Log initial incoming request details
    log_extra = {
        "request_trace_id": trace_id,
        "http_method": request.method,
        "request_path": request.url.path,
        "remote_addr": request.client.host if request.client else None,
    }
    logger.info(f"Incoming request: {request.method} {request.url.path}", extra=log_extra)

    # WORKAROUND: For /mcp/request, bypass call_next and call the handler directly
    # This avoids a suspected silent hang in FastAPI's internal request processing.
    if request.method == "POST" and request.url.path == "/mcp/request":
        response = None
        try:
            json_body = await request.json()
            mcp_request = MCPRequest.model_validate(json_body)
            
            # Directly call the endpoint logic
            mcp_response = await handle_mcp_request(mcp_request)
            
            # Manually construct the JSONResponse that FastAPI would have made
            response = JSONResponse(
                content=mcp_response.model_dump(),
                status_code=mcp_response.status_code
            )

        except Exception as e:
            logger.error(f"Error in middleware workaround for /mcp/request: {str(e)}", extra=log_extra, exc_info=True)
            response = JSONResponse(
                status_code=500,
                content={"error": "Internal server error during middleware workaround", "trace_id": trace_id}
            )
        
        # Apply standard headers and logging to the manually created response
        execution_time = time.time() - start_time
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Execution-Time"] = str(execution_time)
        response.headers["X-Gateway-Version"] = "1.0.0"

        log_extra["response_status"] = response.status_code
        log_extra["response_time"] = execution_time
        logger.info(f"Response sent (via workaround): {request.method} {request.url.path}", extra=log_extra)
        return response

    # Original flow for all other endpoints
    response = await call_next(request)
    execution_time = time.time() - start_time

    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-Execution-Time"] = str(execution_time)
    response.headers["X-Gateway-Version"] = "1.0.0"

    log_extra["response_status"] = response.status_code
    log_extra["response_time"] = execution_time
    logger.info(f"Response sent: {request.method} {request.url.path}", extra=log_extra)

    return response


@app.post("/mcp/request", response_model=MCPResponse)
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """
    Handle MCP-compliant requests from agents.
    
    Requirement 3.1: FastAPI-based HTTP server for request routing.
    Requirement 3.2: Request validation using Pydantic schemas.
    Requirement 3.3: Enforce MCP-compliant JSON output.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"TRACE: handle_mcp_request called for {request.api_name} {request.method.value} {request.path}")    
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
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns the health status of the gateway itself (not dependent routes).
    """
    if not router:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "Gateway not initialized"}
        )
    
    # Simple health check - just verify gateway is running
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "gateway": "running",
            "timestamp": time.time()
        }
    )

@app.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check endpoint that includes route health.
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
    logger.error(f"Unhandled exception: {str(exc)}", extra={"request_trace_id": trace_id})
    
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