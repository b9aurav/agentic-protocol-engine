"""
Unit tests for Cerebras Proxy - Performance Metrics and API Compatibility
Tests requirements 2.1 and 2.4: API compatibility, TTFT measurement, and token tracking
"""

import pytest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient

# Set test environment variables
os.environ["CEREBRAS_API_KEY"] = "test-cerebras-key"
os.environ["APE_API_KEY"] = "test-ape-key"

from src.main import app
from src.metrics import MetricsCollector


class TestCerebrasProxyMetrics:
    """Test Cerebras Proxy performance metrics and API compatibility"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-ape-key"}
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_models_endpoint_openai_compatible(self, client):
        """Test OpenAI-compatible models endpoint"""
        response = client.get("/v1/models")
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        assert data["data"][0]["id"] == "llama3.1-8b"
    
    def test_metrics_endpoint_prometheus_format(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        content = response.text
        assert "cerebras_proxy_requests_total" in content
        assert "cerebras_proxy_ttft_seconds" in content
        assert "cerebras_proxy_tokens_total" in content
    
    def test_api_validation_error_handling(self, client, auth_headers):
        """Test API request validation and error handling"""
        # Test invalid message role
        invalid_request = {"messages": [{"role": "invalid", "content": "test"}]}
        response = client.post("/v1/chat/completions", json=invalid_request, headers=auth_headers)
        assert response.status_code == 422
        
        # Test missing messages
        response = client.post("/v1/chat/completions", json={"model": "test"}, headers=auth_headers)
        assert response.status_code == 422
    
    def test_authentication_required(self, client):
        """Test authentication is required for API endpoints"""
        request_data = {"messages": [{"role": "user", "content": "test"}]}
        
        # No auth header
        response = client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 401
        
        # Invalid auth format
        headers = {"Authorization": "Invalid format"}
        response = client.post("/v1/chat/completions", json=request_data, headers=headers)
        assert response.status_code == 401


class TestMetricsCollection:
    """Test performance metrics collection functionality"""
    
    def test_metrics_collector_initialization(self):
        """Test MetricsCollector initializes correctly"""
        collector = MetricsCollector(max_metrics=100)
        assert collector.max_metrics == 100
        assert collector._total_requests == 0
        assert collector._total_tokens == 0
    
    def test_ttft_and_token_tracking(self):
        """Test TTFT measurement and token usage tracking"""
        collector = MetricsCollector()
        
        # Record inference metrics
        collector.record_inference_request(
            ttft=0.5,  # Time to First Token
            total_time=1.2,
            total_tokens=100,
            prompt_tokens=60,
            completion_tokens=40,
            model="llama3.1-8b",
            cost_estimate=0.001
        )
        
        # Verify metrics recorded
        assert collector._total_requests == 1
        assert collector._total_tokens == 100
        assert len(collector._metrics) == 1
        
        # Verify metric details
        metric = collector._metrics[0]
        assert metric.ttft == 0.5
        assert metric.total_tokens == 100
        assert metric.prompt_tokens == 60
        assert metric.completion_tokens == 40
    
    def test_performance_statistics_calculation(self):
        """Test performance statistics calculation"""
        collector = MetricsCollector()
        
        # Add multiple metrics
        ttfts = [0.1, 0.2, 0.3, 0.4, 0.5]
        for i, ttft in enumerate(ttfts):
            collector.record_inference_request(
                ttft=ttft,
                total_time=ttft * 2,
                total_tokens=(i + 1) * 10,
                prompt_tokens=(i + 1) * 5,
                completion_tokens=(i + 1) * 5,
                model="llama3.1-8b"
            )
        
        stats = collector.get_summary_stats()
        
        # Verify statistics
        assert stats["total_requests"] == 5
        assert stats["avg_ttft"] == 0.3  # Average of ttfts
        assert stats["total_tokens"] == 150  # Sum of all tokens
        assert stats["p95_ttft"] == 0.5  # 95th percentile
    
    def test_prometheus_metrics_format(self):
        """Test Prometheus metrics format generation"""
        collector = MetricsCollector()
        
        collector.record_inference_request(
            ttft=0.5,
            total_time=1.0,
            total_tokens=100,
            prompt_tokens=60,
            completion_tokens=40,
            model="llama3.1-8b",
            cost_estimate=0.001
        )
        
        prometheus_output = collector.get_prometheus_metrics()
        
        # Verify Prometheus format
        assert "# HELP cerebras_proxy_requests_total" in prometheus_output
        assert "cerebras_proxy_requests_total 1" in prometheus_output
        assert "cerebras_proxy_ttft_seconds_avg 0.5000" in prometheus_output
        assert "cerebras_proxy_tokens_total 100" in prometheus_output
        assert "cerebras_proxy_cost_total 0.001000" in prometheus_output
    
    def test_cost_estimation(self):
        """Test token-based cost estimation"""
        collector = MetricsCollector()
        
        cost = collector.calculate_cost_estimate(
            prompt_tokens=1000,
            completion_tokens=500,
            model="llama3.1-8b"
        )
        
        # Verify cost calculation (based on pricing in metrics.py)
        expected_cost = (1000 * 0.10 / 1_000_000) + (500 * 0.10 / 1_000_000)
        assert abs(cost - expected_cost) < 0.000001
    
    def test_metrics_max_size_limit(self):
        """Test metrics list respects maximum size limit"""
        collector = MetricsCollector(max_metrics=3)
        
        # Add more metrics than the limit
        for i in range(5):
            collector.record_inference_request(
                ttft=0.1,
                total_time=0.5,
                total_tokens=10,
                prompt_tokens=5,
                completion_tokens=5,
                model="llama3.1-8b"
            )
        
        # Should only keep the last 3 metrics
        assert len(collector._metrics) == 3
        assert collector._total_requests == 5  # Counter should still be accurate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])