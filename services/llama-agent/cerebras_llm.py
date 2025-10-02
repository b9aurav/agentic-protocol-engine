"""
Cerebras LLM wrapper for LlamaIndex integration.
"""
import os
import asyncio
from typing import Any, Dict, List, Optional, Sequence, Generator
from llama_index.core.llms import CustomLLM, CompletionResponse, LLMMetadata, CompletionResponseGen
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.base.llms.types import ChatMessage, ChatResponse, MessageRole
from cerebras.cloud.sdk import Cerebras
from pydantic import Field, model_validator
import structlog

logger = structlog.get_logger(__name__)


class CerebrasLLM(CustomLLM):
    """
    Custom LLM wrapper for Cerebras Cloud SDK integration with LlamaIndex.
    """
    
    # Define Pydantic fields that LlamaIndex expects
    api_key: str = Field(default_factory=lambda: os.getenv("CEREBRAS_API_KEY", "dummy-key"))
    base_url: str = Field(default="https://api.cerebras.ai")
    model_name: str = Field(default="llama3.1-8b")
    max_tokens: int = Field(default=1000)
    temperature: float = Field(default=0.7)
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: str = "llama3.1-8b",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ):
        # Initialize with provided values or defaults
        super().__init__(
            api_key=api_key or os.getenv("CEREBRAS_API_KEY", "dummy-key"),
            base_url=base_url or "https://api.cerebras.ai",
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    
        # Initialize Cerebras client manually
        object.__setattr__(self, 'client', Cerebras(
            api_key=self.api_key,
            base_url=self.base_url
        ))
        
        logger.info(
            "Cerebras LLM initialized",
            model=self.model_name,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )

    
    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            context_window=8192,  # Approximate context window for llama3.1-8b
            num_output=self.max_tokens,
            is_chat_model=True,
            model_name=self.model_name,
        )
    
    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """
        Complete a prompt using Cerebras.
        
        Args:
            prompt: The prompt to complete
            **kwargs: Additional arguments
            
        Returns:
            CompletionResponse with the completion
        """
        try:
            # Convert prompt to chat format
            messages = [{"role": "user", "content": prompt}]
            
            # Make request to Cerebras
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            
            # Extract completion text
            completion_text = response.choices[0].message.content
            
            logger.info(
                "Cerebras completion response debug",
                prompt_length=len(prompt),
                completion_text=completion_text,
                completion_text_type=type(completion_text).__name__,
                completion_text_length=len(completion_text) if completion_text else 0,
                model=self.model_name,
                full_response_choices=len(response.choices) if hasattr(response, 'choices') else 0
            )
            
            return CompletionResponse(text=completion_text)
            
        except Exception as e:
            logger.error(
                "Cerebras completion failed",
                error=str(e),
                error_type=type(e).__name__,
                prompt_length=len(prompt)
            )
            raise
    
    @llm_completion_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """
        Chat with Cerebras using a sequence of messages.
        
        Args:
            messages: Sequence of chat messages
            **kwargs: Additional arguments
            
        Returns:
            ChatResponse with the response
        """
        try:
            # Convert LlamaIndex ChatMessage to Cerebras format
            cerebras_messages = []
            for msg in messages:
                cerebras_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
            
            # Make request to Cerebras
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=cerebras_messages,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            
            # Extract response
            response_content = response.choices[0].message.content
            
            logger.info(
                "Cerebras chat response debug",
                message_count=len(messages),
                response_content=response_content,
                response_content_type=type(response_content).__name__,
                response_content_length=len(response_content) if response_content else 0,
                model=self.model_name,
                full_response_choices=len(response.choices) if hasattr(response, 'choices') else 0
            )
            
            # Create ChatMessage for response
            response_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response_content
            )
            
            # Create ChatResponse with additional text field for compatibility
            chat_response = ChatResponse(message=response_message)
            # Add text field for LlamaIndex compatibility
            if hasattr(chat_response, '__dict__'):
                chat_response.__dict__['text'] = response_content
            
            return chat_response
            
        except Exception as e:
            logger.error(
                "Cerebras chat failed",
                error=str(e),
                error_type=type(e).__name__,
                message_count=len(messages)
            )
            raise
    
    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """
        Async completion - runs sync completion in thread pool.
        
        Args:
            prompt: The prompt to complete
            **kwargs: Additional arguments
            
        Returns:
            CompletionResponse with the completion
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.complete, prompt, **kwargs)
    
    async def achat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """
        Async chat - runs sync chat in thread pool.
        
        Args:
            messages: Sequence of chat messages
            **kwargs: Additional arguments
            
        Returns:
            ChatResponse with the response
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat, messages, **kwargs)
    
    def stream_complete(self, prompt: str, **kwargs: Any) -> Generator[CompletionResponseGen, None, None]:
        """
        Stream completion - not implemented for Cerebras, falls back to regular completion.
        
        Args:
            prompt: The prompt to complete
            **kwargs: Additional arguments
            
        Yields:
            CompletionResponseGen chunks (single response in this case)
        """
        # Cerebras SDK doesn't support streaming in our current setup
        # Fall back to regular completion and yield as single chunk
        response = self.complete(prompt, **kwargs)
        yield CompletionResponseGen(text=response.text, delta=response.text)