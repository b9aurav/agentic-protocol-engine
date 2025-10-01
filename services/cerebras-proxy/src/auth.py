"""
Authentication and API key management for Cerebras Proxy
"""

import os
from typing import Optional
from fastapi import HTTPException, Header
import structlog

logger = structlog.get_logger()


async def verify_api_key(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify API key from Authorization header
    
    Args:
        authorization: Authorization header value (Bearer token)
        
    Returns:
        str: The verified API key
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    # Get expected API key from environment
    expected_api_key = os.getenv("APE_API_KEY")
    
    # If no API key is configured, allow all requests (development mode)
    if not expected_api_key:
        logger.warning("No APE_API_KEY configured - allowing all requests")
        return "development"
    
    # Check if Authorization header is present
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    # Parse Bearer token
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        logger.warning("Invalid Authorization header format", authorization=authorization)
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    # Verify API key
    if token != expected_api_key:
        logger.warning("Invalid API key provided", provided_key_prefix=token[:8] + "...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    logger.debug("API key verified successfully")
    return token


def get_cerebras_api_key() -> str:
    """
    Get Cerebras API key from environment
    
    Returns:
        str: Cerebras API key
        
    Raises:
        ValueError: If CEREBRAS_API_KEY is not set
    """
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY environment variable is required")
    return api_key