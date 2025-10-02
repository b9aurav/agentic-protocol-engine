"""
Structured logging configuration for Cerebras Proxy
"""

import os
import sys
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory


def setup_logging() -> structlog.BoundLogger:
    """
    Setup structured logging with JSON output for containerized environments
    
    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            # Add trace context
            structlog.contextvars.merge_contextvars,
            # JSON formatting for structured logs
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Get logger
    logger = structlog.get_logger("cerebras-proxy")
    
    # Log startup information
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.info(
        "Logging configured",
        service="cerebras-proxy",
        log_level=log_level,
        python_version=sys.version.split()[0]
    )
    
    return logger


def log_request_response(
    logger: structlog.BoundLogger,
    method: str,
    url: str,
    status_code: int,
    duration: float,
    request_size: int = 0,
    response_size: int = 0,
    **kwargs: Any
) -> None:
    """
    Log HTTP request/response with structured data
    
    Args:
        logger: Structured logger instance
        method: HTTP method
        url: Request URL
        status_code: HTTP status code
        duration: Request duration in seconds
        request_size: Request body size in bytes
        response_size: Response body size in bytes
        **kwargs: Additional fields to log
    """
    logger.info(
        "HTTP request completed",
        http_method=method,
        http_url=url,
        http_status_code=status_code,
        duration_seconds=duration,
        request_size_bytes=request_size,
        response_size_bytes=response_size,
        **kwargs
    )


def log_inference_metrics(
    logger: structlog.BoundLogger,
    model: str,
    ttft: float,
    total_time: float,
    total_tokens: int,
    prompt_tokens: int,
    completion_tokens: int,
    **kwargs: Any
) -> None:
    """
    Log inference performance metrics
    
    Args:
        logger: Structured logger instance
        model: Model name used
        ttft: Time to First Token in seconds
        total_time: Total request time in seconds
        total_tokens: Total tokens processed
        prompt_tokens: Input tokens
        completion_tokens: Output tokens
        **kwargs: Additional fields to log
    """
    logger.info(
        "Inference metrics",
        model=model,
        ttft_seconds=ttft,
        total_time_seconds=total_time,
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tokens_per_second=total_tokens / total_time if total_time > 0 else 0,
        **kwargs
    )