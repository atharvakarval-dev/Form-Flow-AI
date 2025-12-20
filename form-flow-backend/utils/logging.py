"""
Logging Configuration Module

Provides structured logging with consistent formatting across the application.
Replaces all print() statements with proper logging.

Usage:
    from utils.logging import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing form", extra={"url": form_url})
    logger.error("Failed to parse", exc_info=True)
"""

import logging
import sys
from typing import Optional
from config.settings import settings


# =============================================================================
# Custom Formatters
# =============================================================================

class ColoredFormatter(logging.Formatter):
    """
    Colored log formatter for console output.
    
    Colors:
        - DEBUG: Cyan
        - INFO: Green
        - WARNING: Yellow
        - ERROR: Red
        - CRITICAL: Bold Red
    """
    
    COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[1;31m", # Bold Red
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname:8}{self.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production/structured logging.
    
    Outputs logs as JSON objects for easy parsing by log aggregators.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json
        from datetime import datetime
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra
            
        return json.dumps(log_data)


# =============================================================================
# Logger Configuration
# =============================================================================

def setup_logging(
    level: Optional[str] = None,
    json_format: bool = False
) -> None:
    """
    Configure application-wide logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to DEBUG if settings.DEBUG else INFO.
        json_format: Use JSON formatter for structured logging.
    
    Example:
        setup_logging(level="DEBUG")
        setup_logging(json_format=True)  # For production
    """
    # Determine log level
    if level is None:
        level = "DEBUG" if settings.DEBUG else "INFO"
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Choose formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = ColoredFormatter(
            fmt="%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s",
            datefmt="%H:%M:%S"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name, typically __name__ of the calling module.
    
    Returns:
        logging.Logger: Configured logger instance.
    
    Example:
        logger = get_logger(__name__)
        logger.info("Starting process")
        logger.debug("Debug details", extra={"data": some_dict})
    """
    return logging.getLogger(name)


# =============================================================================
# Convenience Functions
# =============================================================================

def log_api_call(
    service: str,
    endpoint: str,
    success: bool,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """
    Log an external API call with standard format.
    
    Args:
        service: Name of the service (e.g., "ElevenLabs", "Gemini")
        endpoint: API endpoint called
        success: Whether the call succeeded
        duration_ms: Call duration in milliseconds
        error: Error message if failed
    """
    logger = get_logger("api")
    
    status = "✅" if success else "❌"
    msg = f"{status} {service} | {endpoint}"
    
    if duration_ms is not None:
        msg += f" | {duration_ms:.0f}ms"
    
    if success:
        logger.info(msg)
    else:
        logger.error(f"{msg} | Error: {error}")


def log_form_action(
    action: str,
    url: str,
    success: bool,
    details: Optional[str] = None
) -> None:
    """
    Log a form-related action with standard format.
    
    Args:
        action: Action performed (e.g., "scrape", "submit", "fill")
        url: Form URL
        success: Whether the action succeeded
        details: Additional details
    """
    logger = get_logger("form")
    
    status = "✅" if success else "❌"
    msg = f"{status} {action.upper()} | {url[:50]}..."
    
    if details:
        msg += f" | {details}"
    
    if success:
        logger.info(msg)
    else:
        logger.warning(msg)
