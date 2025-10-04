"""
Custom LlamaIndex AgentWorker implementation for stateful MCP-based agents.
"""
import uuid
import time
from typing import Dict, List, Optional, Any, Sequence
from datetime import datetime
import structlog
from pydantic import Field

from llama_index.core.agent.types import Task, TaskStep, TaskStepOutput
from llama_index.core.agent import CustomSimpleAgentWorker
from llama_index.core.tools import BaseTool
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory
from llama_index.core.base.llms.types import ChatResponse as AgentChatResponse, ChatMessage, MessageRole

from models import AgentSessionContext, AgentConfig, ToolExecution, MCPToolCall
from metrics import get_metrics_collector


logger = structlog.get_logger(__name__)


class StatefulAgentWorker(CustomSimpleAgentWorker):
    """
    Custom LlamaIndex AgentWorker with session context management.
    Implements stateful behavior for multi-step user journey simulation.
    """
    
    config: AgentConfig = Field(..., description="Agent configuration")
    
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
        # Ensure internal agent config attribute exists for compatibility with AgentRunner
        # Store in __dict__ to avoid pydantic conflicts
        if '_agent_config' not in self.__dict__:
            self.__dict__['_agent_config'] = {}
    
    @property
    def sessions(self) -> Dict[str, Any]:
        """Access sessions dictionary stored in __dict__ to avoid pydantic conflicts."""
        sessions_dict = self.__dict__.get('sessions', {})
        print(f"DEBUG: sessions property accessed - Current sessions: {list(sessions_dict.keys())}")
        return sessions_dict
    
    @property
    def logger(self):
        """Access logger stored in __dict__ to avoid pydantic conflicts."""
        stored_logger = self.__dict__.get('logger')
        if stored_logger is None:
            # Fallback: create a new logger if none exists
            import structlog
            stored_logger = structlog.get_logger(__name__).bind(agent_id=self.config.agent_id if hasattr(self, 'config') else 'unknown')
            self.__dict__['logger'] = stored_logger
        return stored_logger
    
    def create_session(self, goal: str, session_id: Optional[str] = None) -> str:
        """
        Create a new agent session with a specific goal.
        
        Args:
            goal: The user journey goal for this session
            session_id: Optional session ID, generates UUID if not provided
            
        Returns:
            The session ID for the created session
        """
        if not isinstance(goal, str):
            raise TypeError(f"goal must be str, got {type(goal)}")
            
        print(f"DEBUG: create_session called - Goal: {goal}")
        if session_id is None:
            session_id = str(uuid.uuid4())
        elif not isinstance(session_id, str) or len(session_id) != 36:
            raise ValueError(f"Invalid session_id format: {session_id}")
            
        print(f"DEBUG: Generated session_id: {session_id}")
        
        trace_id = str(uuid.uuid4())
        
        try:
            print(f"DEBUG: Creating session context - ID: {session_id}, Goal: {goal}")
            session_context = AgentSessionContext(
                session_id=session_id,
                trace_id=trace_id,
                goal=goal,
                session_data={},
                execution_history=[],
                current_step=0,
                start_time=datetime.utcnow(),
                last_action_time=datetime.utcnow(),
                success_indicators=[],
                failure_indicators=[],
                action_timestamps=[],
                current_mtba=0.0,
                cognitive_violations=0
            )
            
            # Validate session context structure
            required_attrs = ['session_id', 'trace_id', 'goal', 'session_data',
                            'execution_history', 'current_step', 'start_time',
                            'last_action_time', 'success_indicators', 'failure_indicators']
            if not all(hasattr(session_context, attr) for attr in required_attrs):
                raise ValueError("Invalid session context structure after creation")
            print(f"DEBUG: Session context created successfully")
            
            # Access sessions dictionary directly from __dict__ to avoid pydantic conflicts
            sessions_dict = self.__dict__.get('sessions', {})
            print(f"DEBUG: Before storing - Current sessions: {len(sessions_dict)}, Keys: {list(sessions_dict.keys())}")
            sessions_dict[session_id] = session_context
            self.__dict__['sessions'] = sessions_dict
            print(f"DEBUG: After storing - Total sessions now: {len(sessions_dict)}, Keys: {list(sessions_dict.keys())}")
            
            # Verify it was stored by accessing it again
            updated_sessions_dict = self.__dict__.get('sessions', {})
            retrieved = updated_sessions_dict.get(session_id)
            print(f"DEBUG: Verification - Retrieved session: {retrieved is not None}, Total in dict: {len(updated_sessions_dict)}")
            
            # Also check via the property
            property_sessions = self.sessions
            property_retrieved = property_sessions.get(session_id)
            print(f"DEBUG: Property check - Retrieved via property: {property_retrieved is not None}, Total via property: {len(property_sessions)}")
            
        except Exception as e:
            print(f"DEBUG: Session creation failed - Error: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        self.logger.info(
            "Created new agent session",
            session_id=session_id,
            trace_id=trace_id,
            goal=goal
        )
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[AgentSessionContext]:
        """Get session context by ID."""
        if not isinstance(session_id, str):
            raise TypeError(f"session_id must be str, got {type(session_id)}")
            
        sessions_dict = self.__dict__.get('sessions', {})
        if not isinstance(sessions_dict, dict):
            self.__dict__['sessions'] = {}
            sessions_dict = self.__dict__['sessions']
            
        print(f"DEBUG: get_session called - ID: {session_id}, Available sessions: {list(sessions_dict.keys())}")
        result = sessions_dict.get(session_id)
        print(f"DEBUG: get_session result - Found: {result is not None}")
        
        # Validate session context structure
        if result and not all(hasattr(result, attr) for attr in ['session_id', 'trace_id', 'goal']):
            self.logger.error("Invalid session context structure", session_id=session_id)
            return None
            
        return result
    
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
        
        if expired_sessions:
            self.logger.info("Session cleanup completed", expired_count=len(expired_sessions), remaining_sessions=len(self.sessions))
    
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
        # Ensure step is a TaskStep object
        if isinstance(step, dict):
            if "step_id" not in step:
                step["step_id"] = str(uuid.uuid4())
            step = TaskStep(**step)
        
        # Get session_id from stored context in agent worker
        session_id = self.__dict__.get('_current_session_id', None)
        session_context = None
        
        if session_id:
            session_context = self.get_session(session_id)
            if session_context:
                # Check if session has expired or reached max steps
                if session_context.is_expired(self.config.session_timeout_minutes):
                    self.logger.warning("Session expired", session_id=session_id)
                    return (
                        TaskStepOutput(
                            output=AgentChatResponse(
                                message=ChatMessage(role=MessageRole.ASSISTANT, content="Session expired"),
                                text="Session expired"
                            ),
                            task_step=step,
                            is_last=False,
                            next_steps=[]
                        ),
                        True
                    )
                
                if session_context.has_reached_max_steps():
                    self.logger.warning("Session reached max steps", session_id=session_id)
                    return (
                        TaskStepOutput(
                            output=AgentChatResponse(
                                message=ChatMessage(role=MessageRole.ASSISTANT, content="Maximum steps reached"),
                                text="Maximum steps reached"
                            ),
                            task_step=step,
                            is_last=False,
                            next_steps=[]
                        ),
                        True
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
                
                self.logger.info(
                    "Calling super()._run_step",
                    session_id=session_id,
                    step_id=step.step_id,
                    step_type=type(step).__name__,
                    task_type=type(task).__name__,
                    step_input=str(step.input)[:200] if hasattr(step, 'input') else "N/A"
                )
                
                try:
                    result = super()._run_step(step, task, **kwargs)
                except Exception as e:
                    self.logger.error(
                        "Error during super()._run_step",
                        session_id=session_id,
                        step_id=step.step_id,
                        error=str(e),
                        error_type=type(e).__name__,
                        step_details=str(step),
                        task_details=str(task)
                    )
                    raise # Re-raise the exception to continue the original error flow
                
                # Debug: Log the raw output from the LLM before further processing
                if result and hasattr(result, 'output') and hasattr(result.output, 'message') and hasattr(result.output.message, 'content'):
                    self.logger.info(
                        "LLM raw response content",
                        session_id=session_id,
                        step_id=step.step_id,
                        content_type=type(result.output.message.content).__name__,
                        content_preview=str(result.output.message.content)[:500] + "..." if len(str(result.output.message.content)) > 500 else str(result.output.message.content)
                    )
                elif result and hasattr(result, 'output') and hasattr(result.output, 'response'):
                     self.logger.info(
                        "LLM raw response content (fallback to response attribute)",
                        session_id=session_id,
                        step_id=step.step_id,
                        content_type=type(result.output.response).__name__,
                        content_preview=str(result.output.response)[:500] + "..." if len(str(result.output.response)) > 500 else str(result.output.response)
                    )
                
                # Handle cases where the step does not produce a result
                if result is None:
                    result = TaskStepOutput(
                        output=AgentChatResponse(
                            message=ChatMessage(role=MessageRole.ASSISTANT, content="Step completed without output")
                        ),
                        task_step=step,
                        is_last=False,
                        next_steps=[]
                    )
                
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
                
                return result, result.is_last
                
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
    
    def _initialize_state(self, task: Task, **kwargs) -> Dict[str, Any]:
        """
        Initialize state for a new task.
        
        Args:
            task: The task to initialize state for
            **kwargs: Additional keyword arguments
            
        Returns:
            Dictionary containing initial state
        """
        # Initialize basic state
        state = {
            "task_id": task.task_id,
            "step_count": 0,
            "start_time": time.time(),
            "session_id": getattr(task, 'session_id', None)
        }
        
        # If task has a session_id, link it to our session management
        session_id = getattr(task, 'session_id', None)
        if session_id and session_id in self.sessions:
            session_context = self.sessions[session_id]
            state["session_context"] = {
                "goal": session_context.goal,
                "current_step": session_context.current_step,
                "session_data": session_context.session_data.copy()
            }
            
            self.logger.info(
                "Task state initialized with session context",
                task_id=task.task_id,
                session_id=session_id,
                goal=session_context.goal
            )
        else:
            self.logger.info(
                "Task state initialized without session context",
                task_id=task.task_id
            )
        
        return state
    
    def _finalize_task(self, task: Task, **kwargs) -> None:
        """
        Finalize a completed task.
        
        Args:
            task: The task to finalize
            **kwargs: Additional keyword arguments
        """
        # Update session context if available
        session_id = getattr(task, 'session_id', None)
        if session_id and session_id in self.sessions:
            session_context = self.sessions[session_id]
            session_context.update_last_action()
            
            self.logger.info(
                "Task finalized with session update",
                task_id=task.task_id,
                session_id=session_id,
                total_steps=session_context.current_step
            )
        else:
            self.logger.info(
                "Task finalized without session context",
                task_id=task.task_id
            )