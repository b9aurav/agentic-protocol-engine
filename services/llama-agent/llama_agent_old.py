"""
Main Llama Agent implementation with LlamaIndex integration.
"""
import os
from typing import Optional, Dict, Any
import structlog
import asyncio

from llama_index.core.agent import AgentRunner
from llama_index.core.tools import BaseTool

from agent_worker import StatefulAgentWorker
from models import AgentConfig
from tools import HTTPGetTool, HTTPPostTool, HTTPPutTool, HTTPDeleteTool, StateUpdateTool
from metrics import initialize_metrics


logger = structlog.get_logger(__name__)


class LlamaAgent:
    """
    Main Llama Agent class that orchestrates the agent workflow.
    Integrates LlamaIndex CustomSimpleAgentWorker with MCP tools and session management.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.api_endpoints = config.api_endpoints if config.api_endpoints else []
        # Ensure logger is properly initialized
        if logger is None:
            import structlog
            self.logger = structlog.get_logger(__name__).bind(agent_id=config.agent_id)
        else:
            self.logger = logger.bind(agent_id=config.agent_id)
        
        # Initialize metrics collector with enhanced session tracking
        self.metrics_collector = initialize_metrics(config.agent_id)
        
        self.model_name = "llama3.1-8b"
        
        # Initialize MCP tools
        self.tools = self._initialize_tools()
        
        # Create Cerebras LLM wrapper for proper LlamaIndex integration
        from cerebras_llm import CerebrasLLM
        
        # Debug LLM configuration
        api_key = os.getenv("CEREBRAS_API_KEY", "dummy-key")
        self.logger.info(
            "Initializing Cerebras LLM",
            api_key_length=len(api_key),
            api_key_preview=api_key[:10] + "..." if len(api_key) > 10 else api_key,
            base_url=config.cerebras_proxy_url,
            model_name=self.model_name
        )
        
        cerebras_llm = CerebrasLLM(
            api_key=api_key,
            base_url=config.cerebras_proxy_url,
            model_name=self.model_name,
            max_tokens=1000,
            temperature=0.7
        )
        
        # Test LLM connectivity immediately
        try:
            self.logger.info("Testing LLM connectivity with simple prompt")
            test_response = cerebras_llm.complete("Hello, respond with 'test successful'")
            self.logger.info(
                "LLM connectivity test result",
                success=bool(test_response and test_response.text),
                response_text=test_response.text if test_response else "No response"
            )
        except Exception as test_error:
            self.logger.error(
                "LLM connectivity test failed",
                error=str(test_error),
                error_type=type(test_error).__name__
            )
        
        # Initialize agent worker with Cerebras LLM
        self.agent_worker = StatefulAgentWorker(
            tools=self.tools,
            llm=cerebras_llm,
            config=config,
            verbose=True
        )
        
        self.logger.info("Llama Agent initialized successfully")
    
    def _create_enhanced_system_prompt(self) -> str:
        """
        Create an enhanced system prompt that forces tool usage for API interactions.
        
        Returns:
            String containing the enhanced system prompt
        """
        # Get the configured API name from environment or use default
        import os
        api_name = os.getenv('TARGET_API_NAME', 'sut_api')
        
        api_name = os.getenv('TARGET_API_NAME', 'sut_api')
        
        endpoint_examples = []
        if self.api_endpoints:
            for endpoint in self.api_endpoints:
                if "login" in endpoint:
                    endpoint_examples.append(f"- To login: http_post(api_name=\"{api_name}\", path=\"{endpoint}\", data={{\"username\": \"user\", \"password\": \"pass\"}})")
                elif "product" in endpoint and "{" not in endpoint: # Generic product list
                    endpoint_examples.append(f"- To browse products: http_get(api_name=\"{api_name}\", path=\"{endpoint}\")")
                elif "product" in endpoint and "{" in endpoint: # Specific product
                    endpoint_examples.append(f"- To view product details: http_get(api_name=\"{api_name}\", path=\"{endpoint.replace('{id}', '1')}\")")
                elif "category" in endpoint:
                    endpoint_examples.append(f"- To view categories: http_get(api_name=\"{api_name}\", path=\"{endpoint}\")")
                elif "cart" in endpoint and "{" not in endpoint: # Add to cart
                    endpoint_examples.append(f"- To add to cart: http_post(api_name=\"{api_name}\", path=\"{endpoint}\", data={{\"productId\": \"1\", \"quantity\": 1}})")
                elif "cart" in endpoint and "{" in endpoint: # View cart
                    endpoint_examples.append(f"- To view cart: http_get(api_name=\"{api_name}\", path=\"{endpoint}\")")
                else:
                    endpoint_examples.append(f"- To access {endpoint.replace('/', '')}: http_get(api_name=\"{api_name}\", path=\"{endpoint}\")")
        
        endpoint_examples_str = "\n   ".join(endpoint_examples) if endpoint_examples else "   - No specific endpoint examples available. Use http_get/post/put/delete with appropriate paths."

        return f"""You are an AI agent that performs load testing by making actual API calls through tools.

