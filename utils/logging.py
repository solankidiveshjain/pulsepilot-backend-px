"""
Logging configuration and utilities
"""

import os
import logging
import sys
from datetime import datetime
from typing import Dict, Any


def setup_logging():
    """Setup application logging"""
    
    # Configure logging level
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)


class StructuredLogger:
    """Structured logger for API events"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_api_request(
        self,
        method: str,
        endpoint: str,
        team_id: str = None,
        user_id: str = None,
        **kwargs
    ):
        """Log API request"""
        self.logger.info(
            "API Request",
            extra={
                "event_type": "api_request",
                "method": method,
                "endpoint": endpoint,
                "team_id": team_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                **kwargs
            }
        )
    
    def log_api_response(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: int,
        team_id: str = None,
        user_id: str = None,
        **kwargs
    ):
        """Log API response"""
        self.logger.info(
            "API Response",
            extra={
                "event_type": "api_response",
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "team_id": team_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                **kwargs
            }
        )
    
    def log_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        **kwargs
    ):
        """Log error with context"""
        self.logger.error(
            f"Error: {str(error)}",
            extra={
                "event_type": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat(),
                **kwargs
            }
        )
