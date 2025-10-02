"""
Logging configuration for MCP Gateway.
Implements structured logging for Requirements 4.2, 8.2.
"""

import logging
import logging.config
import sys
from typing import Dict, Any

from pythonjsonlogger import jsonlogger

from .models import LoggingConfig


def setup_logging(config: LoggingConfig):
    """
    Setup structured logging configuration.
    
    Requirement 4.2: Structured logging for all requests and responses.
    Requirement 8.2: Comprehensive logging for observability.
    """
    
    # Define log format based on configuration
    if config.format.lower() == "json":
        formatter_class = jsonlogger.JsonFormatter
        log_format = "%(asctime)s %(name)s %(levelname)s %(message)s %(trace_id)s %(api_name)s %(method)s %(path)s %(status_code)s %(execution_time)s"
    else:
        formatter_class = logging.Formatter
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s [trace_id=%(trace_id)s]"
    
    # Logging configuration dictionary
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": formatter_class,
                "format": log_format
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": config.level.upper(),
                "formatter": "default",
                "stream": sys.stdout
            }
        },
        "loggers": {
            "": {  # Root logger
                "level": config.level.upper(),
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "httpx": {
                "level": "WARNING",  # Reduce noise from HTTP client
                "handlers": ["console"],
                "propagate": False
            }
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Set up custom log record factory for trace ID
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        
        # Add default values for custom fields
        record.trace_id = getattr(record, 'trace_id', 'N/A')
        record.api_name = getattr(record, 'api_name', 'N/A')
        record.method = getattr(record, 'method', 'N/A')
        record.path = getattr(record, 'path', 'N/A')
        record.status_code = getattr(record, 'status_code', 'N/A')
        record.execution_time = getattr(record, 'execution_time', 'N/A')
        record.client_ip = getattr(record, 'client_ip', 'N/A')
        
        return record
    
    logging.setLogRecordFactory(record_factory)


class TraceIDFilter(logging.Filter):
    """
    Logging filter to ensure trace ID is always present.
    """
    
    def filter(self, record):
        if not hasattr(record, 'trace_id'):
            record.trace_id = 'N/A'
        return True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with trace ID support.
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.addFilter(TraceIDFilter())
    return logger