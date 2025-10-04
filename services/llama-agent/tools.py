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
    """MVP Tool for HTTP GET operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__()
    
    @property
    def metadata(self):
        from llama_index.core.tools.tool_spec.base import ToolMetadata
        return ToolMetadata(
            name="http_get",
            description=(
                "Use this tool to retrieve data from an API endpoint. "
                "Parameters: api_name (str), path (str), headers (dict, optional)"
            )
        )
    
    def __call__(self, api_name: str, path: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        return self.call(api_name, path, headers, **kwargs)
    
    def call(self, api_name: str, path: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.GET,
            endpoint_path=path,
            session_headers=headers or {}
        )
        
        logger.info("Executing HTTP GET tool ()", trace_id=trace_id, api_name=api_name, path=path)
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.mcp_gateway_url}/mcp/request",
                    json=mcp_call.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-ID": trace_id,
                    }
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "method": "GET",
                    "api_name": api_name,
                    "path": path,
                    "data": None
                }
                
                try:
                    result["data"] = response.json()
                except json.JSONDecodeError:
                    result["data"] = response.text
                
                session_data = {}
                for header_name, header_value in response.headers.items():
                    if header_name.lower() in ['set-cookie', 'authorization', 'x-session-token', 'x-auth-token']:
                        session_data[header_name] = header_value
                
                if isinstance(result.get("data"), dict):
                    response_data = result["data"]
                    session_keys = ['token', 'access_token', 'session_id', 'session_token', 'auth_token', 'csrf_token']
                    for key in session_keys:
                        if key in response_data:
                            session_data[key] = response_data[key]
                
                if session_data:
                    result["session_data"] = session_data
                
                logger.info("HTTP GET completed ()", trace_id=trace_id, status_code=response.status_code, success=result["success"])
                
                return result
                        
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
            logger.error("HTTP GET failed ()", trace_id=trace_id, error=str(e))
            return error_result


class HTTPPostTool(BaseTool):
    """ Tool for HTTP POST operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__()
    
    @property
    def metadata(self):
        from llama_index.core.tools.tool_spec.base import ToolMetadata
        return ToolMetadata(
            name="http_post",
            description=(
                "Use this tool to submit data to an API. "
                "Parameters: api_name (str), path (str), data (dict), headers (dict, optional)"
            )
        )
    
    def __call__(self, api_name: str, path: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        return self.call(api_name, path, data, headers, **kwargs)
    
    def call(self, api_name: str, path: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.POST,
            endpoint_path=path,
            request_payload=data,
            session_headers=headers or {}
        )
        
        logger.info("Executing HTTP POST tool ()", trace_id=trace_id, api_name=api_name, path=path)
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.mcp_gateway_url}/mcp/request",
                    json=mcp_call.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-ID": trace_id,
                    }
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "method": "POST",
                    "api_name": api_name,
                    "path": path,
                    "data": None
                }
                
                try:
                    result["data"] = response.json()
                except json.JSONDecodeError:
                    result["data"] = response.text
                
                session_data = {}
                for header_name, header_value in response.headers.items():
                    if header_name.lower() in ['set-cookie', 'authorization', 'x-session-token', 'x-auth-token']:
                        session_data[header_name] = header_value
                
                if isinstance(result.get("data"), dict):
                    response_data = result["data"]
                    session_keys = ['token', 'access_token', 'session_id', 'session_token', 'auth_token', 'csrf_token', 'transaction_id', 'user_id']
                    for key in session_keys:
                        if key in response_data:
                            session_data[key] = response_data[key]
                
                if session_data:
                    result["session_data"] = session_data
                
                logger.info("HTTP POST completed ()", trace_id=trace_id, status_code=response.status_code, success=result["success"])
                
                return result
                        
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
            logger.error("HTTP POST failed ()", trace_id=trace_id, error=str(e))
            return error_result


