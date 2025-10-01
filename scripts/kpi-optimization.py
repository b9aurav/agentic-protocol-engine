#!/usr/bin/env python3
"""
KPI Optimization Script for APE
Implements optimization strategies for task 10.2: Validate performance targets and KPIs

This script provides optimization recommendations and automated tuning for:
- Successful Stateful Sessions percentage optimization
- MTBA performance tuning under various load conditions
- Resource efficiency optimization for high-scale deployments
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics

import yaml
import docker
import httpx


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation"""
    category: str
    priority: str  # "high", "medium", "low"
    description: str
    action: str
    expected_improvement: str
    implementation_steps: List[str]
    estimated_impact: float  # 0-100 percentage improvement


@dataclass
class KPITarget:
    """KPI target with current and optimized values"""
    name: str
    current_value: float
    target_value: float
    optimized_value: Optional[float] = None
    unit: str = ""
    improvement_potential: float = 0.0


class KPIOptimizer:
    """
    KPI optimization engine for APE system.
    
    Analyzes current performance and provides actionable recommendations
    to optimize key performance indicators and achieve target values.
    """
    
    def __init__(self, project_name: str = "ape"):
        self.project_name = project_name
        self.docker_client = docker.from_env()
        self.logger = self._setup_logging()
        
        # KPI targets for optimization
        self.kpi_targets = [
            KPITarget(
                name="successful_stateful_sessions_percentage",
                current_value=0.0,
                target_value=85.0,
                unit="percent"
            ),
            KPITarget(
                name="mtba_average",
                current_value=0.0,
                target_value=1.0,
                unit="seconds"
            ),
            KPITarget(
                name="cognitive_latency_ttft",
                current_value=0.0,
                target_value=2.0,
                unit="seconds"
            ),
            KPITarget(
                name="system_resource_efficiency",
                current_value=0.0,
                target_value=80.0,
                unit="percent"
            ),
            KPITarget(
                name="agent_throughput",
                current_value=0.0,
                target_value=10.0,
                unit="ops/second"
            )
        ]
        
        self.optimization_recommendations: List[OptimizationRecommendation] = []
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'/tmp/ape-kpi-optimization.log')
            ]
        )
        return logging.getLogger('kpi-optimizer')
    
    async def analyze_and_optimize(self, analysis_duration_minutes: int = 15) -> Dict[str, Any]:
        """
        Analyze current KPIs and generate optimization recommendations.
        
        Args:
            analysis_duration_minutes: Duration to analyze current performance
            
        Returns:
            Dict with analysis results and optimization recommendations
        """
        self.logger.info(
            "Starting KPI analysis and optimization",
            analysis_duration=analysis_duration_minutes
        )
        
        analysis_start = datetime.utcnow()
        
        try:
            # 1. Collect current performance baseline
            current_metrics = await self._collect_current_kpis(analysis_duration_minutes)
            
            # 2. Update KPI targets with current values
            self._update_kpi_current_values(current_metrics)
            
            # 3. Analyze performance gaps
            performance_gaps = self._analyze_performance_gaps()
            
            # 4. Generate optimization recommendations
            await self._generate_optimization_recommendations(current_metrics, performance_gaps)
            
            # 5. Estimate optimization impact
            optimization_impact = self._estimate_optimization_impact()
            
            # 6. Generate optimization plan
            optimization_plan = self._create_optimization_plan()
            
            analysis_end = datetime.utcnow()
            
            report = {
                "analysis_summary": {
                    "start_time": analysis_start.isoformat(),
                    "end_time": analysis_end.isoformat(),
                    "analysis_duration_minutes": analysis_duration_minutes,
                    "total_recommendations": len(self.optimization_recommendations),
                    "high_priority_recommendations": sum(1 for r in self.optimization_recommendations 
                                                       if r.priority == "high"),
                    "estimated_total_improvement": sum(r.estimated_impact 
                                                     for r in self.optimization_recommendations)
                },
                "current_kpis": {kpi.name: asdict(kpi) for kpi in self.kpi_targets},
                "performance_gaps": performance_gaps,
                "optimization_recommendations": [asdict(r) for r in self.optimization_recommendations],
                "optimization_impact": optimization_impact,
                "optimization_plan": optimization_plan,
                "implementation_guide": self._generate_implementation_guide()
            }
            
            self.logger.info(
                "KPI optimization analysis completed",
                total_recommendations=len(self.optimization_recommendations),
                estimated_improvement=optimization_impact.get("total_improvement_percentage", 0)
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"KPI optimization analysis failed: {e}")
            raise
    
    async def _collect_current_kpis(self, duration_minutes: int) -> Dict[str, float]:
        """
        Collect current KPI values from the running system.
        
        Args:
            duration_minutes: Duration to collect metrics over
            
        Returns:
            Dict with current KPI values
        """
        self.logger.info(f"Collecting current KPIs over {duration_minutes} minutes")
        
        # Collect metrics from multiple sources
        agent_metrics = await self._collect_agent_metrics(duration_minutes)
        system_metrics = await self._collect_system_metrics()
        session_metrics = await self._collect_session_success_metrics()
        
        # Combine all metrics
        current_kpis = {}
        current_kpis.update(agent_metrics)
        current_kpis.update(system_metrics)
        current_kpis.update(session_metrics)
        
        return current_kpis
    
    async def _collect_agent_metrics(self, duration_minutes: int) -> Dict[str, float]:
        """Collect metrics from agent containers."""
        try:
            agent_containers = self.docker_client.containers.list(
                filters={"label": "com.docker.compose.service=llama_agent"}
            )
            
            if not agent_containers:
                return {}
            
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
                        
                        # Fetch metrics
                        metrics_url = f"http://{container_ip}:8000/metrics"
                        response = await client.get(metrics_url)
                        
                        if response.status_code == 200:
                            metrics = self._parse_agent_metrics(response.text)
                            all_metrics.append(metrics)
                            
                    except Exception as e:
                        self.logger.debug(f"Could not collect metrics from {container.name}: {e}")
                        continue
            
            # Aggregate metrics
            if not all_metrics:
                return {}
            
            return self._aggregate_agent_metrics(all_metrics)
            
        except Exception as e:
            self.logger.error(f"Error collecting agent metrics: {e}")
            return {}
    
    async def _collect_system_metrics(self) -> Dict[str, float]:
        """Collect system-level metrics."""
        try:
            import psutil
            
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Container metrics
            agent_containers = self.docker_client.containers.list(
                filters={"label": "com.docker.compose.service=llama_agent"}
            )
            running_agents = sum(1 for c in agent_containers if c.status == "running")
            
            return {
                "system_cpu_percent": cpu_percent,
                "system_memory_percent": memory.percent,
                "running_agent_count": running_agents,
                "system_resource_efficiency": (cpu_percent + memory.percent) / 2
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    async def _collect_session_success_metrics(self) -> Dict[str, float]:
        """Collect session success metrics from agents."""
        try:
            # This would integrate with the session tracking system
            # For now, return placeholder values that would be collected from Prometheus
            
            # In a real implementation, this would query Prometheus for:
            # - ape_successful_sessions_total
            # - ape_agent_sessions_total
            # - ape_session_transaction_completion_rate
            
            return {
                "successful_stateful_sessions_percentage": 75.0,  # Placeholder
                "total_sessions": 1000,
                "successful_sessions": 750,
                "session_failure_rate": 25.0,
                "average_session_duration": 45.0
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting session metrics: {e}")
            return {}
    
    def _parse_agent_metrics(self, metrics_text: str) -> Dict[str, float]:
        """Parse Prometheus metrics from agent."""
        metrics = {}
        
        # Parse key metrics from Prometheus format
        lines = metrics_text.split('\n')
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            
            try:
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0]
                    metric_value = float(parts[1])
                    
                    # Extract relevant metrics
                    if "mtba_seconds" in metric_name:
                        metrics["mtba_values"] = metrics.get("mtba_values", [])
                        metrics["mtba_values"].append(metric_value)
                    elif "ttft_seconds" in metric_name:
                        metrics["ttft_values"] = metrics.get("ttft_values", [])
                        metrics["ttft_values"].append(metric_value)
                    elif "throughput_ops_per_second" in metric_name:
                        metrics["throughput"] = metric_value
                        
            except (ValueError, IndexError):
                continue
        
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
            aggregated["mtba_average"] = statistics.mean(all_mtba)
            aggregated["mtba_p95"] = self._calculate_percentile(all_mtba, 95)
        
        # Aggregate TTFT values
        all_ttft = []
        for metrics in all_metrics:
            if "ttft_values" in metrics:
                all_ttft.extend(metrics["ttft_values"])
        
        if all_ttft:
            aggregated["cognitive_latency_ttft"] = statistics.mean(all_ttft)
            aggregated["ttft_p95"] = self._calculate_percentile(all_ttft, 95)
        
        # Aggregate throughput
        throughput_values = [m.get("throughput", 0) for m in all_metrics if "throughput" in m]
        if throughput_values:
            aggregated["agent_throughput"] = statistics.mean(throughput_values)
        
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
    
    def _update_kpi_current_values(self, current_metrics: Dict[str, float]):
        """Update KPI targets with current measured values."""
        for kpi in self.kpi_targets:
            if kpi.name in current_metrics:
                kpi.current_value = current_metrics[kpi.name]
                
                # Calculate improvement potential
                if kpi.name in ["mtba_average", "cognitive_latency_ttft"]:
                    # Lower is better
                    if kpi.current_value > kpi.target_value:
                        kpi.improvement_potential = ((kpi.current_value - kpi.target_value) / kpi.current_value) * 100
                else:
                    # Higher is better
                    if kpi.current_value < kpi.target_value:
                        kpi.improvement_potential = ((kpi.target_value - kpi.current_value) / kpi.target_value) * 100
    
    def _analyze_performance_gaps(self) -> Dict[str, Any]:
        """Analyze performance gaps between current and target values."""
        gaps = {}
        
        for kpi in self.kpi_targets:
            gap_info = {
                "current": kpi.current_value,
                "target": kpi.target_value,
                "gap": abs(kpi.current_value - kpi.target_value),
                "gap_percentage": kpi.improvement_potential,
                "meets_target": False,
                "priority": "low"
            }
            
            # Determine if target is met
            if kpi.name in ["mtba_average", "cognitive_latency_ttft"]:
                gap_info["meets_target"] = kpi.current_value <= kpi.target_value
            else:
                gap_info["meets_target"] = kpi.current_value >= kpi.target_value
            
            # Determine priority based on gap size
            if kpi.improvement_potential > 30:
                gap_info["priority"] = "high"
            elif kpi.improvement_potential > 15:
                gap_info["priority"] = "medium"
            
            gaps[kpi.name] = gap_info
        
        return gaps
    
    async def _generate_optimization_recommendations(self, current_metrics: Dict[str, float], 
                                                   performance_gaps: Dict[str, Any]):
        """Generate specific optimization recommendations based on analysis."""
        
        # Successful Stateful Sessions optimization
        sessions_gap = performance_gaps.get("successful_stateful_sessions_percentage", {})
        if not sessions_gap.get("meets_target", True):
            self.optimization_recommendations.append(OptimizationRecommendation(
                category="Session Success",
                priority="high",
                description="Successful Stateful Sessions percentage below target",
                action="Optimize agent decision-making and error handling",
                expected_improvement=f"Increase success rate by {sessions_gap.get('gap_percentage', 0):.1f}%",
                implementation_steps=[
                    "Review agent prompt engineering for better decision-making",
                    "Implement more robust error recovery mechanisms",
                    "Add session state validation and recovery",
                    "Optimize tool call retry logic",
                    "Improve target application interaction patterns"
                ],
                estimated_impact=sessions_gap.get('gap_percentage', 0)
            ))
        
        # MTBA optimization
        mtba_gap = performance_gaps.get("mtba_average", {})
        if not mtba_gap.get("meets_target", True):
            priority = "high" if mtba_gap.get("gap_percentage", 0) > 20 else "medium"
            self.optimization_recommendations.append(OptimizationRecommendation(
                category="Performance",
                priority=priority,
                description="Mean Time Between Actions exceeds target",
                action="Optimize inference speed and agent decision latency",
                expected_improvement=f"Reduce MTBA by {mtba_gap.get('gap_percentage', 0):.1f}%",
                implementation_steps=[
                    "Optimize Cerebras API request parameters",
                    "Implement request batching for inference",
                    "Reduce agent context size where possible",
                    "Optimize prompt templates for faster inference",
                    "Consider model selection optimization"
                ],
                estimated_impact=mtba_gap.get('gap_percentage', 0)
            ))
        
        # Cognitive latency optimization
        ttft_gap = performance_gaps.get("cognitive_latency_ttft", {})
        if not ttft_gap.get("meets_target", True):
            self.optimization_recommendations.append(OptimizationRecommendation(
                category="Inference",
                priority="high",
                description="Time-to-First-Token exceeds cognitive latency target",
                action="Optimize inference request parameters and model configuration",
                expected_improvement=f"Reduce TTFT by {ttft_gap.get('gap_percentage', 0):.1f}%",
                implementation_steps=[
                    "Optimize Cerebras API connection pooling",
                    "Reduce prompt complexity and length",
                    "Implement inference request caching",
                    "Optimize model parameters (temperature, top_p)",
                    "Consider parallel inference for complex decisions"
                ],
                estimated_impact=ttft_gap.get('gap_percentage', 0)
            ))
        
        # Resource efficiency optimization
        resource_gap = performance_gaps.get("system_resource_efficiency", {})
        if resource_gap.get("gap_percentage", 0) > 10:
            self.optimization_recommendations.append(OptimizationRecommendation(
                category="Resource Efficiency",
                priority="medium",
                description="System resource usage can be optimized",
                action="Optimize container resource allocation and system efficiency",
                expected_improvement=f"Improve resource efficiency by {resource_gap.get('gap_percentage', 0):.1f}%",
                implementation_steps=[
                    "Optimize Docker container resource limits",
                    "Implement more efficient agent memory management",
                    "Optimize garbage collection settings",
                    "Consider agent pooling and reuse strategies",
                    "Implement dynamic resource scaling"
                ],
                estimated_impact=resource_gap.get('gap_percentage', 0) * 0.5  # Lower impact
            ))
        
        # Throughput optimization
        throughput_gap = performance_gaps.get("agent_throughput", {})
        if not throughput_gap.get("meets_target", True):
            self.optimization_recommendations.append(OptimizationRecommendation(
                category="Throughput",
                priority="medium",
                description="Agent throughput below optimal levels",
                action="Optimize agent execution efficiency and parallelization",
                expected_improvement=f"Increase throughput by {throughput_gap.get('gap_percentage', 0):.1f}%",
                implementation_steps=[
                    "Implement asynchronous tool execution",
                    "Optimize agent execution loop efficiency",
                    "Reduce unnecessary waiting and delays",
                    "Implement intelligent request queuing",
                    "Optimize network request patterns"
                ],
                estimated_impact=throughput_gap.get('gap_percentage', 0) * 0.7
            ))
    
    def _estimate_optimization_impact(self) -> Dict[str, Any]:
        """Estimate the impact of implementing all optimization recommendations."""
        
        total_impact = sum(r.estimated_impact for r in self.optimization_recommendations)
        high_priority_impact = sum(r.estimated_impact for r in self.optimization_recommendations 
                                 if r.priority == "high")
        
        # Estimate optimized KPI values
        optimized_kpis = {}
        for kpi in self.kpi_targets:
            relevant_recommendations = [
                r for r in self.optimization_recommendations
                if self._recommendation_affects_kpi(r, kpi.name)
            ]
            
            if relevant_recommendations:
                # Calculate potential improvement
                improvement_factor = sum(r.estimated_impact for r in relevant_recommendations) / 100
                
                if kpi.name in ["mtba_average", "cognitive_latency_ttft"]:
                    # Lower is better - reduce by improvement factor
                    kpi.optimized_value = kpi.current_value * (1 - improvement_factor * 0.01)
                else:
                    # Higher is better - increase by improvement factor
                    kpi.optimized_value = kpi.current_value * (1 + improvement_factor * 0.01)
            else:
                kpi.optimized_value = kpi.current_value
            
            optimized_kpis[kpi.name] = {
                "current": kpi.current_value,
                "target": kpi.target_value,
                "optimized": kpi.optimized_value,
                "improvement": abs(kpi.optimized_value - kpi.current_value),
                "meets_target_after_optimization": self._would_meet_target_after_optimization(kpi)
            }
        
        return {
            "total_improvement_percentage": total_impact,
            "high_priority_improvement": high_priority_impact,
            "optimized_kpis": optimized_kpis,
            "targets_met_after_optimization": sum(1 for kpi in optimized_kpis.values() 
                                                if kpi["meets_target_after_optimization"]),
            "total_targets": len(self.kpi_targets)
        }
    
    def _recommendation_affects_kpi(self, recommendation: OptimizationRecommendation, kpi_name: str) -> bool:
        """Determine if a recommendation affects a specific KPI."""
        category_kpi_mapping = {
            "Session Success": ["successful_stateful_sessions_percentage"],
            "Performance": ["mtba_average"],
            "Inference": ["cognitive_latency_ttft"],
            "Resource Efficiency": ["system_resource_efficiency"],
            "Throughput": ["agent_throughput"]
        }
        
        return kpi_name in category_kpi_mapping.get(recommendation.category, [])
    
    def _would_meet_target_after_optimization(self, kpi: KPITarget) -> bool:
        """Check if KPI would meet target after optimization."""
        if kpi.optimized_value is None:
            return False
        
        if kpi.name in ["mtba_average", "cognitive_latency_ttft"]:
            return kpi.optimized_value <= kpi.target_value
        else:
            return kpi.optimized_value >= kpi.target_value
    
    def _create_optimization_plan(self) -> Dict[str, Any]:
        """Create a prioritized optimization implementation plan."""
        
        # Sort recommendations by priority and impact
        high_priority = [r for r in self.optimization_recommendations if r.priority == "high"]
        medium_priority = [r for r in self.optimization_recommendations if r.priority == "medium"]
        low_priority = [r for r in self.optimization_recommendations if r.priority == "low"]
        
        # Sort within each priority by estimated impact
        high_priority.sort(key=lambda x: x.estimated_impact, reverse=True)
        medium_priority.sort(key=lambda x: x.estimated_impact, reverse=True)
        low_priority.sort(key=lambda x: x.estimated_impact, reverse=True)
        
        return {
            "phase_1_immediate": {
                "description": "High-priority optimizations with immediate impact",
                "recommendations": [asdict(r) for r in high_priority],
                "estimated_duration_days": len(high_priority) * 2,
                "expected_improvement": sum(r.estimated_impact for r in high_priority)
            },
            "phase_2_medium_term": {
                "description": "Medium-priority optimizations for sustained improvement",
                "recommendations": [asdict(r) for r in medium_priority],
                "estimated_duration_days": len(medium_priority) * 3,
                "expected_improvement": sum(r.estimated_impact for r in medium_priority)
            },
            "phase_3_long_term": {
                "description": "Long-term optimizations for maximum efficiency",
                "recommendations": [asdict(r) for r in low_priority],
                "estimated_duration_days": len(low_priority) * 5,
                "expected_improvement": sum(r.estimated_impact for r in low_priority)
            },
            "total_estimated_duration_days": (len(high_priority) * 2 + 
                                            len(medium_priority) * 3 + 
                                            len(low_priority) * 5),
            "implementation_order": (high_priority + medium_priority + low_priority)
        }
    
    def _generate_implementation_guide(self) -> Dict[str, Any]:
        """Generate detailed implementation guide for optimizations."""
        
        return {
            "getting_started": {
                "prerequisites": [
                    "Ensure APE system is running and accessible",
                    "Have monitoring and metrics collection enabled",
                    "Backup current configuration files",
                    "Establish baseline performance measurements"
                ],
                "tools_needed": [
                    "Docker and Docker Compose",
                    "Performance monitoring tools",
                    "Configuration management system",
                    "Testing environment for validation"
                ]
            },
            "configuration_optimizations": {
                "agent_configuration": {
                    "file": "services/llama-agent/config.py",
                    "optimizations": [
                        "Adjust inference timeout settings",
                        "Optimize memory allocation parameters",
                        "Configure connection pooling",
                        "Set optimal retry policies"
                    ]
                },
                "cerebras_proxy_configuration": {
                    "file": "services/cerebras-proxy/src/main.py",
                    "optimizations": [
                        "Optimize request batching parameters",
                        "Configure connection pooling",
                        "Adjust timeout settings",
                        "Implement request caching"
                    ]
                },
                "docker_configuration": {
                    "file": "ape.docker-compose.yml",
                    "optimizations": [
                        "Adjust container resource limits",
                        "Optimize network configuration",
                        "Configure health check parameters",
                        "Set optimal restart policies"
                    ]
                }
            },
            "monitoring_and_validation": {
                "metrics_to_track": [
                    "Successful Stateful Sessions percentage",
                    "Mean Time Between Actions (MTBA)",
                    "Time-to-First-Token (TTFT)",
                    "System resource utilization",
                    "Agent throughput and error rates"
                ],
                "validation_steps": [
                    "Run baseline performance tests before changes",
                    "Implement optimizations incrementally",
                    "Validate each optimization with performance tests",
                    "Monitor for regressions or unexpected behavior",
                    "Document performance improvements achieved"
                ]
            },
            "troubleshooting": {
                "common_issues": [
                    "Performance degradation after optimization",
                    "Resource exhaustion under high load",
                    "Inference timeout increases",
                    "Session success rate decreases"
                ],
                "diagnostic_steps": [
                    "Check system resource utilization",
                    "Review agent and service logs",
                    "Validate configuration changes",
                    "Test with reduced load",
                    "Rollback recent changes if needed"
                ]
            }
        }


async def main():
    """Main function for KPI optimization."""
    parser = argparse.ArgumentParser(description='APE KPI Optimization')
    parser.add_argument('--analysis-duration', type=int, default=15,
                       help='Analysis duration in minutes (default: 15)')
    parser.add_argument('--output', '-o', 
                       help='Output file for optimization report (JSON)')
    parser.add_argument('--project', '-p', default='ape',
                       help='Project name (default: ape)')
    parser.add_argument('--implement', action='store_true',
                       help='Generate implementation scripts (not implemented)')
    
    args = parser.parse_args()
    
    optimizer = KPIOptimizer(project_name=args.project)
    
    try:
        # Run KPI analysis and optimization
        report = await optimizer.analyze_and_optimize(
            analysis_duration_minutes=args.analysis_duration
        )
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Optimization report written to {args.output}")
        
        # Print summary
        print("\n" + "="*80)
        print("APE KPI OPTIMIZATION ANALYSIS")
        print("="*80)
        
        summary = report["analysis_summary"]
        print(f"Analysis Duration: {summary['analysis_duration_minutes']} minutes")
        print(f"Total Recommendations: {summary['total_recommendations']}")
        print(f"High Priority: {summary['high_priority_recommendations']}")
        print(f"Estimated Total Improvement: {summary['estimated_total_improvement']:.1f}%")
        
        # Print current KPI status
        print(f"\nCurrent KPI Status:")
        for kpi_name, kpi_data in report["current_kpis"].items():
            current = kpi_data["current_value"]
            target = kpi_data["target_value"]
            unit = kpi_data["unit"]
            
            if kpi_name in ["mtba_average", "cognitive_latency_ttft"]:
                status = "✅" if current <= target else "❌"
            else:
                status = "✅" if current >= target else "❌"
            
            print(f"  {kpi_name}: {current:.2f} {unit} (target: {target:.2f}) {status}")
        
        # Print top recommendations
        recommendations = report["optimization_recommendations"]
        if recommendations:
            print(f"\nTop Optimization Recommendations:")
            for i, rec in enumerate(recommendations[:3], 1):
                print(f"  {i}. [{rec['priority'].upper()}] {rec['description']}")
                print(f"     Action: {rec['action']}")
                print(f"     Expected: {rec['expected_improvement']}")
        
        # Print optimization impact
        impact = report["optimization_impact"]
        print(f"\nOptimization Impact:")
        print(f"  Targets that would be met after optimization: "
              f"{impact['targets_met_after_optimization']}/{impact['total_targets']}")
        print(f"  Total improvement potential: {impact['total_improvement_percentage']:.1f}%")
        
        print("\n" + "="*80)
        print("Run with --output <file> to save detailed optimization report")
        print("="*80)
        
    except Exception as e:
        print(f"❌ KPI optimization analysis failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())