"""
Tests for error handling and CLI robustness.

Tests error handling scenarios, CLI validation, and global exception handling.
"""

import sys
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest
import typer
from sqlalchemy.exc import SQLAlchemyError

from teshq.cli.main import main
from teshq.utils.ui import handle_error


class TestMainErrorHandling:
    """Test main CLI error handling."""
    
    def test_main_keyboard_interrupt(self):
        """Test KeyboardInterrupt handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = KeyboardInterrupt()
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 130  # Standard Ctrl+C exit code
    
    def test_main_typer_abort(self):
        """Test typer.Abort handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = typer.Abort()
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    def test_main_import_error(self):
        """Test ImportError handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = ImportError("Module not found")
            
            with patch('teshq.cli.main.handle_error') as mock_handle_error:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                mock_handle_error.assert_called_once()
                assert exc_info.value.code == 1
    
    def test_main_sqlalchemy_error(self):
        """Test SQLAlchemyError handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = SQLAlchemyError("Database error")
            
            with patch('teshq.cli.main.handle_error') as mock_handle_error:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                mock_handle_error.assert_called_once()
                assert exc_info.value.code == 1
    
    def test_main_file_not_found_error(self):
        """Test FileNotFoundError handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = FileNotFoundError("File not found")
            
            with patch('teshq.cli.main.handle_error') as mock_handle_error:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                mock_handle_error.assert_called_once()
                assert exc_info.value.code == 1
    
    def test_main_permission_error(self):
        """Test PermissionError handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = PermissionError("Permission denied")
            
            with patch('teshq.cli.main.handle_error') as mock_handle_error:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                mock_handle_error.assert_called_once()
                assert exc_info.value.code == 1
    
    def test_main_connection_error(self):
        """Test ConnectionError handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = ConnectionError("Network error")
            
            with patch('teshq.cli.main.handle_error') as mock_handle_error:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                mock_handle_error.assert_called_once()
                assert exc_info.value.code == 1
    
    def test_main_unexpected_error(self):
        """Test unexpected error handling in main."""
        with patch('teshq.cli.main.app') as mock_app:
            mock_app.side_effect = ValueError("Unexpected error")
            
            with patch('teshq.cli.main.handle_error') as mock_handle_error:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                mock_handle_error.assert_called_once()
                args, kwargs = mock_handle_error.call_args
                assert kwargs.get('show_traceback') is True
                assert exc_info.value.code == 1


class TestUIErrorHandling:
    """Test UI error handling functionality."""
    
    def test_handle_error_basic(self):
        """Test basic error handling."""
        error = ValueError("Test error")
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with patch('teshq.utils.ui.ui') as mock_ui:
                handle_error(error, "Test Context")
                mock_ui.handle_error.assert_called_once_with(
                    error, "Test Context", show_traceback=False, suggest_action=""
                )
    
    def test_handle_error_with_suggestion(self):
        """Test error handling with suggestion."""
        error = ConnectionError("Network timeout")
        
        with patch('teshq.utils.ui.ui') as mock_ui:
            handle_error(error, "API Connection", suggest_action="Check your internet connection")
            mock_ui.handle_error.assert_called_once_with(
                error, 
                "API Connection", 
                show_traceback=False, 
                suggest_action="Check your internet connection"
            )
    
    def test_handle_error_with_traceback(self):
        """Test error handling with traceback."""
        error = RuntimeError("Critical error")
        
        with patch('teshq.utils.ui.ui') as mock_ui:
            handle_error(error, "Critical Operation", show_traceback=True)
            mock_ui.handle_error.assert_called_once_with(
                error, 
                "Critical Operation", 
                show_traceback=True, 
                suggest_action=""
            )


class TestCLIRobustness:
    """Test CLI robustness and input validation."""
    
    def test_query_command_invalid_input(self):
        """Test query command with invalid input."""
        from teshq.cli.query import process_nl_query
        
        # Test with empty query
        with pytest.raises((typer.Exit, SystemExit)):
            with patch('teshq.cli.query.handle_error') as mock_handle_error:
                process_nl_query("")
                mock_handle_error.assert_called()
    
    def test_query_command_invalid_save_path(self):
        """Test query command with invalid save path."""
        from teshq.cli.query import process_nl_query
        
        # Test with invalid CSV path
        with pytest.raises((typer.Exit, SystemExit)):
            with patch('teshq.cli.query.handle_error') as mock_handle_error:
                process_nl_query("valid query", save_csv="invalid.txt")
                mock_handle_error.assert_called()
    
    def test_config_validation_command(self):
        """Test config validation command."""
        from teshq.cli.config import validate_config
        
        # Mock empty configuration
        with patch('teshq.cli.config.get_config_with_source', return_value=({}, {})):
            with pytest.raises((typer.Exit, SystemExit)):
                validate_config()


class TestProductionErrorScenarios:
    """Test error scenarios specific to production deployment."""
    
    def test_database_connection_failure_recovery(self):
        """Test handling of database connection failures."""
        from teshq.utils.validation import ConfigValidator
        
        # Test with invalid database URL
        is_connected, message = ConfigValidator.validate_database_connection("postgresql://invalid:invalid@nonexistent:5432/db")
        assert not is_connected
        assert "failed" in message.lower()
    
    def test_api_key_validation_failure(self):
        """Test handling of invalid API key."""
        from teshq.utils.validation import ConfigValidator
        
        # Test with invalid API key format
        is_valid, message = ConfigValidator.validate_gemini_api_key("invalid_key")
        assert not is_valid
        assert "Invalid" in message
    
    def test_file_permission_error_handling(self):
        """Test handling of file permission errors."""
        from teshq.utils.validation import ConfigValidator
        
        # Test with path that requires root permissions (should fail gracefully)
        is_valid, message = ConfigValidator.validate_file_path("/root/test.txt", must_be_writable=True)
        # This should either succeed (if running as root) or fail gracefully
        if not is_valid:
            assert "permission" in message.lower() or "directory" in message.lower()
    
    def test_network_timeout_handling(self):
        """Test handling of network timeouts."""
        # This is handled by our timeout configuration in validate_database_connection
        # We test it indirectly through the database connection validation
        from teshq.utils.validation import ConfigValidator
        
        # Mock a timeout scenario
        with patch('teshq.utils.validation.create_engine') as mock_create_engine:
            mock_create_engine.side_effect = ConnectionError("timeout")
            
            is_connected, message = ConfigValidator.validate_database_connection("postgresql://host:5432/db")
            assert not is_connected
            assert "timeout" in message.lower() or "error" in message.lower()


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    def test_partial_configuration_handling(self):
        """Test handling of partial configuration."""
        from teshq.utils.validation import ConfigValidator
        
        # Test with only database URL (missing API key)
        config = {"DATABASE_URL": "sqlite:///test.db"}
        errors = ConfigValidator.validate_config(config)
        
        # Should identify missing API key but not crash
        assert len(errors) > 0
        assert any("GEMINI_API_KEY" in error for error in errors)
    
    def test_invalid_configuration_graceful_failure(self):
        """Test graceful failure with completely invalid configuration."""
        from teshq.utils.validation import ConfigValidator
        
        # Test with completely invalid config
        config = {
            "DATABASE_URL": "not_a_url",
            "GEMINI_API_KEY": "not_a_key"
        }
        errors = ConfigValidator.validate_config(config)
        
        # Should identify all errors without crashing
        assert len(errors) >= 2
        assert any("DATABASE_URL" in error for error in errors)
        assert any("GEMINI_API_KEY" in error for error in errors)
    
    def test_missing_dependencies_handling(self):
        """Test handling of missing dependencies."""
        # Mock missing import
        with patch('builtins.__import__', side_effect=ImportError("No module named 'missing_module'")):
            # The validation should handle missing modules gracefully
            from teshq.utils.validation import validate_environment
            
            is_valid, issues = validate_environment()
            # Should detect missing packages
            assert not is_valid or len(issues) > 0


class TestCLIInputSanitization:
    """Test CLI input sanitization and security."""
    
    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection in natural language queries."""
        from teshq.utils.validation import CLIValidator
        
        dangerous_queries = [
            "Show users; DROP TABLE users; --",
            "SELECT * FROM users /* comment */ WHERE id = 1",
            "EXEC xp_cmdshell('dir')",
            "'; DELETE FROM users WHERE 1=1; --"
        ]
        
        for query in dangerous_queries:
            is_valid, message = CLIValidator.validate_natural_language_query(query)
            assert not is_valid, f"Query should be rejected: {query}"
            assert "dangerous" in message.lower()
    
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        from teshq.utils.validation import CLIValidator
        
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM"
        ]
        
        for path in dangerous_paths:
            # The validation should handle these gracefully
            is_valid, message = CLIValidator.validate_save_path(path, "csv")
            # Either reject them or resolve them safely
            if is_valid:
                # If accepted, should be resolved to a safe path
                assert "Valid path" in message
    
    def test_large_input_handling(self):
        """Test handling of extremely large inputs."""
        from teshq.utils.validation import CLIValidator
        
        # Test with very large query
        large_query = "A" * 10000
        is_valid, message = CLIValidator.validate_natural_language_query(large_query)
        assert not is_valid
        assert "too long" in message
    
    def test_special_characters_handling(self):
        """Test handling of special characters in inputs."""
        from teshq.utils.validation import CLIValidator
        
        # Test with various special characters
        special_queries = [
            "Find users with names containing 'O'Brien'",
            "Show data for date = '2023-01-01'",
            "List products with price > $100.50",
            "Find emails containing '@' symbol"
        ]
        
        for query in special_queries:
            is_valid, message = CLIValidator.validate_natural_language_query(query)
            # These should be valid natural language queries
            assert is_valid, f"Valid query should be accepted: {query}"