#!/usr/bin/env python3
"""
Performance Validation Script for APE
Implements task 10.2: Validate performance targets and KPIs

This script validates:
- MTBA < 1 second under various load conditions (Requirement 2.2)
- Successful scaling to 1000+ concurrent agents (Requirement 6.4)
- Successful Stateful Sessions percentage optimization (Requirement 8.3)
"""

import os
import sys
import time
import json
import asyncio
import argparse
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics

import docker
import httpx
import psutil
from prometheus_client.parser import text_string_to_metric_families


@dataclass
class PerformanceTarget:
    """Performance target definition"""
    name: str
    description: str
    target_value: float
    unit: str
    comparison: str  # "less_than", "greater_than", "equals"
    critical: bool = True  # Whether failure blocks overall validation


@dataclass
class ValidationResult:
    """Result of a performance validation test"""
    target: PerformanceTarget
    measured_value: float
    passed: bool
    timestamp: datetime
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": asdict(self.target),
            "measured_value": self.measured_value,
            "passed": self.passed,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }


@dataclass
class ScalingTestResult:
    """Result of agent scaling test"""
    target_agents: int
    achieved_agents: int
    startup_time_seconds: float
    resource_usage: Dict[str, float]
    performance_metrics: Dict[str, float]
    success: bool
    errors: List[str]


