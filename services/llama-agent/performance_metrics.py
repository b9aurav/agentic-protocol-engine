"""
Performance Validation Metrics Module for Llama Agent.
Implements Requirements 2.2, 8.1, 8.3 for performance validation with MTBA and latency metrics.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
import statistics
import structlog

from prometheus_client import Histogram, Counter, Gauge, Summary


logger = structlog.get_logger(__name__)


# Prometheus metrics for performance validation
mtba_seconds = Histogram(
    'ape_mtba_seconds_detailed',
    'Mean Time Between Actions with detailed buckets',
    ['agent_id', 'session_id'],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0, 10.0]
)

end_to_end_latency = Histogram(
    'ape_end_to_end_latency_seconds',
    'End-to-end latency from agent decision to SUT response',
    ['agent_id', 'operation_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
)

cognitive_latency_ttft = Histogram(
    'ape_cognitive_latency_ttft_seconds',
    'Time-to-First-Token for inference requests',
    ['agent_id', 'model'],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
)

cognitive_latency_violations = Counter(
    'ape_cognitive_latency_violations_total',
    'Count of cognitive latency threshold violations',
    ['agent_id', 'violation_type', 'threshold_seconds']
)

performance_validation_summary = Summary(
    'ape_performance_validation_seconds',
    'Summary of performance validation metrics',
    ['agent_id', 'metric_type']
)

agent_throughput_ops_per_second = Gauge(
    'ape_agent_throughput_ops_per_second',
    'Agent throughput in operations per second',
    ['agent_id', 'time_window_seconds']
)

latency_percentiles = Gauge(
    'ape_latency_percentiles_seconds',
    'Latency percentiles for different operations',
    ['agent_id', 'operation_type', 'percentile']
)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a specific time window."""
    agent_id: str
    time_window_start: datetime
    time_window_end: datetime
    
    # MTBA metrics
    mean_time_between_actions: float
    mtba_p50: float
    mtba_p95: float
    mtba_p99: float
    mtba_violations: int
    
    # End-to-end latency metrics
    mean_e2e_latency: float
    e2e_latency_p50: float
    e2e_latency_p95: float
    e2e_latency_p99: float
    
    # Cognitive latency metrics
    mean_ttft: float
    ttft_p50: float
    ttft_p95: float
    ttft_p99: float
    ttft_violations: int
    
    # Throughput metrics
    operations_per_second: float
    total_operations: int
    
    # Validation results
    mtba_target_met: bool
    cognitive_latency_target_met: bool
    overall_performance_valid: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "agent_id": self.agent_id,
            "time_window_start": self.time_window_start.isoformat(),
            "time_window_end": self.time_window_end.isoformat(),
            "mean_time_between_actions": self.mean_time_between_actions,
            "mtba_p50": self.mtba_p50,
            "mtba_p95": self.mtba_p95,
            "mtba_p99": self.mtba_p99,
            "mtba_violations": self.mtba_violations,
            "mean_e2e_latency": self.mean_e2e_latency,
            "e2e_latency_p50": self.e2e_latency_p50,
            "e2e_latency_p95": self.e2e_latency_p95,
            "e2e_latency_p99": self.e2e_latency_p99,
            "mean_ttft": self.mean_ttft,
            "ttft_p50": self.ttft_p50,
            "ttft_p95": self.ttft_p95,
            "ttft_p99": self.ttft_p99,
            "ttft_violations": self.ttft_violations,
            "operations_per_second": self.operations_per_second,
            "total_operations": self.total_operations,
            "mtba_target_met": self.mtba_target_met,
            "cognitive_latency_target_met": self.cognitive_latency_target_met,
            "overall_performance_valid": self.overall_performance_valid
        }


