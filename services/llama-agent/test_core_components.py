#!/usr/bin/env python3
"""
Core unit tests for Llama Agent components.
Tests tool call generation, validation, session context management, and LLM response mocking.
This version focuses on testable components without external dependencies.

Requirements: 1.3, 7.5
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the core components to test
from models import (
    MCPToolCall, HTTPMethod, AgentSessionContext, ToolExecution, AgentConfig
)
from session_tracker import SessionSuccessTracker, SessionOutcome, TransactionType


class TestMCPToolCallValidation(unittest.TestCase):
    """Test MCP tool call generation and validation."""
    
    def test_mcp_tool_call_creation(self):
        """Test creating valid MCP tool calls."""
        # Test GET request
        get_call = MCPToolCall(
            target_api_name="test_api",
            http_method=HTTPMethod.GET,
            endpoint_path="/api/users",
            session_headers={"Authorization": "Bearer token123"}
        )
        
        self.assertEqual(get_call.target_api_name, "test_api")
        self.assertEqual(get_call.http_method, HTTPMethod.GET)
        self.assertEqual(get_call.endpoint_path, "/api/users")
        self.assertIsNone(get_call.request_payload)
        self.assertEqual(get_call.session_headers["Authorization"], "Bearer token123")
        
        # Test POST request with payload
        post_call = MCPToolCall(
            target_api_name="test_api",
            http_method=HTTPMethod.POST,
            endpoint_path="/api/login",
            request_payload={"username": "test", "password": "pass"},
            session_headers={"Content-Type": "application/json"}
        )
        
        self.assertEqual(post_call.http_method, HTTPMethod.POST)
        self.assertEqual(post_call.request_payload["username"], "test")
        
    def test_mcp_tool_call_serialization(self):
        """Test MCP tool call serialization to dict."""
        tool_call = MCPToolCall(
            target_api_name="sut_api",
            http_method=HTTPMethod.PUT,
            endpoint_path="/api/profile",
            request_payload={"name": "John Doe"},
            session_headers={"X-Session-Token": "abc123"}
        )
        
        serialized = tool_call.model_dump()
        
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["target_api_name"], "sut_api")
        self.assertEqual(serialized["http_method"], "PUT")
        self.assertEqual(serialized["endpoint_path"], "/api/profile")
        self.assertEqual(serialized["request_payload"]["name"], "John Doe")
        
    def test_http_method_enum_validation(self):
        """Test HTTP method enum validation."""
        # Valid methods
        for method in [HTTPMethod.GET, HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.DELETE]:
            tool_call = MCPToolCall(
                target_api_name="test",
                http_method=method,
                endpoint_path="/test"
            )
            self.assertEqual(tool_call.http_method, method)
        
        # Test enum values
        self.assertEqual(HTTPMethod.GET.value, "GET")
        self.assertEqual(HTTPMethod.POST.value, "POST")
        
    def test_mcp_tool_call_validation_errors(self):
        """Test MCP tool call validation with invalid data."""
        # Test missing required fields
        with self.assertRaises(Exception):  # Pydantic validation error
            MCPToolCall()
        
        # Test invalid HTTP method (this should work with enum)
        try:
            tool_call = MCPToolCall(
                target_api_name="test",
                http_method=HTTPMethod.GET,
                endpoint_path="/test"
            )
            self.assertEqual(tool_call.http_method, HTTPMethod.GET)
        except Exception as e:
            self.fail(f"Valid HTTP method should not raise exception: {e}")


class TestAgentSessionContext(unittest.TestCase):
    """Test agent session context management."""
    
    def test_session_context_creation(self):
        """Test creating agent session context."""
        session_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        
        context = AgentSessionContext(
            session_id=session_id,
            trace_id=trace_id,
            goal="Complete user login flow"
        )
        
        self.assertEqual(context.session_id, session_id)
        self.assertEqual(context.trace_id, trace_id)
        self.assertEqual(context.goal, "Complete user login flow")
        self.assertEqual(context.current_step, 0)
        self.assertEqual(len(context.execution_history), 0)
        self.assertIsInstance(context.start_time, datetime)
        
    def test_session_context_execution_tracking(self):
        """Test tracking tool executions in session context."""
        context = AgentSessionContext(
            session_id="test-session",
            trace_id="test-trace",
            goal="Test goal"
        )
        
        # Add successful execution
        execution1 = ToolExecution(
            tool_name="http_get",
            parameters={"api_name": "sut_api", "path": "/api/users"},
            response={"status_code": 200, "data": {"users": []}},
            execution_time=0.5,
            success=True
        )
        context.add_execution(execution1)
        
        self.assertEqual(context.current_step, 1)
        self.assertEqual(len(context.execution_history), 1)
        self.assertTrue(context.execution_history[0].success)
        
        # Add failed execution
        execution2 = ToolExecution(
            tool_name="http_post",
            parameters={"api_name": "sut_api", "path": "/api/login"},
            response={"status_code": 401, "error": "Unauthorized"},
            execution_time=0.3,
            success=False,
            error_message="Authentication failed"
        )
        context.add_execution(execution2)
        
        self.assertEqual(context.current_step, 2)
        self.assertEqual(len(context.execution_history), 2)
        self.assertFalse(context.execution_history[1].success)
        
    def test_session_context_expiration(self):
        """Test session context expiration logic."""
        context = AgentSessionContext(
            session_id="test-session",
            trace_id="test-trace", 
            goal="Test goal"
        )
        
        # Fresh session should not be expired
        self.assertFalse(context.is_expired(timeout_minutes=30))
        
        # Simulate old last action time
        context.last_action_time = datetime.utcnow() - timedelta(minutes=35)
        self.assertTrue(context.is_expired(timeout_minutes=30))
        
    def test_session_context_max_steps(self):
        """Test session context max steps logic."""
        context = AgentSessionContext(
            session_id="test-session",
            trace_id="test-trace",
            goal="Test goal",
            max_steps=3
        )
        
        self.assertFalse(context.has_reached_max_steps())
        
        # Add executions to reach max steps
        for i in range(3):
            execution = ToolExecution(
                tool_name=f"tool_{i}",
                parameters={},
                response={},
                execution_time=0.1,
                success=True
            )
            context.add_execution(execution)
        
        self.assertTrue(context.has_reached_max_steps())
        
    def test_session_context_data_management(self):
        """Test session context data management."""
        context = AgentSessionContext(
            session_id="test-session",
            trace_id="test-trace",
            goal="Test goal"
        )
        
        # Test initial state
        self.assertEqual(len(context.session_data), 0)
        
        # Add session data
        context.session_data.update({
            "auth_token": "token123",
            "user_id": "user456",
            "csrf_token": "csrf789"
        })
        
        self.assertEqual(len(context.session_data), 3)
        self.assertEqual(context.session_data["auth_token"], "token123")
        
        # Test last action time update
        old_time = context.last_action_time
        context.update_last_action()
        self.assertGreater(context.last_action_time, old_time)


class TestSessionSuccessTracker(unittest.TestCase):
    """Test session success tracking functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = SessionSuccessTracker("test-agent")
        
    def test_session_tracking_initialization(self):
        """Test session tracker initialization."""
        self.assertEqual(self.tracker.agent_id, "test-agent")
        self.assertEqual(len(self.tracker.active_sessions), 0)
        self.assertEqual(len(self.tracker.completed_sessions), 0)
        
    def test_transaction_type_classification(self):
        """Test transaction type classification from goals."""
        test_cases = [
            ("Complete user login flow", TransactionType.LOGIN_FLOW),
            ("Purchase product and checkout", TransactionType.PURCHASE_FLOW),
            ("Register new user account", TransactionType.REGISTRATION_FLOW),
            ("Retrieve user profile data", TransactionType.DATA_RETRIEVAL),
            ("Submit contact form", TransactionType.FORM_SUBMISSION),
            ("Complete multi-step workflow", TransactionType.MULTI_STEP_WORKFLOW),
            ("Generic task", TransactionType.GENERIC)
        ]
        
        for goal, expected_type in test_cases:
            transaction_type = self.tracker._classify_transaction_type(goal)
            self.assertEqual(transaction_type, expected_type,
                           f"Goal '{goal}' should be classified as '{expected_type}', got '{transaction_type}'")
    
    def test_session_success_patterns(self):
        """Test success pattern initialization and matching."""
        # Test that success patterns are properly initialized
        self.assertIn("authentication", self.tracker.success_patterns)
        self.assertIn("transaction", self.tracker.success_patterns)
        self.assertIn("general", self.tracker.success_patterns)
        
        # Test that failure patterns are properly initialized
        self.assertIn("authentication", self.tracker.failure_patterns)
        self.assertIn("server_errors", self.tracker.failure_patterns)
        self.assertIn("general", self.tracker.failure_patterns)
        
    def test_successful_stateful_sessions_percentage_calculation(self):
        """Test calculation of successful stateful sessions percentage."""
        # Create and finalize multiple sessions with different outcomes
        sessions_data = [
            ("session1", SessionOutcome.SUCCESS, True),   # Successful with session data
            ("session2", SessionOutcome.SUCCESS, False),  # Successful but no session data
            ("session3", SessionOutcome.FAILURE, True),   # Failed with session data
            ("session4", SessionOutcome.SUCCESS, True),   # Successful with session data
        ]
        
        for session_id, outcome, has_session_data in sessions_data:
            context = AgentSessionContext(
                session_id=session_id,
                trace_id=f"trace-{session_id}",
                goal="Test goal"
            )
            
            if has_session_data:
                context.session_data["token"] = f"token-{session_id}"
            
            # Add to completed sessions directly for testing
            from session_tracker import SessionSuccessMetrics
            metrics = SessionSuccessMetrics(
                session_id=session_id,
                trace_id=f"trace-{session_id}",
                goal="Test goal",
                transaction_type=TransactionType.GENERIC,
                outcome=outcome,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration_seconds=10.0,
                total_steps=1,
                successful_steps=1 if outcome == SessionOutcome.SUCCESS else 0,
                failed_steps=0 if outcome == SessionOutcome.SUCCESS else 1,
                step_success_rate=1.0 if outcome == SessionOutcome.SUCCESS else 0.0,
                completed_transactions=1,
                expected_transactions=1,
                transaction_completion_rate=1.0,
                has_authentication=has_session_data,
                has_session_data=has_session_data,
                session_data_keys=["token"] if has_session_data else [],
                error_count=0,
                error_types=[],
                recovery_attempts=0,
                mean_time_between_actions=0.5,
                cognitive_latency_violations=0
            )
            
            self.tracker.completed_sessions[session_id] = metrics
        
        # Calculate percentage
        percentage = self.tracker.get_successful_stateful_sessions_percentage(time_window_minutes=60)
        
        # Expected: 2 successful stateful sessions out of 4 total = 50%
        self.assertEqual(percentage, 50.0)
        
    def test_session_metrics_summary(self):
        """Test comprehensive session metrics summary."""
        # Add some test sessions
        for i in range(3):
            session_id = f"session_{i}"
            from session_tracker import SessionSuccessMetrics
            metrics = SessionSuccessMetrics(
                session_id=session_id,
                trace_id=f"trace_{i}",
                goal="Test goal",
                transaction_type=TransactionType.LOGIN_FLOW,
                outcome=SessionOutcome.SUCCESS if i < 2 else SessionOutcome.FAILURE,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration_seconds=10.0 + i,
                total_steps=5,
                successful_steps=4 if i < 2 else 2,
                failed_steps=1 if i < 2 else 3,
                step_success_rate=0.8 if i < 2 else 0.4,
                completed_transactions=1,
                expected_transactions=1,
                transaction_completion_rate=1.0,
                has_authentication=True,
                has_session_data=True,
                session_data_keys=["token"],
                error_count=1 if i < 2 else 3,
                error_types=["network"] if i < 2 else ["auth", "server"],
                recovery_attempts=0,
                mean_time_between_actions=0.5,
                cognitive_latency_violations=0
            )
            self.tracker.completed_sessions[session_id] = metrics
        
        # Get summary
        summary = self.tracker.get_session_metrics_summary(time_window_minutes=60)
        
        # Verify summary
        self.assertEqual(summary["total_sessions"], 3)
        self.assertAlmostEqual(summary["successful_stateful_sessions_percentage"], 66.67, places=1)  # 2/3 * 100
        self.assertAlmostEqual(summary["average_session_duration"], 11.0, places=1)  # (10+11+12)/3
        self.assertEqual(summary["average_steps_per_session"], 5.0)
        self.assertAlmostEqual(summary["average_step_success_rate"], 0.67, places=1)  # (0.8+0.8+0.4)/3


