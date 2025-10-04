import uuid
from typing import Dict, List, Optional, Any, Sequence
from datetime import datetime
import structlog
from pydantic import Field
import asyncio

from llama_index.core.agent.types import Task, TaskStep, TaskStepOutput
from llama_index.core.agent import CustomSimpleAgentWorker
from llama_index.core.tools import BaseTool
from llama_index.core.llms import LLM
from llama_index.core.base.llms.types import ChatResponse as AgentChatResponse, ChatMessage, MessageRole

from models import AgentSessionContext, AgentConfig, ToolExecution


logger = structlog.get_logger(__name__)


class StatefulAgentWorker(CustomSimpleAgentWorker):
    """
    MVP Custom LlamaIndex AgentWorker with simplified session context management.
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
        self.__dict__['sessions'] = {} # Initialize sessions directly
    
    @property
    def sessions(self) -> Dict[str, Any]:
        return self.__dict__.get('sessions', {})

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
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        trace_id = str(uuid.uuid4())
        
        session_context = AgentSessionContext(
            session_id=session_id,
            trace_id=trace_id,
            goal=goal,
            session_data={},
            execution_history=[],
            current_step=0,
            start_time=datetime.utcnow(),
            last_action_time=datetime.utcnow(),
        )
        
        self.sessions[session_id] = session_context
        self.logger.info("Created new agent session (MVP)", session_id=session_id, goal=goal)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[AgentSessionContext]:
        return self.sessions.get(session_id)
    
    def update_session_data(self, session_id: str, data: Dict[str, Any]):
        if session_id in self.sessions:
            self.sessions[session_id].session_data.update(data)
            self.sessions[session_id].update_last_action()
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions to prevent memory leaks (minimal implementation)."""
        expired_sessions = []
        for session_id, context in self.sessions.items():
            # Assuming AgentSessionContext has an is_expired method
            if context.is_expired(self.config.session_timeout_minutes):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            self.logger.info("Cleaned up expired session (MVP)", session_id=session_id)
        
        if expired_sessions:
            self.logger.info("Session cleanup completed (MVP)", expired_count=len(expired_sessions), remaining_sessions=len(self.sessions))

    def _run_step(
        self,
        step: TaskStep,
        task: Task,
        **kwargs: Any,
    ) -> TaskStepOutput:
        # Ensure step is a TaskStep object
        if isinstance(step, dict):
            if "step_id" not in step:
                step["step_id"] = str(uuid.uuid4())
            step = TaskStep(**step)

        session_id = self.__dict__.get('_current_session_id', None)
        session_context = None
        if session_id:
            session_context = self.get_session(session_id)

        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Calling super()._run_step", session_id=session_id, step_id=step.step_id, task_id=task.task_id, step_input=step.input)
            result = super()._run_step(step, task, **kwargs)
            self.logger.info("super()._run_step returned", session_id=session_id, step_id=step.step_id, result_type=type(result).__name__, result_is_none=(result is None))
            
            # Handle cases where result or result.output might be None
            output_content = "No output from step"
            if result and hasattr(result, 'output') and result.output is not None:
                output_content = str(result.output)
            elif result is None:
                output_content = "Step returned None"
            
            if session_context:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                execution = ToolExecution(
                    tool_name=step.step_id,
                    parameters={"input": step.input},
                    response={"content": output_content},
                    execution_time=execution_time,
                    success=True
                )
                session_context.add_execution(execution)
            
            # Ensure result is not None before returning its attributes
            if result is None:
                self.logger.error("super()._run_step returned None. Generating a failure response.", session_id=session_id, step_id=step.step_id)
                
                # Create a TaskStepOutput indicating failure
                failure_message = "Agent failed to produce a response from the underlying LLM/tools."
                failure_output = AgentChatResponse(
                    message=ChatMessage(role=MessageRole.ASSISTANT, content=failure_message),
                    text=failure_message # Ensure text attribute is present
                )
                
                return TaskStepOutput(
                    output=failure_output,
                    task_step=step,
                    is_last=True, # Mark as last step to prevent infinite loops
                    next_steps=[]
                ), True # Return a tuple (TaskStepOutput, bool)
            
            return result, result.is_last # Ensure this returns a tuple
                
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            if session_context:
                execution = ToolExecution(
                    tool_name=step.step_id,
                    parameters={"input": step.input},
                    response={"error": str(e)},
                    execution_time=execution_time,
                    success=False,
                    error_message=str(e)
                )
                session_context.add_execution(execution)
            self.logger.error("Step execution failed (MVP)", session_id=session_id, error=str(e))
            raise

    async def _arun_step(
        self,
        step: TaskStep,
        task: Task,
        **kwargs: Any,
    ) -> TaskStepOutput:
        """Asynchronous version of _run_step, calls sync version in a thread pool."""
        # asyncio.to_thread returns the result of the function call directly.
        # We need to ensure it's unpacked correctly if _run_step returns a tuple.
        result_tuple = await asyncio.to_thread(self._run_step, step, task, **kwargs)
        return result_tuple # This will already be a tuple (TaskStepOutput, bool)

    def _initialize_state(self, task: Task, **kwargs: Any) -> Dict[str, Any]:
        """Initialize state for a new task."""
        # Minimal implementation for MVP
        return {"task_id": task.task_id, "step_count": 0}

    def _finalize_task(self, task: Task, **kwargs: Any) -> None:
        """Finalize a completed task."""
        # Minimal implementation for MVP
        pass
