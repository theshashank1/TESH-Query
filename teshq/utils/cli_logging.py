"""
Structured CLI logging system for TESH-Query.

Provides opt-in logging functionality that writes command logs to files 
instead of cluttering the terminal, with support for configuration-based 
default behavior.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json

from teshq.utils.config import get_config
from teshq.utils.logging import logger


class CLILoggerConfig:
    """Configuration for CLI logging behavior."""
    
    def __init__(self):
        self.enabled_by_default = self._get_default_logging_setting()
        self.log_directory = Path("logs")
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.max_log_files = 30  # Keep logs for 30 days
        
    def _get_default_logging_setting(self) -> bool:
        """Get default logging setting from config or environment."""
        # Check environment variable first
        env_setting = os.getenv("TESH_CLI_LOGGING", "").lower()
        if env_setting in ("true", "1", "yes", "on"):
            return True
        elif env_setting in ("false", "0", "no", "off"):
            return False
        
        # Check config file
        try:
            config = get_config()
            return config.get("CLI_LOGGING", False)
        except Exception:
            return False


class CLILogger:
    """Manages structured logging for CLI commands."""
    
    def __init__(self, command_name: str, config: Optional[CLILoggerConfig] = None):
        self.command_name = command_name
        self.config = config or CLILoggerConfig()
        self.log_file_path: Optional[Path] = None
        self.file_handler: Optional[logging.FileHandler] = None
        
        # Create command-specific logger
        self.command_logger = logging.getLogger(f"teshq.cli.{command_name}")
        
    def should_log_to_file(self, explicit_flag: Optional[bool] = None) -> bool:
        """Determine if logging should be enabled based on flag and config."""
        # Explicit flag overrides config
        if explicit_flag is not None:
            return explicit_flag
        
        # Use config default
        return self.config.enabled_by_default
    
    def setup_file_logging(self, log_flag: Optional[bool] = None) -> bool:
        """Set up file logging if enabled. Returns True if logging is active."""
        if not self.should_log_to_file(log_flag):
            return False
        
        try:
            # Create logs directory
            self.config.log_directory.mkdir(parents=True, exist_ok=True)
            
            # Clean up old log files
            self._cleanup_old_logs()
            
            # Create log file path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file_path = self.config.log_directory / f"{self.command_name}_{timestamp}.log"
            
            # Set up file handler
            self.file_handler = logging.FileHandler(self.log_file_path)
            self.file_handler.setLevel(logging.DEBUG)
            
            # Set up formatter
            formatter = logging.Formatter(self.config.log_format)
            self.file_handler.setFormatter(formatter)
            
            # Add handler to command logger
            self.command_logger.addHandler(self.file_handler)
            self.command_logger.setLevel(logging.DEBUG)
            
            # Also add to main logger to capture all logs
            main_logger = logging.getLogger("teshq")
            main_logger.addHandler(self.file_handler)
            
            # Log startup message
            self.log_info(f"CLI logging started for command: {self.command_name}")
            self.log_info(f"Log file: {self.log_file_path}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to setup CLI file logging: {e}")
            return False
    
    def log_info(self, message: str, **kwargs):
        """Log info message to file."""
        if self.file_handler:
            extra_info = f" | {json.dumps(kwargs)}" if kwargs else ""
            self.command_logger.info(f"{message}{extra_info}")
    
    def log_error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message to file."""
        if self.file_handler:
            error_info = f" | Error: {error}" if error else ""
            extra_info = f" | {json.dumps(kwargs)}" if kwargs else ""
            self.command_logger.error(f"{message}{error_info}{extra_info}")
    
    def log_warning(self, message: str, **kwargs):
        """Log warning message to file."""
        if self.file_handler:
            extra_info = f" | {json.dumps(kwargs)}" if kwargs else ""
            self.command_logger.warning(f"{message}{extra_info}")
    
    def log_debug(self, message: str, **kwargs):
        """Log debug message to file."""
        if self.file_handler:
            extra_info = f" | {json.dumps(kwargs)}" if kwargs else ""
            self.command_logger.debug(f"{message}{extra_info}")
    
    def log_command_start(self, args: Dict[str, Any]):
        """Log command start with arguments."""
        self.log_info("Command started", args=args)
    
    def log_command_end(self, success: bool, duration_seconds: float, **kwargs):
        """Log command completion."""
        status = "SUCCESS" if success else "FAILED"
        self.log_info(f"Command completed: {status}", 
                     duration_seconds=duration_seconds, **kwargs)
    
    def log_query_execution(self, query: str, parameters: Dict[str, Any], 
                           row_count: int, execution_time_ms: float):
        """Log query execution details."""
        self.log_info("Query executed", 
                     query=query[:200] + "..." if len(query) > 200 else query,
                     parameters=parameters,
                     row_count=row_count,
                     execution_time_ms=execution_time_ms)
    
    def log_token_usage(self, tokens: int, cost: float, model: str):
        """Log LLM token usage."""
        self.log_info("LLM token usage", 
                     tokens=tokens, cost=cost, model=model)
    
    def log_configuration_change(self, setting: str, old_value: Any, new_value: Any):
        """Log configuration changes."""
        self.log_info("Configuration changed", 
                     setting=setting, old_value=old_value, new_value=new_value)
    
    def log_file_operation(self, operation: str, file_path: str, 
                          success: bool, size_bytes: Optional[int] = None):
        """Log file operations like save/export."""
        self.log_info(f"File operation: {operation}", 
                     file_path=file_path, success=success, 
                     size_bytes=size_bytes)
    
    def cleanup(self):
        """Clean up logging resources."""
        if self.file_handler:
            # Log completion
            self.log_info(f"CLI logging completed for command: {self.command_name}")
            
            # Remove handler
            self.command_logger.removeHandler(self.file_handler)
            main_logger = logging.getLogger("teshq")
            main_logger.removeHandler(self.file_handler)
            
            # Close file handler
            self.file_handler.close()
            self.file_handler = None
            
            # Print log file location to user
            if self.log_file_path and self.log_file_path.exists():
                from teshq.utils.ui import info
                info(f"📁 Command logs saved to: {self.log_file_path}")
    
    def _cleanup_old_logs(self):
        """Remove old log files to prevent disk space issues."""
        try:
            if not self.config.log_directory.exists():
                return
            
            # Get all log files for this command
            pattern = f"{self.command_name}_*.log"
            log_files = list(self.config.log_directory.glob(pattern))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Remove files beyond the limit
            for old_file in log_files[self.config.max_log_files:]:
                try:
                    old_file.unlink()
                except Exception:
                    pass  # Ignore errors in cleanup
                    
        except Exception:
            pass  # Ignore cleanup errors


