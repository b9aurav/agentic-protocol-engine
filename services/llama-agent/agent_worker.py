"""
Custom LlamaIndex AgentWorker implementation for stateful MCP-based agents.
"""
import uuid
from typing import Dict, List, Optional, Any, Sequence
from datetime import datetime
import structlog

from llama_index.core.agent.types import Task
from llama_index.core.agent import CustomSimpleAgentWorker
from llama_index.core.tools import BaseTool
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory
from llama_index.core.agent.types import TaskStep, TaskStepOutput
from llama_index.core.schema import AgentChatResponse

from models import AgentSessionContext, AgentConfig, ToolExecution, MCPToolCall
from metrics import get_metrics_collector


logger = structlog.get_logger(__name__)


class StatefulAgentWorker(CustomSimpleAgentWorker):
    """
    Custom LlamaIndex AgentWorker with session context management.
    Implements stateful behavior for multi-step user journey simulation.
    """
    
    def __init__(
        self,
        tools: Sequence[BaseTool],
        llm: LLM,
        config: AgentConfig,
        verbose: bool = False,
        **kwargs
    ):
        super().__init__(
            tools=tools,
            llm=llm,
            verbose=verbose,
            **kwargs
        )
        self.config = config
        self.sessions: Dict[str, AgentSessionContext] = {}
        self.logger = logger.bind(agent_id=config.agent_id)
    
    def create_session(self, goal: str, session_id: Optional[str] = None) -> str:
        """
        Create a new agent session with a specific goal.
        
        Args:
            goal: The user journey goal for this session
            session_id: Optional session ID, generates UUID if not provided
            
        Returns:
            The session ID for the created session
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        trace_id = str(uuid.uuid4())
        
        session_context = AgentSessionContext(
            session_id=session_id,
            trace_id=trace_id,
            goal=goal
        )
        
        self.sessions[session_id] = session_context
        
        self.logger.info(
            "Created new agent session",
            session_id=session_id,
            trace_id=trace_id,
            goal=goal
        )
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[AgentSessionContext]:
        """Get session context by ID."""
        return self.sessions.get(session_id)
    
    def update_session_data(self, session_id: str, data: Dict[str, Any]):
        """Update session data (cookies, tokens, etc.)."""
        if session_id in self.sessions:
            self.sessions[session_id].session_data.update(data)
            self.sessions[session_id].update_last_action()
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions to prevent memory leaks."""
        expired_sessions = []
        for session_id, context in self.sessions.items():
            if context.is_expired(self.config.session_timeout_minutes):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            self.logger.info("Cleaned up expired session", session_id=session_id)
    
    def _run_step(
        self,
        step: TaskStep,
        task: Task,
        **kwargs: Any,
    ) -> TaskStepOutput:
        """
        Execute a single step in the agent workflow with enhanced error handling.
        Overrides the base implementation to add session context management and error categorization.
        """
        # Extract session_id from task metadata if available
        session_id = getattr(task, 'session_id', None)
        session_context = None
        
        if session_id:
            session_context = self.get_session(session_id)
            if session_context:
                # Check if session has expired or reached max steps
                if session_context.is_expired(self.config.session_timeout_minutes):
                    self.logger.warning("Session expired", session_id=session_id)
                    return TaskStepOutput(
                        output=AgentChatResponse(response="Session expired"),
                        task_step=step,
                        is_last=True
                    )
                
                if session_context.has_reached_max_steps():
                    self.logger.warning("Session reached max steps", session_id=session_id)
                    return TaskStepOutput(
                        output=AgentChatResponse(response="Maximum steps reached"),
                        task_step=step,
                        is_last=True
                    )
        
        # Execute the step using parent implementation with enhanced error handling
        start_time = datetime.utcnow()
        execution_attempt = 0
        max_step_retries = 2  # Allow 2 retries per step for transient errors
        
        while execution_attempt <= max_step_retries:
            try:
                execution_attempt += 1
                
                # Add retry context to step if this is a retry
                if execution_attempt > 1:
                    self.logger.info(
                        "Retrying step execution",
                        session_id=session_id,
                        step_id=step.step_id,
                        attempt=execution_attempt,
                        max_attempts=max_step_retries + 1
                    )
                
                result = super()._run_step(step, task, **kwargs)
                
                # Record successful execution
                if session_context:
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    # Extract additional metadata from the result
                    response_data = {"output": str(result.output)}
                    
                    # Try to extract structured data from tool calls if available
                    if hasattr(result.output, 'sources') and result.output.sources:
                        response_data["sources"] = [str(source) for source in result.output.sources]
                    
                    execution = ToolExecution(
                        tool_name=step.step_id,
                        parameters={"input": step.input, "attempt": execution_attempt},
                        response=response_data,
                        execution_time=execution_time,
                        success=True
                    )
                    session_context.add_execution(execution)
                    
                    # Record tool call in metrics collector
                    metrics_collector = get_metrics_collector()
                    if metrics_collector:
                        metrics_collector.record_tool_call(
                            tool_name=step.step_id,
                            success=True,
                            session_id=session_id,
                            execution=execution
                        )
                    
                    self.logger.info(
                        "Step executed successfully",
                        session_id=session_id,
                        step=session_context.current_step,
                        execution_time=execution_time,
                        attempts=execution_attempt
                    )
                
                return result
                
            except Exception as e:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                error_type = type(e).__name__
                error_message = str(e)
                
                # Categorize the error
                error_category = self._categorize_error(e)
                
                # Determine if this error should trigger a retry
                should_retry = (
                    execution_attempt <= max_step_retries and
                    error_category in ["transient", "network", "rate_limit"]
                )
                
                # Record failed execution
                if session_context:
                    execution = ToolExecution(
                        tool_name=step.step_id,
                        parameters={
                            "input": step.input, 
                            "attempt": execution_attempt,
                            "error_category": error_category
                        },
                        response={
                            "error": error_message,
                            "error_type": error_type,
                            "error_category": error_category
                        },
                        execution_time=execution_time,
                        success=False,
                        error_message=error_message
                    )
                    session_context.add_execution(execution)
                    
                    # Record failed tool call in metrics collector
                    metrics_collector = get_metrics_collector()
                    if metrics_collector:
                        metrics_collector.record_tool_call(
                            tool_name=step.step_id,
                            success=False,
                            session_id=session_id,
                            execution=execution
                        )
                
                if should_retry:
                    self.logger.warning(
                        "Step execution failed, will retry",
                        session_id=session_id,
                        step_id=step.step_id,
                        error=error_message,
                        error_type=error_type,
                        error_category=error_category,
                        attempt=execution_attempt,
                        execution_time=execution_time
                    )
                    
                    # Apply exponential backoff for retries
                    import asyncio
                    import time
                    time.sleep(min(0.5 * (2 ** (execution_attempt - 1)), 2.0))
                    continue
                else:
                    self.logger.error(
                        "Step execution failed permanently",
                        session_id=session_id,
                        step_id=step.step_id,
                        error=error_message,
                        error_type=error_type,
                        error_category=error_category,
                        attempts=execution_attempt,
                        execution_time=execution_time
                    )
                    
                    # For non-retryable errors, re-raise immediately
                    raise
        
        # If we get here, all retries were exhausted
        raise Exception(f"Step execution failed after {execution_attempt} attempts")
    
    def _categorize_error(self, error: Exception) -> str:
        """
        Categorize errors for appropriate handling and retry logic.
        
        Args:
            error: Exception to categorize
            
        Returns:
            String category: "transient", "network", "rate_limit", "auth", "client", "server", "fatal"
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Network and connection errors
        if any(pattern in error_str for pattern in ["connection", "network", "timeout", "dns"]):
            return "network"
        
        # Rate limiting errors
        if any(pattern in error_str for pattern in ["rate limit", "throttle", "429", "too many requests"]):
            return "rate_limit"
        
        # Authentication and authorization errors
        if any(pattern in error_str for pattern in ["401", "403", "unauthorized", "forbidden", "authentication"]):
            return "auth"
        
        # Client errors (4xx)
        if any(pattern in error_str for pattern in ["400", "404", "405", "406", "409", "422"]):
            return "client"
        
        # Server errors (5xx) - often transient
        if any(pattern in error_str for pattern in ["500", "502", "503", "504", "server error"]):
            return "server"
        
        # Transient errors that should be retried
        if any(pattern in error_str for pattern in ["temporary", "unavailable", "busy", "overload"]):
            return "transient"
        
        # Schema and validation errors - usually fatal
        if any(pattern in error_str for pattern in ["schema", "validation", "invalid", "malformed"]):
            return "fatal"
        
        # Default categorization based on exception type
        transient_types = ["TimeoutError", "ConnectionError", "HTTPError"]
        if error_type in transient_types:
            return "transient"
        
        # Default to fatal for unknown errors
        return "fatal"
    
    def finalize_response(
        self,
        task: Task,
        step_output: TaskStepOutput,
    ) -> AgentChatResponse:
        """
        Finalize the agent response and update session context.
        """
        response = super().finalize_response(task, step_output)
        
        # Update session context if available
        session_id = getattr(task, 'session_id', None)
        if session_id and session_id in self.sessions:
            session_context = self.sessions[session_id]
            session_context.update_last_action()
            
            self.logger.info(
                "Response finalized",
                session_id=session_id,
                total_steps=session_context.current_step,
                session_duration=(
                    session_context.last_action_time - session_context.start_time
                ).total_seconds()
            )
        
        return response