class TestMockLLMResponses(unittest.TestCase):
    """Test mocking LLM responses for deterministic testing."""
    
    def test_mock_llm_response_generation(self):
        """Test generating mock LLM responses for tool calls."""
        # Mock LLM that generates tool calls
        mock_llm = Mock()
        
        # Define deterministic responses for different scenarios
        mock_responses = {
            "login_scenario": {
                "tool_calls": [
                    {
                        "tool_name": "http_post",
                        "parameters": {
                            "api_name": "sut_api",
                            "path": "/api/login",
                            "data": {"username": "testuser", "password": "testpass"}
                        }
                    }
                ],
                "reasoning": "I need to authenticate the user first"
            },
            "get_profile_scenario": {
                "tool_calls": [
                    {
                        "tool_name": "http_get", 
                        "parameters": {
                            "api_name": "sut_api",
                            "path": "/api/profile",
                            "headers": {"Authorization": "Bearer token123"}
                        }
                    }
                ],
                "reasoning": "Retrieving user profile with authentication"
            }
        }
        
        # Test login scenario
        mock_llm.complete.return_value = Mock(
            text=json.dumps(mock_responses["login_scenario"])
        )
        
        response = mock_llm.complete("Please log in the user")
        parsed_response = json.loads(response.text)
        
        self.assertIn("tool_calls", parsed_response)
        self.assertEqual(len(parsed_response["tool_calls"]), 1)
        
        tool_call = parsed_response["tool_calls"][0]
        self.assertEqual(tool_call["tool_name"], "http_post")
        self.assertEqual(tool_call["parameters"]["path"], "/api/login")
        
    def test_mock_llm_error_responses(self):
        """Test mock LLM responses for error scenarios."""
        mock_llm = Mock()
        
        # Mock error response
        error_response = {
            "error": "Unable to process request",
            "retry_suggestion": "Please check the input parameters",
            "tool_calls": []
        }
        
        mock_llm.complete.return_value = Mock(
            text=json.dumps(error_response)
        )
        
        response = mock_llm.complete("Invalid request")
        parsed_response = json.loads(response.text)
        
        self.assertIn("error", parsed_response)
        self.assertEqual(len(parsed_response["tool_calls"]), 0)
        
    def test_mock_llm_adaptive_responses(self):
        """Test mock LLM adaptive responses based on context."""
        mock_llm = Mock()
        
        # Define context-aware responses
        def mock_complete(prompt):
            if "401" in prompt or "unauthorized" in prompt.lower():
                return Mock(text=json.dumps({
                    "tool_calls": [{
                        "tool_name": "http_post",
                        "parameters": {
                            "api_name": "sut_api", 
                            "path": "/api/login",
                            "data": {"username": "user", "password": "pass"}
                        }
                    }],
                    "reasoning": "Need to re-authenticate due to 401 error"
                }))
            elif "success" in prompt.lower():
                return Mock(text=json.dumps({
                    "tool_calls": [{
                        "tool_name": "http_get",
                        "parameters": {
                            "api_name": "sut_api",
                            "path": "/api/next-step"
                        }
                    }],
                    "reasoning": "Proceeding to next step after success"
                }))
            else:
                return Mock(text=json.dumps({
                    "tool_calls": [],
                    "reasoning": "No action needed"
                }))
        
        mock_llm.complete.side_effect = mock_complete
        
        # Test 401 error response
        response = mock_llm.complete("Received 401 unauthorized error")
        parsed = json.loads(response.text)
        self.assertEqual(parsed["tool_calls"][0]["parameters"]["path"], "/api/login")
        
        # Test success response
        response = mock_llm.complete("Login was successful")
        parsed = json.loads(response.text)
        self.assertEqual(parsed["tool_calls"][0]["parameters"]["path"], "/api/next-step")
        
    def test_mock_llm_session_context_responses(self):
        """Test mock LLM responses that incorporate session context."""
        mock_llm = Mock()
        
        # Mock session context
        session_context = {
            "session_data": {
                "auth_token": "token123",
                "user_id": "user456"
            },
            "current_step": 2,
            "goal": "Complete purchase flow"
        }
        
        def context_aware_complete(prompt):
            # Use session context to generate appropriate responses
            if "purchase" in prompt.lower() and session_context["session_data"].get("auth_token"):
                return Mock(text=json.dumps({
                    "tool_calls": [{
                        "tool_name": "http_post",
                        "parameters": {
                            "api_name": "sut_api",
                            "path": "/api/cart/checkout",
                            "headers": {"Authorization": f"Bearer {session_context['session_data']['auth_token']}"},
                            "data": {"user_id": session_context["session_data"]["user_id"]}
                        }
                    }],
                    "reasoning": f"Proceeding with checkout using stored auth token at step {session_context['current_step']}"
                }))
            else:
                return Mock(text=json.dumps({
                    "tool_calls": [],
                    "reasoning": "Insufficient context for action"
                }))
        
        mock_llm.complete.side_effect = context_aware_complete
        
        # Test context-aware response
        response = mock_llm.complete("Continue with purchase flow")
        parsed = json.loads(response.text)
        
        self.assertEqual(len(parsed["tool_calls"]), 1)
        tool_call = parsed["tool_calls"][0]
        self.assertEqual(tool_call["parameters"]["path"], "/api/cart/checkout")
        self.assertIn("Bearer token123", tool_call["parameters"]["headers"]["Authorization"])
        self.assertEqual(tool_call["parameters"]["data"]["user_id"], "user456")


