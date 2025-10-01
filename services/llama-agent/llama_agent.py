"""
Main Llama Agent implementation with LlamaIndex integration.
"""
import os
import uuid
from typing import Optional, Dict, Any
import structlog
import asyncio

from llama_index.core.agent import AgentRunner
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import BaseTool

from agent_worker import StatefulAgentWorker
from models import AgentConfig, AgentSessionContext
from tools import HTTPGetTool, HTTPPostTool, HTTPPutTool, HTTPDeleteTool, StateUpdateTool


logger = structlog.get_logger(__name__)


class LlamaAgent:
    """
    Main Llama Agent class that orchestrates the agent workflow.
    Integrates LlamaIndex CustomSimpleAgentWorker with MCP tools and session management.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logger.bind(agent_id=config.agent_id)
        
        # Initialize LLM with Cerebras Proxy endpoint
        self.llm = OpenAI(
            api_base=f"{config.cerebras_proxy_url}/v1",
            api_key=os.getenv("CEREBRAS_API_KEY", "dummy-key"),
            model="llama-3.1-8b",
            timeout=config.inference_timeout
        )
        
        # Initialize MCP tools
        self.tools = self._initialize_tools()
        
        # Initialize agent worker
        self.agent_worker = StatefulAgentWorker(
            tools=self.tools,
            llm=self.llm,
            config=config,
            verbose=True
        )
        
        # Initialize agent runner
        self.agent_runner = AgentRunner(self.agent_worker)
        
        self.logger.info("Llama Agent initialized successfully")
    
    def _initialize_tools(self) -> list[BaseTool]:
        """Initialize MCP tools for HTTP operations and state management."""
        return [
            HTTPGetTool(
                mcp_gateway_url=self.config.mcp_gateway_url,
                agent_worker=None  # Will be set after agent_worker is created
            ),
            HTTPPostTool(
                mcp_gateway_url=self.config.mcp_gateway_url,
                agent_worker=None
            ),
            HTTPPutTool(
                mcp_gateway_url=self.config.mcp_gateway_url,
                agent_worker=None
            ),
            HTTPDeleteTool(
                mcp_gateway_url=self.config.mcp_gateway_url,
                agent_worker=None
            ),
            StateUpdateTool(agent_worker=None)
        ]
    
    def _update_tool_references(self):
        """Update tool references to the agent worker after initialization."""
        for tool in self.tools:
            if hasattr(tool, 'agent_worker'):
                tool.agent_worker = self.agent_worker
    
    async def start_session(self, goal: str, session_id: Optional[str] = None) -> str:
        """
        Start a new agent session with a specific goal.
        
        Args:
            goal: The user journey goal (e.g., "complete purchase flow")
            session_id: Optional session ID
            
        Returns:
            The session ID for the created session
        """
        # Update tool references if not already done
        self._update_tool_references()
        
        session_id = self.agent_worker.create_session(goal, session_id)
        
        self.logger.info(
            "Started new agent session",
            session_id=session_id,
            goal=goal
        )
        
        return session_id
    
    async def execute_goal(self, session_id: str, initial_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the agent goal for a specific session.
        
        Args:
            session_id: The session ID to execute
            initial_prompt: Optional initial prompt to start the conversation
            
        Returns:
            Dictionary containing execution results and session info
        """
        session_context = self.agent_worker.get_session(session_id)
        if not session_context:
            raise ValueError(f"Session {session_id} not found")
        
        self.logger.info(
            "Starting goal execution",
            session_id=session_id,
            goal=session_context.goal
        )
        
        try:
            # Create task with session context
            if initial_prompt is None:
                initial_prompt = f"""
You are an AI agent simulating a user journey with the goal: {session_context.goal}

You have access to HTTP tools to interact with web services through an MCP Gateway.
Use the available tools to complete the user journey step by step.

Session ID: {session_id}
Trace ID: {session_context.trace_id}

Start by analyzing the goal and planning your approach.
"""
            
            # Create a task with session metadata
            task = self.agent_runner.create_task(initial_prompt)
            task.session_id = session_id  # Attach session ID to task
            
            # Execute the task
            response = await self.agent_runner.arun_task(task)
            
            # Get updated session context
            updated_context = self.agent_worker.get_session(session_id)
            
            result = {
                "session_id": session_id,
                "response": str(response),
                "steps_completed": updated_context.current_step if updated_context else 0,
                "execution_history": [
                    exec.dict() for exec in updated_context.execution_history
                ] if updated_context else [],
                "session_data": updated_context.session_data if updated_context else {},
                "success": True
            }
            
            self.logger.info(
                "Goal execution completed",
                session_id=session_id,
                steps_completed=result["steps_completed"]
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Goal execution failed",
                session_id=session_id,
                error=str(e)
            )
            
            return {
                "session_id": session_id,
                "response": f"Execution failed: {str(e)}",
                "steps_completed": 0,
                "execution_history": [],
                "session_data": {},
                "success": False,
                "error": str(e)
            }
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session."""
        session_context = self.agent_worker.get_session(session_id)
        if not session_context:
            return None
        
        return {
            "session_id": session_context.session_id,
            "trace_id": session_context.trace_id,
            "goal": session_context.goal,
            "current_step": session_context.current_step,
            "start_time": session_context.start_time.isoformat(),
            "last_action_time": session_context.last_action_time.isoformat(),
            "session_data": session_context.session_data,
            "execution_count": len(session_context.execution_history),
            "is_expired": session_context.is_expired(self.config.session_timeout_minutes),
            "has_reached_max_steps": session_context.has_reached_max_steps()
        }
    
    def cleanup_sessions(self):
        """Clean up expired sessions."""
        self.agent_worker.cleanup_expired_sessions()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the agent."""
        try:
            # Test LLM connectivity
            test_response = await self.llm.acomplete("Hello")
            llm_healthy = bool(test_response.text)
        except Exception as e:
            self.logger.error("LLM health check failed", error=str(e))
            llm_healthy = False
        
        active_sessions = len(self.agent_worker.sessions)
        
        return {
            "agent_id": self.config.agent_id,
            "llm_healthy": llm_healthy,
            "active_sessions": active_sessions,
            "tools_count": len(self.tools),
            "status": "healthy" if llm_healthy else "unhealthy"
        }