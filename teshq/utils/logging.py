"""
Structured logging utilities for TESH-Query

Provides production-grade logging with proper formatting, levels, and integration
with monitoring systems using logfire.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console

# Initialize logfire for production monitoring - but only if configured
try:
    import logfire

    # Only configure logfire if we have credentials or explicit config
    if os.getenv("LOGFIRE_TOKEN") or os.getenv("LOGFIRE_PROJECT_NAME"):
        logfire.configure()
        LOGFIRE_ENABLED = True
    else:
        LOGFIRE_ENABLED = False
except ImportError:
    LOGFIRE_ENABLED = False
    logfire = None
except Exception:
    # If logfire configuration fails, continue without it
    LOGFIRE_ENABLED = False
    logfire = None


class TeshqLogger:
    """Production-grade logger for TESH-Query with structured logging."""

    def __init__(self, name: str = "teshq", enable_cli_output: bool = False, log_file_path: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.console = Console()
        self.enable_cli_output = enable_cli_output
        self.log_file_path = log_file_path or self._get_default_log_path()
        self._setup_logger()

    def _get_default_log_path(self) -> str:
        """Get the default log file path."""
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        return str(log_dir / "teshq.log")

    def _setup_logger(self):
        """Configure the logger with appropriate handlers and formatters."""
        if self.logger.handlers:
            # Clear existing handlers to avoid duplicates
            self.logger.handlers.clear()

        # Always set up file handler for logging to file
        self._setup_file_handler()

        # Set up console handler only if CLI output is enabled
        if self.enable_cli_output:
            self._setup_console_handler()

        self.logger.setLevel(logging.INFO)

    def _setup_file_handler(self):
        """Set up file handler for logging to file."""
        try:
            # Ensure log directory exists
            log_path = Path(self.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(self.log_file_path, mode="a", encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            # If file logging fails, fallback to stderr
            fallback_handler = logging.StreamHandler(sys.stderr)
            fallback_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(fallback_handler)
            # Log the error to stderr
            self.logger.error(f"Failed to set up file logging: {e}")

    def _setup_console_handler(self):
        """Set up console handler for CLI output."""
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def enable_cli_logging(self):
        """Enable CLI output for debugging."""
        if not self.enable_cli_output:
            self.enable_cli_output = True
            self._setup_console_handler()

    def disable_cli_logging(self):
        """Disable CLI output, keep only file logging."""
        if self.enable_cli_output:
            self.enable_cli_output = False
            # Remove console handlers
            self.logger.handlers = [
                h for h in self.logger.handlers if not isinstance(h, logging.StreamHandler) or h.stream != sys.stdout
            ]

    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self.logger.info(message, extra=kwargs)
        if LOGFIRE_ENABLED and logfire:
            logfire.info(message, **kwargs)

    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with structured data."""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)
        self.logger.error(message, extra=kwargs)
        if LOGFIRE_ENABLED and logfire:
            logfire.error(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self.logger.warning(message, extra=kwargs)
        if LOGFIRE_ENABLED and logfire:
            logfire.warn(message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self.logger.debug(message, extra=kwargs)
        if LOGFIRE_ENABLED and logfire:
            logfire.debug(message, **kwargs)

    def success(self, message: str, **kwargs):
        """Log success message with structured data."""
        self.logger.info(f"SUCCESS: {message}", extra=kwargs)
        if LOGFIRE_ENABLED and logfire:
            logfire.info(f"SUCCESS: {message}", **kwargs)


# Global logger instance - default to file-only logging
logger = TeshqLogger()


# Function to configure global logger
def configure_global_logger(enable_cli_output: bool = False, log_file_path: Optional[str] = None):
    """Configure the global logger with CLI output and log file settings."""
    global logger
    logger = TeshqLogger(enable_cli_output=enable_cli_output, log_file_path=log_file_path)
    return logger
