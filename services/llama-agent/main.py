"""
Main entry point for the Llama Agent service.
"""
import os
import asyncio
import signal
import sys
from typing import Dict, Any
import structlog
from dotenv import load_dotenv

from llama_agent import LlamaAgent
from models import AgentConfig


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


class AgentService:
    """Main service class for the Llama Agent."""
    
    def __init__(self):
        self.agent: Optional[LlamaAgent] = None
        self.running = False
        self.config = self._load_config()
    
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
            # Initialize the agent
            self.agent = LlamaAgent(self.config)
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
        """Main service loop."""
        logger.info("Agent service started successfully")
        
        # For now, just keep the service running
        # In a full implementation, this would handle incoming requests
        # via HTTP API, message queue, or other communication mechanism
        
        try:
            while self.running:
                # Cleanup expired sessions periodically
                if self.agent:
                    self.agent.cleanup_sessions()
                
                # Wait before next cleanup cycle
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            logger.info("Service loop cancelled")
        except Exception as e:
            logger.error("Service loop error", error=str(e))
    
    async def stop(self):
        """Stop the agent service."""
        logger.info("Stopping Llama Agent service")
        self.running = False
        
        if self.agent:
            # Cleanup all sessions
            self.agent.cleanup_sessions()
        
        logger.info("Agent service stopped")
    
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