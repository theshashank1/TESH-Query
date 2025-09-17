"""
Structured logging utilities for TESH-Query

Provides production-grade logging with proper formatting, levels, and integration
with monitoring systems using logfire.
"""

import logging
import os
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
            
            file_handler = logging.FileHandler(self.log_file_path, mode='a', encoding='utf-8')
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
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
            self.logger.handlers = [h for h in self.logger.handlers if not isinstance(h, logging.StreamHandler) or h.stream != sys.stdout]

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


def log_performance(operation_name: str):
    """Decorator to log performance metrics for operations."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{int(start_time * 1000)}"

            logger.info(f"Starting {operation_name}", operation_id=operation_id, operation_name=operation_name)

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                logger.success(
                    f"Completed {operation_name}",
                    operation_id=operation_id,
                    operation_name=operation_name,
                    execution_time_seconds=execution_time,
                    status="success",
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                logger.error(
                    f"Failed {operation_name}",
                    error=e,
                    operation_id=operation_id,
                    operation_name=operation_name,
                    execution_time_seconds=execution_time,
                    status="error",
                )
                raise

        return wrapper

    return decorator


@contextmanager
def log_operation(operation_name: str, **context):
    """Context manager to log the start and end of operations with metrics."""
    start_time = time.time()
    operation_id = f"{operation_name}_{int(start_time * 1000)}"

    logger.info(f"Starting {operation_name}", operation_id=operation_id, operation_name=operation_name, **context)

    try:
        yield operation_id
        execution_time = time.time() - start_time

        logger.success(
            f"Completed {operation_name}",
            operation_id=operation_id,
            operation_name=operation_name,
            execution_time_seconds=execution_time,
            status="success",
            **context,
        )

    except Exception as e:
        execution_time = time.time() - start_time

        logger.error(
            f"Failed {operation_name}",
            error=e,
            operation_id=operation_id,
            operation_name=operation_name,
            execution_time_seconds=execution_time,
            status="error",
            **context,
        )
        raise


class MetricsCollector:
    """Collects and provides advanced aggregation for performance metrics."""

    def __init__(self):
        self.metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.counters: Dict[str, Union[int, float]] = defaultdict(int)
        self.gauges: Dict[str, Union[int, float]] = defaultdict(int)

    def add_point(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None):
        """Record a single data point for a metric with optional tags."""
        tags = tags or {}
        self.metrics[name].append({"value": value, "timestamp": time.time(), "tags": tags})
        logger.debug(f"Metric point: {name}", metric_name=name, metric_value=value, **tags)

    def increment_counter(self, name: str, value: Union[int, float] = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter. Useful for tracking counts of events."""
        tags_key = self._get_tags_key(tags)
        counter_key = f"{name}{tags_key}"
        self.counters[counter_key] += value
        logger.debug(f"Metric counter incremented: {name}", metric_name=name, increment_value=value, **(tags or {}))

    def set_gauge(self, name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """Set a gauge to a specific value. Useful for tracking current states."""
        tags_key = self._get_tags_key(tags)
        gauge_key = f"{name}{tags_key}"
        self.gauges[gauge_key] = value
        logger.debug(f"Metric gauge set: {name}", metric_name=name, gauge_value=value, **(tags or {}))

    def get_metric(self, name: str) -> List[Dict[str, Any]]:
        """Get all data points for a specific metric."""
        return self.metrics.get(name, [])

    def get_summary(self, group_by: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a summary of all collected metrics, with optional grouping by tags."""
        summary = {}

        # Summarize point-based metrics
        for name, points in self.metrics.items():
            if not points:
                continue

            # Ensure the metric is numeric
            if not isinstance(points[0]["value"], (int, float)):
                summary[name] = {"count": len(points)}
                continue

            if not group_by:
                numeric_values = [p["value"] for p in points]
                summary[name] = self._calculate_stats(numeric_values)
            else:
                summary[name] = self._summarize_by_group(points, group_by)

        # Add counters and gauges to the summary
        summary["counters"] = dict(self.counters)
        summary["gauges"] = dict(self.gauges)

        return summary

    def _summarize_by_group(self, points: List[Dict[str, Any]], group_by: List[str]) -> Dict[str, Any]:
        grouped_data = defaultdict(list)
        for point in points:
            key_parts = [str(point["tags"].get(g, "untagged")) for g in group_by]
            group_key = ":".join(key_parts)
            grouped_data[group_key].append(point["value"])

        group_summary = {}
        for group_name, values in grouped_data.items():
            group_summary[group_name] = self._calculate_stats(values)
        return group_summary

    @staticmethod
    def _calculate_stats(values: List[Union[int, float]]) -> Dict[str, Any]:
        """Calculate basic statistics for a list of numeric values."""
        if not values:
            return {"count": 0}
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "total": sum(values),
        }

    @staticmethod
    def _get_tags_key(tags: Optional[Dict[str, str]]) -> str:
        if not tags:
            return ""
        return "[" + ",".join(sorted(f"{k}={v}" for k, v in tags.items())) + "]"


# Global metrics collector
metrics = MetricsCollector()


def log_query_metrics(query_type: str, execution_time: float, row_count: int = None, **kwargs):
    """Log specific query performance metrics."""
    tags = {"query_type": query_type, **kwargs.get("tags", {})}
    metrics.add_point("db_query_execution_time", execution_time, tags)

    if row_count is not None:
        metrics.add_point("db_query_row_count", row_count, tags)

    logger.info(
        "Query execution completed",
        query_type=query_type,
        execution_time_seconds=execution_time,
        row_count=row_count,
        **kwargs,
    )


def log_api_call(provider: str, model: str, tokens_used: int = None, **kwargs):
    """Log API call metrics."""
    tags = {"provider": provider, "model": model}
    metrics.increment_counter("api_calls_total", tags=tags)

    if tokens_used:
        metrics.add_point("api_tokens_used", tokens_used, tags=tags)

    logger.info("API call completed", provider=provider, model=model, tokens_used=tokens_used, **kwargs)
