"""
MCP tools for HTTP operations and state management.
Implements agent tools for HTTP operations through MCP Gateway and session state management.
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Union
import httpx
import structlog
from llama_index.core.tools import BaseTool

from models import MCPToolCall, HTTPMethod, ToolExecution


logger = structlog.get_logger(__name__)


class HTTPGetTool(BaseTool):
    """Tool for HTTP GET operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__(
            name="http_get",
            description=(
                "Perform HTTP GET request through MCP Gateway. "
                "Use for read-only operations like fetching data, checking status, or retrieving information. "
                "Parameters: api_name (str), path (str), headers (dict, optional)"
            )
        )
    
    def call(self, api_name: str, path: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute HTTP GET request through MCP Gateway.
        
        Args:
            api_name: Target API name for MCP Gateway routing
            path: API endpoint path
            headers: Optional headers (session tokens, auth, etc.)
            
        Returns:
            Dict containing response data and metadata
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Create MCP-compliant tool call
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.GET,
            endpoint_path=path,
            session_headers=headers or {}
        )
        
        logger.info(
            "Executing HTTP GET tool",
            trace_id=trace_id,
            api_name=api_name,
            path=path,
            has_headers=bool(headers)
        )
        
        try:
            # Send request to MCP Gateway with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            f"{self.mcp_gateway_url}/mcp/route",
                            json=mcp_call.model_dump(),
                            headers={
                                "Content-Type": "application/json",
                                "X-Trace-ID": trace_id,
                                "X-Retry-Count": str(retry_count)
                            }
                        )
                        
                        execution_time = (datetime.utcnow() - start_time).total_seconds()
                        
                        # Process response with enhanced error categorization
                        result = {
                            "success": response.status_code < 400,
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                            "execution_time": execution_time,
                            "trace_id": trace_id,
                            "method": "GET",
                            "api_name": api_name,
                            "path": path,
                            "retry_count": retry_count
                        }
                        
                        # Parse response body
                        try:
                            result["data"] = response.json()
                        except json.JSONDecodeError:
                            result["data"] = response.text
                        
                        # Enhanced session data extraction
                        session_data = {}
                        
                        # Extract from response headers
                        for header_name, header_value in response.headers.items():
                            if header_name.lower() in ['set-cookie', 'authorization', 'x-session-token', 'x-auth-token']:
                                session_data[header_name] = header_value
                        
                        # Extract from response body if it contains session information
                        if isinstance(result.get("data"), dict):
                            response_data = result["data"]
                            session_keys = ['token', 'access_token', 'session_id', 'session_token', 'auth_token', 'csrf_token']
                            for key in session_keys:
                                if key in response_data:
                                    session_data[key] = response_data[key]
                        
                        if session_data:
                            result["session_data"] = session_data
                        
                        # Add error details for non-2xx responses
                        if not result["success"]:
                            result["error_category"] = self._categorize_http_error(response.status_code)
                            result["error_message"] = f"HTTP {response.status_code}: {response.reason_phrase}"
                            
                            # Check if this is a retryable error
                            if self._is_retryable_status(response.status_code) and retry_count < max_retries:
                                retry_count += 1
                                logger.warning(
                                    "HTTP GET failed with retryable error, retrying",
                                    trace_id=trace_id,
                                    status_code=response.status_code,
                                    retry_count=retry_count,
                                    max_retries=max_retries
                                )
                                import time
                                time.sleep(min(0.5 * (2 ** retry_count), 5.0))  # Exponential backoff
                                continue
                        
                        logger.info(
                            "HTTP GET completed",
                            trace_id=trace_id,
                            status_code=response.status_code,
                            execution_time=execution_time,
                            success=result["success"],
                            retry_count=retry_count
                        )
                        
                        return result
                        
                except httpx.TimeoutException as e:
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.warning(
                            "HTTP GET timeout, retrying",
                            trace_id=trace_id,
                            retry_count=retry_count,
                            timeout=30.0
                        )
                        import time
                        time.sleep(min(1.0 * retry_count, 5.0))
                        continue
                    else:
                        raise
                        
        except httpx.RequestError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "request_error",
                "execution_time": execution_time,
                "trace_id": trace_id,
                "method": "GET",
                "api_name": api_name,
                "path": path
            }
            
            logger.error(
                "HTTP GET failed",
                trace_id=trace_id,
                error=str(e),
                execution_time=execution_time
            )
            
            return error_result
    
    def _categorize_http_error(self, status_code: int) -> str:
        """Categorize HTTP status codes for error handling."""
        if status_code in [401, 403]:
            return "authentication"
        elif status_code == 404:
            return "not_found"
        elif status_code == 429:
            return "rate_limit"
        elif 400 <= status_code < 500:
            return "client_error"
        elif 500 <= status_code < 600:
            return "server_error"
        else:
            return "unknown"
    
    def _is_retryable_status(self, status_code: int) -> bool:
        """Determine if an HTTP status code indicates a retryable error."""
        # Retry on server errors and rate limiting
        return status_code in [429, 500, 502, 503, 504]


