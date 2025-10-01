#!/usr/bin/env python3
"""
Performance Test Runner for APE
Orchestrates comprehensive performance validation for task 10.2

This script runs the complete performance validation suite including:
- Baseline performance validation
- Scaling tests up to 1000+ agents
- KPI optimization analysis
- Comprehensive reporting
"""

import os
import sys
import json
import asyncio
import argparse
import logging
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime
import tempfile


class PerformanceTestRunner:
    """
    Orchestrates comprehensive performance testing for APE system.
    
    Runs validation tests, optimization analysis, and generates
    comprehensive reports for performance targets and KPIs.
    """
    
    def __init__(self, project_name: str = "ape"):
        self.project_name = project_name
        self.logger = self._setup_logging()
        self.test_results = {}
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'/tmp/ape-performance-tests.log')
            ]
        )
        return logging.getLogger('performance-test-runner')
    
    async def run_comprehensive_tests(self, max_agents: int = 1000, 
                                    test_duration: int = 30,
                                    skip_optimization: bool = False) -> Dict[str, Any]:
        """
        Run comprehensive performance test suite.
        
        Args:
            max_agents: Maximum number of agents to test
            test_duration: Test duration in minutes
            skip_optimization: Skip optimization analysis
            
        Returns:
            Dict with comprehensive test results
        """
        test_start = datetime.utcnow()
        
        self.logger.info(
            "Starting comprehensive performance test suite",
            max_agents=max_agents,
            test_duration=test_duration
        )
        
        try:
            # 1. Pre-test system check
            await self._pre_test_system_check()
            
            # 2. Run performance validation
            validation_results = await self._run_performance_validation(
                max_agents, test_duration
            )
            
            # 3. Run KPI optimization analysis (if not skipped)
            optimization_results = None
            if not skip_optimization:
                optimization_results = await self._run_kpi_optimization()
            
            # 4. Generate comprehensive report
            test_end = datetime.utcnow()
            
            comprehensive_report = self._generate_comprehensive_report(
                test_start, test_end, validation_results, optimization_results
            )
            
            self.logger.info(
                "Comprehensive performance tests completed",
                duration_minutes=(test_end - test_start).total_seconds() / 60,
                overall_success=comprehensive_report["overall_success"]
            )
            
            return comprehensive_report
            
        except Exception as e:
            self.logger.error(f"Performance test suite failed: {e}")
            raise
    
    async def _pre_test_system_check(self):
        """Perform pre-test system checks."""
        self.logger.info("Performing pre-test system checks")
        
        checks = {
            "docker_available": self._check_docker_available(),
            "compose_file_exists": self._check_compose_file_exists(),
            "system_resources": self._check_system_resources(),
            "services_running": await self._check_services_running()
        }
        
        failed_checks = [name for name, result in checks.items() if not result]
        
        if failed_checks:
            raise RuntimeError(f"Pre-test checks failed: {failed_checks}")
        
        self.logger.info("All pre-test checks passed")
    
    def _check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _check_compose_file_exists(self) -> bool:
        """Check if Docker Compose file exists."""
        return os.path.exists('ape.docker-compose.yml')
    
    def _check_system_resources(self) -> bool:
        """Check if system has sufficient resources."""
        try:
            import psutil
            
            # Check available memory (need at least 8GB for high-scale tests)
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            
            # Check CPU cores (need at least 4 cores)
            cpu_count = psutil.cpu_count()
            
            # Check disk space (need at least 10GB free)
            disk = psutil.disk_usage('/')
            free_gb = disk.free / (1024**3)
            
            sufficient_resources = (
                available_gb >= 8.0 and
                cpu_count >= 4 and
                free_gb >= 10.0
            )
            
            if not sufficient_resources:
                self.logger.warning(
                    "System resources may be insufficient for high-scale testing",
                    available_memory_gb=available_gb,
                    cpu_cores=cpu_count,
                    free_disk_gb=free_gb
                )
            
            return True  # Don't fail on resource warnings
            
        except ImportError:
            self.logger.warning("Could not check system resources (psutil not available)")
            return True
    
    async def _check_services_running(self) -> bool:
        """Check if required services are running."""
        try:
            # Check if any APE containers are running
            result = subprocess.run([
                'docker', 'ps', '--filter', f'label=com.docker.compose.project={self.project_name}',
                '--format', '{{.Names}}'
            ], capture_output=True, text=True)
            
            running_containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            if not running_containers:
                self.logger.info("No APE containers currently running - will start fresh")
            else:
                self.logger.info(f"Found {len(running_containers)} running APE containers")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking running services: {e}")
            return False
    
    async def _run_performance_validation(self, max_agents: int, 
                                        test_duration: int) -> Dict[str, Any]:
        """Run performance validation tests."""
        self.logger.info("Running performance validation tests")
        
        # Create temporary file for validation results
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            validation_output_file = f.name
        
        try:
            # Run performance validation script
            cmd = [
                sys.executable, 'scripts/performance-validation.py',
                '--max-agents', str(max_agents),
                '--test-duration', str(test_duration),
                '--project', self.project_name,
                '--output', validation_output_file
            ]
            
            self.logger.info(f"Running command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Log output
            if stdout:
                self.logger.info(f"Validation stdout: {stdout.decode()}")
            if stderr:
                self.logger.warning(f"Validation stderr: {stderr.decode()}")
            
            # Read results
            if os.path.exists(validation_output_file):
                with open(validation_output_file, 'r') as f:
                    validation_results = json.load(f)
                
                validation_results['exit_code'] = process.returncode
                validation_results['stdout'] = stdout.decode()
                validation_results['stderr'] = stderr.decode()
                
                return validation_results
            else:
                raise RuntimeError("Performance validation did not generate output file")
                
        finally:
            # Clean up temporary file
            if os.path.exists(validation_output_file):
                os.unlink(validation_output_file)
    
    async def _run_kpi_optimization(self) -> Dict[str, Any]:
        """Run KPI optimization analysis."""
        self.logger.info("Running KPI optimization analysis")
        
        # Create temporary file for optimization results
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            optimization_output_file = f.name
        
        try:
            # Run KPI optimization script
            cmd = [
                sys.executable, 'scripts/kpi-optimization.py',
                '--analysis-duration', '15',
                '--project', self.project_name,
                '--output', optimization_output_file
            ]
            
            self.logger.info(f"Running command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Log output
            if stdout:
                self.logger.info(f"Optimization stdout: {stdout.decode()}")
            if stderr:
                self.logger.warning(f"Optimization stderr: {stderr.decode()}")
            
            # Read results
            if os.path.exists(optimization_output_file):
                with open(optimization_output_file, 'r') as f:
                    optimization_results = json.load(f)
                
                optimization_results['exit_code'] = process.returncode
                optimization_results['stdout'] = stdout.decode()
                optimization_results['stderr'] = stderr.decode()
                
                return optimization_results
            else:
                self.logger.warning("KPI optimization did not generate output file")
                return {"error": "No optimization results generated"}
                
        finally:
            # Clean up temporary file
            if os.path.exists(optimization_output_file):
                os.unlink(optimization_output_file)
    
    def _generate_comprehensive_report(self, test_start: datetime, test_end: datetime,
                                     validation_results: Dict[str, Any],
                                     optimization_results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        
        # Determine overall success
        validation_success = (
            validation_results.get('exit_code', 1) == 0 and
            validation_results.get('validation_summary', {}).get('overall_success', False)
        )
        
        optimization_success = (
            optimization_results is None or  # Skipped
            optimization_results.get('exit_code', 1) == 0
        )
        
        overall_success = validation_success and optimization_success
        
        # Extract key metrics
        validation_summary = validation_results.get('validation_summary', {})
        scaling_validation = validation_results.get('scaling_validation', {})
        performance_targets = validation_results.get('performance_targets', {})
        kpi_validation = validation_results.get('kpi_validation', {})
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            validation_results, optimization_results, overall_success
        )
        
        # Generate recommendations
        recommendations = self._generate_consolidated_recommendations(
            validation_results, optimization_results
        )
        
        comprehensive_report = {
            "test_execution": {
                "start_time": test_start.isoformat(),
                "end_time": test_end.isoformat(),
                "total_duration_minutes": (test_end - test_start).total_seconds() / 60,
                "overall_success": overall_success,
                "validation_success": validation_success,
                "optimization_success": optimization_success
            },
            "executive_summary": executive_summary,
            "performance_validation": {
                "summary": validation_summary,
                "scaling_results": scaling_validation,
                "performance_targets": performance_targets,
                "kpi_validation": kpi_validation,
                "full_results": validation_results
            },
            "optimization_analysis": optimization_results,
            "consolidated_recommendations": recommendations,
            "next_steps": self._generate_next_steps(overall_success, recommendations),
            "appendix": {
                "test_configuration": {
                    "project_name": self.project_name,
                    "max_agents_tested": validation_results.get('scaling_validation', {}).get('max_achieved_agents', 0),
                    "test_duration_minutes": validation_summary.get('duration_minutes', 0)
                },
                "system_information": self._get_system_information()
            }
        }
        
        return comprehensive_report
    
    def _generate_executive_summary(self, validation_results: Dict[str, Any],
                                  optimization_results: Optional[Dict[str, Any]],
                                  overall_success: bool) -> Dict[str, Any]:
        """Generate executive summary of test results."""
        
        validation_summary = validation_results.get('validation_summary', {})
        scaling_validation = validation_results.get('scaling_validation', {})
        
        # Key achievements
        achievements = []
        concerns = []
        
        # Scaling achievements
        max_agents = scaling_validation.get('max_achieved_agents', 0)
        if max_agents >= 1000:
            achievements.append(f"Successfully scaled to {max_agents} concurrent agents")
        elif max_agents >= 500:
            achievements.append(f"Scaled to {max_agents} agents (partial success)")
            concerns.append("Did not achieve full 1000+ agent target")
        else:
            concerns.append(f"Only achieved {max_agents} concurrent agents (target: 1000+)")
        
        # Performance achievements
        performance_targets = validation_results.get('performance_targets', {})
        mtba_status = performance_targets.get('mtba_validation', {}).get('status', 'UNKNOWN')
        ttft_status = performance_targets.get('cognitive_latency_validation', {}).get('status', 'UNKNOWN')
        
        if mtba_status == 'PASS':
            achievements.append("MTBA performance targets met")
        else:
            concerns.append("MTBA performance below target")
        
        if ttft_status == 'PASS':
            achievements.append("Cognitive latency (TTFT) targets met")
        else:
            concerns.append("Cognitive latency exceeds targets")
        
        # KPI achievements
        kpi_validation = validation_results.get('kpi_validation', {})
        session_success = kpi_validation.get('successful_stateful_sessions', {})
        if session_success.get('status') == 'PASS':
            achievements.append("Session success rate targets met")
        else:
            concerns.append("Session success rate below target")
        
        # Optimization potential
        optimization_potential = 0
        if optimization_results:
            optimization_impact = optimization_results.get('optimization_impact', {})
            optimization_potential = optimization_impact.get('total_improvement_percentage', 0)
        
        return {
            "overall_status": "PASS" if overall_success else "FAIL",
            "key_achievements": achievements,
            "key_concerns": concerns,
            "optimization_potential_percentage": optimization_potential,
            "readiness_assessment": self._assess_production_readiness(overall_success, concerns),
            "critical_metrics": {
                "max_concurrent_agents": max_agents,
                "mtba_performance": mtba_status,
                "cognitive_latency": ttft_status,
                "session_success_rate": session_success.get('status', 'UNKNOWN')
            }
        }
    
    def _assess_production_readiness(self, overall_success: bool, concerns: List[str]) -> str:
        """Assess production readiness based on test results."""
        if overall_success and not concerns:
            return "READY - All targets met, system ready for production deployment"
        elif overall_success and len(concerns) <= 2:
            return "MOSTLY_READY - Minor concerns identified, consider optimization before production"
        elif len(concerns) <= 3:
            return "NEEDS_OPTIMIZATION - Significant optimization required before production"
        else:
            return "NOT_READY - Major issues identified, extensive work required"
    
    def _generate_consolidated_recommendations(self, validation_results: Dict[str, Any],
                                            optimization_results: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate consolidated recommendations from all test results."""
        recommendations = []
        
        # Add validation recommendations
        validation_recs = validation_results.get('recommendations', [])
        for rec in validation_recs:
            recommendations.append({
                "source": "performance_validation",
                "priority": "high",
                "category": "performance",
                "recommendation": rec
            })
        
        # Add optimization recommendations
        if optimization_results:
            opt_recs = optimization_results.get('optimization_recommendations', [])
            for rec in opt_recs:
                recommendations.append({
                    "source": "kpi_optimization",
                    "priority": rec.get('priority', 'medium'),
                    "category": rec.get('category', 'optimization'),
                    "recommendation": rec.get('description', ''),
                    "action": rec.get('action', ''),
                    "expected_improvement": rec.get('expected_improvement', ''),
                    "implementation_steps": rec.get('implementation_steps', [])
                })
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))
        
        return recommendations
    
    def _generate_next_steps(self, overall_success: bool, 
                           recommendations: List[Dict[str, Any]]) -> List[str]:
        """Generate next steps based on test results."""
        next_steps = []
        
        if overall_success:
            next_steps.extend([
                "✅ System meets performance targets - ready for production consideration",
                "📊 Review optimization recommendations for further improvements",
                "🔄 Establish regular performance monitoring and validation schedule",
                "📋 Document current configuration as baseline for future tests"
            ])
        else:
            next_steps.extend([
                "❌ Address critical performance issues identified in validation",
                "🔧 Implement high-priority optimization recommendations",
                "🧪 Re-run performance validation after implementing fixes",
                "📈 Monitor system performance during optimization implementation"
            ])
        
        # Add specific next steps based on recommendations
        high_priority_recs = [r for r in recommendations if r.get('priority') == 'high']
        if high_priority_recs:
            next_steps.append(f"🚨 Focus on {len(high_priority_recs)} high-priority recommendations first")
        
        next_steps.extend([
            "📚 Review detailed test results and optimization analysis",
            "🔍 Consider running focused tests on specific problem areas",
            "💡 Engage with APE development team for additional optimization guidance"
        ])
        
        return next_steps
    
    def _get_system_information(self) -> Dict[str, Any]:
        """Get system information for the report."""
        try:
            import psutil
            import platform
            
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "disk_total_gb": psutil.disk_usage('/').total / (1024**3),
                "timestamp": datetime.utcnow().isoformat()
            }
        except ImportError:
            return {
                "platform": "unknown",
                "timestamp": datetime.utcnow().isoformat()
            }


async def main():
    """Main function for performance test runner."""
    parser = argparse.ArgumentParser(description='APE Performance Test Runner')
    parser.add_argument('--max-agents', type=int, default=1000,
                       help='Maximum number of agents to test (default: 1000)')
    parser.add_argument('--test-duration', type=int, default=30,
                       help='Test duration in minutes (default: 30)')
    parser.add_argument('--skip-optimization', action='store_true',
                       help='Skip KPI optimization analysis')
    parser.add_argument('--output', '-o', 
                       help='Output file for comprehensive report (JSON)')
    parser.add_argument('--project', '-p', default='ape',
                       help='Project name (default: ape)')
    
    args = parser.parse_args()
    
    runner = PerformanceTestRunner(project_name=args.project)
    
    try:
        # Run comprehensive test suite
        report = await runner.run_comprehensive_tests(
            max_agents=args.max_agents,
            test_duration=args.test_duration,
            skip_optimization=args.skip_optimization
        )
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Comprehensive test report written to {args.output}")
        
        # Print executive summary
        print("\n" + "="*100)
        print("APE COMPREHENSIVE PERFORMANCE TEST RESULTS")
        print("="*100)
        
        exec_summary = report["executive_summary"]
        print(f"Overall Status: {exec_summary['overall_status']}")
        print(f"Production Readiness: {exec_summary['readiness_assessment']}")
        
        if exec_summary["key_achievements"]:
            print(f"\n✅ Key Achievements:")
            for achievement in exec_summary["key_achievements"]:
                print(f"   • {achievement}")
        
        if exec_summary["key_concerns"]:
            print(f"\n⚠️  Key Concerns:")
            for concern in exec_summary["key_concerns"]:
                print(f"   • {concern}")
        
        print(f"\n📊 Critical Metrics:")
        metrics = exec_summary["critical_metrics"]
        print(f"   • Max Concurrent Agents: {metrics['max_concurrent_agents']}")
        print(f"   • MTBA Performance: {metrics['mtba_performance']}")
        print(f"   • Cognitive Latency: {metrics['cognitive_latency']}")
        print(f"   • Session Success Rate: {metrics['session_success_rate']}")
        
        if exec_summary["optimization_potential_percentage"] > 0:
            print(f"\n🚀 Optimization Potential: {exec_summary['optimization_potential_percentage']:.1f}%")
        
        # Print next steps
        next_steps = report["next_steps"]
        if next_steps:
            print(f"\n📋 Next Steps:")
            for step in next_steps[:5]:  # Show first 5 steps
                print(f"   {step}")
        
        print("\n" + "="*100)
        print("For detailed results and recommendations, see the full report JSON file")
        print("="*100)
        
        # Exit with appropriate code
        sys.exit(0 if report["test_execution"]["overall_success"] else 1)
        
    except Exception as e:
        print(f"❌ Performance test suite failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())