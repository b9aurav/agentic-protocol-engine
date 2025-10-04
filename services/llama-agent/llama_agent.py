"""
 Llama Agent implementation with LlamaIndex integration.
Simplified version for core functionality.
"""
import os
from typing import Optional, Dict, Any, Sequence
import structlog
import asyncio
import re
import json

from llama_index.core.agent import AgentRunner
from llama_index.core.tools import BaseTool
from llama_index.core.base.llms.types import ChatMessage, MessageRole

from agent_worker import StatefulAgentWorker
from models import AgentConfig, ToolExecution
from tools import HTTPGetTool, HTTPPostTool, HTTPPutTool, HTTPDeleteTool, StateUpdateTool
from cerebras_llm import CerebrasLLM

logger = structlog.get_logger(__name__)


class LlamaAgent:
    """
     Llama Agent class that orchestrates the agent workflow.
    Focuses on core functionality without extensive logging, metrics, or complex error handling.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.api_endpoints = config.api_endpoints if config.api_endpoints else []
        self.logger = logger.bind(agent_id=config.agent_id)

        self.model_name = "llama3.1-8b"

        # Initialize MCP tools
        self.tools = self._initialize_tools()

        # Initialize Cerebras LLM
        api_key = os.getenv("CEREBRAS_API_KEY", "dummy-key")
        cerebras_llm = CerebrasLLM(
            api_key=api_key,
            base_url=config.cerebras_proxy_url,
            model_name=self.model_name,
            max_tokens=1000,
            temperature=0.7
        )

        # Initialize agent worker with Cerebras LLM
        self.agent_worker = StatefulAgentWorker(
            tools=self.tools,
            llm=cerebras_llm,
            config=config,
            verbose=True
        )
        
        # Update tool references to the agent worker
        self._update_tool_references()

        self.logger.info("Llama Agent initialized successfully")

    def _create_system_prompt(self) -> str:
        """
        Create a simplified system prompt.
        """
        api_name = os.getenv('TARGET_API_NAME', 'sut_api')
        return f"""You are an AI agent that performs tasks by making API calls through tools.
You MUST call tools for every API interaction.
Your response MUST contain tool calls, not explanations.

Available Endpoints: {self.api_endpoints if self.api_endpoints else 'Not specified.'}

TOOL CALL FORMAT:
- Always include api_name parameter: "{api_name}"
- Always include path parameter with the endpoint
- Include data parameter for POST/PUT requests
- Include headers parameter if you have session data

