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
        Execute a single step in the agent workflow.
        Overrides the base implementation to add session context management.
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
        
        # Execute the step using parent implementation
        start_time = datetime.utcnow()
        
        try:
            result = super()._run_step(step, task, **kwargs)
            
            # Record successful execution
            if session_context:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                execution = ToolExecution(
                    tool_name=step.step_id,
                    parameters={"input": step.input},
                    response={"output": str(result.output)},
                    execution_time=execution_time,
                    success=True
                )
                session_context.add_execution(execution)
                
                self.logger.info(
                    "Step executed successfully",
                    session_id=session_id,
                    step=session_context.current_step,
                    execution_time=execution_time
                )
            
            return result
            
        except Exception as e:
            # Record failed execution
            if session_context:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                execution = ToolExecution(
                    tool_name=step.step_id,
                    parameters={"input": step.input},
                    response={},
                    execution_time=execution_time,
                    success=False,
                    error_message=str(e)
                )
                session_context.add_execution(execution)
                
                self.logger.error(
                    "Step execution failed",
                    session_id=session_id,
                    step=session_context.current_step,
                    error=str(e),
                    execution_time=execution_time
                )
            
            # Re-raise the exception to be handled by the caller
            raise
    
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