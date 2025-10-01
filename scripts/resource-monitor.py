#!/usr/bin/env python3
"""
Resource monitoring script for APE containers
Implements resource tracking for Requirements 6.4
"""

import os
import sys
import time
import json
import asyncio
import logging
import argparse
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import docker
import psutil

@dataclass
class ContainerMetrics:
    """Container resource metrics"""
    container_id: str
    name: str
    service: str
    cpu_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    network_rx_mb: float
    network_tx_mb: float
    disk_read_mb: float
    disk_write_mb: float
    status: str
    uptime_seconds: float
    restart_count: int

@dataclass
class SystemMetrics:
    """System-wide resource metrics"""
    timestamp: str
    total_containers: int
    running_containers: int
    agent_containers: int
    total_cpu_percent: float
    total_memory_usage_mb: float
    total_memory_available_mb: float
    memory_percent: float
    disk_usage_percent: float
    network_connections: int

class ResourceMonitor:
    def __init__(self, project_name: str = "ape", monitoring_interval: int = 10):
        self.project_name = project_name
        self.monitoring_interval = monitoring_interval
        self.docker_client = docker.from_env()
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'/tmp/ape-resource-monitor.log')
            ]
        )
        return logging.getLogger('resource-monitor')
    
    def get_ape_containers(self) -> List[docker.models.containers.Container]:
        """Get all APE-related containers"""
        try:
            containers = self.docker_client.containers.list(all=True)
            ape_containers = []
            
            for container in containers:
                # Check if container belongs to APE project
                labels = container.labels or {}
                compose_project = labels.get('com.docker.compose.project', '')
                service_name = labels.get('com.docker.compose.service', '')
                
                if (compose_project.startswith(self.project_name) or 
                    service_name in ['llama_agent', 'mcp_gateway', 'cerebras_proxy'] or
                    'ape' in container.name.lower()):
                    ape_containers.append(container)
            
            return ape_containers
            
        except Exception as e:
            self.logger.error(f"Error getting APE containers: {e}")
            return []
    
    def get_container_metrics(self, container: docker.models.containers.Container) -> Optional[ContainerMetrics]:
        """Get detailed metrics for a single container"""
        try:
            # Refresh container info
            container.reload()
            
            # Get container stats
            stats = container.stats(stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_count = len(stats['cpu_stats']['cpu_usage']['percpu_usage'])
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0
            
            # Memory metrics
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_usage_mb = memory_usage / (1024 * 1024)
            memory_limit_mb = memory_limit / (1024 * 1024)
            memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            
            # Network metrics
            network_rx_bytes = 0
            network_tx_bytes = 0
            if 'networks' in stats:
                for interface in stats['networks'].values():
                    network_rx_bytes += interface['rx_bytes']
                    network_tx_bytes += interface['tx_bytes']
            
            network_rx_mb = network_rx_bytes / (1024 * 1024)
            network_tx_mb = network_tx_bytes / (1024 * 1024)
            
            # Disk I/O metrics
            disk_read_bytes = 0
            disk_write_bytes = 0
            if 'blkio_stats' in stats and 'io_service_bytes_recursive' in stats['blkio_stats']:
                for entry in stats['blkio_stats']['io_service_bytes_recursive']:
                    if entry['op'] == 'Read':
                        disk_read_bytes += entry['value']
                    elif entry['op'] == 'Write':
                        disk_write_bytes += entry['value']
            
            disk_read_mb = disk_read_bytes / (1024 * 1024)
            disk_write_mb = disk_write_bytes / (1024 * 1024)
            
            # Container info
            labels = container.labels or {}
            service_name = labels.get('com.docker.compose.service', 'unknown')
            
            # Uptime calculation
            created_time = datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00'))
            uptime_seconds = (datetime.now(created_time.tzinfo) - created_time).total_seconds()
            
            # Restart count
            restart_count = container.attrs['RestartCount']
            
            return ContainerMetrics(
                container_id=container.id[:12],
                name=container.name,
                service=service_name,
                cpu_percent=round(cpu_percent, 2),
                memory_usage_mb=round(memory_usage_mb, 2),
                memory_limit_mb=round(memory_limit_mb, 2),
                memory_percent=round(memory_percent, 2),
                network_rx_mb=round(network_rx_mb, 2),
                network_tx_mb=round(network_tx_mb, 2),
                disk_read_mb=round(disk_read_mb, 2),
                disk_write_mb=round(disk_write_mb, 2),
                status=container.status,
                uptime_seconds=round(uptime_seconds, 2),
                restart_count=restart_count
            )
            
        except Exception as e:
            self.logger.error(f"Error getting metrics for container {container.name}: {e}")
            return None
    
    def get_system_metrics(self, container_metrics: List[ContainerMetrics]) -> SystemMetrics:
        """Get system-wide metrics"""
        try:
            # Container counts
            total_containers = len(container_metrics)
            running_containers = len([c for c in container_metrics if c.status == 'running'])
            agent_containers = len([c for c in container_metrics if 'agent' in c.service])
            
            # System CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Network connections
            network_connections = len(psutil.net_connections())
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                total_containers=total_containers,
                running_containers=running_containers,
                agent_containers=agent_containers,
                total_cpu_percent=round(cpu_percent, 2),
                total_memory_usage_mb=round(memory_usage_mb, 2),
                total_memory_available_mb=round(memory_available_mb, 2),
                memory_percent=round(memory.percent, 2),
                disk_usage_percent=round(disk_usage_percent, 2),
                network_connections=network_connections
            )
            
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                total_containers=0, running_containers=0, agent_containers=0,
                total_cpu_percent=0.0, total_memory_usage_mb=0.0, 
                total_memory_available_mb=0.0, memory_percent=0.0,
                disk_usage_percent=0.0, network_connections=0
            )
    
    def check_resource_thresholds(self, system_metrics: SystemMetrics, 
                                container_metrics: List[ContainerMetrics]) -> List[str]:
        """Check for resource threshold violations"""
        alerts = []
        
        # System-level thresholds
        if system_metrics.memory_percent > 85:
            alerts.append(f"HIGH_MEMORY: System memory usage at {system_metrics.memory_percent}%")
        
        if system_metrics.total_cpu_percent > 80:
            alerts.append(f"HIGH_CPU: System CPU usage at {system_metrics.total_cpu_percent}%")
        
        if system_metrics.disk_usage_percent > 90:
            alerts.append(f"HIGH_DISK: Disk usage at {system_metrics.disk_usage_percent}%")
        
        # Container-level thresholds
        for container in container_metrics:
            if container.status == 'running':
                if container.memory_percent > 90:
                    alerts.append(f"CONTAINER_HIGH_MEMORY: {container.name} using {container.memory_percent}% memory")
                
                if container.cpu_percent > 95:
                    alerts.append(f"CONTAINER_HIGH_CPU: {container.name} using {container.cpu_percent}% CPU")
                
                if container.restart_count > 3:
                    alerts.append(f"CONTAINER_RESTARTS: {container.name} has restarted {container.restart_count} times")
        
        return alerts
    
    def generate_report(self, system_metrics: SystemMetrics, 
                       container_metrics: List[ContainerMetrics]) -> Dict:
        """Generate comprehensive resource report"""
        # Calculate aggregated metrics
        total_memory_usage = sum(c.memory_usage_mb for c in container_metrics if c.status == 'running')
        total_cpu_usage = sum(c.cpu_percent for c in container_metrics if c.status == 'running')
        avg_memory_per_agent = total_memory_usage / max(1, system_metrics.agent_containers)
        avg_cpu_per_agent = total_cpu_usage / max(1, system_metrics.agent_containers)
        
        # Service breakdown
        service_breakdown = {}
        for container in container_metrics:
            service = container.service
            if service not in service_breakdown:
                service_breakdown[service] = {
                    'count': 0, 'running': 0, 'memory_mb': 0, 'cpu_percent': 0
                }
            
            service_breakdown[service]['count'] += 1
            if container.status == 'running':
                service_breakdown[service]['running'] += 1
                service_breakdown[service]['memory_mb'] += container.memory_usage_mb
                service_breakdown[service]['cpu_percent'] += container.cpu_percent
        
        # Check alerts
        alerts = self.check_resource_thresholds(system_metrics, container_metrics)
        
        return {
            'timestamp': system_metrics.timestamp,
            'system': asdict(system_metrics),
            'containers': [asdict(c) for c in container_metrics],
            'aggregated': {
                'total_memory_usage_mb': round(total_memory_usage, 2),
                'total_cpu_usage_percent': round(total_cpu_usage, 2),
                'avg_memory_per_agent_mb': round(avg_memory_per_agent, 2),
                'avg_cpu_per_agent_percent': round(avg_cpu_per_agent, 2)
            },
            'service_breakdown': service_breakdown,
            'alerts': alerts,
            'health_status': 'healthy' if not alerts else 'warning'
        }
    
    async def monitor_loop(self, output_file: Optional[str] = None, 
                          console_output: bool = True) -> None:
        """Main monitoring loop"""
        self.logger.info(f"Starting resource monitoring for project: {self.project_name}")
        self.logger.info(f"Monitoring interval: {self.monitoring_interval}s")
        
        try:
            while True:
                # Get container metrics
                containers = self.get_ape_containers()
                container_metrics = []
                
                for container in containers:
                    metrics = self.get_container_metrics(container)
                    if metrics:
                        container_metrics.append(metrics)
                
                # Get system metrics
                system_metrics = self.get_system_metrics(container_metrics)
                
                # Generate report
                report = self.generate_report(system_metrics, container_metrics)
                
                # Output results
                if console_output:
                    self._print_console_report(report)
                
                if output_file:
                    self._write_json_report(report, output_file)
                
                # Log alerts
                for alert in report['alerts']:
                    self.logger.warning(f"ALERT: {alert}")
                
                await asyncio.sleep(self.monitoring_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"Error in monitoring loop: {e}")
    
    def _print_console_report(self, report: Dict) -> None:
        """Print formatted report to console"""
        print(f"\n{'='*80}")
        print(f"APE Resource Monitor - {report['timestamp']}")
        print(f"{'='*80}")
        
        # System overview
        system = report['system']
        print(f"System: CPU {system['total_cpu_percent']}% | "
              f"Memory {system['memory_percent']}% | "
              f"Disk {system['disk_usage_percent']}%")
        print(f"Containers: {system['running_containers']}/{system['total_containers']} running | "
              f"Agents: {system['agent_containers']}")
        
        # Service breakdown
        print(f"\nService Breakdown:")
        for service, metrics in report['service_breakdown'].items():
            print(f"  {service}: {metrics['running']}/{metrics['count']} running | "
                  f"Memory: {metrics['memory_mb']:.1f}MB | "
                  f"CPU: {metrics['cpu_percent']:.1f}%")
        
        # Alerts
        if report['alerts']:
            print(f"\n⚠️  ALERTS ({len(report['alerts'])}):")
            for alert in report['alerts']:
                print(f"  - {alert}")
        else:
            print(f"\n✅ No alerts - System healthy")
    
    def _write_json_report(self, report: Dict, output_file: str) -> None:
        """Write report to JSON file"""
        try:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error writing report to {output_file}: {e}")

def main():
    parser = argparse.ArgumentParser(description='APE Resource Monitor')
    parser.add_argument('--project', '-p', default='ape', 
                       help='Project name to monitor (default: ape)')
    parser.add_argument('--interval', '-i', type=int, default=10,
                       help='Monitoring interval in seconds (default: 10)')
    parser.add_argument('--output', '-o', 
                       help='Output file for JSON reports')
    parser.add_argument('--no-console', action='store_true',
                       help='Disable console output')
    
    args = parser.parse_args()
    
    monitor = ResourceMonitor(
        project_name=args.project,
        monitoring_interval=args.interval
    )
    
    asyncio.run(monitor.monitor_loop(
        output_file=args.output,
        console_output=not args.no_console
    ))

if __name__ == '__main__':
    main()