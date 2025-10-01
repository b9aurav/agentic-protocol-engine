"""
Pydantic models for OpenAI-compatible API
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message model"""
    role: Literal["system", "user", "assistant"] = Field(..., description="The role of the message author")
    content: str = Field(..., description="The content of the message")


class ChatCompletionRequest(BaseModel):
    """Chat completion request model (OpenAI-compatible)"""
    model: Optional[str] = Field(default="llama3.1-8b", description="Model to use for completion")
    messages: List[ChatMessage] = Field(..., description="List of messages in the conversation")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum number of tokens to generate")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    stream: Optional[bool] = Field(default=False, description="Whether to stream responses")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences")


class Usage(BaseModel):
    """Token usage information"""
    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens")


class ChatCompletionChoice(BaseModel):
    """Chat completion choice"""
    index: int = Field(..., description="Index of the choice")
    message: ChatMessage = Field(..., description="The message content")
    finish_reason: Optional[str] = Field(default="stop", description="Reason for completion finish")


class ChatCompletionResponse(BaseModel):
    """Chat completion response model (OpenAI-compatible)"""
    id: str = Field(..., description="Unique identifier for the completion")
    object: Literal["chat.completion"] = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used for completion")
    choices: List[ChatCompletionChoice] = Field(..., description="List of completion choices")
    usage: Usage = Field(..., description="Token usage information")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: Dict[str, Any] = Field(..., description="Error details")


class InferenceMetrics(BaseModel):
    """Inference performance metrics"""
    request_id: str = Field(..., description="Unique request identifier")
    ttft: float = Field(..., description="Time to First Token in seconds")
    total_time: float = Field(..., description="Total request time in seconds")
    total_tokens: int = Field(..., description="Total tokens processed")
    prompt_tokens: int = Field(..., description="Input tokens")
    completion_tokens: int = Field(..., description="Output tokens")
    model: str = Field(..., description="Model used")
    timestamp: float = Field(..., description="Unix timestamp")
    cost_estimate: Optional[float] = Field(default=None, description="Estimated cost in USD")