class TestToolExecutionValidation(unittest.TestCase):
    """Test tool execution validation and tracking."""
    
    def test_tool_execution_creation(self):
        """Test creating tool execution records."""
        execution = ToolExecution(
            tool_name="http_get",
            parameters={"api_name": "sut_api", "path": "/api/users"},
            response={"status_code": 200, "data": {"users": []}},
            execution_time=0.5,
            success=True
        )
        
        self.assertEqual(execution.tool_name, "http_get")
        self.assertTrue(execution.success)
        self.assertEqual(execution.execution_time, 0.5)
        self.assertIsNone(execution.error_message)
        self.assertIsInstance(execution.timestamp, datetime)
        
    def test_tool_execution_error_handling(self):
        """Test tool execution with error conditions."""
        execution = ToolExecution(
            tool_name="http_post",
            parameters={"api_name": "sut_api", "path": "/api/login"},
            response={"status_code": 401, "error": "Unauthorized"},
            execution_time=0.3,
            success=False,
            error_message="Authentication failed"
        )
        
        self.assertFalse(execution.success)
        self.assertEqual(execution.error_message, "Authentication failed")
        self.assertEqual(execution.response["status_code"], 401)
        
    def test_tool_execution_serialization(self):
        """Test tool execution serialization."""
        execution = ToolExecution(
            tool_name="http_get",
            parameters={"api_name": "test"},
            response={"data": "test"},
            execution_time=1.0,
            success=True
        )
        
        # Test that it can be converted to dict (for logging/storage)
        execution_dict = execution.model_dump()
        self.assertIsInstance(execution_dict, dict)
        self.assertEqual(execution_dict["tool_name"], "http_get")
        self.assertTrue(execution_dict["success"])


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)