@dataclass
class OperationTiming:
    """Timing information for a single operation."""
    operation_id: str
    session_id: str
    operation_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Detailed timing breakdown
    inference_start: Optional[datetime] = None
    inference_ttft: Optional[datetime] = None
    inference_end: Optional[datetime] = None
    mcp_request_start: Optional[datetime] = None
    mcp_request_end: Optional[datetime] = None
    sut_response_received: Optional[datetime] = None
    
    # Calculated metrics
    total_latency: Optional[float] = None
    inference_latency: Optional[float] = None
    ttft_latency: Optional[float] = None
    mcp_latency: Optional[float] = None
    sut_latency: Optional[float] = None
    
    def calculate_metrics(self):
        """Calculate all timing metrics."""
        if self.end_time:
            self.total_latency = (self.end_time - self.start_time).total_seconds()
        
        if self.inference_start and self.inference_end:
            self.inference_latency = (self.inference_end - self.inference_start).total_seconds()
        
        if self.inference_start and self.inference_ttft:
            self.ttft_latency = (self.inference_ttft - self.inference_start).total_seconds()
        
        if self.mcp_request_start and self.mcp_request_end:
            self.mcp_latency = (self.mcp_request_end - self.mcp_request_start).total_seconds()
        
        if self.mcp_request_end and self.sut_response_received:
            self.sut_latency = (self.sut_response_received - self.mcp_request_end).total_seconds()


