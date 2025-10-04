"""
Main entry point for the Llama Agent service.
"""
import os
import asyncio
import signal
import sys
from typing import Optional
import structlog
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
import threading
import json

from llama_agent import LlamaAgent
from models import AgentConfig
from metrics import initialize_metrics, get_metrics_collector, AgentMetricsCollector


# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global agent instance for API access
_global_agent_instance = None

def get_agent_instance():
    """Get the global agent instance."""
    return _global_agent_instance

class AgentService:
    """Main service class for the Llama Agent."""
    
    def __init__(self):
        self.agent: Optional[LlamaAgent] = None
        self.running = False
        self.config = self._load_config()
        self.metrics_collector: Optional[AgentMetricsCollector] = None
        self.metrics_app: Optional[FastAPI] = None
        self.metrics_server = None

    def _load_api_endpoints(self) -> Optional[list[str]]:
        """Load API endpoints from ape.config.json."""
        config_path = os.path.join(os.path.dirname(__file__), "ape.config.json")
        if not os.path.exists(config_path):
            logger.warning(f"ape.config.json not found at {config_path}. Using default endpoints.") 
            return None
        
        try:
            with open(config_path, 'r') as f:
                ape_config = json.load(f)
            
            # Prioritize endpointDetails if available (from parsed API spec)
            if "apiSpec" in ape_config and "parsed" in ape_config["apiSpec"] and "endpoints" in ape_config["apiSpec"]["parsed"]:
                endpoints = [ep["path"] for ep in ape_config["apiSpec"]["parsed"]["endpoints"]]
                logger.info(f"Loaded {len(endpoints)} endpoints from apiSpec.parsed.endpoints in ape.config.json")
                return endpoints
            elif "target" in ape_config and "endpoints" in ape_config["target"]:
                endpoints = ape_config["target"]["endpoints"]
                logger.info(f"Loaded {len(endpoints)} endpoints from target.endpoints in ape.config.json")
                return endpoints
            else:
                logger.warning("No endpoints found in ape.config.json under apiSpec.parsed.endpoints or target.endpoints.")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding ape.config.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading API endpoints from ape.config.json: {e}")
            return None

    def _load_config(self) -> AgentConfig:
        """Load configuration from environment variables."""
        config = AgentConfig(
            agent_id=os.getenv("AGENT_ID", f"agent-{os.getpid()}"),
            mcp_gateway_url=os.getenv("MCP_GATEWAY_URL", "http://mcp_gateway:3000"),
            cerebras_proxy_url=os.getenv("CEREBRAS_PROXY_URL", "http://cerebras_proxy:8000"),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            inference_timeout=float(os.getenv("INFERENCE_TIMEOUT", "10.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            api_endpoints=self._load_api_endpoints()
        )
        return config
    
    async def start(self):
        """Start the agent service."""
        logger.info("Starting Llama Agent service", config=self.config.dict())
        
        try:
            # Initialize metrics
            self.metrics_collector = initialize_metrics(self.config.agent_id)
            
            # Metrics server is handled by startup.py
            
            # Initialize the agent
            self.agent = LlamaAgent(self.config)
            global _global_agent_instance
            _global_agent_instance = self.agent
            self.running = True
            
            # Perform health check
            health = await self.agent.health_check()
            logger.info("Agent health check", **health)
            
            if health["status"] != "healthy":
                logger.error("Agent failed health check, but continuing...")
            
            # Start the main service loop
            await self._service_loop()
            
        except Exception as e:
            logger.error("Failed to start agent service", error=str(e))
            sys.exit(1)
    
    async def _service_loop(self):
        """Main service loop with AI-driven load testing."""
        logger.info("Agent service started successfully")
        logger.info("Starting AI-driven load testing mode")
        
        # AI-driven load testing scenarios
        realistic_scenarios = [
            "Complete user registration and profile setup flow",
            "Perform e-commerce product search and purchase journey", 
            "Test user authentication and session management",
            "Validate API data operations and CRUD workflows",
            "Simulate mobile app user interaction patterns",
            "Test error handling and recovery scenarios",
            "Validate API rate limiting and performance under load",
            "Simulate concurrent user sessions and data conflicts",
            "Test API security and authorization boundaries",
            "Validate real-time features and WebSocket connections"
        ]
        
        session_counter = 0
        
        try:
            while self.running:
                # AI-driven session creation and execution
                if self.agent:
                    try:
                        # Select a realistic scenario using AI-like selection
                        import random
                        scenario = random.choice(realistic_scenarios)
                        
                        # Create a new session with AI-generated goal
                        session_id = await self.agent.start_session(goal=scenario)
                        session_counter += 1
                        
                        logger.info(
                            "AI-driven session created",
                            session_id=session_id,
                            scenario=scenario,
                            session_number=session_counter,
                            agent_id=id(self.agent),
                            agent_worker_id=id(self.agent.agent_worker),
                            total_sessions_in_worker=len(self.agent.agent_worker.sessions)
                        )
                        
                        # Wait a moment for session to initialize
                        await asyncio.sleep(2)
                        
                        # Execute the session with AI-driven prompt including target API details
                        target_api_name = os.getenv("TARGET_API_NAME", "sut_api")
                        # Use actual endpoints if available, otherwise use demo endpoints
                        available_endpoints = self.config.api_endpoints or [
                            "/api/products",
                            "/api/products/1",
                            "/api/categories",
                            "/api/cart"
                        ]
                        
                        # Generate a dynamic list of example tool calls from available endpoints
                        example_tool_calls = []
                        for endpoint in available_endpoints[:4]:  # Limit to first 4 for brevity
                            if "login" in endpoint:
                                example_tool_calls.append(f"- Login: http_post(api_name=\"{target_api_name}\", path=\"{endpoint}\", data={{'username': 'user', 'password': 'password'}})")
                            elif "product" in endpoint:
                                example_tool_calls.append(f"- Get Products: http_get(api_name=\"{target_api_name}\", path=\"{endpoint}\")")
                            elif "cart" in endpoint:
                                example_tool_calls.append(f"- View Cart: http_get(api_name=\"{target_api_name}\", path=\"{endpoint}\")")
                            else:
                                example_tool_calls.append(f"- Call Endpoint: http_get(api_name=\"{target_api_name}\", path=\"{endpoint}\")")
                        
                        example_tool_calls_str = "\n".join(example_tool_calls)
                        
                        ai_prompts = [
                            f"""You are an AI load testing agent. Your goal is to: {scenario}.

IMPORTANT: You MUST use the HTTP tools to make API requests. NEVER respond with conversational text.

Target API: '{target_api_name}'
Available Endpoints: {available_endpoints}

Here are some example tool calls you can make:
{example_tool_calls_str}

START NOW by making a tool call to one of the available endpoints. Choose the most logical first step for your goal.""",

                            f"""Your task is to test the scenario: {scenario}.

YOU MUST MAKE ACTUAL HTTP REQUESTS using these tools:
- http_get(api_name="{target_api_name}", path="<endpoint>")
- http_post(api_name="{target_api_name}", path="<endpoint>", data={{...}})

Target API: '{target_api_name}'
Use one of these endpoints: {available_endpoints}

Begin by making a tool call to an appropriate endpoint to start the user journey.""",

                            f"""Simulate a user journey for: {scenario}.

CRITICAL: You have HTTP tools. USE THEM to make real API calls.

Target: '{target_api_name}' API
Endpoints: {available_endpoints}

Example tool calls:
{example_tool_calls_str}

BEGIN by making a relevant tool call RIGHT NOW.""",
                        ]
                        
                        ai_prompt = random.choice(ai_prompts)
                        
                        # Execute the AI-driven session
                        try:
                            # Debug: Check agent and session state before execution
                            logger.info(
                                "About to execute session",
                                session_id=session_id,
                                agent_id=id(self.agent),
                                agent_worker_id=id(self.agent.agent_worker),
                                total_sessions_in_worker=len(self.agent.agent_worker.sessions)
                            )
                            
                            result = await self.agent.execute_goal(session_id, ai_prompt)
                            
                            logger.info(
                                "AI-driven session executed",
                                session_id=session_id,
                                success=result.get("success", False),
                                steps_completed=result.get("steps_completed", 0)
                            )
                            
                        except Exception as exec_error:
                            logger.error(
                                "AI-driven session execution failed",
                                session_id=session_id,
                                error=str(exec_error),
                                agent_id=id(self.agent),
                                agent_worker_id=id(self.agent.agent_worker),
                                total_sessions_in_worker=len(self.agent.agent_worker.sessions) if self.agent and hasattr(self.agent.agent_worker, 'sessions') else 0
                            )
                    
                    except Exception as session_error:
                        logger.error(
                            "AI-driven session creation failed", 
                            error=str(session_error)
                        )
                    
                    # Note: Removed cleanup_sessions() call here as it was interfering with active sessions
                    # Cleanup will happen during shutdown instead
                
                # AI-driven timing - vary intervals to simulate realistic load patterns
                base_interval = 30  # Base 30 seconds between sessions
                variation = random.uniform(0.5, 2.0)  # 50% to 200% variation
                sleep_time = base_interval * variation
                
                logger.info(
                    "AI load testing cycle complete",
                    next_session_in_seconds=int(sleep_time),
                    total_sessions_created=session_counter
                )
                
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            logger.info("AI-driven load testing cancelled")
        except Exception as e:
            logger.error("AI-driven load testing error", error=str(e))
    
    async def stop(self):
        """Stop the agent service."""
        logger.info("Stopping Llama Agent service")
        self.running = False
        
        if self.agent:
            # Cleanup all sessions
            self.agent.cleanup_sessions()
        
        # Cleanup metrics
        if self.metrics_collector:
            self.metrics_collector.cleanup()
        
        # Stop metrics server
        if self.metrics_server:
            self.metrics_server.should_exit = True
        
        logger.info("Agent service stopped")
    
    async def _start_metrics_server(self):
        """Start the metrics HTTP server."""
        self.metrics_app = FastAPI(title="Agent Metrics", version="1.0.0")
        
        @self.metrics_app.get("/metrics")
        async def get_metrics():
            """Prometheus metrics endpoint."""
            collector = get_metrics_collector()
            if collector:
                metrics_data = collector.get_prometheus_metrics()
                return PlainTextResponse(content=metrics_data, media_type="text/plain")
            else:
                return PlainTextResponse(content="# No metrics available\n", media_type="text/plain")
        
        @self.metrics_app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "agent_id": self.config.agent_id}
        
        # Start the metrics server in a separate thread
        metrics_port = int(os.getenv("METRICS_PORT", "8000"))
        
        def run_metrics_server():
            uvicorn.run(
                self.metrics_app,
                host="0.0.0.0",
                port=metrics_port,
                log_level="warning"  # Reduce log noise
            )
        
        metrics_thread = threading.Thread(target=run_metrics_server, daemon=True)
        metrics_thread.start()
        
        logger.info(f"Metrics server started on port {metrics_port}")
    
    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal", signal=signum)
        asyncio.create_task(self.stop())


async def main():
    """Main function."""
    service = AgentService()
    
    # Setup signal handlers for graceful shutdown
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, service.handle_signal)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await service.stop()


if __name__ == "__main__":
    # Use uvloop for better performance if available
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    asyncio.run(main())