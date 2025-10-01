"""
Prometheus metrics collection for Llama Agent.
Implements Requirements 4.4, 6.2 for agent performance monitoring.
"""

import time
from contextlib import contextmanager
from typing import Dict, Optional
from threading import Lock

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST


# Prometheus metrics for agent performance
agent_sessions_total = Counter(
    'ape_agent_sessions_total',
    'Total number of agent sessions started',
    ['agent_id', 'goal_type']
)

agent_sessions_successful = Counter(
    'ape_successful_sessions_total',
    'Total number of successful stateful sessions',
    ['agent_id', 'goal_type']
)

agent_sessions_failed = Counter(
    'ape_agent_sessions_failed_total',
    'Total number of failed agent sessions',
    ['agent_id', 'goal_type', 'failure_reason']
)

agent_requests_total = Counter(
    'ape_agent_requests_total',
    'Total number of HTTP requests made by agents',
    ['agent_id', 'method', 'status_code']
)

agent_errors_total = Counter(
    'ape_agent_errors_total',
    'Total number of agent errors',
    ['agent_id', 'error_type']
)

agent_mtba_seconds = Histogram(
    'ape_agent_mtba_seconds',
    'Mean Time Between Actions in seconds',
    ['agent_id'],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
)

agent_session_duration = Histogram(
    'ape_agent_session_duration_seconds',
    'Agent session duration in seconds',
    ['agent_id', 'goal_type', 'outcome'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1200, 3600]
)

agent_tool_calls_total = Counter(
    'ape_agent_tool_calls_total',
    'Total number of tool calls made by agents',
    ['agent_id', 'tool_name', 'success']
)

agent_inference_requests = Counter(
    'ape_inference_requests_total',
    'Total number of inference requests',
    ['agent_id', 'model']
)

agent_inference_ttft = Histogram(
    'ape_inference_ttft_seconds',
    'Time to First Token for inference requests',
    ['agent_id', 'model'],
    buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
)

concurrent_agents_count = Gauge(
    'ape_concurrent_agents_count',
    'Number of currently active agents'
)

agent_context_size = Histogram(
    'ape_agent_context_size_bytes',
    'Size of agent session context in bytes',
    ['agent_id'],
    buckets=[100, 500, 1000, 2000, 5000, 10000, 20000, 50000]
)

agent_info = Info(
    'ape_agent_info',
    'Information about the agent instance'
)