class PerformanceValidator:
    """
    Performance validation and metrics collection for Llama Agent.
    
    This class implements comprehensive performance tracking including:
    - MTBA (Mean Time Between Actions) calculation and validation
    - End-to-end latency measurement across agent → MCP → SUT
    - Cognitive latency validation (TTFT < target thresholds)
    """
    
    def __init__(self, agent_id: str):
        """
        Initialize performance validator.
        
        Args:
            agent_id: Unique identifier for the agent
        """
        self.agent_id = agent_id
        self.logger = logger.bind(agent_id=agent_id, component="performance_validator")
        
        # Performance thresholds (Requirements 2.2, 8.1)
        self.mtba_threshold = 1.0  # Target: MTBA < 1 second
        self.ttft_threshold = 2.0  # Target: TTFT < 2 seconds for cognitive latency
        self.e2e_latency_threshold = 10.0  # Target: E2E latency < 10 seconds
        
        # Timing data storage
        self.session_timings: Dict[str, List[datetime]] = {}  # session_id -> action timestamps
        self.operation_timings: Dict[str, OperationTiming] = {}  # operation_id -> timing data
        self.recent_operations = deque(maxlen=1000)  # Recent operations for analysis
        
        # Performance history
        self.mtba_history = deque(maxlen=100)  # Recent MTBA measurements
        self.ttft_history = deque(maxlen=100)  # Recent TTFT measurements
        self.e2e_latency_history = deque(maxlen=100)  # Recent E2E latency measurements
        
        self.logger.info(
            "Performance validator initialized",
            mtba_threshold=self.mtba_threshold,
            ttft_threshold=self.ttft_threshold,
            e2e_latency_threshold=self.e2e_latency_threshold
        )
    
    def start_operation(self, operation_id: str, session_id: str, 
                       operation_type: str = "generic") -> OperationTiming:
        """
        Start tracking a new operation.
        
        Args:
            operation_id: Unique identifier for this operation
            session_id: Session ID this operation belongs to
            operation_type: Type of operation (e.g., "http_get", "inference", "form_submit")
            
        Returns:
            OperationTiming object for this operation
        """
        timing = OperationTiming(
            operation_id=operation_id,
            session_id=session_id,
            operation_type=operation_type,
            start_time=datetime.utcnow()
        )
        
        self.operation_timings[operation_id] = timing
        
        # Track session-level action timing for MTBA calculation
        if session_id not in self.session_timings:
            self.session_timings[session_id] = []
        self.session_timings[session_id].append(timing.start_time)
        
        self.logger.debug(
            "Started operation tracking",
            operation_id=operation_id,
            session_id=session_id,
            operation_type=operation_type
        )
        
        return timing
    
    def record_inference_start(self, operation_id: str) -> None:
        """Record the start of inference for an operation."""
        if operation_id in self.operation_timings:
            self.operation_timings[operation_id].inference_start = datetime.utcnow()
    
    def record_inference_ttft(self, operation_id: str) -> None:
        """Record Time-to-First-Token for inference."""
        if operation_id in self.operation_timings:
            timing = self.operation_timings[operation_id]
            timing.inference_ttft = datetime.utcnow()
            
            # Calculate and record TTFT
            if timing.inference_start:
                ttft = (timing.inference_ttft - timing.inference_start).total_seconds()
                timing.ttft_latency = ttft
                self.ttft_history.append(ttft)
                
                # Record Prometheus metrics
                cognitive_latency_ttft.labels(
                    agent_id=self.agent_id,
                    model="llama-3.1-8b"
                ).observe(ttft)
                
                # Check for threshold violations
                if ttft > self.ttft_threshold:
                    cognitive_latency_violations.labels(
                        agent_id=self.agent_id,
                        violation_type="ttft",
                        threshold_seconds=str(self.ttft_threshold)
                    ).inc()
                    
                    self.logger.warning(
                        "TTFT threshold violation",
                        operation_id=operation_id,
                        ttft=ttft,
                        threshold=self.ttft_threshold
                    )
    
    def record_inference_end(self, operation_id: str) -> None:
        """Record the end of inference for an operation."""
        if operation_id in self.operation_timings:
            self.operation_timings[operation_id].inference_end = datetime.utcnow()
    
    def record_mcp_request_start(self, operation_id: str) -> None:
        """Record the start of MCP Gateway request."""
        if operation_id in self.operation_timings:
            self.operation_timings[operation_id].mcp_request_start = datetime.utcnow()
    
    def record_mcp_request_end(self, operation_id: str) -> None:
        """Record the end of MCP Gateway request."""
        if operation_id in self.operation_timings:
            self.operation_timings[operation_id].mcp_request_end = datetime.utcnow()
    
    def record_sut_response(self, operation_id: str) -> None:
        """Record when SUT response is received."""
        if operation_id in self.operation_timings:
            self.operation_timings[operation_id].sut_response_received = datetime.utcnow()
    
    def end_operation(self, operation_id: str) -> Optional[OperationTiming]:
        """
        End operation tracking and calculate all metrics.
        
        Args:
            operation_id: Operation ID to end
            
        Returns:
            OperationTiming with calculated metrics, or None if operation not found
        """
        if operation_id not in self.operation_timings:
            return None
        
        timing = self.operation_timings[operation_id]
        timing.end_time = datetime.utcnow()
        timing.calculate_metrics()
        
        # Record end-to-end latency
        if timing.total_latency:
            self.e2e_latency_history.append(timing.total_latency)
            
            end_to_end_latency.labels(
                agent_id=self.agent_id,
                operation_type=timing.operation_type
            ).observe(timing.total_latency)
            
            # Check for E2E latency violations
            if timing.total_latency > self.e2e_latency_threshold:
                cognitive_latency_violations.labels(
                    agent_id=self.agent_id,
                    violation_type="e2e_latency",
                    threshold_seconds=str(self.e2e_latency_threshold)
                ).inc()
        
        # Calculate and record MTBA for this session
        self._calculate_and_record_mtba(timing.session_id)
        
        # Add to recent operations for analysis
        self.recent_operations.append(timing)
        
        self.logger.debug(
            "Completed operation tracking",
            operation_id=operation_id,
            total_latency=timing.total_latency,
            ttft_latency=timing.ttft_latency,
            mcp_latency=timing.mcp_latency
        )
        
        return timing
    
    def _calculate_and_record_mtba(self, session_id: str) -> Optional[float]:
        """
        Calculate Mean Time Between Actions for a session.
        
        Args:
            session_id: Session ID to calculate MTBA for
            
        Returns:
            MTBA in seconds, or None if insufficient data
        """
        if session_id not in self.session_timings:
            return None
        
        timestamps = self.session_timings[session_id]
        if len(timestamps) < 2:
            return None
        
        # Calculate time differences between consecutive actions
        time_diffs = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i-1]).total_seconds()
            time_diffs.append(diff)
        
        if not time_diffs:
            return None
        
        # Calculate MTBA
        mtba = statistics.mean(time_diffs)
        self.mtba_history.append(mtba)
        
        # Record Prometheus metrics
        mtba_seconds.labels(
            agent_id=self.agent_id,
            session_id=session_id
        ).observe(mtba)
        
        # Check for MTBA threshold violations
        if mtba > self.mtba_threshold:
            cognitive_latency_violations.labels(
                agent_id=self.agent_id,
                violation_type="mtba",
                threshold_seconds=str(self.mtba_threshold)
            ).inc()
            
            self.logger.warning(
                "MTBA threshold violation",
                session_id=session_id,
                mtba=mtba,
                threshold=self.mtba_threshold
            )
        
        return mtba
    
    def get_performance_metrics(self, time_window_minutes: int = 60) -> PerformanceMetrics:
        """
        Get comprehensive performance metrics for a time window.
        
        Args:
            time_window_minutes: Time window to analyze
            
        Returns:
            PerformanceMetrics with comprehensive analysis
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_window_minutes)
        
        # Filter operations within time window
        recent_ops = [
            op for op in self.recent_operations
            if op.start_time >= start_time
        ]
        
        # Calculate MTBA metrics
        recent_mtba = [mtba for mtba in self.mtba_history if mtba is not None]
        if recent_mtba:
            mean_mtba = statistics.mean(recent_mtba)
            mtba_p50 = statistics.median(recent_mtba)
            mtba_p95 = self._calculate_percentile(recent_mtba, 95)
            mtba_p99 = self._calculate_percentile(recent_mtba, 99)
            mtba_violations = sum(1 for mtba in recent_mtba if mtba > self.mtba_threshold)
        else:
            mean_mtba = mtba_p50 = mtba_p95 = mtba_p99 = 0.0
            mtba_violations = 0
        
        # Calculate E2E latency metrics
        recent_e2e = [op.total_latency for op in recent_ops if op.total_latency is not None]
        if recent_e2e:
            mean_e2e = statistics.mean(recent_e2e)
            e2e_p50 = statistics.median(recent_e2e)
            e2e_p95 = self._calculate_percentile(recent_e2e, 95)
            e2e_p99 = self._calculate_percentile(recent_e2e, 99)
        else:
            mean_e2e = e2e_p50 = e2e_p95 = e2e_p99 = 0.0
        
        # Calculate TTFT metrics
        recent_ttft = [ttft for ttft in self.ttft_history if ttft is not None]
        if recent_ttft:
            mean_ttft = statistics.mean(recent_ttft)
            ttft_p50 = statistics.median(recent_ttft)
            ttft_p95 = self._calculate_percentile(recent_ttft, 95)
            ttft_p99 = self._calculate_percentile(recent_ttft, 99)
            ttft_violations = sum(1 for ttft in recent_ttft if ttft > self.ttft_threshold)
        else:
            mean_ttft = ttft_p50 = ttft_p95 = ttft_p99 = 0.0
            ttft_violations = 0
        
        # Calculate throughput
        total_operations = len(recent_ops)
        time_window_seconds = time_window_minutes * 60
        ops_per_second = total_operations / time_window_seconds if time_window_seconds > 0 else 0.0
        
        # Validate performance targets
        mtba_target_met = mean_mtba <= self.mtba_threshold if mean_mtba > 0 else True
        cognitive_latency_target_met = mean_ttft <= self.ttft_threshold if mean_ttft > 0 else True
        overall_performance_valid = mtba_target_met and cognitive_latency_target_met
        
        # Record Prometheus metrics
        agent_throughput_ops_per_second.labels(
            agent_id=self.agent_id,
            time_window_seconds=str(time_window_seconds)
        ).set(ops_per_second)
        
        # Record latency percentiles
        for op_type in ["generic", "http_get", "http_post", "inference"]:
            type_ops = [op for op in recent_ops if op.operation_type == op_type and op.total_latency]
            if type_ops:
                latencies = [op.total_latency for op in type_ops]
                for percentile in [50, 95, 99]:
                    value = self._calculate_percentile(latencies, percentile)
                    latency_percentiles.labels(
                        agent_id=self.agent_id,
                        operation_type=op_type,
                        percentile=str(percentile)
                    ).set(value)
        
        metrics = PerformanceMetrics(
            agent_id=self.agent_id,
            time_window_start=start_time,
            time_window_end=end_time,
            mean_time_between_actions=mean_mtba,
            mtba_p50=mtba_p50,
            mtba_p95=mtba_p95,
            mtba_p99=mtba_p99,
            mtba_violations=mtba_violations,
            mean_e2e_latency=mean_e2e,
            e2e_latency_p50=e2e_p50,
            e2e_latency_p95=e2e_p95,
            e2e_latency_p99=e2e_p99,
            mean_ttft=mean_ttft,
            ttft_p50=ttft_p50,
            ttft_p95=ttft_p95,
            ttft_p99=ttft_p99,
            ttft_violations=ttft_violations,
            operations_per_second=ops_per_second,
            total_operations=total_operations,
            mtba_target_met=mtba_target_met,
            cognitive_latency_target_met=cognitive_latency_target_met,
            overall_performance_valid=overall_performance_valid
        )
        
        self.logger.info(
            "Generated performance metrics",
            time_window_minutes=time_window_minutes,
            mtba_target_met=mtba_target_met,
            cognitive_latency_target_met=cognitive_latency_target_met,
            overall_valid=overall_performance_valid
        )
        
        return metrics
    
    def _calculate_percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile for a list of values."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            if upper_index >= len(sorted_data):
                return sorted_data[lower_index]
            
            weight = index - lower_index
            return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
    
    def validate_performance_targets(self) -> Dict[str, Any]:
        """
        Validate current performance against targets.
        
        Returns:
            Dictionary with validation results
        """
        metrics = self.get_performance_metrics(15)  # Last 15 minutes
        
        validation_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "mtba_validation": {
                "target": self.mtba_threshold,
                "current": metrics.mean_time_between_actions,
                "target_met": metrics.mtba_target_met,
                "violations": metrics.mtba_violations
            },
            "cognitive_latency_validation": {
                "target": self.ttft_threshold,
                "current": metrics.mean_ttft,
                "target_met": metrics.cognitive_latency_target_met,
                "violations": metrics.ttft_violations
            },
            "throughput_validation": {
                "current_ops_per_second": metrics.operations_per_second,
                "total_operations": metrics.total_operations
            },
            "overall_performance_valid": metrics.overall_performance_valid
        }
        
        return validation_results
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """
        Clean up old timing data to prevent memory leaks.
        
        Args:
            max_age_hours: Maximum age of data to keep
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Clean up operation timings
        old_operations = [
            op_id for op_id, timing in self.operation_timings.items()
            if timing.start_time < cutoff_time
        ]
        
        for op_id in old_operations:
            del self.operation_timings[op_id]
        
        # Clean up session timings
        for session_id in list(self.session_timings.keys()):
            timestamps = self.session_timings[session_id]
            recent_timestamps = [ts for ts in timestamps if ts >= cutoff_time]
            
            if recent_timestamps:
                self.session_timings[session_id] = recent_timestamps
            else:
                del self.session_timings[session_id]
        
        self.logger.info(
            "Cleaned up old performance data",
            removed_operations=len(old_operations),
            cutoff_hours=max_age_hours
        )