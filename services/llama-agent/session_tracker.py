"""
Session Success Tracking Module for Llama Agent.
Implements Requirements 4.6, 7.5, 8.3 for comprehensive session success validation.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
import json
import re

from models import AgentSessionContext, ToolExecution


logger = structlog.get_logger(__name__)


class SessionOutcome(str, Enum):
    """Possible outcomes for agent sessions."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    MAX_STEPS_REACHED = "max_steps_reached"
    ERROR = "error"
    ABANDONED = "abandoned"


class TransactionType(str, Enum):
    """Types of transactions that can be tracked."""
    LOGIN_FLOW = "login_flow"
    PURCHASE_FLOW = "purchase_flow"
    REGISTRATION_FLOW = "registration_flow"
    DATA_RETRIEVAL = "data_retrieval"
    FORM_SUBMISSION = "form_submission"
    MULTI_STEP_WORKFLOW = "multi_step_workflow"
    GENERIC = "generic"


@dataclass
class SessionSuccessMetrics:
    """Metrics for session success tracking."""
    session_id: str
    trace_id: str
    goal: str
    transaction_type: TransactionType
    outcome: SessionOutcome
    
    # Timing metrics
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    
    # Step metrics
    total_steps: int
    successful_steps: int
    failed_steps: int
    step_success_rate: float
    
    # Transaction completion metrics
    completed_transactions: int
    expected_transactions: int
    transaction_completion_rate: float
    
    # Session state metrics
    has_authentication: bool
    has_session_data: bool
    session_data_keys: List[str]
    
    # Error metrics
    error_count: int
    error_types: List[str]
    recovery_attempts: int
    
    # Performance metrics
    mean_time_between_actions: float
    cognitive_latency_violations: int
    
    # Success indicators
    success_indicators: List[str] = field(default_factory=list)
    failure_indicators: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging/storage."""
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "goal": self.goal,
            "transaction_type": self.transaction_type.value,
            "outcome": self.outcome.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "step_success_rate": self.step_success_rate,
            "completed_transactions": self.completed_transactions,
            "expected_transactions": self.expected_transactions,
            "transaction_completion_rate": self.transaction_completion_rate,
            "has_authentication": self.has_authentication,
            "has_session_data": self.has_session_data,
            "session_data_keys": self.session_data_keys,
            "error_count": self.error_count,
            "error_types": self.error_types,
            "recovery_attempts": self.recovery_attempts,
            "mean_time_between_actions": self.mean_time_between_actions,
            "cognitive_latency_violations": self.cognitive_latency_violations,
            "success_indicators": self.success_indicators,
            "failure_indicators": self.failure_indicators
        }


class SessionSuccessTracker:
    """
    Comprehensive session success tracking and validation.
    
    This class implements sophisticated logic to detect successful multi-step
    transaction completion and calculate the Successful Stateful Sessions metric.
    """
    
    def __init__(self, agent_id: str):
        """
        Initialize session success tracker.
        
        Args:
            agent_id: Unique identifier for the agent
        """
        self.agent_id = agent_id
        self.logger = logger.bind(agent_id=agent_id, component="session_tracker")
        
        # Session tracking state
        self.active_sessions: Dict[str, AgentSessionContext] = {}
        self.completed_sessions: Dict[str, SessionSuccessMetrics] = {}
        
        # Success pattern definitions
        self.success_patterns = self._initialize_success_patterns()
        self.failure_patterns = self._initialize_failure_patterns()
        
        # Performance thresholds
        self.mtba_threshold = 1.0  # Mean Time Between Actions threshold (seconds)
        self.cognitive_latency_threshold = 2.0  # TTFT threshold (seconds)
        
        self.logger.info("Session success tracker initialized")
    
    def start_tracking_session(self, session_context: AgentSessionContext) -> None:
        """
        Start tracking a new session for success metrics.
        
        Args:
            session_context: Session context to track
        """
        self.active_sessions[session_context.session_id] = session_context
        
        # Determine transaction type from goal
        transaction_type = self._classify_transaction_type(session_context.goal)
        
        self.logger.info(
            "Started tracking session",
            session_id=session_context.session_id,
            goal=session_context.goal,
            transaction_type=transaction_type.value
        )
    
    def update_session_progress(self, session_id: str, execution: ToolExecution) -> None:
        """
        Update session progress with new tool execution.
        
        Args:
            session_id: Session ID to update
            execution: Tool execution to record
        """
        if session_id not in self.active_sessions:
            return
        
        session_context = self.active_sessions[session_id]
        
        # Analyze execution for success/failure indicators
        self._analyze_execution_indicators(session_context, execution)
        
        # Update MTBA calculations
        self._update_mtba_metrics(session_context, execution)
        
        self.logger.debug(
            "Updated session progress",
            session_id=session_id,
            tool_name=execution.tool_name,
            success=execution.success,
            current_step=session_context.current_step
        )
    
    def finalize_session(self, session_id: str, outcome: SessionOutcome = None) -> SessionSuccessMetrics:
        """
        Finalize session tracking and calculate comprehensive success metrics.
        
        Args:
            session_id: Session ID to finalize
            outcome: Optional explicit outcome, will be determined if not provided
            
        Returns:
            SessionSuccessMetrics with comprehensive analysis
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not being tracked")
        
        session_context = self.active_sessions.pop(session_id)
        end_time = datetime.utcnow()
        
        # Determine outcome if not explicitly provided
        if outcome is None:
            outcome = self._determine_session_outcome(session_context)
        
        # Calculate comprehensive metrics
        metrics = self._calculate_session_metrics(session_context, end_time, outcome)
        
        # Store completed session metrics
        self.completed_sessions[session_id] = metrics
        
        self.logger.info(
            "Session finalized",
            session_id=session_id,
            outcome=outcome.value,
            duration=metrics.duration_seconds,
            success_rate=metrics.step_success_rate,
            transaction_completion=metrics.transaction_completion_rate
        )
        
        return metrics
    
    def get_successful_stateful_sessions_percentage(self, time_window_minutes: int = 60) -> float:
        """
        Calculate the percentage of Successful Stateful Sessions.
        
        This is the primary success metric for APE (Requirement 4.6).
        
        Args:
            time_window_minutes: Time window to consider for calculation
            
        Returns:
            Percentage of successful stateful sessions (0.0 to 100.0)
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        # Get sessions within time window
        recent_sessions = [
            metrics for metrics in self.completed_sessions.values()
            if metrics.start_time >= cutoff_time
        ]
        
        if not recent_sessions:
            return 0.0
        
        # Count successful stateful sessions
        successful_sessions = [
            metrics for metrics in recent_sessions
            if metrics.outcome == SessionOutcome.SUCCESS and metrics.has_session_data
        ]
        
        percentage = (len(successful_sessions) / len(recent_sessions)) * 100.0
        
        self.logger.info(
            "Calculated Successful Stateful Sessions percentage",
            percentage=percentage,
            successful_count=len(successful_sessions),
            total_count=len(recent_sessions),
            time_window_minutes=time_window_minutes
        )
        
        return percentage
    
    def get_session_metrics_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get comprehensive session metrics summary.
        
        Args:
            time_window_minutes: Time window to consider
            
        Returns:
            Dictionary with comprehensive metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        recent_sessions = [
            metrics for metrics in self.completed_sessions.values()
            if metrics.start_time >= cutoff_time
        ]
        
        if not recent_sessions:
            return {
                "total_sessions": 0,
                "successful_stateful_sessions_percentage": 0.0,
                "average_session_duration": 0.0,
                "average_steps_per_session": 0.0,
                "average_step_success_rate": 0.0,
                "average_mtba": 0.0,
                "cognitive_latency_violations": 0,
                "outcome_distribution": {},
                "transaction_type_distribution": {}
            }
        
        # Calculate aggregate metrics
        total_sessions = len(recent_sessions)
        successful_stateful = len([m for m in recent_sessions 
                                 if m.outcome == SessionOutcome.SUCCESS and m.has_session_data])
        
        avg_duration = sum(m.duration_seconds for m in recent_sessions) / total_sessions
        avg_steps = sum(m.total_steps for m in recent_sessions) / total_sessions
        avg_success_rate = sum(m.step_success_rate for m in recent_sessions) / total_sessions
        avg_mtba = sum(m.mean_time_between_actions for m in recent_sessions) / total_sessions
        total_violations = sum(m.cognitive_latency_violations for m in recent_sessions)
        
        # Outcome distribution
        outcome_dist = {}
        for outcome in SessionOutcome:
            count = len([m for m in recent_sessions if m.outcome == outcome])
            outcome_dist[outcome.value] = count
        
        # Transaction type distribution
        transaction_dist = {}
        for trans_type in TransactionType:
            count = len([m for m in recent_sessions if m.transaction_type == trans_type])
            transaction_dist[trans_type.value] = count
        
        return {
            "total_sessions": total_sessions,
            "successful_stateful_sessions_percentage": (successful_stateful / total_sessions) * 100.0,
            "average_session_duration": avg_duration,
            "average_steps_per_session": avg_steps,
            "average_step_success_rate": avg_success_rate,
            "average_mtba": avg_mtba,
            "cognitive_latency_violations": total_violations,
            "outcome_distribution": outcome_dist,
            "transaction_type_distribution": transaction_dist,
            "time_window_minutes": time_window_minutes
        }
    
    def _initialize_success_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns that indicate successful operations."""
        return {
            "authentication": [
                r"login.*success", r"authenticated", r"token.*received",
                r"session.*created", r"welcome", r"dashboard"
            ],
            "transaction": [
                r"order.*created", r"payment.*success", r"transaction.*complete",
                r"purchase.*confirmed", r"order.*confirmed"
            ],
            "data_operations": [
                r"data.*saved", r"record.*created", r"updated.*success",
                r"deleted.*success", r"operation.*complete"
            ],
            "navigation": [
                r"page.*loaded", r"redirect.*success", r"navigation.*complete"
            ],
            "form_submission": [
                r"form.*submitted", r"validation.*passed", r"data.*accepted"
            ],
            "general": [
                r"success", r"completed", r"confirmed", r"approved",
                r"created", r"updated", r"processed"
            ]
        }
    
    def _initialize_failure_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns that indicate failed operations."""
        return {
            "authentication": [
                r"login.*failed", r"invalid.*credentials", r"unauthorized",
                r"authentication.*failed", r"access.*denied"
            ],
            "validation": [
                r"validation.*failed", r"invalid.*input", r"required.*field",
                r"format.*error", r"constraint.*violation"
            ],
            "server_errors": [
                r"server.*error", r"internal.*error", r"service.*unavailable",
                r"timeout", r"connection.*failed"
            ],
            "business_logic": [
                r"insufficient.*funds", r"out.*of.*stock", r"limit.*exceeded",
                r"quota.*exceeded", r"operation.*not.*allowed"
            ],
            "general": [
                r"error", r"failed", r"denied", r"rejected",
                r"invalid", r"forbidden", r"not.*found"
            ]
        }
    
    def _classify_transaction_type(self, goal: str) -> TransactionType:
        """
        Classify transaction type based on goal description.
        
        Args:
            goal: Goal description
            
        Returns:
            TransactionType classification
        """
        goal_lower = goal.lower()
        
        if any(term in goal_lower for term in ["login", "sign in", "authenticate"]):
            return TransactionType.LOGIN_FLOW
        elif any(term in goal_lower for term in ["purchase", "buy", "order", "checkout"]):
            return TransactionType.PURCHASE_FLOW
        elif any(term in goal_lower for term in ["register", "sign up", "create account"]):
            return TransactionType.REGISTRATION_FLOW
        elif any(term in goal_lower for term in ["retrieve", "fetch", "get", "search"]):
            return TransactionType.DATA_RETRIEVAL
        elif any(term in goal_lower for term in ["submit", "form", "create", "update"]):
            return TransactionType.FORM_SUBMISSION
        elif any(term in goal_lower for term in ["workflow", "process", "multi-step"]):
            return TransactionType.MULTI_STEP_WORKFLOW
        else:
            return TransactionType.GENERIC
    
    def _analyze_execution_indicators(self, session_context: AgentSessionContext, 
                                    execution: ToolExecution) -> None:
        """
        Analyze tool execution for success/failure indicators.
        
        Args:
            session_context: Session context to update
            execution: Tool execution to analyze
        """
        response_text = json.dumps(execution.response).lower()
        
        # Check for success patterns
        for category, patterns in self.success_patterns.items():
            for pattern in patterns:
                if re.search(pattern, response_text):
                    indicator = f"{category}:{pattern}"
                    if not hasattr(session_context, 'success_indicators'):
                        session_context.success_indicators = []
                    if indicator not in session_context.success_indicators:
                        session_context.success_indicators.append(indicator)
        
        # Check for failure patterns
        for category, patterns in self.failure_patterns.items():
            for pattern in patterns:
                if re.search(pattern, response_text):
                    indicator = f"{category}:{pattern}"
                    if not hasattr(session_context, 'failure_indicators'):
                        session_context.failure_indicators = []
                    if indicator not in session_context.failure_indicators:
                        session_context.failure_indicators.append(indicator)
    
    def _update_mtba_metrics(self, session_context: AgentSessionContext, 
                           execution: ToolExecution) -> None:
        """
        Update Mean Time Between Actions metrics.
        
        Args:
            session_context: Session context to update
            execution: Current execution
        """
        if not hasattr(session_context, 'action_timestamps'):
            session_context.action_timestamps = []
        
        session_context.action_timestamps.append(execution.timestamp)
        
        # Calculate MTBA for recent actions
        if len(session_context.action_timestamps) >= 2:
            recent_timestamps = session_context.action_timestamps[-10:]  # Last 10 actions
            time_diffs = []
            
            for i in range(1, len(recent_timestamps)):
                diff = (recent_timestamps[i] - recent_timestamps[i-1]).total_seconds()
                time_diffs.append(diff)
            
            if time_diffs:
                mtba = sum(time_diffs) / len(time_diffs)
                session_context.current_mtba = mtba
                
                # Track cognitive latency violations
                if not hasattr(session_context, 'cognitive_violations'):
                    session_context.cognitive_violations = 0
                
                if mtba > self.cognitive_latency_threshold:
                    session_context.cognitive_violations += 1
    
    def _determine_session_outcome(self, session_context: AgentSessionContext) -> SessionOutcome:
        """
        Determine session outcome based on execution history and indicators.
        
        Args:
            session_context: Session context to analyze
            
        Returns:
            SessionOutcome classification
        """
        # Check for explicit termination conditions
        if session_context.has_reached_max_steps():
            return SessionOutcome.MAX_STEPS_REACHED
        
        if session_context.is_expired():
            return SessionOutcome.TIMEOUT
        
        # Analyze execution history
        if not session_context.execution_history:
            return SessionOutcome.ABANDONED
        
        successful_steps = sum(1 for exec in session_context.execution_history if exec.success)
        failed_steps = sum(1 for exec in session_context.execution_history if not exec.success)
        total_steps = len(session_context.execution_history)
        
        success_rate = successful_steps / total_steps if total_steps > 0 else 0.0
        
        # Check for critical errors
        critical_errors = sum(1 for exec in session_context.execution_history 
                            if not exec.success and exec.error_message and 
                            any(term in exec.error_message.lower() 
                                for term in ["fatal", "critical", "abort"]))
        
        if critical_errors > 0:
            return SessionOutcome.ERROR
        
        # Analyze success/failure indicators
        success_indicators = getattr(session_context, 'success_indicators', [])
        failure_indicators = getattr(session_context, 'failure_indicators', [])
        
        # Determine success based on multiple criteria
        has_session_data = bool(session_context.session_data)
        has_meaningful_progress = successful_steps >= 2
        good_success_rate = success_rate >= 0.7
        has_success_indicators = len(success_indicators) > 0
        no_critical_failures = len(failure_indicators) == 0
        
        # Success criteria (all must be true for SUCCESS outcome)
        success_criteria = [
            has_meaningful_progress,
            good_success_rate,
            has_session_data or has_success_indicators,
            not (len(failure_indicators) > len(success_indicators))
        ]
        
        if all(success_criteria):
            return SessionOutcome.SUCCESS
        else:
            return SessionOutcome.FAILURE
    
    def _calculate_session_metrics(self, session_context: AgentSessionContext, 
                                 end_time: datetime, outcome: SessionOutcome) -> SessionSuccessMetrics:
        """
        Calculate comprehensive session metrics.
        
        Args:
            session_context: Session context to analyze
            end_time: Session end time
            outcome: Determined outcome
            
        Returns:
            SessionSuccessMetrics with complete analysis
        """
        duration = (end_time - session_context.start_time).total_seconds()
        
        # Step metrics
        successful_steps = sum(1 for exec in session_context.execution_history if exec.success)
        failed_steps = sum(1 for exec in session_context.execution_history if not exec.success)
        total_steps = len(session_context.execution_history)
        step_success_rate = successful_steps / total_steps if total_steps > 0 else 0.0
        
        # Transaction completion metrics
        transaction_type = self._classify_transaction_type(session_context.goal)
        completed_transactions, expected_transactions = self._analyze_transaction_completion(
            session_context, transaction_type
        )
        transaction_completion_rate = (
            completed_transactions / expected_transactions 
            if expected_transactions > 0 else 0.0
        )
        
        # Session state metrics
        has_authentication = self._has_authentication_data(session_context)
        has_session_data = bool(session_context.session_data)
        session_data_keys = list(session_context.session_data.keys())
        
        # Error metrics
        error_count = failed_steps
        error_types = list(set(
            exec.error_message.split(':')[0] if exec.error_message else "unknown"
            for exec in session_context.execution_history 
            if not exec.success
        ))
        recovery_attempts = sum(1 for exec in session_context.execution_history 
                              if "retry" in exec.parameters.get("attempt", ""))
        
        # Performance metrics
        mtba = getattr(session_context, 'current_mtba', 0.0)
        cognitive_violations = getattr(session_context, 'cognitive_violations', 0)
        
        # Success/failure indicators
        success_indicators = getattr(session_context, 'success_indicators', [])
        failure_indicators = getattr(session_context, 'failure_indicators', [])
        
        return SessionSuccessMetrics(
            session_id=session_context.session_id,
            trace_id=session_context.trace_id,
            goal=session_context.goal,
            transaction_type=transaction_type,
            outcome=outcome,
            start_time=session_context.start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_steps=total_steps,
            successful_steps=successful_steps,
            failed_steps=failed_steps,
            step_success_rate=step_success_rate,
            completed_transactions=completed_transactions,
            expected_transactions=expected_transactions,
            transaction_completion_rate=transaction_completion_rate,
            has_authentication=has_authentication,
            has_session_data=has_session_data,
            session_data_keys=session_data_keys,
            error_count=error_count,
            error_types=error_types,
            recovery_attempts=recovery_attempts,
            mean_time_between_actions=mtba,
            cognitive_latency_violations=cognitive_violations,
            success_indicators=success_indicators,
            failure_indicators=failure_indicators
        )
    
    def _analyze_transaction_completion(self, session_context: AgentSessionContext, 
                                     transaction_type: TransactionType) -> Tuple[int, int]:
        """
        Analyze transaction completion based on type and execution history.
        
        Args:
            session_context: Session context to analyze
            transaction_type: Type of transaction
            
        Returns:
            Tuple of (completed_transactions, expected_transactions)
        """
        success_indicators = getattr(session_context, 'success_indicators', [])
        
        # Define expected transaction patterns for each type
        transaction_patterns = {
            TransactionType.LOGIN_FLOW: ["authentication:login.*success", "authentication:authenticated"],
            TransactionType.PURCHASE_FLOW: ["transaction:order.*created", "transaction:payment.*success"],
            TransactionType.REGISTRATION_FLOW: ["data_operations:record.*created", "authentication:session.*created"],
            TransactionType.DATA_RETRIEVAL: ["data_operations:data.*saved", "navigation:page.*loaded"],
            TransactionType.FORM_SUBMISSION: ["form_submission:form.*submitted", "data_operations:data.*saved"],
            TransactionType.MULTI_STEP_WORKFLOW: ["general:completed", "general:success"],
            TransactionType.GENERIC: ["general:success", "general:completed"]
        }
        
        expected_patterns = transaction_patterns.get(transaction_type, ["general:success"])
        expected_transactions = len(expected_patterns)
        
        self.logger.debug(
            "Analyzing transaction completion",
            session_id=session_context.session_id,
            transaction_type=transaction_type.value,
            expected_patterns=expected_patterns,
            success_indicators=success_indicators
        )
        
        # Count completed transactions based on matching patterns
        completed_transactions = 0
        for pattern in expected_patterns:
            if any(pattern in indicator for indicator in success_indicators):
                completed_transactions += 1
        
        return completed_transactions, expected_transactions
    
    def _has_authentication_data(self, session_context: AgentSessionContext) -> bool:
        """
        Check if session has authentication-related data.
        
        Args:
            session_context: Session context to check
            
        Returns:
            Boolean indicating presence of authentication data
        """
        auth_keywords = ["token", "auth", "session", "cookie", "jwt", "bearer"]
        
        for key in session_context.session_data.keys():
            if any(keyword in key.lower() for keyword in auth_keywords):
                return True
        
        return False