ABSOLUTE REQUIREMENTS - FAILURE TO FOLLOW WILL RESULT IN SYSTEM FAILURE:

1. TOOL CALLS ARE MANDATORY - NO EXCEPTIONS
   - You MUST call tools for every API interaction
   - NEVER respond with text like "I'll browse the products" or "Let me check the API"
   - IMMEDIATELY call the appropriate tool: http_get, http_post, http_put, or http_delete
   - Your response MUST contain tool calls, not explanations

2. BANNED RESPONSES - NEVER SAY THESE:
   - "I'll help you..."
   - "Let me check..."
   - "I can browse..."
   - "I will make a request..."
   - Any conversational response without a tool call

3. REQUIRED BEHAVIOR FOR TARGET API ('{api_name}'):
   - Available Endpoints: {self.api_endpoints if self.api_endpoints else 'Not specified, use your best judgment.'}
   {endpoint_examples_str}

4. TOOL CALL FORMAT:
   - Always include api_name parameter: "{api_name}"
   - Always include path parameter with the endpoint
   - Include data parameter for POST/PUT requests
   - Include headers parameter if you have session data

5. SESSION STATE MANAGEMENT:
   - Cart operations require session state (cookies)
   - Use saved session data in headers for subsequent requests
   - Call state_update to save session cookies after successful cart operations

6. ERROR RECOVERY:
   - 401/403 errors: Session expired, start fresh with GET requests
   - 404 errors: Try alternative endpoints with http_get
   - 5xx errors: Retry the same tool call
   - Validation errors: Modify data and retry

