"""
Main entry point for the Llama Agent service.
"""
import os
import asyncio
import signal
import sys
from typing import Dict, Any, Optional
import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
import uvicorn
import threading

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
    
    def _load_config(self) -> AgentConfig:
        """Load configuration from environment variables."""
        return AgentConfig(
            agent_id=os.getenv("AGENT_ID", f"agent-{os.getpid()}"),
            mcp_gateway_url=os.getenv("MCP_GATEWAY_URL", "http://mcp-gateway:8080"),
            cerebras_proxy_url=os.getenv("CEREBRAS_PROXY_URL", "http://cerebras-proxy:8000"),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            inference_timeout=float(os.getenv("INFERENCE_TIMEOUT", "10.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )
    
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
                        target_api_name = "test-api"
                        available_endpoints = ["/admin/login", "/admin/dashboard/metrics", "/admin/users", "/admin/products"]
                        
                        ai_prompts = [
                            f"""You are simulating a real user performing: {scenario}. 

IMPORTANT: You MUST use the HTTP tools to make actual API requests. Here's the EXACT syntax:

1. Use http_post tool for login: http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})
2. Use http_get tool for data retrieval: http_get(api_name="{target_api_name}", path="/admin/dashboard/metrics")
3. Use http_get tool for listing: http_get(api_name="{target_api_name}", path="/admin/users")
4. Use http_post tool for creating: http_post(api_name="{target_api_name}", path="/admin/products", data={{"name": "test product"}})

Target API: '{target_api_name}'
Available endpoints: {available_endpoints}

START NOW by calling: http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})""",

                            f"""Begin testing the scenario: {scenario}. 

YOU MUST MAKE ACTUAL HTTP REQUESTS using these tools with CORRECT parameters:
- http_get(api_name="{target_api_name}", path="endpoint") - for GET requests
- http_post(api_name="{target_api_name}", path="endpoint", data={{...}}) - for POST requests  
- http_put(api_name="{target_api_name}", path="endpoint", data={{...}}) - for PUT requests
- http_delete(api_name="{target_api_name}", path="endpoint") - for DELETE requests

Target API: '{target_api_name}'
Test these endpoints: {available_endpoints}

STEP 1: Call http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})
STEP 2: Call http_get(api_name="{target_api_name}", path="/admin/dashboard/metrics")
STEP 3: Call http_get(api_name="{target_api_name}", path="/admin/users")

Execute these steps NOW.""",

                            f"""Simulate a user journey for: {scenario}. 

CRITICAL: You have HTTP tools available - USE THEM to make real API calls with EXACT syntax:

Example usage:
- Login: http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})
- Get metrics: http_get(api_name="{target_api_name}", path="/admin/dashboard/metrics") 
- List users: http_get(api_name="{target_api_name}", path="/admin/users")
- Create product: http_post(api_name="{target_api_name}", path="/admin/products", data={{"name": "Test Product", "price": 99.99}})

Target: '{target_api_name}' API
Endpoints: {available_endpoints}

BEGIN by making this call RIGHT NOW: http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})""",

                            f"""Execute realistic testing for: {scenario}. 

YOU HAVE HTTP TOOLS - USE THEM! Make actual API requests with CORRECT syntax:

1. FIRST: http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})
2. THEN: http_get(api_name="{target_api_name}", path="/admin/dashboard/metrics")
3. NEXT: http_get(api_name="{target_api_name}", path="/admin/users") 
4. FINALLY: http_get(api_name="{target_api_name}", path="/admin/products")

Target API: '{target_api_name}'
Available endpoints: {available_endpoints}

DO NOT just describe what you would do - ACTUALLY CALL THE TOOLS NOW!""",

                            f"""Perform intelligent load testing for: {scenario}. 

MANDATORY: Use the HTTP tools to make real requests. Available tools with CORRECT syntax:
- http_get(api_name="{target_api_name}", path="endpoint") 
- http_post(api_name="{target_api_name}", path="endpoint", data={{...}})
- http_put(api_name="{target_api_name}", path="endpoint", data={{...}})
- http_delete(api_name="{target_api_name}", path="endpoint")

API: '{target_api_name}'
Endpoints: {available_endpoints}

EXECUTE THIS SEQUENCE:
1. http_post(api_name="{target_api_name}", path="/admin/login", data={{"username": "admin", "password": "admin123"}})
2. http_get(api_name="{target_api_name}", path="/admin/dashboard/metrics")
3. http_get(api_name="{target_api_name}", path="/admin/users")
4. http_get(api_name="{target_api_name}", path="/admin/products")

START MAKING THESE HTTP CALLS IMMEDIATELY."""
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
                                total_sessions_in_worker=len(self.agent.agent_worker.sessions)
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