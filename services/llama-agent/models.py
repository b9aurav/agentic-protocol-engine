"""
Pydantic models for MCP tool calls and agent session management.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class HTTPMethod(str, Enum):
    """Supported HTTP methods for MCP tool calls."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class MCPToolCall(BaseModel):
    """
    Pydantic model for MCP-compliant tool calls.
    Enforces schema validation for agent-to-MCP Gateway communication.
    """
    target_api_name: str = Field(..., description="Routing identifier for MCP Gateway")
    http_method: HTTPMethod = Field(..., description="HTTP method for the request")
    endpoint_path: str = Field(..., description="API endpoint path")
    request_payload: Optional[Dict[str, Any]] = Field(None, description="Request body data")
    session_headers: Optional[Dict[str, str]] = Field(None, description="Authentication/session headers")
    
    class Config:
        use_enum_values = True


class ToolExecution(BaseModel):
    """Record of a single tool execution for session history."""
    tool_name: str
    parameters: Dict[str, Any]
    response: Dict[str, Any]
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentSessionContext(BaseModel):
    """
    Session context management for stateful agent behavior.
    Maintains state across multi-step transactions.
    """
    session_id: str = Field(..., description="Unique session identifier")
    trace_id: str = Field(..., description="Trace ID for request correlation")
    goal: str = Field(..., description="User journey goal for this session")
    current_step: int = Field(default=0, description="Current step in the journey")
    session_data: Dict[str, Any] = Field(default_factory=dict, description="Cookies, tokens, transaction IDs")
    execution_history: List[ToolExecution] = Field(default_factory=list, description="History of tool executions")
    start_time: datetime = Field(default_factory=datetime.utcnow)
    last_action_time: datetime = Field(default_factory=datetime.utcnow)
    max_steps: int = Field(default=50, description="Maximum steps before termination")
    failure_indicators: List[str] = Field(default_factory=list, description="Indicators of task failure")
    action_timestamps: List[datetime] = Field(default_factory=list, description="Timestamps of each action")
    
    # Additional fields used by session tracker
    success_indicators: List[str] = Field(default_factory=list, description="Success indicators found during execution")
    current_mtba: float = Field(default=0.0, description="Current mean time between actions")
    cognitive_violations: int = Field(default=0, description="Count of cognitive latency violations")
    
    class Config:
        arbitrary_types_allowed = True
    
    def update_last_action(self):
        """Update the last action timestamp."""
        self.last_action_time = datetime.utcnow()
    
    def add_execution(self, execution: ToolExecution):
        """Add a tool execution to the history."""
        self.execution_history.append(execution)
        self.current_step += 1
        self.update_last_action()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired based on last action time."""
        time_diff = datetime.utcnow() - self.last_action_time
        return time_diff.total_seconds() > (timeout_minutes * 60)
    
    def has_reached_max_steps(self) -> bool:
        """Check if session has reached maximum steps."""
        return self.current_step >= self.max_steps


class AgentConfig(BaseModel):
    """Configuration for the Llama Agent."""
    agent_id: str
    mcp_gateway_url: str = "http://mcp_gateway:3000"
    cerebras_proxy_url: str = "http://cerebras_proxy:8000"
    session_timeout_minutes: int = 30
    max_retries: int = 3
    inference_timeout: float = 10.0
    log_level: str = "INFO"
    api_endpoints: Optional[list[str]] = None