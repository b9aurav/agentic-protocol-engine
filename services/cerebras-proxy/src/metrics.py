"""
Performance metrics collection and monitoring for Cerebras Proxy
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Lock
import structlog

logger = structlog.get_logger()


@dataclass
class InferenceMetric:
    """Individual inference request metric"""
    timestamp: float
    ttft: float  # Time to First Token
    total_time: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    model: str
    cost_estimate: Optional[float] = None


class MetricsCollector:
    """
    Collects and aggregates performance metrics for Cerebras Proxy
    Implements requirements 2.2 and 2.4 for TTFT measurement and token tracking
    """
    
    def __init__(self, max_metrics: int = 10000):
        """
        Initialize metrics collector
        
        Args:
            max_metrics: Maximum number of metrics to keep in memory
        """
        self.max_metrics = max_metrics
        self._metrics: List[InferenceMetric] = []
        self._lock = Lock()
        
        # Aggregated counters
        self._total_requests = 0
        self._total_errors = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        
        logger.info("Metrics collector initialized", max_metrics=max_metrics)
    
    def record_inference_request(
        self,
        ttft: float,
        total_time: float,
        total_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        cost_estimate: Optional[float] = None
    ) -> None:
        """
        Record metrics for an inference request
        
        Args:
            ttft: Time to First Token in seconds
            total_time: Total request time in seconds
            total_tokens: Total tokens processed
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            model: Model name used
            cost_estimate: Estimated cost in USD
        """
        with self._lock:
            # Create metric record
            metric = InferenceMetric(
                timestamp=time.time(),
                ttft=ttft,
                total_time=total_time,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
                cost_estimate=cost_estimate
            )
            
            # Add to metrics list
            self._metrics.append(metric)
            
            # Trim if exceeding max size
            if len(self._metrics) > self.max_metrics:
                self._metrics = self._metrics[-self.max_metrics:]
            
            # Update counters
            self._total_requests += 1
            self._total_tokens += total_tokens
            if cost_estimate:
                self._total_cost += cost_estimate
            
            logger.debug(
                "Recorded inference metric",
                ttft=ttft,
                total_time=total_time,
                total_tokens=total_tokens,
                model=model
            )
    
    def record_error(self) -> None:
        """Record an error occurrence"""
        with self._lock:
            self._total_errors += 1
    
    def get_summary_stats(self, window_seconds: Optional[int] = None) -> Dict:
        """
        Get summary statistics for metrics
        
        Args:
            window_seconds: Time window for stats (None for all time)
            
        Returns:
            Dict: Summary statistics
        """
        with self._lock:
            metrics = self._metrics.copy()
        
        if not metrics:
            return {
                "total_requests": 0,
                "total_errors": 0,
                "error_rate": 0.0,
                "avg_ttft": 0.0,
                "p95_ttft": 0.0,
                "avg_total_time": 0.0,
                "total_tokens": 0,
                "tokens_per_second": 0.0,
                "total_cost": 0.0
            }
        
        # Filter by time window if specified
        if window_seconds:
            cutoff_time = time.time() - window_seconds
            metrics = [m for m in metrics if m.timestamp >= cutoff_time]
        
        if not metrics:
            return self.get_summary_stats(None)  # Fallback to all-time stats
        
        # Calculate statistics
        ttfts = [m.ttft for m in metrics]
        total_times = [m.total_time for m in metrics]
        total_tokens = sum(m.total_tokens for m in metrics)
        total_cost = sum(m.cost_estimate or 0 for m in metrics)
        
        # Sort for percentiles
        ttfts_sorted = sorted(ttfts)
        
        return {
            "total_requests": len(metrics),
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / max(self._total_requests, 1),
            "avg_ttft": sum(ttfts) / len(ttfts),
            "p95_ttft": ttfts_sorted[int(0.95 * len(ttfts_sorted))] if ttfts_sorted else 0,
            "avg_total_time": sum(total_times) / len(total_times),
            "total_tokens": total_tokens,
            "tokens_per_second": total_tokens / sum(total_times) if sum(total_times) > 0 else 0,
            "total_cost": total_cost
        }
    
    def get_prometheus_metrics(self) -> str:
        """
        Generate Prometheus-compatible metrics
        
        Returns:
            str: Prometheus metrics format
        """
        stats = self.get_summary_stats()
        
        metrics = [
            f"# HELP cerebras_proxy_requests_total Total number of inference requests",
            f"# TYPE cerebras_proxy_requests_total counter",
            f"cerebras_proxy_requests_total {stats['total_requests']}",
            "",
            f"# HELP cerebras_proxy_errors_total Total number of errors",
            f"# TYPE cerebras_proxy_errors_total counter", 
            f"cerebras_proxy_errors_total {stats['total_errors']}",
            "",
            f"# HELP cerebras_proxy_ttft_seconds Time to First Token in seconds",
            f"# TYPE cerebras_proxy_ttft_seconds gauge",
            f"cerebras_proxy_ttft_seconds_avg {stats['avg_ttft']:.4f}",
            f"cerebras_proxy_ttft_seconds_p95 {stats['p95_ttft']:.4f}",
            "",
            f"# HELP cerebras_proxy_tokens_total Total tokens processed",
            f"# TYPE cerebras_proxy_tokens_total counter",
            f"cerebras_proxy_tokens_total {stats['total_tokens']}",
            "",
            f"# HELP cerebras_proxy_tokens_per_second Token processing rate",
            f"# TYPE cerebras_proxy_tokens_per_second gauge",
            f"cerebras_proxy_tokens_per_second {stats['tokens_per_second']:.2f}",
            "",
            f"# HELP cerebras_proxy_cost_total Total estimated cost in USD",
            f"# TYPE cerebras_proxy_cost_total counter",
            f"cerebras_proxy_cost_total {stats['total_cost']:.6f}",
            ""
        ]
        
        return "\n".join(metrics)
    
    def get_recent_metrics(self, count: int = 100) -> List[Dict]:
        """
        Get recent metrics for debugging
        
        Args:
            count: Number of recent metrics to return
            
        Returns:
            List[Dict]: Recent metrics as dictionaries
        """
        with self._lock:
            recent = self._metrics[-count:] if self._metrics else []
        
        return [
            {
                "timestamp": m.timestamp,
                "ttft": m.ttft,
                "total_time": m.total_time,
                "total_tokens": m.total_tokens,
                "prompt_tokens": m.prompt_tokens,
                "completion_tokens": m.completion_tokens,
                "model": m.model,
                "cost_estimate": m.cost_estimate
            }
            for m in recent
        ]
    
    def calculate_cost_estimate(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "llama3.1-8b"
    ) -> float:
        """
        Calculate estimated cost for token usage
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            model: Model name
            
        Returns:
            float: Estimated cost in USD
        """
        # Cerebras pricing (example rates - adjust based on actual pricing)
        pricing = {
            "llama3.1-8b": {
                "input": 0.10 / 1_000_000,  # $0.10 per 1M input tokens
                "output": 0.10 / 1_000_000   # $0.10 per 1M output tokens
            }
        }
        
        model_pricing = pricing.get(model, pricing["llama3.1-8b"])
        
        input_cost = prompt_tokens * model_pricing["input"]
        output_cost = completion_tokens * model_pricing["output"]
        
        return input_cost + output_cost