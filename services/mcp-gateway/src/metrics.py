"""
Prometheus metrics collection for MCP Gateway.
Implements Requirements 4.4, 6.2 for performance monitoring.
"""

import time
from contextlib import contextmanager
from typing import Dict, Optional

from prometheus_client import Counter, Histogram, Gauge, Info
from .models import MetricsConfig


# Prometheus metrics
request_count = Counter(
    'mcp_gateway_requests_total',
    'Total number of MCP requests processed',
    ['api_name', 'method', 'status_code']
)

request_duration = Histogram(
    'mcp_gateway_request_duration_seconds',
    'Request duration in seconds',
    ['api_name', 'method'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

active_requests = Gauge(
    'mcp_gateway_active_requests',
    'Number of active requests being processed',
    ['api_name']
)

route_health = Gauge(
    'mcp_gateway_route_health',
    'Health status of configured routes (1=healthy, 0=unhealthy)',
    ['api_name', 'route_name']
)

gateway_info = Info(
    'mcp_gateway_info',
    'Information about the MCP Gateway instance'
)

error_count = Counter(
    'mcp_gateway_errors_total',
    'Total number of errors by type',
    ['error_type', 'api_name']
)

retry_count = Counter(
    'mcp_gateway_retries_total',
    'Total number of request retries',
    ['api_name', 'attempt']
)


def setup_metrics(config: MetricsConfig):
    """
    Initialize metrics collection.
    
    Requirement 4.4: Custom metrics endpoints for MCP Gateway performance.
    """
    if not config.enabled:
        return
    
    # Set gateway information
    gateway_info.info({
        'version': '1.0.0',
        'metrics_endpoint': config.endpoint
    })


@contextmanager
def track_request_metrics(api_name: str, method: str):
    """
    Context manager to track request metrics.
    
    Args:
        api_name: Name of the target API
        method: HTTP method
        
    Yields:
        None
        
    Usage:
        with track_request_metrics('sut_api', 'POST'):
            # Process request
            pass
    """
    start_time = time.time()
    active_requests.labels(api_name=api_name).inc()
    
    try:
        yield
        # Success - will be recorded in finally block
        status_code = "2xx"  # Default to success
    except Exception as e:
        # Error occurred
        status_code = "5xx"  # Default to server error
        error_count.labels(
            error_type=type(e).__name__,
            api_name=api_name
        ).inc()
        raise
    finally:
        # Record metrics
        duration = time.time() - start_time
        
        request_count.labels(
            api_name=api_name,
            method=method,
            status_code=status_code
        ).inc()
        
        request_duration.labels(
            api_name=api_name,
            method=method
        ).observe(duration)
        
        active_requests.labels(api_name=api_name).dec()


def record_retry_attempt(api_name: str, attempt: int):
    """
    Record a retry attempt.
    
    Args:
        api_name: Name of the target API
        attempt: Retry attempt number (1-based)
    """
    retry_count.labels(
        api_name=api_name,
        attempt=str(attempt)
    ).inc()


def update_route_health(api_name: str, route_name: str, is_healthy: bool):
    """
    Update route health status.
    
    Args:
        api_name: API identifier
        route_name: Human-readable route name
        is_healthy: Whether the route is healthy
    """
    route_health.labels(
        api_name=api_name,
        route_name=route_name
    ).set(1 if is_healthy else 0)


def record_error(error_type: str, api_name: str):
    """
    Record an error occurrence.
    
    Args:
        error_type: Type/class of the error
        api_name: API where the error occurred
    """
    error_count.labels(
        error_type=error_type,
        api_name=api_name
    ).inc()