class PerformanceValidator:
    """
    Comprehensive performance validation for APE system.
    
    Validates performance targets and KPIs across different load conditions
    and scaling scenarios to ensure system meets requirements.
    """
    
    def __init__(self, project_name: str = "ape"):
        self.project_name = project_name
        self.docker_client = docker.from_env()
        self.logger = self._setup_logging()
        
        # Performance targets (Requirements 2.2, 6.4, 8.3)
        self.targets = [
            PerformanceTarget(
                name="mtba_threshold",
                description="Mean Time Between Actions under normal load",
                target_value=1.0,
                unit="seconds",
                comparison="less_than",
                critical=True
            ),
            PerformanceTarget(
                name="mtba_high_load",
                description="Mean Time Between Actions under high load (500+ agents)",
                target_value=1.5,
                unit="seconds",
                comparison="less_than",
                critical=True
            ),
            PerformanceTarget(
                name="cognitive_latency_ttft",
                description="Time-to-First-Token for inference requests",
                target_value=2.0,
                unit="seconds",
                comparison="less_than",
                critical=True
            ),
            PerformanceTarget(
                name="successful_stateful_sessions",
                description="Percentage of successful stateful sessions",
                target_value=85.0,
                unit="percent",
                comparison="greater_than",
                critical=True
            ),
            PerformanceTarget(
                name="max_concurrent_agents",
                description="Maximum concurrent agents supported",
                target_value=1000.0,
                unit="agents",
                comparison="greater_than",
                critical=True
            ),
            PerformanceTarget(
                name="agent_startup_time",
                description="Average agent startup time",
                target_value=30.0,
                unit="seconds",
                comparison="less_than",
                critical=False
            ),
            PerformanceTarget(
                name="system_memory_efficiency",
                description="System memory usage under max load",
                target_value=85.0,
                unit="percent",
                comparison="less_than",
                critical=False
            ),
            PerformanceTarget(
                name="system_cpu_efficiency",
                description="System CPU usage under max load",
                target_value=80.0,
                unit="percent",
                comparison="less_than",
                critical=False
            )
        ]
        
        self.validation_results: List[ValidationResult] = []
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'/tmp/ape-performance-validation.log')
            ]
        )
        return logging.getLogger('performance-validator')
    
    async def validate_all_targets(self, max_agents: int = 1000, 
                                 test_duration_minutes: int = 30) -> Dict[str, Any]:
        """
        Run comprehensive performance validation across all targets.
        
        Args:
            max_agents: Maximum number of agents to test scaling with
            test_duration_minutes: Duration for sustained load testing
            
        Returns:
            Dict with comprehensive validation results
        """
        self.logger.info(
            "Starting comprehensive performance validation",
            max_agents=max_agents,
            test_duration_minutes=test_duration_minutes
        )
        
        validation_start = datetime.utcnow()
        
        try:
            # 1. Validate baseline performance (low load)
            await self._validate_baseline_performance()
            
            # 2. Validate scaling capabilities
            scaling_results = await self._validate_scaling_performance(max_agents)
            
            # 3. Validate sustained high-load performance
            await self._validate_sustained_load_performance(
                target_agents=min(500, max_agents),
                duration_minutes=test_duration_minutes
            )
            
            # 4. Validate KPI targets
            await self._validate_kpi_targets()
            
            # 5. Generate comprehensive report
            validation_end = datetime.utcnow()
            
            report = self._generate_validation_report(
                validation_start, validation_end, scaling_results
            )
            
            self.logger.info(
                "Performance validation completed",
                total_targets=len(self.targets),
                passed_targets=sum(1 for r in self.validation_results if r.passed),
                critical_failures=sum(1 for r in self.validation_results 
                                    if not r.passed and r.target.critical)
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"Performance validation failed: {e}")
            raise
    
    async def _validate_baseline_performance(self):
        """Validate performance under baseline (low load) conditions."""
        self.logger.info("Validating baseline performance (10 agents)")
        
        # Start with minimal agent count
        await self._ensure_agent_count(10)
        await asyncio.sleep(60)  # Warm-up period
        
        # Collect baseline metrics
        metrics = await self._collect_performance_metrics(duration_seconds=300)  # 5 minutes
        
        # Validate MTBA under normal load
        if 'mtba_avg' in metrics:
            result = ValidationResult(
                target=next(t for t in self.targets if t.name == "mtba_threshold"),
                measured_value=metrics['mtba_avg'],
                passed=metrics['mtba_avg'] < 1.0,
                timestamp=datetime.utcnow(),
                details={
                    "agent_count": 10,
                    "test_duration": 300,
                    "mtba_p95": metrics.get('mtba_p95', 0),
                    "mtba_p99": metrics.get('mtba_p99', 0)
                }
            )
            self.validation_results.append(result)
        
        # Validate cognitive latency (TTFT)
        if 'ttft_avg' in metrics:
            result = ValidationResult(
                target=next(t for t in self.targets if t.name == "cognitive_latency_ttft"),
                measured_value=metrics['ttft_avg'],
                passed=metrics['ttft_avg'] < 2.0,
                timestamp=datetime.utcnow(),
                details={
                    "agent_count": 10,
                    "ttft_p95": metrics.get('ttft_p95', 0),
                    "ttft_violations": metrics.get('ttft_violations', 0)
                }
            )
            self.validation_results.append(result)
    
    async def _validate_scaling_performance(self, max_agents: int) -> List[ScalingTestResult]:
        """
        Validate scaling performance across different agent counts.
        
        Args:
            max_agents: Maximum number of agents to test
            
        Returns:
            List of scaling test results
        """
        self.logger.info(f"Validating scaling performance up to {max_agents} agents")
        
        # Test scaling at different levels
        scaling_levels = [50, 100, 200, 500, min(1000, max_agents)]
        scaling_results = []
        
        for target_count in scaling_levels:
            if target_count > max_agents:
                continue
                
            self.logger.info(f"Testing scaling to {target_count} agents")
            
            try:
                # Measure scaling time and resource usage
                scale_start = time.time()
                success = await self._ensure_agent_count(target_count)
                scale_time = time.time() - scale_start
                
                if not success:
                    scaling_results.append(ScalingTestResult(
                        target_agents=target_count,
                        achieved_agents=0,
                        startup_time_seconds=scale_time,
                        resource_usage={},
                        performance_metrics={},
                        success=False,
                        errors=[f"Failed to scale to {target_count} agents"]
                    ))
                    continue
                
                # Wait for stabilization
                await asyncio.sleep(min(60, target_count * 0.1))
                
                # Measure actual agent count and resource usage
                actual_count = await self._get_running_agent_count()
                resource_usage = await self._get_system_resource_usage()
                
                # Collect performance metrics under this load
                perf_metrics = await self._collect_performance_metrics(duration_seconds=180)
                
                scaling_result = ScalingTestResult(
                    target_agents=target_count,
                    achieved_agents=actual_count,
                    startup_time_seconds=scale_time,
                    resource_usage=resource_usage,
                    performance_metrics=perf_metrics,
                    success=actual_count >= target_count * 0.95,  # 95% success rate
                    errors=[]
                )
                
                scaling_results.append(scaling_result)
                
                # Validate MTBA under this load level
                if target_count >= 500 and 'mtba_avg' in perf_metrics:
                    result = ValidationResult(
                        target=next(t for t in self.targets if t.name == "mtba_high_load"),
                        measured_value=perf_metrics['mtba_avg'],
                        passed=perf_metrics['mtba_avg'] < 1.5,
                        timestamp=datetime.utcnow(),
                        details={
                            "agent_count": actual_count,
                            "target_count": target_count,
                            "mtba_p95": perf_metrics.get('mtba_p95', 0)
                        }
                    )
                    self.validation_results.append(result)
                
                self.logger.info(
                    f"Scaling test completed",
                    target=target_count,
                    achieved=actual_count,
                    success=scaling_result.success,
                    scale_time=scale_time
                )
                
            except Exception as e:
                self.logger.error(f"Scaling test failed for {target_count} agents: {e}")
                scaling_results.append(ScalingTestResult(
                    target_agents=target_count,
                    achieved_agents=0,
                    startup_time_seconds=0,
                    resource_usage={},
                    performance_metrics={},
                    success=False,
                    errors=[str(e)]
                ))
        
        # Validate maximum concurrent agents target
        max_achieved = max((r.achieved_agents for r in scaling_results), default=0)
        result = ValidationResult(
            target=next(t for t in self.targets if t.name == "max_concurrent_agents"),
            measured_value=max_achieved,
            passed=max_achieved >= 1000,
            timestamp=datetime.utcnow(),
            details={
                "scaling_results": [asdict(r) for r in scaling_results],
                "max_attempted": max_agents
            }
        )
        self.validation_results.append(result)
        
        return scaling_results
    
    async def _validate_sustained_load_performance(self, target_agents: int, 
                                                 duration_minutes: int):
        """
        Validate performance under sustained high load.
        
        Args:
            target_agents: Number of agents to maintain
            duration_minutes: Duration to sustain the load
        """
        self.logger.info(
            f"Validating sustained load performance",
            agents=target_agents,
            duration_minutes=duration_minutes
        )
        
        # Ensure target agent count
        await self._ensure_agent_count(target_agents)
        
        # Monitor performance over the duration
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        performance_samples = []
        resource_samples = []
        
        while time.time() < end_time:
            # Collect performance sample
            metrics = await self._collect_performance_metrics(duration_seconds=60)
            performance_samples.append({
                "timestamp": time.time(),
                "metrics": metrics
            })
            
            # Collect resource usage sample
            resources = await self._get_system_resource_usage()
            resource_samples.append({
                "timestamp": time.time(),
                "resources": resources
            })
            
            # Wait before next sample
            await asyncio.sleep(60)
        
        # Analyze sustained performance
        if performance_samples:
            # Calculate average performance over the duration
            avg_metrics = self._calculate_average_metrics(performance_samples)
            
            # Validate system resource efficiency
            avg_resources = self._calculate_average_resources(resource_samples)
            
            if 'memory_percent' in avg_resources:
                result = ValidationResult(
                    target=next(t for t in self.targets if t.name == "system_memory_efficiency"),
                    measured_value=avg_resources['memory_percent'],
                    passed=avg_resources['memory_percent'] < 85.0,
                    timestamp=datetime.utcnow(),
                    details={
                        "agent_count": target_agents,
                        "duration_minutes": duration_minutes,
                        "peak_memory": max(s["resources"].get("memory_percent", 0) 
                                         for s in resource_samples)
                    }
                )
                self.validation_results.append(result)
            
            if 'cpu_percent' in avg_resources:
                result = ValidationResult(
                    target=next(t for t in self.targets if t.name == "system_cpu_efficiency"),
                    measured_value=avg_resources['cpu_percent'],
                    passed=avg_resources['cpu_percent'] < 80.0,
                    timestamp=datetime.utcnow(),
                    details={
                        "agent_count": target_agents,
                        "duration_minutes": duration_minutes,
                        "peak_cpu": max(s["resources"].get("cpu_percent", 0) 
                                      for s in resource_samples)
                    }
                )
                self.validation_results.append(result)
    
    async def _validate_kpi_targets(self):
        """Validate key performance indicator targets."""
        self.logger.info("Validating KPI targets")
        
        # Get current agent count for KPI validation
        agent_count = await self._get_running_agent_count()
        
        if agent_count > 0:
            # Collect comprehensive metrics for KPI validation
            metrics = await self._collect_performance_metrics(duration_seconds=300)
            
            # Validate Successful Stateful Sessions percentage
            if 'successful_sessions_percentage' in metrics:
                result = ValidationResult(
                    target=next(t for t in self.targets if t.name == "successful_stateful_sessions"),
                    measured_value=metrics['successful_sessions_percentage'],
                    passed=metrics['successful_sessions_percentage'] >= 85.0,
                    timestamp=datetime.utcnow(),
                    details={
                        "agent_count": agent_count,
                        "total_sessions": metrics.get('total_sessions', 0),
                        "successful_sessions": metrics.get('successful_sessions', 0),
                        "session_failure_rate": metrics.get('session_failure_rate', 0)
                    }
                )
                self.validation_results.append(result)
    
    async def _ensure_agent_count(self, target_count: int) -> bool:
        """
        Ensure the specified number of agents are running.
        
        Args:
            target_count: Target number of agents
            
        Returns:
            bool: True if target count achieved, False otherwise
        """
        try:
            # Use docker-compose to scale agents
            scale_command = [
                "docker-compose", "-f", "ape.docker-compose.yml",
                "up", "-d", "--scale", f"llama_agent={target_count}"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *scale_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"Failed to scale agents: {stderr.decode()}")
                return False
            
            # Wait for agents to start and become healthy
            max_wait_time = min(300, target_count * 0.5)  # Max 5 minutes or 0.5s per agent
            wait_start = time.time()
            
            while time.time() - wait_start < max_wait_time:
                current_count = await self._get_running_agent_count()
                if current_count >= target_count * 0.95:  # 95% of target
                    return True
                await asyncio.sleep(5)
            
            self.logger.warning(
                f"Timeout waiting for agents to start",
                target=target_count,
                current=await self._get_running_agent_count()
            )
            return False
            
        except Exception as e:
            self.logger.error(f"Error scaling agents: {e}")
            return False
    
    async def _get_running_agent_count(self) -> int:
        """Get the current number of running agent containers."""
        try:
            containers = self.docker_client.containers.list(
                filters={"label": "com.docker.compose.service=llama_agent"}
            )
            running_count = sum(1 for c in containers if c.status == "running")
            return running_count
        except Exception as e:
            self.logger.error(f"Error getting agent count: {e}")
            return 0
    
    async def _get_system_resource_usage(self) -> Dict[str, float]:
        """Get current system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network connections
            network_connections = len(psutil.net_connections())
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "network_connections": network_connections,
                "memory_available_gb": memory.available / (1024**3),
                "memory_used_gb": (memory.total - memory.available) / (1024**3)
            }
        except Exception as e:
            self.logger.error(f"Error getting system resources: {e}")
            return {}
    
    async def _collect_performance_metrics(self, duration_seconds: int = 60) -> Dict[str, float]:
        """
        Collect performance metrics from running agents.
        
        Args:
            duration_seconds: Duration to collect metrics over
            
        Returns:
            Dict with aggregated performance metrics
        """
        try:
            # Find agent containers with metrics endpoints
            agent_containers = self.docker_client.containers.list(
                filters={"label": "com.docker.compose.service=llama_agent"}
            )
            
            if not agent_containers:
                return {}
            
            # Collect metrics from all agents
            all_metrics = []
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                for container in agent_containers:
                    if container.status != "running":
                        continue
                    
                    try:
                        # Get container IP
                        container.reload()
                        networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
                        container_ip = None
                        
                        for network_name, network_info in networks.items():
                            if network_info.get('IPAddress'):
                                container_ip = network_info['IPAddress']
                                break
                        
                        if not container_ip:
                            continue
                        
                        # Fetch metrics from agent
                        metrics_url = f"http://{container_ip}:8000/metrics"
                        response = await client.get(metrics_url)
                        
                        if response.status_code == 200:
                            metrics_text = response.text
                            parsed_metrics = self._parse_prometheus_metrics(metrics_text)
                            all_metrics.append(parsed_metrics)
                            
                    except Exception as e:
                        self.logger.debug(f"Could not collect metrics from {container.name}: {e}")
                        continue
            
            # Aggregate metrics across all agents
            if not all_metrics:
                return {}
            
            aggregated = self._aggregate_agent_metrics(all_metrics)
            
            # Add system-level metrics
            system_metrics = await self._get_system_resource_usage()
            aggregated.update(system_metrics)
            
            return aggregated
            
        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {e}")
            return {}
    
    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, float]:
        """Parse Prometheus metrics text format."""
        metrics = {}
        
        try:
            for family in text_string_to_metric_families(metrics_text):
                for sample in family.samples:
                    metric_name = sample.name
                    metric_value = sample.value
                    
                    # Extract key metrics
                    if "mtba_seconds" in metric_name:
                        if metric_name not in metrics:
                            metrics["mtba_values"] = []
                        metrics["mtba_values"].append(metric_value)
                    elif "ttft_seconds" in metric_name:
                        if "ttft_values" not in metrics:
                            metrics["ttft_values"] = []
                        metrics["ttft_values"].append(metric_value)
                    elif "successful_sessions_percentage" in metric_name:
                        metrics["successful_sessions_percentage"] = metric_value
                    elif "sessions_total" in metric_name:
                        metrics["total_sessions"] = metrics.get("total_sessions", 0) + metric_value
                    elif "sessions_successful" in metric_name:
                        metrics["successful_sessions"] = metrics.get("successful_sessions", 0) + metric_value
                        
        except Exception as e:
            self.logger.debug(f"Error parsing Prometheus metrics: {e}")
        
        return metrics
    
    def _aggregate_agent_metrics(self, all_metrics: List[Dict[str, Any]]) -> Dict[str, float]:
        """Aggregate metrics from multiple agents."""
        aggregated = {}
        
        # Aggregate MTBA values
        all_mtba = []
        for metrics in all_metrics:
            if "mtba_values" in metrics:
                all_mtba.extend(metrics["mtba_values"])
        
        if all_mtba:
            aggregated["mtba_avg"] = statistics.mean(all_mtba)
            aggregated["mtba_p95"] = self._calculate_percentile(all_mtba, 95)
            aggregated["mtba_p99"] = self._calculate_percentile(all_mtba, 99)
        
        # Aggregate TTFT values
        all_ttft = []
        for metrics in all_metrics:
            if "ttft_values" in metrics:
                all_ttft.extend(metrics["ttft_values"])
        
        if all_ttft:
            aggregated["ttft_avg"] = statistics.mean(all_ttft)
            aggregated["ttft_p95"] = self._calculate_percentile(all_ttft, 95)
            aggregated["ttft_p99"] = self._calculate_percentile(all_ttft, 99)
        
        # Aggregate session success metrics
        total_sessions = sum(m.get("total_sessions", 0) for m in all_metrics)
        successful_sessions = sum(m.get("successful_sessions", 0) for m in all_metrics)
        
        if total_sessions > 0:
            aggregated["successful_sessions_percentage"] = (successful_sessions / total_sessions) * 100
            aggregated["total_sessions"] = total_sessions
            aggregated["successful_sessions"] = successful_sessions
            aggregated["session_failure_rate"] = ((total_sessions - successful_sessions) / total_sessions) * 100
        
        return aggregated
    
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
    
    def _calculate_average_metrics(self, samples: List[Dict]) -> Dict[str, float]:
        """Calculate average metrics from samples."""
        if not samples:
            return {}
        
        # Extract all metric keys
        all_keys = set()
        for sample in samples:
            all_keys.update(sample["metrics"].keys())
        
        # Calculate averages
        averages = {}
        for key in all_keys:
            values = [s["metrics"].get(key, 0) for s in samples if key in s["metrics"]]
            if values:
                averages[key] = statistics.mean(values)
        
        return averages
    
    def _calculate_average_resources(self, samples: List[Dict]) -> Dict[str, float]:
        """Calculate average resource usage from samples."""
        if not samples:
            return {}
        
        # Extract all resource keys
        all_keys = set()
        for sample in samples:
            all_keys.update(sample["resources"].keys())
        
        # Calculate averages
        averages = {}
        for key in all_keys:
            values = [s["resources"].get(key, 0) for s in samples if key in s["resources"]]
            if values:
                averages[key] = statistics.mean(values)
        
        return averages
    
    def _generate_validation_report(self, start_time: datetime, end_time: datetime,
                                 scaling_results: List[ScalingTestResult]) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        
        # Calculate overall results
        total_targets = len(self.targets)
        passed_targets = sum(1 for r in self.validation_results if r.passed)
        critical_failures = sum(1 for r in self.validation_results 
                              if not r.passed and r.target.critical)
        
        overall_success = critical_failures == 0
        
        # Group results by category
        results_by_category = {
            "performance": [],
            "scaling": [],
            "efficiency": [],
            "kpi": []
        }
        
        for result in self.validation_results:
            if "mtba" in result.target.name or "cognitive_latency" in result.target.name:
                results_by_category["performance"].append(result)
            elif "concurrent_agents" in result.target.name or "startup_time" in result.target.name:
                results_by_category["scaling"].append(result)
            elif "efficiency" in result.target.name:
                results_by_category["efficiency"].append(result)
            elif "successful_stateful_sessions" in result.target.name:
                results_by_category["kpi"].append(result)
        
        report = {
            "validation_summary": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": (end_time - start_time).total_seconds() / 60,
                "overall_success": overall_success,
                "total_targets": total_targets,
                "passed_targets": passed_targets,
                "failed_targets": total_targets - passed_targets,
                "critical_failures": critical_failures
            },
            "performance_targets": {
                "mtba_validation": {
                    "target": "< 1.0 seconds (normal load), < 1.5 seconds (high load)",
                    "status": "PASS" if all(r.passed for r in results_by_category["performance"] 
                                          if "mtba" in r.target.name) else "FAIL",
                    "details": [r.to_dict() for r in results_by_category["performance"] 
                              if "mtba" in r.target.name]
                },
                "cognitive_latency_validation": {
                    "target": "< 2.0 seconds TTFT",
                    "status": "PASS" if all(r.passed for r in results_by_category["performance"] 
                                          if "cognitive_latency" in r.target.name) else "FAIL",
                    "details": [r.to_dict() for r in results_by_category["performance"] 
                              if "cognitive_latency" in r.target.name]
                }
            },
            "scaling_validation": {
                "target": ">= 1000 concurrent agents",
                "status": "PASS" if any(r.passed for r in results_by_category["scaling"] 
                                      if "concurrent_agents" in r.target.name) else "FAIL",
                "scaling_test_results": [asdict(r) for r in scaling_results],
                "max_achieved_agents": max((r.achieved_agents for r in scaling_results), default=0),
                "details": [r.to_dict() for r in results_by_category["scaling"]]
            },
            "kpi_validation": {
                "successful_stateful_sessions": {
                    "target": ">= 85% success rate",
                    "status": "PASS" if all(r.passed for r in results_by_category["kpi"]) else "FAIL",
                    "details": [r.to_dict() for r in results_by_category["kpi"]]
                }
            },
            "efficiency_validation": {
                "resource_usage": {
                    "target": "< 85% memory, < 80% CPU under max load",
                    "status": "PASS" if all(r.passed for r in results_by_category["efficiency"]) else "FAIL",
                    "details": [r.to_dict() for r in results_by_category["efficiency"]]
                }
            },
            "all_validation_results": [r.to_dict() for r in self.validation_results],
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Check for specific failure patterns
        failed_results = [r for r in self.validation_results if not r.passed]
        
        for result in failed_results:
            if "mtba" in result.target.name:
                if result.measured_value > 2.0:
                    recommendations.append(
                        "MTBA significantly exceeds target. Consider optimizing inference speed "
                        "or reducing agent decision complexity."
                    )
                elif result.measured_value > result.target.target_value:
                    recommendations.append(
                        "MTBA slightly exceeds target. Monitor inference latency and "
                        "consider Cerebras API optimization."
                    )
            
            elif "cognitive_latency" in result.target.name:
                recommendations.append(
                    "TTFT exceeds target. Verify Cerebras API performance and "
                    "consider request optimization or model selection."
                )
            
            elif "concurrent_agents" in result.target.name:
                recommendations.append(
                    "Failed to achieve target concurrent agents. Check system resources, "
                    "container limits, and Docker Compose scaling configuration."
                )
            
            elif "successful_stateful_sessions" in result.target.name:
                recommendations.append(
                    "Session success rate below target. Review agent logic, error handling, "
                    "and target application stability."
                )
            
            elif "efficiency" in result.target.name:
                recommendations.append(
                    "Resource usage exceeds targets. Consider optimizing container resource "
                    "limits, agent memory usage, or system capacity."
                )
        
        if not recommendations:
            recommendations.append(
                "All performance targets met! System is ready for production deployment."
            )
        
        return recommendations


async def main():
    """Main function for performance validation."""
    parser = argparse.ArgumentParser(description='APE Performance Validation')
    parser.add_argument('--max-agents', type=int, default=1000,
                       help='Maximum number of agents to test (default: 1000)')
    parser.add_argument('--test-duration', type=int, default=30,
                       help='Test duration in minutes (default: 30)')
    parser.add_argument('--output', '-o', 
                       help='Output file for validation report (JSON)')
    parser.add_argument('--project', '-p', default='ape',
                       help='Project name (default: ape)')
    
    args = parser.parse_args()
    
    validator = PerformanceValidator(project_name=args.project)
    
    try:
        # Run comprehensive validation
        report = await validator.validate_all_targets(
            max_agents=args.max_agents,
            test_duration_minutes=args.test_duration
        )
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Validation report written to {args.output}")
        
        # Print summary
        print("\n" + "="*80)
        print("APE PERFORMANCE VALIDATION SUMMARY")
        print("="*80)
        
        summary = report["validation_summary"]
        print(f"Overall Status: {'✅ PASS' if summary['overall_success'] else '❌ FAIL'}")
        print(f"Targets Passed: {summary['passed_targets']}/{summary['total_targets']}")
        print(f"Critical Failures: {summary['critical_failures']}")
        print(f"Test Duration: {summary['duration_minutes']:.1f} minutes")
        
        # Print key results
        print(f"\nKey Performance Indicators:")
        
        scaling = report["scaling_validation"]
        print(f"  Max Concurrent Agents: {scaling['max_achieved_agents']} "
              f"({'✅' if scaling['status'] == 'PASS' else '❌'})")
        
        perf = report["performance_targets"]
        print(f"  MTBA Validation: {perf['mtba_validation']['status']} "
              f"({'✅' if perf['mtba_validation']['status'] == 'PASS' else '❌'})")
        print(f"  Cognitive Latency: {perf['cognitive_latency_validation']['status']} "
              f"({'✅' if perf['cognitive_latency_validation']['status'] == 'PASS' else '❌'})")
        
        kpi = report["kpi_validation"]
        print(f"  Session Success Rate: {kpi['successful_stateful_sessions']['status']} "
              f"({'✅' if kpi['successful_stateful_sessions']['status'] == 'PASS' else '❌'})")
        
        # Print recommendations
        recommendations = report["recommendations"]
        if recommendations:
            print(f"\nRecommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "="*80)
        
        # Exit with appropriate code
        sys.exit(0 if summary['overall_success'] else 1)
        
    except Exception as e:
        print(f"❌ Performance validation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())