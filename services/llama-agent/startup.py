#!/usr/bin/env python3
"""
Optimized startup script for Llama Agent
Implements fast startup and graceful shutdown for Requirements 6.1, 6.4
"""

import os
import sys
import signal
import asyncio
import logging
import time
from typing import Optional
import psutil
import httpx

# Configure logging for startup optimization
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('agent-startup')

class OptimizedAgentStartup:
    def __init__(self):
        self.startup_timeout = int(os.getenv('AGENT_STARTUP_TIMEOUT', '30'))
        self.graceful_shutdown_timeout = int(os.getenv('AGENT_GRACEFUL_SHUTDOWN_TIMEOUT', '10'))
        self.startup_delay = int(os.getenv('AGENT_STARTUP_DELAY', '0'))
        self.memory_limit_mb = int(os.getenv('MEMORY_LIMIT_MB', '512'))
        self.cpu_limit = float(os.getenv('CPU_LIMIT', '0.5'))
        self.agent_process: Optional[asyncio.subprocess.Process] = None
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self._graceful_shutdown())
        
    async def _graceful_shutdown(self):
        """Perform graceful shutdown of agent process"""
        self.shutdown_event.set()
        
        if self.agent_process:
            logger.info("Terminating agent process...")
            try:
                self.agent_process.terminate()
                await asyncio.wait_for(
                    self.agent_process.wait(), 
                    timeout=self.graceful_shutdown_timeout
                )
                logger.info("Agent process terminated gracefully")
            except asyncio.TimeoutError:
                logger.warning("Graceful shutdown timeout, forcing kill...")
                self.agent_process.kill()
                await self.agent_process.wait()
                logger.info("Agent process killed")
        
        # Cleanup resources
        await self._cleanup_resources()
        
    async def _cleanup_resources(self):
        """Clean up resources before shutdown"""
        try:
            # Close any open connections, files, etc.
            logger.info("Cleaning up resources...")
            
            # Force garbage collection to free memory
            import gc
            gc.collect()
            
            logger.info("Resource cleanup completed")
        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")
    
    async def _wait_for_dependencies(self):
        """Wait for required services to be available"""
        mcp_gateway_url = os.getenv('MCP_GATEWAY_URL', 'http://mcp_gateway:3000')
        max_retries = 30
        retry_delay = 2
        
        logger.info(f"Waiting for MCP Gateway at {mcp_gateway_url}...")
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(f"{mcp_gateway_url}/health")
                    if response.status_code == 200:
                        logger.info("MCP Gateway is ready")
                        return True
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"MCP Gateway not ready (attempt {attempt + 1}/{max_retries}): {e}")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"MCP Gateway not available after {max_retries} attempts")
                        return False
        
        return False
    
    def _optimize_process_resources(self):
        """Optimize process resources based on limits"""
        try:
            process = psutil.Process()
            
            # Set memory limit if supported
            if hasattr(process, 'memory_limit'):
                memory_limit_bytes = self.memory_limit_mb * 1024 * 1024
                process.memory_limit = memory_limit_bytes
                logger.info(f"Set memory limit to {self.memory_limit_mb}MB")
            
            # Set CPU affinity for better resource distribution
            cpu_count = psutil.cpu_count()
            if cpu_count and self.cpu_limit < 1.0:
                # Limit to specific CPU cores based on CPU limit
                max_cores = max(1, int(cpu_count * self.cpu_limit))
                available_cores = list(range(max_cores))
                process.cpu_affinity(available_cores)
                logger.info(f"Set CPU affinity to {max_cores} cores: {available_cores}")
            
            # Set process priority for better scheduling
            if hasattr(process, 'nice'):
                process.nice(5)  # Lower priority for better system responsiveness
                
        except Exception as e:
            logger.warning(f"Could not optimize process resources: {e}")
    
    async def _start_health_server(self):
        """Start health check server for container orchestration"""
        from aiohttp import web
        import json
        
        async def health_check(request):
            """Health check endpoint"""
            health_status = {
                'status': 'healthy',
                'timestamp': time.time(),
                'agent_id': os.getenv('AGENT_ID', 'unknown'),
                'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
                'cpu_percent': psutil.Process().cpu_percent()
            }
            return web.json_response(health_status)
        
        async def metrics(request):
            """Metrics endpoint for Prometheus"""
            process = psutil.Process()
            metrics_data = {
                'agent_memory_usage_bytes': process.memory_info().rss,
                'agent_cpu_usage_percent': process.cpu_percent(),
                'agent_startup_time': time.time(),
                'agent_status': 'running'
            }
            
            # Convert to Prometheus format
            prometheus_metrics = []
            for key, value in metrics_data.items():
                prometheus_metrics.append(f"{key} {value}")
            
            return web.Response(text='\n'.join(prometheus_metrics), content_type='text/plain')
        
        app = web.Application()
        app.router.add_get('/health', health_check)
        app.router.add_get('/metrics', metrics)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        metrics_port = int(os.getenv('METRICS_PORT', '8000'))
        site = web.TCPSite(runner, '0.0.0.0', metrics_port)
        await site.start()
        
        logger.info(f"Health server started on port {metrics_port}")
        return runner
    
    async def start_agent(self):
        """Start the agent with optimized startup"""
        try:
            # Apply startup delay for staggered deployment
            if self.startup_delay > 0:
                logger.info(f"Applying startup delay: {self.startup_delay}s")
                await asyncio.sleep(self.startup_delay)
            
            # Optimize process resources
            self._optimize_process_resources()
            
            # Start health server
            health_runner = await self._start_health_server()
            
            # Wait for dependencies
            if not await self._wait_for_dependencies():
                logger.error("Required dependencies not available, exiting...")
                return 1
            
            # Start the main agent process
            logger.info("Starting main agent process...")
            
            # Import and start the actual agent
            from main import main as agent_main
            
            # Run agent in a separate task
            agent_task = asyncio.create_task(agent_main())
            
            # Wait for shutdown signal or agent completion
            done, pending = await asyncio.wait(
                [agent_task, asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup health server
            await health_runner.cleanup()
            
            logger.info("Agent startup completed")
            return 0
            
        except Exception as e:
            logger.error(f"Error during agent startup: {e}")
            return 1

async def main():
    """Main startup function"""
    startup = OptimizedAgentStartup()
    exit_code = await startup.start_agent()
    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(main())