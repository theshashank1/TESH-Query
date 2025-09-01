"""Enhanced error handling for TESH-Query."""

import sys
import traceback
import logging
from typing import Optional, Any, Dict
from functools import wraps

from teshq.utils.validation import ValidationError


class TeshqError(Exception):
    """Base exception for TESH-Query specific errors."""
    
    def __init__(self, message: str, suggestions: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.suggestions = suggestions
        self.details = details or {}


class ConfigurationError(TeshqError):
    """Error related to configuration issues."""
    pass


class DatabaseError(TeshqError):
    """Error related to database operations."""
    pass


class QueryError(TeshqError):
    """Error related to query generation or execution."""
    pass


class APIError(TeshqError):
    """Error related to external API calls."""
    pass


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        verbose: Enable verbose/debug logging
        
    Returns:
        Configured logger instance
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger('teshq')


def handle_error(error: Exception, context: str = "Operation", show_traceback: bool = False, 
                suggest_action: str = "") -> None:
    """
    Handle and display errors in a user-friendly manner.
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        show_traceback: Whether to show full traceback
        suggest_action: Suggested action for the user
    """
    logger = logging.getLogger('teshq')
    
    # Determine error type and message
    if isinstance(error, TeshqError):
        error_type = type(error).__name__
        message = error.message
        suggestions = error.suggestions or suggest_action
        details = error.details
    elif isinstance(error, ValidationError):
        error_type = "ValidationError"
        message = str(error)
        suggestions = suggest_action or "Please check your input and try again"
        details = {}
    else:
        error_type = type(error).__name__
        message = str(error)
        suggestions = suggest_action or "Please check the logs and try again"
        details = {}
    
    # Log the error
    logger.error(f"{context} failed: {error_type}: {message}")
    
    # Display user-friendly error
    print(f"\n❌ {context} Failed")
    print(f"Error: {message}")
    
    if suggestions:
        print(f"💡 Suggestion: {suggestions}")
    
    if details:
        print("\nAdditional Information:")
        for key, value in details.items():
            print(f"  {key}: {value}")
    
    if show_traceback:
        print("\nDetailed Traceback:")
        traceback.print_exc()


def error_handler(context: str = "Operation", reraise: bool = False, 
                 suggest_action: str = ""):
    """
    Decorator for automatic error handling.
    
    Args:
        context: Context description for the error
        reraise: Whether to reraise the exception after handling
        suggest_action: Suggested action for the user
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handle_error(e, context, suggest_action=suggest_action)
                if reraise:
                    raise
                return None
        return wrapper
    return decorator


def graceful_exit(message: str, exit_code: int = 1) -> None:
    """
    Exit the application gracefully with a message.
    
    Args:
        message: Exit message
        exit_code: Exit code (0 for success, non-zero for error)
    """
    if exit_code == 0:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    
    sys.exit(exit_code)


def validate_and_execute(validation_func, data, context: str = "Validation"):
    """
    Validate data and handle validation errors gracefully.
    
    Args:
        validation_func: Function to validate the data
        data: Data to validate
        context: Context for error reporting
        
    Returns:
        Validated data or None if validation fails
    """
    try:
        return validation_func(data)
    except ValidationError as e:
        handle_error(e, context)
        return None
    except Exception as e:
        handle_error(e, context, suggest_action="Please check your input format")
        return None


def safe_database_operation(operation_func, *args, **kwargs):
    """
    Execute database operation with error handling.
    
    Args:
        operation_func: Database operation function
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation
        
    Returns:
        Operation result or None if it fails
    """
    try:
        return operation_func(*args, **kwargs)
    except Exception as e:
        error_context = "Database Operation"
        suggestions = []
        
        # Provide specific suggestions based on error type
        error_str = str(e).lower()
        
        if "connection" in error_str:
            suggestions.append("Check your database connection URL")
            suggestions.append("Ensure the database server is running")
            suggestions.append("Verify network connectivity")
        elif "authentication" in error_str or "password" in error_str:
            suggestions.append("Check your database credentials")
            suggestions.append("Verify username and password")
        elif "permission" in error_str or "access" in error_str:
            suggestions.append("Check database permissions")
            suggestions.append("Verify user has required access rights")
        elif "table" in error_str and "not exist" in error_str:
            suggestions.append("Check if the table exists in the database")
            suggestions.append("Run database introspection to see available tables")
        else:
            suggestions.append("Check the database configuration")
            suggestions.append("Review the error message for specific details")
        
        handle_error(
            DatabaseError(
                str(e),
                suggestions=" | ".join(suggestions),
                details={"operation": operation_func.__name__}
            ),
            error_context
        )
        return None


def safe_api_call(api_func, *args, **kwargs):
    """
    Execute API call with error handling.
    
    Args:
        api_func: API function to call
        *args: Arguments for the API call
        **kwargs: Keyword arguments for the API call
        
    Returns:
        API response or None if it fails
    """
    try:
        return api_func(*args, **kwargs)
    except Exception as e:
        error_context = "API Call"
        suggestions = []
        
        # Provide specific suggestions based on error type
        error_str = str(e).lower()
        
        if "api key" in error_str or "authentication" in error_str:
            suggestions.append("Check your API key configuration")
            suggestions.append("Verify the API key is valid and active")
        elif "rate limit" in error_str or "quota" in error_str:
            suggestions.append("API rate limit exceeded")
            suggestions.append("Wait before making more requests")
        elif "network" in error_str or "connection" in error_str:
            suggestions.append("Check your internet connection")
            suggestions.append("Verify API endpoint is accessible")
        elif "timeout" in error_str:
            suggestions.append("Request timed out")
            suggestions.append("Try again or check network connectivity")
        else:
            suggestions.append("Check API configuration and try again")
        
        handle_error(
            APIError(
                str(e),
                suggestions=" | ".join(suggestions),
                details={"api_function": api_func.__name__}
            ),
            error_context
        )
        return None


class ProgressContext:
    """Context manager for showing progress and handling errors."""
    
    def __init__(self, description: str, success_message: str = "Completed successfully"):
        self.description = description
        self.success_message = success_message
        self.logger = logging.getLogger('teshq')
    
    def __enter__(self):
        print(f"⏳ {self.description}...")
        self.logger.info(f"Starting: {self.description}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            print(f"✅ {self.success_message}")
            self.logger.info(f"Completed: {self.description}")
        else:
            print(f"❌ Failed: {self.description}")
            self.logger.error(f"Failed: {self.description} - {exc_val}")
            handle_error(exc_val, self.description)
        
        # Return False to propagate exceptions
        return False