class HTTPPostTool(BaseTool):
    """Tool for HTTP POST operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__(
            name="http_post",
            description=(
                "Perform HTTP POST request through MCP Gateway. "
                "Use for write operations like login, form submission, creating resources. "
                "Parameters: api_name (str), path (str), data (dict), headers (dict, optional)"
            )
        )
    
    def call(self, api_name: str, path: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute HTTP POST request through MCP Gateway.
        
        Args:
            api_name: Target API name for MCP Gateway routing
            path: API endpoint path
            data: Request payload data
            headers: Optional headers (session tokens, auth, etc.)
            
        Returns:
            Dict containing response data and metadata
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Create MCP-compliant tool call
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.POST,
            endpoint_path=path,
            request_payload=data,
            session_headers=headers or {}
        )
        
        logger.info(
            "Executing HTTP POST tool",
            trace_id=trace_id,
            api_name=api_name,
            path=path,
            has_data=bool(data),
            has_headers=bool(headers)
        )
        
        try:
            # Send request to MCP Gateway with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            f"{self.mcp_gateway_url}/mcp/route",
                            json=mcp_call.model_dump(),
                            headers={
                                "Content-Type": "application/json",
                                "X-Trace-ID": trace_id,
                                "X-Retry-Count": str(retry_count)
                            }
                        )
                        
                        execution_time = (datetime.utcnow() - start_time).total_seconds()
                        
                        # Process response with enhanced error categorization
                        result = {
                            "success": response.status_code < 400,
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                            "execution_time": execution_time,
                            "trace_id": trace_id,
                            "method": "POST",
                            "api_name": api_name,
                            "path": path,
                            "retry_count": retry_count
                        }
                        
                        # Parse response body
                        try:
                            result["data"] = response.json()
                        except json.JSONDecodeError:
                            result["data"] = response.text
                        
                        # Enhanced session data extraction
                        session_data = {}
                        
                        # Extract from response headers
                        for header_name, header_value in response.headers.items():
                            if header_name.lower() in ['set-cookie', 'authorization', 'x-session-token', 'x-auth-token']:
                                session_data[header_name] = header_value
                        
                        # Extract from response body if it contains session information
                        if isinstance(result.get("data"), dict):
                            response_data = result["data"]
                            session_keys = ['token', 'access_token', 'session_id', 'session_token', 'auth_token', 'csrf_token', 'transaction_id', 'user_id']
                            for key in session_keys:
                                if key in response_data:
                                    session_data[key] = response_data[key]
                        
                        if session_data:
                            result["session_data"] = session_data
                        
                        # Add error details for non-2xx responses
                        if not result["success"]:
                            result["error_category"] = self._categorize_http_error(response.status_code)
                            result["error_message"] = f"HTTP {response.status_code}: {response.reason_phrase}"
                            
                            # Check if this is a retryable error
                            if self._is_retryable_status(response.status_code) and retry_count < max_retries:
                                retry_count += 1
                                logger.warning(
                                    "HTTP POST failed with retryable error, retrying",
                                    trace_id=trace_id,
                                    status_code=response.status_code,
                                    retry_count=retry_count,
                                    max_retries=max_retries
                                )
                                import time
                                time.sleep(min(0.5 * (2 ** retry_count), 5.0))  # Exponential backoff
                                continue
                        
                        logger.info(
                            "HTTP POST completed",
                            trace_id=trace_id,
                            status_code=response.status_code,
                            execution_time=execution_time,
                            success=result["success"],
                            has_session_data=bool(session_data),
                            retry_count=retry_count
                        )
                        
                        return result
                        
                except httpx.TimeoutException as e:
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.warning(
                            "HTTP POST timeout, retrying",
                            trace_id=trace_id,
                            retry_count=retry_count,
                            timeout=30.0
                        )
                        import time
                        time.sleep(min(1.0 * retry_count, 5.0))
                        continue
                    else:
                        raise
                
        except httpx.RequestError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "request_error",
                "execution_time": execution_time,
                "trace_id": trace_id,
                "method": "POST",
                "api_name": api_name,
                "path": path
            }
            
            logger.error(
                "HTTP POST failed",
                trace_id=trace_id,
                error=str(e),
                execution_time=execution_time
            )
            
            return error_result
    
    def _categorize_http_error(self, status_code: int) -> str:
        """Categorize HTTP status codes for error handling."""
        if status_code in [401, 403]:
            return "authentication"
        elif status_code == 404:
            return "not_found"
        elif status_code == 429:
            return "rate_limit"
        elif 400 <= status_code < 500:
            return "client_error"
        elif 500 <= status_code < 600:
            return "server_error"
        else:
            return "unknown"
    
    def _is_retryable_status(self, status_code: int) -> bool:
        """Determine if an HTTP status code indicates a retryable error."""
        # Retry on server errors and rate limiting
        return status_code in [429, 500, 502, 503, 504]


class HTTPPutTool(BaseTool):
    """Tool for HTTP PUT operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__(
            name="http_put",
            description=(
                "Perform HTTP PUT request through MCP Gateway. "
                "Use for update operations like modifying resources or updating data. "
                "Parameters: api_name (str), path (str), data (dict), headers (dict, optional)"
            )
        )
    
    def call(self, api_name: str, path: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute HTTP PUT request through MCP Gateway.
        
        Args:
            api_name: Target API name for MCP Gateway routing
            path: API endpoint path
            data: Request payload data
            headers: Optional headers (session tokens, auth, etc.)
            
        Returns:
            Dict containing response data and metadata
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Create MCP-compliant tool call
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.PUT,
            endpoint_path=path,
            request_payload=data,
            session_headers=headers or {}
        )
        
        logger.info(
            "Executing HTTP PUT tool",
            trace_id=trace_id,
            api_name=api_name,
            path=path,
            has_data=bool(data),
            has_headers=bool(headers)
        )
        
        try:
            # Send request to MCP Gateway
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.mcp_gateway_url}/mcp/route",
                    json=mcp_call.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-ID": trace_id
                    }
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Process response
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "method": "PUT",
                    "api_name": api_name,
                    "path": path
                }
                
                # Parse response body
                try:
                    result["data"] = response.json()
                except json.JSONDecodeError:
                    result["data"] = response.text
                
                # Extract session data from response headers for state management
                session_data = {}
                for header_name, header_value in response.headers.items():
                    if header_name.lower() in ['set-cookie', 'authorization', 'x-session-token']:
                        session_data[header_name] = header_value
                
                if session_data:
                    result["session_data"] = session_data
                
                logger.info(
                    "HTTP PUT completed",
                    trace_id=trace_id,
                    status_code=response.status_code,
                    execution_time=execution_time,
                    success=result["success"]
                )
                
                return result
                
        except httpx.RequestError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "request_error",
                "execution_time": execution_time,
                "trace_id": trace_id,
                "method": "PUT",
                "api_name": api_name,
                "path": path
            }
            
            logger.error(
                "HTTP PUT failed",
                trace_id=trace_id,
                error=str(e),
                execution_time=execution_time
            )
            
            return error_result