YOU ARE A TOOL-CALLING AGENT, NOT A CONVERSATIONAL AGENT. EVERY RESPONSE MUST CONTAIN TOOL CALLS."""

    
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
        Start a new agent session with a specific goal and enhanced tracking.
        
        Args:
            goal: The user journey goal (e.g., "complete purchase flow")
            session_id: Optional session ID
            
        Returns:
            The session ID for the created session
        """
        # Update tool references if not already done
        self._update_tool_references()
        
        session_id = self.agent_worker.create_session(goal, session_id)
        session_context = self.agent_worker.get_session(session_id)
        
        # Debug: Verify session was created
        print(f"DEBUG: Session created - ID: {session_id}, Found: {session_context is not None}, Total sessions: {len(self.agent_worker.sessions)}")
        self.logger.info(
            "Session creation debug",
            session_id=session_id,
            session_found=session_context is not None,
            agent_worker_id=id(self.agent_worker),
            total_sessions=len(self.agent_worker.sessions)
        )
        
        # Start enhanced session tracking
        if session_context:
            self.metrics_collector.start_session(session_id, goal, session_context)
        
        self.logger.info(
            "Started new agent session with enhanced tracking",
            session_id=session_id,
            goal=goal,
            trace_id=session_context.trace_id if session_context else None
        )
        
        return session_id
    
    async def execute_goal(self, session_id: str, initial_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the agent goal for a specific session with comprehensive error handling.
        
        Args:
            session_id: The session ID to execute
            initial_prompt: Optional initial prompt to start the conversation
            
        Returns:
            Dictionary containing execution results and session info
        """
        # Validate inputs
        if not isinstance(session_id, str) or len(session_id) != 36:
            raise ValueError(f"Invalid session_id format: {session_id}")
        if initial_prompt and not isinstance(initial_prompt, str):
            raise TypeError(f"initial_prompt must be str, got {type(initial_prompt)}")
            
        # Debug: Check available sessions
        available_sessions = list(self.agent_worker.sessions.keys())
        print(f"DEBUG: Execute goal - Session ID: {session_id}, Available: {available_sessions}, Worker ID: {id(self.agent_worker)}")
        self.logger.info(
            "Execute goal debug",
            session_id=session_id,
            available_sessions=available_sessions,
            agent_worker_id=id(self.agent_worker)
        )
        
        # Get session with proper error handling
        session_context = self.agent_worker.get_session(session_id)
        if not session_context:
            raise ValueError(f"Session {session_id} not found. Available sessions: {available_sessions}")
            
        # Validate session context structure
        required_attrs = ['session_id', 'trace_id', 'goal', 'session_data',
                         'execution_history', 'current_step', 'start_time',
                         'last_action_time']
        if not all(hasattr(session_context, attr) for attr in required_attrs):
            raise ValueError(f"Invalid session context structure for session {session_id}")
            
        # Ensure execution_history is a list
        if not isinstance(session_context.execution_history, list):
            session_context.execution_history = []
        if not session_context:
            raise ValueError(f"Session {session_id} not found. Available sessions: {available_sessions}")
        
        self.logger.info(
            "Starting goal execution",
            session_id=session_id,
            goal=session_context.goal
        )
        
        # Initialize execution loop variables
        max_execution_attempts = self.config.max_retries
        execution_attempt = 0
        last_error = None
        
        while execution_attempt < max_execution_attempts:
            try:
                execution_attempt += 1
                
                # Create enhanced prompt with explicit tool usage instructions
                if initial_prompt is None or execution_attempt > 1:
                    prompt_parts = [
                        f"GOAL: {session_context.goal}",
                        "",
                        "MANDATORY INSTRUCTIONS:",
                        "- You MUST use HTTP tools for ALL API interactions",
                        "- DO NOT generate conversational responses",
                        "- IMMEDIATELY call the appropriate tool for your goal",
                        "- If your goal involves browsing/viewing data, call http_get",
                        "- If your goal involves submitting/creating data, call http_post", 
                        "- If your goal involves updating data, call http_put",
                        "- If your goal involves deleting data, call http_delete",
                        "",
                        f"Session ID: {session_id}",
                        f"Trace ID: {session_context.trace_id}",
                        f"Current Step: {session_context.current_step}",
                        ""
                    ]
                    
                    # Add session context if available
                    if session_context.session_data:
                        prompt_parts.extend([
                            "Current Session Data:",
                            f"- Available session tokens/cookies: {list(session_context.session_data.keys())}",
                            ""
                        ])
                    
                    # Add execution history context
                    if session_context.execution_history:
                        prompt_parts.extend([
                            "Previous Actions Taken:",
                            *[f"- Step {i+1}: {exec.tool_name} ({'SUCCESS' if exec.success else 'FAILED'})" 
                              for i, exec in enumerate(session_context.execution_history[-5:])],  # Last 5 actions
                            ""
                        ])
                    
                    # Add error recovery context if this is a retry
                    if execution_attempt > 1 and last_error:
                        prompt_parts.extend([
                            f"RECOVERY MODE - Attempt {execution_attempt}/{max_execution_attempts}:",
                            f"Previous attempt failed with error: {last_error}",
                            "You MUST use tools to recover from this error:",
                            "- For 401/403 errors: Call http_post to re-authenticate",
                            "- For 5xx errors: Retry the same tool call",
                            "- For 404 errors: Try alternative endpoints with http_get",
                            "- For validation errors: Modify data and retry with http_post",
                            ""
                        ])
                    
                    # Add explicit tool usage examples with correct API name
                    import os
                    api_name = os.getenv('TARGET_API_NAME', 'sut_api')
                    
                    prompt_parts.extend([
                        "TOOL USAGE EXAMPLES FOR DEMO API:",
                        f"- To browse products: http_get(api_name='{api_name}', path='/api/products')",
                        f"- To view product details: http_get(api_name='{api_name}', path='/api/products/1')",
                        f"- To view categories: http_get(api_name='{api_name}', path='/api/categories')",
                        f"- To add to cart: http_post(api_name='{api_name}', path='/api/cart', data={{'productId': '1', 'quantity': 1}})",
                        f"- To view cart: http_get(api_name='{api_name}', path='/api/cart')",
                        "",
                        "START IMMEDIATELY WITH A TOOL CALL - DO NOT EXPLAIN WHAT YOU WILL DO!"
                    ])
                    
                    execution_prompt = "\n".join(prompt_parts)
                else:
                    execution_prompt = initial_prompt
                
                # Store current session ID in agent worker for access during execution
                self.agent_worker.__dict__['_current_session_id'] = session_id
                
                self.logger.info(
                    "Executing agent task",
                    session_id=session_id,
                    attempt=execution_attempt,
                    max_attempts=max_execution_attempts
                )
                
                # Store session_id in agent worker for access during execution
                self.agent_worker.__dict__['_current_session_id'] = session_id
                
                # Use the LLM directly to get a response and then process it
                from llama_index.core.base.llms.types import ChatMessage, MessageRole

                system_prompt = self._create_enhanced_system_prompt()
                
                # Create chat messages
                messages = [
                    ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                    ChatMessage(role=MessageRole.USER, content=execution_prompt)
                ]

                # Debug tool availability
                available_tools = [tool.metadata.name for tool in self.tools]
                agent_worker_tools = [tool.metadata.name for tool in self.agent_worker.tools] if hasattr(self.agent_worker, 'tools') else []
                
                self.logger.info(
                    "Sending messages to LLM",
                    session_id=session_id,
                    system_prompt_length=len(system_prompt),
                    user_prompt_length=len(execution_prompt),
                    available_tools=available_tools,
                    agent_worker_tools=agent_worker_tools,
                    tools_count=len(self.tools)
                )

                # Get response from LLM
                response = await asyncio.wait_for(
                    self.agent_worker.llm.achat(messages),
                    timeout=self.config.inference_timeout * 3
                )
                
                self.logger.info(
                    "Received response from LLM",
                    session_id=session_id,
                    response_type=type(response).__name__,
                    response_length=len(str(response)) if response else 0,
                    response_str=str(response)[:500] + "..." if len(str(response)) > 500 else str(response)
                )
                
                # Process response and extract session state
                await self._process_execution_response(session_id, response)
                
                # Get updated session context
                updated_context = self.agent_worker.get_session(session_id)
                
                # Log the exact prompt being sent (truncated)
                self.logger.info(
                    "System prompt preview",
                    system_prompt_preview=system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt
                )
                
                self.logger.info(
                    "User prompt preview",
                    user_prompt_preview=execution_prompt[:500] + "..." if len(execution_prompt) > 500 else execution_prompt
                )
                
                # Execute the task using the agent runner (sync version)
                loop = asyncio.get_event_loop()
                
                self.logger.info("About to call agent_runner.chat", session_id=session_id)
                
                try:
                    # Prefer structured messages to ensure the agent receives system + user context
                    import asyncio as _asyncio
                    response = await _asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            lambda: agent_runner.chat(messages)  # Pass ChatMessage list to preserve roles
                        ),
                        timeout=self.config.inference_timeout * 3
                    )
                    
                    self.logger.info(
                        "Received response from AgentRunner",
                        session_id=session_id,
                        response_type=type(response).__name__,
                        response_length=len(str(response)) if response else 0,
                        response_str=str(response)[:500] + "..." if len(str(response)) > 500 else str(response)
                    )
                    
                    # Check if response has expected attributes
                    if hasattr(response, 'response'):
                        self.logger.info(
                            "Response has 'response' attribute",
                            response_response=str(response.response)[:300]
                        )
                    if hasattr(response, 'source_nodes'):
                        self.logger.info(
                            "Response has source_nodes",
                            source_nodes_count=len(response.source_nodes) if response.source_nodes else 0
                        )
                        # Log source node details to see tool calls
                        if response.source_nodes:
                            for i, node in enumerate(response.source_nodes[:3]):  # First 3 nodes
                                self.logger.info(
                                    f"Source node {i}",
                                    node_type=type(node).__name__,
                                    node_content=str(node)[:200] if hasattr(node, '__str__') else "No string representation"
                                )
                    if hasattr(response, 'sources'):
                        self.logger.info(
                            "Response has sources",
                            sources_count=len(response.sources) if response.sources else 0
                        )
                        # Log source details to see tool calls
                        if response.sources:
                            for i, source in enumerate(response.sources[:3]):  # First 3 sources
                                self.logger.info(
                                    f"Source {i}",
                                    source_type=type(source).__name__,
                                    source_content=str(source)[:200] if hasattr(source, '__str__') else "No string representation"
                                )
                    
                    # Check for tool call related attributes
                    response_attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                    self.logger.info(
                        "Response attributes",
                        all_attributes=response_attrs[:10]  # First 10 attributes
                    )
                    
                    # Try to extract tool calls or function calls
                    if hasattr(response, 'tool_calls'):
                        self.logger.info(
                            "Response has tool_calls",
                            tool_calls=str(response.tool_calls)
                        )
                    
                    # Check for LlamaIndex agent response patterns
                    response_text = str(response)
                    if "http_get" in response_text or "http_post" in response_text:
                        self.logger.info(
                            "Response contains HTTP tool references",
                            contains_tools=True
                        )
                    else:
                        self.logger.warning(
                            "Response does NOT contain HTTP tool references",
                            contains_tools=False,
                            response_preview=response_text[:300]
                        )
                        
                except Exception as llm_error:
                    import traceback
                    error_str = str(llm_error)
                    # Gracefully handle LlamaIndex finalize_response type enforcement on max steps
                    if (
                        isinstance(llm_error, Exception)
                        and "AGENT_CHAT_RESPONSE_TYPE" in error_str
                        and "Maximum steps reached" in error_str
                    ):
                        self.logger.warning(
                            "AgentRunner.chat hit max-steps finalize constraint; synthesizing response",
                            session_id=session_id,
                            error=error_str
                        )
                        # Synthesize a simple textual response so downstream logic can proceed
                        response = "assistant: Maximum steps reached"
                    else:
                        self.logger.error(
                            "AgentRunner.chat failed",
                            session_id=session_id,
                            error=error_str,
                            error_type=type(llm_error).__name__,
                            traceback=traceback.format_exc()
                        )
                        raise
                
                # Process response and extract session state
                await self._process_execution_response(session_id, response)
                
                # Get updated session context
                updated_context = self.agent_worker.get_session(session_id)
                
                # Determine if execution was successful
                success_indicators = self._evaluate_execution_success(updated_context)
                
                result = {
                    "session_id": session_id,
                    "response": str(response),
                    "steps_completed": updated_context.current_step if updated_context else 0,
                    "execution_history": [
                        exec.dict() for exec in updated_context.execution_history
                    ] if updated_context else [],
                    "session_data": updated_context.session_data if updated_context else {},
                    "success": success_indicators["overall_success"],
                    "success_metrics": success_indicators,
                    "execution_attempts": execution_attempt,
                    "trace_id": session_context.trace_id
                }
                
                # Record session completion in metrics
                self.metrics_collector.end_session(
                    session_id=session_id,
                    goal_type=updated_context.goal if updated_context else "unknown",
                    success=result["success"],
                    failure_reason=None,
                    session_context=updated_context
                )
                
                self.logger.info(
                    "Goal execution completed successfully",
                    session_id=session_id,
                    steps_completed=result["steps_completed"],
                    attempts=execution_attempt,
                    success=result["success"]
                )
                
                return result
                
            except asyncio.TimeoutError:
                last_error = f"Execution timeout after {self.config.inference_timeout * 3}s"
                self.logger.warning(
                    "Goal execution timeout",
                    session_id=session_id,
                    attempt=execution_attempt,
                    timeout=self.config.inference_timeout * 3
                )
                
                if execution_attempt >= max_execution_attempts:
                    break
                    
                # Wait before retry with exponential backoff
                await asyncio.sleep(min(2 ** execution_attempt, 10))
                
            except Exception as e:
                last_error = str(e)
                error_type = type(e).__name__
                
                self.logger.error(
                    "Goal execution error",
                    session_id=session_id,
                    attempt=execution_attempt,
                    error=str(e),
                    error_type=error_type
                )
                
                # Determine if error is recoverable
                if self._is_recoverable_error(e):
                    if execution_attempt >= max_execution_attempts:
                        break
                    
                    # Apply error-specific recovery strategies
                    await self._apply_error_recovery_strategy(session_id, e)
                    
                    # Wait before retry with exponential backoff
                    await asyncio.sleep(min(2 ** execution_attempt, 10))
                else:
                    # Non-recoverable error, fail immediately
                    break
        
        # All attempts failed
        updated_context = self.agent_worker.get_session(session_id)
        
        # Record session failure in metrics
        self.metrics_collector.end_session(
            session_id=session_id,
            goal_type=updated_context.goal if updated_context else "unknown",
            success=False,
            failure_reason=last_error,
            session_context=updated_context
        )
        
        self.logger.error(
            "Goal execution failed after all attempts",
            session_id=session_id,
            attempts=execution_attempt,
            final_error=last_error
        )
        
        return {
            "session_id": session_id,
            "response": f"Execution failed after {execution_attempt} attempts: {last_error}",
            "steps_completed": updated_context.current_step if updated_context else 0,
            "execution_history": [
                exec.dict() for exec in updated_context.execution_history
            ] if updated_context else [],
            "session_data": updated_context.session_data if updated_context else {},
            "success": False,
            "error": last_error,
            "error_type": "execution_failure",
            "execution_attempts": execution_attempt,
            "trace_id": session_context.trace_id
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
    
    async def _process_execution_response(self, session_id: str, response: Any) -> None:
        """
        Process execution response and extract session state information.
        
        Args:
            session_id: Session ID to update
            response: Agent execution response
        """
        session_context = self.agent_worker.get_session(session_id)
        if not session_context:
            return
        
        # Extract session data from recent tool executions
        recent_executions = session_context.execution_history[-5:]  # Last 5 executions
        
        for execution in recent_executions:
            # Be defensive: response may not be a dict
            if execution.success and isinstance(execution.response, dict) and "session_data" in execution.response:
                session_data_from_response = execution.response.get("session_data")
                if session_data_from_response:
                    # Update session context with extracted data
                    self.agent_worker.update_session_data(session_id, session_data_from_response)
                    
                    self.logger.info(
                        "Extracted session data from execution",
                        session_id=session_id,
                        extracted_keys=list(session_data_from_response.keys())
                    )
    
    def _evaluate_execution_success(self, session_context: Optional[Any]) -> Dict[str, Any]:
        """
        Evaluate the success of the execution based on multiple criteria.
        
        Args:
            session_context: Updated session context
            
        Returns:
            Dictionary with success metrics and indicators
        """
        if not session_context:
            return {
                "overall_success": False,
                "reason": "No session context available",
                "successful_steps": 0,
                "failed_steps": 0,
                "success_rate": 0.0,
                "has_session_data": False,
                "completed_goal": False
            }
        
        # Calculate success metrics from execution history
        successful_steps = sum(1 for exec in session_context.execution_history if exec.success)
        failed_steps = sum(1 for exec in session_context.execution_history if not exec.success)
        total_steps = len(session_context.execution_history)
        
        success_rate = successful_steps / total_steps if total_steps > 0 else 0.0
        
        # Check for session data indicating successful authentication/state management
        has_session_data = bool(session_context.session_data)
        
        # Determine if goal appears to be completed based on execution patterns
        completed_goal = self._assess_goal_completion(session_context)
        
        # Overall success criteria:
        # - At least 70% success rate on tool executions
        # - Has session data (indicates successful authentication/state management)
        # - Made meaningful progress (at least 2 successful steps)
        overall_success = (
            success_rate >= 0.7 and
            successful_steps >= 2 and
            not session_context.has_reached_max_steps()
        )
        
        return {
            "overall_success": overall_success,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "total_steps": total_steps,
            "success_rate": success_rate,
            "has_session_data": has_session_data,
            "completed_goal": completed_goal,
            "reached_max_steps": session_context.has_reached_max_steps(),
            "session_duration": (
                session_context.last_action_time - session_context.start_time
            ).total_seconds()
        }
    
    def _assess_goal_completion(self, session_context: Any) -> bool:
        """
        Assess if the goal appears to be completed based on execution patterns.
        
        Args:
            session_context: Session context to analyze
            
        Returns:
            Boolean indicating if goal appears completed
        """
        if not session_context.execution_history:
            return False
        
        # Look for patterns indicating successful completion
        recent_executions = session_context.execution_history[-3:]  # Last 3 executions
        
        # Check for successful sequence of operations
        recent_success_count = sum(1 for exec in recent_executions if exec.success)
        
        # Check for specific success indicators in responses
        success_indicators = [
            "success", "completed", "confirmed", "approved", 
            "created", "updated", "logged in", "authenticated"
        ]
        
        has_success_indicators = False
        for execution in recent_executions:
            if execution.success and execution.response:
                response_text = str(execution.response).lower()
                if any(indicator in response_text for indicator in success_indicators):
                    has_success_indicators = True
                    break
        
        # Goal is likely completed if:
        # - Recent executions are mostly successful
        # - Response contains success indicators
        # - Has made reasonable progress (at least 3 steps)
        return (
            recent_success_count >= 2 and
            has_success_indicators and
            len(session_context.execution_history) >= 3
        )
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """
        Determine if an error is recoverable and should trigger retry logic.
        
        Args:
            error: Exception that occurred
            
        Returns:
            Boolean indicating if error is recoverable
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Recoverable errors
        recoverable_patterns = [
            "timeout", "connection", "network", "503", "502", "500",
            "rate limit", "throttle", "temporary", "unavailable"
        ]
        
        # Non-recoverable errors
        non_recoverable_patterns = [
            "authentication", "unauthorized", "forbidden", "404", "400",
            "invalid", "malformed", "schema", "validation"
        ]
        
        # Check for non-recoverable patterns first
        if any(pattern in error_str for pattern in non_recoverable_patterns):
            return False
        
        # Check for recoverable patterns
        if any(pattern in error_str for pattern in recoverable_patterns):
            return True
        
        # Default recovery behavior based on error type
        recoverable_types = [
            "TimeoutError", "ConnectionError", "HTTPError", 
            "RequestException", "NetworkError"
        ]
        
        return error_type in recoverable_types
    
    async def _apply_error_recovery_strategy(self, session_id: str, error: Exception) -> None:
        """
        Apply error-specific recovery strategies.
        
        Args:
            session_id: Session ID to apply recovery for
            error: Exception that occurred
        """
        error_str = str(error).lower()
        session_context = self.agent_worker.get_session(session_id)
        
        if not session_context:
            return
        
        self.logger.info(
            "Applying error recovery strategy",
            session_id=session_id,
            error_type=type(error).__name__,
            error_message=str(error)
        )
        
        # Strategy 1: Authentication errors - clear session data to force re-auth
        if any(pattern in error_str for pattern in ["401", "403", "unauthorized", "forbidden"]):
            # Clear authentication-related session data
            auth_keys = [key for key in session_context.session_data.keys() 
                        if any(auth_term in key.lower() for auth_term in 
                              ["token", "auth", "session", "cookie"])]
            
            for key in auth_keys:
                session_context.session_data.pop(key, None)
            
            self.logger.info(
                "Cleared authentication data for recovery",
                session_id=session_id,
                cleared_keys=auth_keys
            )
        
        # Strategy 2: Rate limiting - add delay and reduce request frequency
        elif any(pattern in error_str for pattern in ["rate limit", "throttle", "429"]):
            # Add a longer delay for rate limiting
            await asyncio.sleep(5)
            
            self.logger.info(
                "Applied rate limiting recovery delay",
                session_id=session_id,
                delay_seconds=5
            )
        
        # Strategy 3: Server errors - reset connection state
        elif any(pattern in error_str for pattern in ["500", "502", "503", "504"]):
            # For server errors, we might want to reset some connection state
            # This is handled by the retry mechanism with exponential backoff
            
            self.logger.info(
                "Server error detected, will retry with backoff",
                session_id=session_id
            )
        
        # Strategy 4: Network/connection errors - clear any cached connection state
        elif any(pattern in error_str for pattern in ["connection", "network", "timeout"]):
            # Network errors might benefit from clearing cached state
            
            self.logger.info(
                "Network error detected, will retry with fresh connection",
                session_id=session_id
            )
    
    def get_session_success_metrics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get comprehensive session success metrics.
        
        Args:
            time_window_minutes: Time window to consider for metrics
            
        Returns:
            Dictionary with session success metrics including Successful Stateful Sessions percentage
        """
        return self.metrics_collector.get_session_success_metrics(time_window_minutes)
    
    def get_successful_stateful_sessions_percentage(self, time_window_minutes: int = 60) -> float:
        """
        Get the Successful Stateful Sessions percentage (primary APE metric).
        
        Args:
            time_window_minutes: Time window to consider
            
        Returns:
            Percentage of successful stateful sessions (0.0 to 100.0)
        """
        return self.metrics_collector.get_successful_stateful_sessions_percentage(time_window_minutes)
    
    def get_performance_metrics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get comprehensive performance validation metrics.
        
        Args:
            time_window_minutes: Time window to analyze
            
        Returns:
            Dictionary with performance metrics including MTBA and latency validation
        """
        return self.metrics_collector.get_performance_metrics(time_window_minutes)
    
    def validate_performance_targets(self) -> Dict[str, Any]:
        """
        Validate current performance against APE targets.
        
        Returns:
            Dictionary with validation results for MTBA and cognitive latency
        """
        return self.metrics_collector.validate_performance_targets()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the agent with session metrics."""
        # Test LLM connectivity with a simple completion
        try:
            test_response = await self.agent_worker.llm.acomplete("Hello")
            llm_healthy = bool(test_response and test_response.text)
            if llm_healthy:
                self.logger.info("LLM health check succeeded")
            else:
                self.logger.error("LLM health check failed - no response")
        except Exception as e:
            self.logger.error("LLM health check failed", error=str(e))
            llm_healthy = False
        
        active_sessions = len(self.agent_worker.sessions)
        
        # Get recent session success metrics
        session_metrics = self.get_session_success_metrics(15)  # Last 15 minutes
        
        # Get performance validation metrics
        performance_metrics = self.get_performance_metrics(15)  # Last 15 minutes
        performance_validation = self.validate_performance_targets()
        
        return {
            "agent_id": self.config.agent_id,
            "llm_healthy": llm_healthy,
            "active_sessions": active_sessions,
            "tools_count": len(self.tools),
            "status": "healthy" if llm_healthy else "unhealthy",
            "session_metrics": session_metrics,
            "performance_metrics": performance_metrics,
            "performance_validation": performance_validation,
            "successful_stateful_sessions_percentage": session_metrics.get("successful_stateful_sessions_percentage", 0.0),
            "mtba_target_met": performance_validation.get("mtba_validation", {}).get("target_met", False),
            "cognitive_latency_target_met": performance_validation.get("cognitive_latency_validation", {}).get("target_met", False)
        }