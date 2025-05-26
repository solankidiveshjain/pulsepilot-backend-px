"""
Structured JSON logging with request context
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4
from contextvars import ContextVar

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
team_id_var: ContextVar[Optional[str]] = ContextVar('team_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add request context if available
        if request_id_var.get():
            log_data["request_id"] = request_id_var.get()
        if team_id_var.get():
            log_data["team_id"] = team_id_var.get()
        if user_id_var.get():
            log_data["user_id"] = user_id_var.get()
        
        # Add extra fields from log record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class StructuredLogger:
    """Structured logger with context management"""
    
    def __init__(self, name: str):
        """
        Initialize structured logger
        
        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with structured data"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with structured data"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with structured data"""
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with structured data"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """
        Internal logging method with extra fields
        
        Args:
            level: Log level
            message: Log message
            **kwargs: Additional structured data
        """
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.log(level, message, extra=extra)


def setup_structured_logging() -> None:
    """Setup structured JSON logging for the application"""
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def set_request_context(request_id: str, team_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    Set request context for structured logging
    
    Args:
        request_id: Unique request identifier
        team_id: Team ID if available
        user_id: User ID if available
    """
    request_id_var.set(request_id)
    if team_id:
        team_id_var.set(team_id)
    if user_id:
        user_id_var.set(user_id)


def get_structured_logger(name: str) -> StructuredLogger:
    """
    Get structured logger instance
    
    Args:
        name: Logger name
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)