def add_logging_option(func):
    """Decorator to add --log option to CLI commands."""
    import typer
    
    def wrapper(*args, **kwargs):
        # Extract log parameter if present
        log_param = kwargs.pop('log', None)
        
        # Create CLI logger
        command_name = func.__name__
        if hasattr(func, '__module__'):
            # Extract command name from module path
            module_parts = func.__module__.split('.')
            if len(module_parts) > 2 and module_parts[-2] == 'cli':
                command_name = module_parts[-1]
        
        cli_logger = CLILogger(command_name)
        
        # Setup logging
        logging_active = cli_logger.setup_file_logging(log_param)
        
        try:
            import time
            start_time = time.time()
            
            # Log command start
            if logging_active:
                cli_logger.log_command_start({
                    'args': args,
                    'kwargs': {k: v for k, v in kwargs.items() if k != 'password'}  # Exclude sensitive data
                })
            
            # Add logger to kwargs for command to use
            kwargs['_cli_logger'] = cli_logger
            
            # Execute original function
            result = func(*args, **kwargs)
            
            # Log successful completion
            if logging_active:
                duration = time.time() - start_time
                cli_logger.log_command_end(True, duration)
            
            return result
            
        except Exception as e:
            # Log error
            if logging_active:
                duration = time.time() - start_time
                cli_logger.log_command_end(False, duration, error=str(e))
            raise
        finally:
            # Cleanup
            cli_logger.cleanup()
    
    # Preserve function metadata
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    
    # Add log parameter to function signature
    import inspect
    sig = inspect.signature(func)
    new_params = list(sig.parameters.values())
    
    # Add log parameter if not already present
    if 'log' not in sig.parameters:
        log_param = inspect.Parameter(
            'log',
            inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=bool,
        )
        new_params.append(log_param)
    
    wrapper.__signature__ = sig.replace(parameters=new_params)
    
    return wrapper


# Convenience function for manual logging in commands
def get_cli_logger(command_name: str, log_flag: Optional[bool] = None) -> CLILogger:
    """Get a CLI logger for manual use in commands."""
    cli_logger = CLILogger(command_name)
    cli_logger.setup_file_logging(log_flag)
    return cli_logger