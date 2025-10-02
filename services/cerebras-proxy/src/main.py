"""
Cerebras Proxy Service - OpenAI-compatible API proxy for Cerebras Llama 4 Scout
"""

import os
import time
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import structlog
from dotenv import load_dotenv

from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    Usage,
    ErrorResponse
)
from .auth import verify_api_key
from .logging_config import setup_logging
from .metrics import MetricsCollector

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logging()

# Initialize metrics collector
metrics = MetricsCollector()

# HTTP client for Cerebras API
cerebras_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global cerebras_client
    
    # Startup
    logger.info("Starting Cerebras Proxy service")
    
    # Initialize HTTP client for Cerebras API
    cerebras_client = httpx.AsyncClient(
        base_url=os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai"),
        timeout=httpx.Timeout(30.0),
        headers={
            "Authorization": f"Bearer {os.getenv('CEREBRAS_API_KEY')}",
            "Content-Type": "application/json"
        }
    )
    
    logger.info("Cerebras Proxy service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Cerebras Proxy service")
    if cerebras_client:
        await cerebras_client.aclose()
    logger.info("Cerebras Proxy service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Cerebras Proxy",
    description="OpenAI-compatible API proxy for Cerebras Llama 4 Scout",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_trace_id_middleware(request: Request, call_next):
    """Add trace ID to all requests for observability"""
    trace_id = request.headers.get("X-Trace-ID", f"trace-{int(time.time() * 1000)}")
    
    # Add trace ID to structlog context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "cerebras-proxy"}


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible endpoint)"""
    return {
        "object": "list",
        "data": [
            {
                "id": "llama3.1-8b",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "cerebras"
            }
        ]
    }


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    OpenAI-compatible chat completions endpoint
    Forwards requests to Cerebras Llama 4 Scout API with performance tracking
    """
    request_start_time = time.time()
    
    logger.info(
        "Received chat completion request",
        model=request.model,
        messages_count=len(request.messages),
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )
    
    try:
        # Prepare request for Cerebras API
        cerebras_request = {
            "model": request.model or "llama3.1-8b",
            "messages": [msg.dict() for msg in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream or False
        }
        
        # Remove None values
        cerebras_request = {k: v for k, v in cerebras_request.items() if v is not None}
        
        # Make request to Cerebras API
        ttft_start = time.time()
        
        response = await cerebras_client.post(
            "/v1/chat/completions",
            json=cerebras_request
        )
        
        # Calculate Time-to-First-Token (TTFT)
        ttft = time.time() - ttft_start
        
        if response.status_code != 200:
            logger.error(
                "Cerebras API error",
                status_code=response.status_code,
                response_text=response.text
            )
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Cerebras API error: {response.text}"
            )
        
        cerebras_response = response.json()
        
        # Extract usage information
        usage_data = cerebras_response.get("usage", {})
        total_tokens = usage_data.get("total_tokens", 0)
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        
        # Calculate total request time
        total_time = time.time() - request_start_time
        
        # Log performance metrics
        logger.info(
            "Chat completion successful",
            ttft_seconds=ttft,
            total_time_seconds=total_time,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=request.model
        )
        
        # Record metrics
        metrics.record_inference_request(
            ttft=ttft,
            total_time=total_time,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=request.model or "llama3.1-8b"
        )
        
        # Convert Cerebras response to OpenAI format
        choices = []
        for choice in cerebras_response.get("choices", []):
            choices.append(ChatCompletionChoice(
                index=choice.get("index", 0),
                message=ChatMessage(
                    role=choice.get("message", {}).get("role", "assistant"),
                    content=choice.get("message", {}).get("content", "")
                ),
                finish_reason=choice.get("finish_reason", "stop")
            ))
        
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
        
        return ChatCompletionResponse(
            id=cerebras_response.get("id", f"chatcmpl-{int(time.time())}"),
            object="chat.completion",
            created=int(time.time()),
            model=request.model or "llama3.1-8b",
            choices=choices,
            usage=usage
        )
        
    except httpx.RequestError as e:
        logger.error("Network error calling Cerebras API", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        )
    except Exception as e:
        logger.error("Unexpected error in chat completion", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.get("/metrics")
async def get_metrics():
    """Prometheus-compatible metrics endpoint"""
    return metrics.get_prometheus_metrics()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)