class HTTPDeleteTool(BaseTool):
    """Tool for HTTP DELETE operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__(
            name="http_delete",
            description=(
                "Perform HTTP DELETE request through MCP Gateway. "
                "Use for delete operations like removing resources or canceling transactions. "
                "Parameters: api_name (str), path (str), headers (dict, optional)"
            )
        )
    
    def call(self, api_name: str, path: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute HTTP DELETE request through MCP Gateway.
        
        Args:
            api_name: Target API name for MCP Gateway routing
            path: API endpoint path
            headers: Optional headers (session tokens, auth, etc.)
            
        Returns:
            Dict containing response data and metadata
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Create MCP-compliant tool call
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.DELETE,
            endpoint_path=path,
            session_headers=headers or {}
        )
        
        logger.info(
            "Executing HTTP DELETE tool",
            trace_id=trace_id,
            api_name=api_name,
            path=path,
            has_headers=bool(headers)
        )
        
        try:
            # Send request to MCP Gateway
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.mcp_gateway_url}/mcp/route",
                    json=mcp_call.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-ID": trace_id
                    }
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Process response
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "method": "DELETE",
                    "api_name": api_name,
                    "path": path
                }
                
                # Parse response body
                try:
                    result["data"] = response.json()
                except json.JSONDecodeError:
                    result["data"] = response.text
                
                logger.info(
                    "HTTP DELETE completed",
                    trace_id=trace_id,
                    status_code=response.status_code,
                    execution_time=execution_time,
                    success=result["success"]
                )
                
                return result
                
        except httpx.RequestError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "request_error",
                "execution_time": execution_time,
                "trace_id": trace_id,
                "method": "DELETE",
                "api_name": api_name,
                "path": path
            }
            
            logger.error(
                "HTTP DELETE failed",
                trace_id=trace_id,
                error=str(e),
                execution_time=execution_time
            )
            
            return error_result


class StateUpdateTool(BaseTool):
    """Tool for internal session context management."""
    
    def __init__(self, agent_worker: Optional[Any] = None):
        self.agent_worker = agent_worker
        super().__init__(
            name="state_update",
            description=(
                "Update internal session context and state. "
                "Use to persist session data like cookies, tokens, transaction IDs for stateful behavior. "
                "Parameters: session_id (str), session_data (dict)"
            )
        )
    
    def call(self, session_id: str, session_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Update session context with new state data.
        
        Args:
            session_id: Session identifier
            session_data: Dictionary containing session state (cookies, tokens, etc.)
            
        Returns:
            Dict containing update status and metadata
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(
            "Executing state update tool",
            trace_id=trace_id,
            session_id=session_id,
            data_keys=list(session_data.keys()) if session_data else []
        )
        
        try:
            # Update session data through agent worker if available
            if self.agent_worker and hasattr(self.agent_worker, 'update_session_data'):
                self.agent_worker.update_session_data(session_id, session_data)
                
                # Get updated session context for verification
                session_context = None
                if hasattr(self.agent_worker, 'get_session'):
                    session_context = self.agent_worker.get_session(session_id)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": True,
                    "session_id": session_id,
                    "updated_keys": list(session_data.keys()),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "action": "state_update"
                }
                
                if session_context:
                    result["session_step"] = session_context.current_step
                    result["session_start_time"] = session_context.start_time.isoformat()
                    result["last_action_time"] = session_context.last_action_time.isoformat()
                
                logger.info(
                    "State update completed",
                    trace_id=trace_id,
                    session_id=session_id,
                    execution_time=execution_time,
                    updated_keys=list(session_data.keys())
                )
                
                return result
                
            else:
                # Fallback when agent worker is not available
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": True,
                    "session_id": session_id,
                    "updated_keys": list(session_data.keys()),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "action": "state_update",
                    "note": "Agent worker not available, state update logged only"
                }
                
                logger.warning(
                    "State update completed without agent worker",
                    trace_id=trace_id,
                    session_id=session_id,
                    execution_time=execution_time
                )
                
                return result
                
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "state_update_error",
                "session_id": session_id,
                "execution_time": execution_time,
                "trace_id": trace_id,
                "action": "state_update"
            }
            
            logger.error(
                "State update failed",
                trace_id=trace_id,
                session_id=session_id,
                error=str(e),
                execution_time=execution_time
            )
            
            return error_result