"""
Structured logging utilities for TESH-Query

Provides production-grade logging with proper formatting, levels, and integration
with monitoring systems using logfire.
"""

import logging
import os
import sys
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Dict, Optional

from rich.console import Console

# Initialize logfire for production monitoring - but only if configured
try:
    import logfire
    # Only configure logfire if we have credentials or explicit config
    if os.getenv('LOGFIRE_TOKEN') or os.getenv('LOGFIRE_PROJECT_NAME'):
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
    
    def __init__(self, name: str = "teshq"):
        self.logger = logging.getLogger(name)
        self.console = Console()
        self._setup_logger()
        
    def _setup_logger(self):
        """Configure the logger with appropriate handlers and formatters."""
        if not self.logger.handlers:
            # Set up console handler
            console_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self.logger.info(message, extra=kwargs)
        if LOGFIRE_ENABLED and logfire:
            logfire.info(message, **kwargs)
    
    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with structured data."""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
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


# Global logger instance
logger = TeshqLogger()


def log_performance(operation_name: str):
    """Decorator to log performance metrics for operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{int(start_time * 1000)}"
            
            logger.info(
                f"Starting {operation_name}",
                operation_id=operation_id,
                operation_name=operation_name
            )
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.success(
                    f"Completed {operation_name}",
                    operation_id=operation_id,
                    operation_name=operation_name,
                    execution_time_seconds=execution_time,
                    status="success"
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
                    status="error"
                )
                raise
                
        return wrapper
    return decorator


@contextmanager
def log_operation(operation_name: str, **context):
    """Context manager to log the start and end of operations with metrics."""
    start_time = time.time()
    operation_id = f"{operation_name}_{int(start_time * 1000)}"
    
    logger.info(
        f"Starting {operation_name}",
        operation_id=operation_id,
        operation_name=operation_name,
        **context
    )
    
    try:
        yield operation_id
        execution_time = time.time() - start_time
        
        logger.success(
            f"Completed {operation_name}",
            operation_id=operation_id,
            operation_name=operation_name,
            execution_time_seconds=execution_time,
            status="success",
            **context
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
            **context
        )
        raise


class MetricsCollector:
    """Collects and logs performance metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
    
    def record_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None):
        """Record a metric with optional tags."""
        tags = tags or {}
        
        logger.info(
            f"Metric: {name}",
            metric_name=name,
            metric_value=value,
            **tags
        )
        
        # Store for aggregation
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append({
            'value': value,
            'timestamp': time.time(),
            'tags': tags
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        summary = {}
        for name, values in self.metrics.items():
            if values and isinstance(values[0]['value'], (int, float)):
                numeric_values = [v['value'] for v in values]
                summary[name] = {
                    'count': len(numeric_values),
                    'avg': sum(numeric_values) / len(numeric_values),
                    'min': min(numeric_values),
                    'max': max(numeric_values),
                    'total': sum(numeric_values)
                }
            else:
                summary[name] = {'count': len(values)}
        
        return summary


# Global metrics collector
metrics = MetricsCollector()


def log_query_metrics(query_type: str, execution_time: float, row_count: int = None, **kwargs):
    """Log specific query performance metrics."""
    metrics.record_metric("query_execution_time", execution_time, {"query_type": query_type})
    
    if row_count is not None:
        metrics.record_metric("query_row_count", row_count, {"query_type": query_type})
    
    logger.info(
        "Query execution completed",
        query_type=query_type,
        execution_time_seconds=execution_time,
        row_count=row_count,
        **kwargs
    )


def log_api_call(provider: str, model: str, tokens_used: int = None, **kwargs):
    """Log API call metrics."""
    metrics.record_metric("api_call", 1, {"provider": provider, "model": model})
    
    if tokens_used:
        metrics.record_metric("api_tokens_used", tokens_used, {"provider": provider, "model": model})
    
    logger.info(
        "API call completed",
        provider=provider,
        model=model,
        tokens_used=tokens_used,
        **kwargs
    )