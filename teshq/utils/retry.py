"""
Retry mechanism with exponential backoff for API calls and external operations.

Provides robust error recovery for network operations, API calls, and database connections
with configurable retry policies and intelligent backoff strategies.
"""

import random
import time
from functools import wraps
from typing import Any, Callable, List, Optional, Type, Union

from teshq.utils.logging import logger


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [
            ConnectionError,
            TimeoutError,
            OSError,  # Network-related errors
        ]


class RetryableError(Exception):
    """Exception that indicates an operation should be retried."""
    pass


class NonRetryableError(Exception):
    """Exception that indicates an operation should NOT be retried."""
    pass


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate the delay for the next retry attempt."""
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    
    # Apply maximum delay cap
    delay = min(delay, config.max_delay)
    
    # Add jitter to prevent thundering herd
    if config.jitter:
        delay *= (0.5 + random.random() * 0.5)  # Random factor between 0.5 and 1.0
    
    return delay


def is_retryable(exception: Exception, config: RetryConfig) -> bool:
    """Determine if an exception should trigger a retry."""
    # Explicit retry control
    if isinstance(exception, RetryableError):
        return True
    if isinstance(exception, NonRetryableError):
        return False
    
    # Check against configured retryable exceptions
    return any(isinstance(exception, exc_type) for exc_type in config.retryable_exceptions)


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    operation_name: str = "operation"
):
    """
    Decorator to add retry logic with exponential backoff to functions.
    
    Args:
        config: RetryConfig instance with retry parameters
        operation_name: Name of the operation for logging
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    logger.debug(
                        f"Attempting {operation_name}",
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        operation_name=operation_name
                    )
                    
                    result = func(*args, **kwargs)
                    
                    if attempt > 1:
                        logger.success(
                            f"Succeeded {operation_name} after retries",
                            attempt=attempt,
                            operation_name=operation_name
                        )
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    if not is_retryable(e, config):
                        logger.error(
                            f"Non-retryable error in {operation_name}",
                            error=e,
                            attempt=attempt,
                            operation_name=operation_name
                        )
                        raise
                    
                    if attempt == config.max_attempts:
                        logger.error(
                            f"Max retries exceeded for {operation_name}",
                            error=e,
                            attempt=attempt,
                            max_attempts=config.max_attempts,
                            operation_name=operation_name
                        )
                        break
                    
                    delay = calculate_delay(attempt, config)
                    
                    logger.warning(
                        f"Retry {attempt} failed for {operation_name}, retrying",
                        error=e,
                        attempt=attempt,
                        next_delay_seconds=delay,
                        operation_name=operation_name
                    )
                    
                    time.sleep(delay)
            
            # If we get here, all retries failed
            raise last_exception
            
        return wrapper
    return decorator


class AsyncRetryManager:
    """Manages retry operations for async contexts."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    async def execute_with_retry(
        self,
        operation: Callable,
        operation_name: str = "async_operation",
        *args,
        **kwargs
    ) -> Any:
        """Execute an async operation with retry logic."""
        import asyncio
        
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(
                    f"Attempting async {operation_name}",
                    attempt=attempt,
                    max_attempts=self.config.max_attempts,
                    operation_name=operation_name
                )
                
                result = await operation(*args, **kwargs)
                
                if attempt > 1:
                    logger.success(
                        f"Succeeded async {operation_name} after retries",
                        attempt=attempt,
                        operation_name=operation_name
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not is_retryable(e, self.config):
                    logger.error(
                        f"Non-retryable error in async {operation_name}",
                        error=e,
                        attempt=attempt,
                        operation_name=operation_name
                    )
                    raise
                
                if attempt == self.config.max_attempts:
                    logger.error(
                        f"Max retries exceeded for async {operation_name}",
                        error=e,
                        attempt=attempt,
                        max_attempts=self.config.max_attempts,
                        operation_name=operation_name
                    )
                    break
                
                delay = calculate_delay(attempt, self.config)
                
                logger.warning(
                    f"Async retry {attempt} failed for {operation_name}, retrying",
                    error=e,
                    attempt=attempt,
                    next_delay_seconds=delay,
                    operation_name=operation_name
                )
                
                await asyncio.sleep(delay)
        
        # If we get here, all retries failed
        raise last_exception


# Predefined retry configurations for common scenarios
API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError,
        RetryableError,
    ]
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError,
        RetryableError,
    ]
)

NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=1.5,
    retryable_exceptions=[
        ConnectionError,
        TimeoutError,
        OSError,
        RetryableError,
    ]
)


# Convenience decorators
def retry_api_call(operation_name: str = "api_call"):
    """Decorator for API calls with appropriate retry policy."""
    return retry_with_backoff(API_RETRY_CONFIG, operation_name)


def retry_database_operation(operation_name: str = "database_operation"):
    """Decorator for database operations with appropriate retry policy."""
    return retry_with_backoff(DATABASE_RETRY_CONFIG, operation_name)


def retry_network_operation(operation_name: str = "network_operation"):
    """Decorator for network operations with appropriate retry policy."""
    return retry_with_backoff(NETWORK_RETRY_CONFIG, operation_name)