class HTTPPutTool(BaseTool):
    """ Tool for HTTP PUT operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__()
    
    @property
    def metadata(self):
        from llama_index.core.tools.tool_spec.base import ToolMetadata
        return ToolMetadata(
            name="http_put",
            description=(
                "Use this tool to update existing resources or modify data. "
                "Parameters: api_name (str), path (str), data (dict), headers (dict, optional)"
            )
        )
    
    def __call__(self, api_name: str, path: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        return self.call(api_name, path, data, headers, **kwargs)
    
    def call(self, api_name: str, path: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.PUT,
            endpoint_path=path,
            request_payload=data,
            session_headers=headers or {}
        )
        
        logger.info("Executing HTTP PUT tool ()", trace_id=trace_id, api_name=api_name, path=path)
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.mcp_gateway_url}/mcp/request",
                    json=mcp_call.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-ID": trace_id,
                    }
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "method": "PUT",
                    "api_name": api_name,
                    "path": path,
                    "data": None
                }
                
                try:
                    result["data"] = response.json()
                except json.JSONDecodeError:
                    result["data"] = response.text
                
                session_data = {}
                for header_name, header_value in response.headers.items():
                    if header_name.lower() in ['set-cookie', 'authorization', 'x-session-token', 'x-auth-token']:
                        session_data[header_name] = header_value
                
                if session_data:
                    result["session_data"] = session_data
                
                logger.info("HTTP PUT completed ()", trace_id=trace_id, status_code=response.status_code, success=result["success"])
                
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
            logger.error("HTTP PUT failed ()", trace_id=trace_id, error=str(e))
            return error_result


class HTTPDeleteTool(BaseTool):
    """ Tool for HTTP DELETE operations through MCP Gateway."""
    
    def __init__(self, mcp_gateway_url: str, agent_worker: Optional[Any] = None):
        self.mcp_gateway_url = mcp_gateway_url.rstrip('/')
        self.agent_worker = agent_worker
        super().__init__()
    
    @property
    def metadata(self):
        from llama_index.core.tools.tool_spec.base import ToolMetadata
        return ToolMetadata(
            name="http_delete",
            description=(
                "Use this tool to delete resources or cancel operations. "
                "Parameters: api_name (str), path (str), headers (dict, optional)"
            )
        )
    
    def __call__(self, api_name: str, path: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        return self.call(api_name, path, headers, **kwargs)
    
    def call(self, api_name: str, path: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        mcp_call = MCPToolCall(
            target_api_name=api_name,
            http_method=HTTPMethod.DELETE,
            endpoint_path=path,
            session_headers=headers or {}
        )
        
        logger.info("Executing HTTP DELETE tool ()", trace_id=trace_id, api_name=api_name, path=path)
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.mcp_gateway_url}/mcp/request",
                    json=mcp_call.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Trace-ID": trace_id,
                    }
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "method": "DELETE",
                    "api_name": api_name,
                    "path": path,
                    "data": None
                }
                
                try:
                    result["data"] = response.json()
                except json.JSONDecodeError:
                    result["data"] = response.text
                
                logger.info("HTTP DELETE completed ()", trace_id=trace_id, status_code=response.status_code, success=result["success"])
                
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
            logger.error("HTTP DELETE failed ()", trace_id=trace_id, error=str(e))
            return error_result


class StateUpdateTool(BaseTool):
    """ Tool for internal session context management."""
    
    def __init__(self, agent_worker: Optional[Any] = None):
        self.agent_worker = agent_worker
        super().__init__()
    
    @property
    def metadata(self):
        from llama_index.core.tools.tool_spec.base import ToolMetadata
        return ToolMetadata(
            name="state_update",
            description=(
                "Use this tool to save session data for future requests. "
                "Parameters: session_id (str), session_data (dict)"
            )
        )
    
    def __call__(self, session_id: str, session_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        return self.call(session_id, session_data, **kwargs)
    
    def call(self, session_id: str, session_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info("Executing state update tool ()", trace_id=trace_id, session_id=session_id)
        
        try:
            if self.agent_worker and hasattr(self.agent_worker, 'update_session_data'):
                self.agent_worker.update_session_data(session_id, session_data)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": True,
                    "session_id": session_id,
                    "updated_keys": list(session_data.keys()),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "action": "state_update"
                }
                
                logger.info("State update completed ()", trace_id=trace_id, session_id=session_id)
                
                return result
            else:
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
                logger.warning("State update completed without agent worker ()", trace_id=trace_id, session_id=session_id)
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
            logger.error("State update failed ()", trace_id=trace_id, session_id=session_id, error=str(e))
            return error_result