START IMMEDIATELY WITH A TOOL CALL - DO NOT EXPLAIN WHAT YOU WILL DO!"""

    def _initialize_tools(self) -> list[BaseTool]:
        """Initialize MCP tools for HTTP operations and state management."""
        return [
            HTTPGetTool(mcp_gateway_url=self.config.mcp_gateway_url),
            HTTPPostTool(mcp_gateway_url=self.config.mcp_gateway_url),
            HTTPPutTool(mcp_gateway_url=self.config.mcp_gateway_url),
            HTTPDeleteTool(mcp_gateway_url=self.config.mcp_gateway_url),
            StateUpdateTool()
        ]
    
    def _update_tool_references(self):
        """Update tool references to the agent worker after initialization."""
        for tool in self.tools:
            if hasattr(tool, 'agent_worker'):
                tool.agent_worker = self.agent_worker

    async def start_session(self, goal: str, session_id: Optional[str] = None) -> str:
        """
        Start a new agent session with a specific goal.
        """
        session_id = self.agent_worker.create_session(goal, session_id)
        self.logger.info("Started new agent session", session_id=session_id, goal=goal)
        return session_id

    async def execute_goal(self, session_id: str, initial_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the agent goal for a specific session.
        Simplified to a single execution attempt, with manual LLM response parsing for tool calls.
        """
        session_context = self.agent_worker.get_session(session_id)
        if not session_context:
            raise ValueError(f"Session {session_id} not found.")

        self.agent_worker.__dict__['_current_session_id'] = session_id

        system_prompt = self._create_system_prompt()
        user_prompt = initial_prompt if initial_prompt else f"GOAL: {session_context.goal}"

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]

        self.logger.info("Executing agent task", session_id=session_id, goal=session_context.goal)

        try:
            # Directly call the LLM to get a response
            llm_response = await asyncio.wait_for(
                self.agent_worker.llm.achat(messages),
                timeout=self.config.inference_timeout * 3
            )
            
            response_content = llm_response.message.content if llm_response and llm_response.message else ""
            self.logger.info("Received LLM response", session_id=session_id, response_content=response_content)

            # Attempt to parse the LLM response for tool calls
            # Updated regex to handle markdown code blocks (```bash ... ```)
            tool_call_pattern = r'```(?:bash)?\s*((http_(?:get|post|delete|put))\((.*?)\))\s*```|((http_(?:get|post|delete|put))\((.*?)\))'
            match = re.search(tool_call_pattern, response_content, re.DOTALL) # re.DOTALL to match across newlines

            tool_executed = False
            tool_result = None
            if match:
                # Determine which group matched
                if match.group(1): # Markdown block matched
                    full_tool_call_str = match.group(1)
                    tool_name = match.group(2)
                    tool_args_str = match.group(3)
                elif match.group(4): # Direct call matched
                    full_tool_call_str = match.group(4)
                    tool_name = match.group(5)
                    tool_args_str = match.group(6)
                else:
                    self.logger.warning("Tool call pattern matched but groups are empty. Skipping tool execution.", session_id=session_id, response_content=response_content)
                    tool_name = None
                    tool_args_str = None
                
                if tool_name and tool_args_str:
                    self.logger.info("Identified potential tool call", session_id=session_id, tool_name=tool_name, tool_args_str=tool_args_str)

                    # Basic parsing of tool arguments (can be improved)
                    tool_args = {}
                    try:
                        # Attempt to parse as JSON if it looks like a dict
                        # This is a simplified approach and might fail for complex JSON
                        if '{' in tool_args_str and '}' in tool_args_str:
                            # Replace single quotes with double quotes for valid JSON
                            tool_args = json.loads(tool_args_str.replace("'", "\""))
                        else:
                            # Simple key=value parsing
                            for arg in tool_args_str.split(','):
                                if '=' in arg:
                                    key, value = arg.split('=', 1)
                                    tool_args[key.strip()] = value.strip().strip("'\"")
                    except json.JSONDecodeError:
                        self.logger.warning("Failed to parse tool arguments as JSON, falling back to simple parsing.", session_id=session_id, tool_args_str=tool_args_str)
                    except Exception as arg_parse_error:
                        self.logger.error("Error parsing tool arguments", session_id=session_id, error=str(arg_parse_error))

                    # Find and execute the tool
                    tool_found = False
                    for tool in self.tools:
                        self.logger.debug(f"Checking tool: {tool.metadata.name} against identified: {tool_name}", session_id=session_id)
                        if tool.metadata.name == tool_name:
                            tool_found = True
                            self.logger.info("Executing tool", session_id=session_id, tool_name=tool_name, tool_args=tool_args)
                            try:
                                # Pass session_id to tools if they support it
                                if 'session_id' not in tool_args:
                                    tool_args['session_id'] = session_id
                                
                                # Log the actual tool call parameters
                                self.logger.info("Tool call parameters", session_id=session_id, tool_name=tool_name, resolved_tool_args=tool_args)

                                tool_result = await asyncio.to_thread(tool.call, **tool_args) # Tools are sync, run in thread
                                tool_executed = True
                                self.logger.info("Tool execution successful", session_id=session_id, tool_name=tool_name, tool_result=tool_result)
                            except Exception as tool_exec_error:
                                self.logger.error("Tool execution failed", session_id=session_id, tool_name=tool_name, error=str(tool_exec_error))
                                tool_result = {"error": str(tool_exec_error)}
                            break
                    
                    if not tool_found:
                        self.logger.warning(f"Tool '{tool_name}' not found in available tools.", session_id=session_id, available_tools=[t.metadata.name for t in self.tools])            
            final_response_content = tool_result if tool_executed else response_content

            # Update session context with execution history
            session_context.add_execution(
                ToolExecution(
                    tool_name="llm_call" if not tool_executed else tool_name,
                    parameters={"prompt": user_prompt, "llm_response": response_content},
                    response={"content": str(final_response_content)},
                    execution_time=0.0, # Placeholder
                    success=True if tool_executed else False # Mark as success if tool was executed
                )
            )

            self.logger.info("Goal execution completed", session_id=session_id, response=str(final_response_content))

            return {
                "session_id": session_id,
                "response": str(final_response_content),
                "steps_completed": session_context.current_step,
                "session_data": session_context.session_data,
                "success": True, # This needs to be re-evaluated based on tool_executed and tool_result
                "trace_id": session_context.trace_id
            }
        except Exception as e:
            self.logger.error("Goal execution failed", session_id=session_id, error=str(e))
            return {
                "session_id": session_id,
                "response": f"Execution failed: {str(e)}",
                "steps_completed": session_context.current_step,
                "session_data": session_context.session_data,
                "success": False,
                "error": str(e),
                "trace_id": session_context.trace_id
            }

    async def health_check(self) -> Dict[str, Any]:
        """Perform a minimal health check of the agent."""
        self.logger.info("Performing minimal health check")
        llm_healthy = False
        try:
            # Attempt a simple LLM completion to check connectivity
            test_response = await self.agent_worker.llm.acomplete("Hello")
            llm_healthy = bool(test_response and test_response.text)
        except Exception as e:
            self.logger.error("LLM health check failed", error=str(e))
        
        return {
            "agent_id": self.config.agent_id,
            "llm_healthy": llm_healthy,
            "status": "healthy" if llm_healthy else "unhealthy",
            "message": "Minimal health check performed."
        }

    def cleanup_sessions(self):
        """Clean up expired sessions (minimal implementation)."""
        self.logger.info("Performing minimal session cleanup")
        # In MVP, we might just log or call a simplified cleanup on agent_worker
        if hasattr(self.agent_worker, 'cleanup_expired_sessions'):
            self.agent_worker.cleanup_expired_sessions()
        else:
            self.logger.warning("agent_worker does not have cleanup_expired_sessions method.")
