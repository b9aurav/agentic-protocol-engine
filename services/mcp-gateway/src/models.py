"""
Pydantic models for MCP Gateway request/response validation.
Implements Requirements 3.1, 3.2, 3.3 for standardized protocol mediation.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class HTTPMethod(str, Enum):
    """Supported HTTP methods for MCP requests."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class MCPRequest(BaseModel):
    """
    MCP-compliant request schema for agent tool calls.
    Requirement 3.3: Enforce Pydantic schema validation for MCP-compliant JSON output.
    """
    api_name: str = Field(..., description="Target API identifier for routing")
    method: HTTPMethod = Field(..., description="HTTP method for the request")
    path: str = Field(..., description="API endpoint path")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Request headers")
    data: Optional[Dict[str, Any]] = Field(None, description="Request body data")
    trace_id: Optional[str] = Field(None, description="Trace ID for request correlation")
    
    @validator('path')
    def validate_path(cls, v):
        """Ensure path starts with forward slash."""
        if not v.startswith('/'):
            v = '/' + v
        return v
    
    @validator('api_name')
    def validate_api_name(cls, v):
        """Ensure api_name is not empty and contains valid characters."""
        if not v or not v.strip():
            raise ValueError("api_name cannot be empty")
        return v.strip()


class MCPResponse(BaseModel):
    """
    Standardized response schema for MCP Gateway responses.
    Requirement 3.2: Standard HTTP/JSON format responses.
    """
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: Optional[Dict[str, Any]] = Field(None, description="Response body")
    execution_time: float = Field(..., description="Request execution time in seconds")
    trace_id: str = Field(..., description="Trace ID for request correlation")
    error_message: Optional[str] = Field(None, description="Error message if request failed")


class RouteConfig(BaseModel):
    """Configuration for a target service route."""
    name: str = Field(..., description="Human-readable route name")
    description: str = Field(..., description="Route description")
    base_url: str = Field(..., description="Base URL for the target service")
    timeout: int = Field(30, description="Request timeout in seconds")
    retry_policy: 'RetryPolicy' = Field(default_factory=lambda: RetryPolicy())
    auth: Optional['AuthConfig'] = Field(None, description="Authentication configuration")
    health_check: Optional['HealthCheckConfig'] = Field(None, description="Health check configuration")


class RetryPolicy(BaseModel):
    """Retry policy configuration for failed requests."""
    max_retries: int = Field(3, description="Maximum number of retry attempts")
    backoff_factor: float = Field(1.5, description="Exponential backoff factor")
    retry_on: List[int] = Field(
        default_factory=lambda: [502, 503, 504, 408, 429],
        description="HTTP status codes to retry on"
    )


class AuthConfig(BaseModel):
    """Authentication configuration for target services."""
    type: str = Field(..., description="Authentication type (bearer, basic, session)")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Auth headers")
    credentials: Optional[Dict[str, str]] = Field(None, description="Auth credentials")


class HealthCheckConfig(BaseModel):
    """Health check configuration for target services."""
    enabled: bool = Field(True, description="Enable health checks")
    path: str = Field("/health", description="Health check endpoint path")
    interval: int = Field(30, description="Health check interval in seconds")


class GatewayConfig(BaseModel):
    """Complete MCP Gateway configuration."""
    gateway: 'GatewaySettings' = Field(default_factory=lambda: GatewaySettings())
    routes: Dict[str, RouteConfig] = Field(..., description="Route configurations")
    logging: 'LoggingConfig' = Field(default_factory=lambda: LoggingConfig())
    metrics: 'MetricsConfig' = Field(default_factory=lambda: MetricsConfig())


class GatewaySettings(BaseModel):
    """Gateway server settings."""
    name: str = Field("mcp-gateway", description="Gateway service name")
    version: str = Field("1.0.0", description="Gateway version")
    port: int = Field(3000, description="Server port")
    host: str = Field("0.0.0.0", description="Server host")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field("INFO", description="Log level")
    format: str = Field("json", description="Log format")
    tracing: 'TracingConfig' = Field(default_factory=lambda: TracingConfig())


class TracingConfig(BaseModel):
    """Tracing configuration."""
    enabled: bool = Field(True, description="Enable request tracing")
    header_name: str = Field("X-Trace-ID", description="Trace ID header name")


class MetricsConfig(BaseModel):
    """Metrics configuration."""
    enabled: bool = Field(True, description="Enable metrics collection")
    endpoint: str = Field("/metrics", description="Metrics endpoint path")


# Update forward references
RouteConfig.model_rebuild()
GatewayConfig.model_rebuild()