class AgentMetricsCollector:
    """
    Metrics collector for Llama Agent performance tracking.
    Implements Requirements 7.5, 8.1, 8.3 for session success tracking and validation.
    """
    
    def __init__(self, agent_id: str):
        """
        Initialize metrics collector for an agent.
        
        Args:
            agent_id: Unique identifier for this agent instance
        """
        self.agent_id = agent_id
        self._lock = Lock()
        self._active_sessions = {}  # session_id -> start_time
        self._last_action_time = {}  # session_id -> last_action_timestamp
        
        # Set agent information
        agent_info.info({
            'agent_id': agent_id,
            'version': '1.0.0',
            'start_time': str(int(time.time()))
        })
        
        # Increment concurrent agents count
        concurrent_agents_count.inc()
    
    def start_session(self, session_id: str, goal_type: str = "unknown"):
        """
        Record the start of a new agent session.
        
        Args:
            session_id: Unique session identifier
            goal_type: Type of goal for this session
        """
        with self._lock:
            self._active_sessions[session_id] = time.time()
            self._last_action_time[session_id] = time.time()
        
        agent_sessions_total.labels(
            agent_id=self.agent_id,
            goal_type=goal_type
        ).inc()
    
    def end_session(self, session_id: str, goal_type: str = "unknown", 
                   success: bool = False, failure_reason: Optional[str] = None):
        """
        Record the end of an agent session.
        
        Args:
            session_id: Session identifier
            goal_type: Type of goal for this session
            success: Whether the session completed successfully
            failure_reason: Reason for failure if not successful
        """
        with self._lock:
            start_time = self._active_sessions.pop(session_id, time.time())
            self._last_action_time.pop(session_id, None)
        
        duration = time.time() - start_time
        outcome = "success" if success else "failure"
        
        # Record session duration
        agent_session_duration.labels(
            agent_id=self.agent_id,
            goal_type=goal_type,
            outcome=outcome
        ).observe(duration)
        
        # Record success or failure
        if success:
            agent_sessions_successful.labels(
                agent_id=self.agent_id,
                goal_type=goal_type
            ).inc()
        else:
            agent_sessions_failed.labels(
                agent_id=self.agent_id,
                goal_type=goal_type,
                failure_reason=failure_reason or "unknown"
            ).inc()
    
    def record_http_request(self, method: str, status_code: int):
        """
        Record an HTTP request made by the agent.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP response status code
        """
        # Categorize status codes
        if 200 <= status_code < 300:
            status_category = "2xx"
        elif 400 <= status_code < 500:
            status_category = "4xx"
        elif 500 <= status_code < 600:
            status_category = "5xx"
        else:
            status_category = "other"
        
        agent_requests_total.labels(
            agent_id=self.agent_id,
            method=method,
            status_code=status_category
        ).inc()
    
    def record_tool_call(self, tool_name: str, success: bool, session_id: Optional[str] = None):
        """
        Record a tool call made by the agent.
        
        Args:
            tool_name: Name of the tool called
            success: Whether the tool call was successful
            session_id: Session ID for MTBA calculation
        """
        agent_tool_calls_total.labels(
            agent_id=self.agent_id,
            tool_name=tool_name,
            success=str(success).lower()
        ).inc()
        
        # Calculate and record MTBA (Mean Time Between Actions)
        if session_id:
            with self._lock:
                current_time = time.time()
                last_time = self._last_action_time.get(session_id)
                
                if last_time:
                    mtba = current_time - last_time
                    agent_mtba_seconds.labels(agent_id=self.agent_id).observe(mtba)
                
                self._last_action_time[session_id] = current_time
    
    def record_inference_request(self, model: str, ttft: float):
        """
        Record an inference request and its Time-to-First-Token.
        
        Args:
            model: Model name used for inference
            ttft: Time to First Token in seconds
        """
        agent_inference_requests.labels(
            agent_id=self.agent_id,
            model=model
        ).inc()
        
        agent_inference_ttft.labels(
            agent_id=self.agent_id,
            model=model
        ).observe(ttft)
    
    def record_error(self, error_type: str):
        """
        Record an error occurrence.
        
        Args:
            error_type: Type/category of the error
        """
        agent_errors_total.labels(
            agent_id=self.agent_id,
            error_type=error_type
        ).inc()
    
    def record_context_size(self, size_bytes: int):
        """
        Record the size of the agent's session context.
        
        Args:
            size_bytes: Size of context in bytes
        """
        agent_context_size.labels(agent_id=self.agent_id).observe(size_bytes)
    
    def cleanup(self):
        """Clean up metrics when agent shuts down."""
        concurrent_agents_count.dec()
    
    @staticmethod
    def get_prometheus_metrics() -> str:
        """
        Get Prometheus-formatted metrics.
        
        Returns:
            str: Prometheus metrics in text format
        """
        return generate_latest().decode('utf-8')


# Global metrics collector instance
_metrics_collector: Optional[AgentMetricsCollector] = None


def initialize_metrics(agent_id: str) -> AgentMetricsCollector:
    """
    Initialize the global metrics collector.
    
    Args:
        agent_id: Unique identifier for this agent
        
    Returns:
        AgentMetricsCollector: The initialized metrics collector
    """
    global _metrics_collector
    _metrics_collector = AgentMetricsCollector(agent_id)
    return _metrics_collector


def get_metrics_collector() -> Optional[AgentMetricsCollector]:
    """
    Get the current metrics collector instance.
    
    Returns:
        Optional[AgentMetricsCollector]: The metrics collector or None if not initialized
    """
    return _metrics_collector


@contextmanager
def track_session_metrics(session_id: str, goal_type: str = "unknown"):
    """
    Context manager to track session metrics.
    
    Args:
        session_id: Session identifier
        goal_type: Type of goal for this session
        
    Usage:
        with track_session_metrics('session-123', 'purchase_flow'):
            # Execute session logic
            pass
    """
    collector = get_metrics_collector()
    if not collector:
        yield
        return
    
    collector.start_session(session_id, goal_type)
    success = False
    failure_reason = None
    
    try:
        yield
        success = True
    except Exception as e:
        failure_reason = type(e).__name__
        raise
    finally:
        collector.end_session(session_id, goal_type, success, failure_reason)