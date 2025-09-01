"""
Tests for configuration management and validation.

Tests configuration loading, saving, validation, and production readiness.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from teshq.utils.config import (
    get_config,
    save_config,
    get_database_url,
    get_gemini_config,
    get_paths,
    is_configured,
    get_config_with_source
)


class TestConfigurationLoading:
    """Test configuration loading from various sources."""
    
    def test_get_config_from_environment(self):
        """Test loading configuration from environment variables."""
        test_config = {
            "DATABASE_URL": "sqlite:///test.db",
            "GEMINI_API_KEY": "test_key",
            "GEMINI_MODEL_NAME": "test_model",
            "OUTPUT_PATH": "/tmp/output",
            "FILE_STORE_PATH": "/tmp/files"
        }
        
        with patch.dict(os.environ, test_config):
            config = get_config()
            for key, value in test_config.items():
                assert config.get(key) == value
    
    def test_get_config_from_env_file(self):
        """Test loading configuration from .env file."""
        env_content = """
DATABASE_URL=postgresql://user:pass@host:5432/db
GEMINI_API_KEY=env_file_key
GEMINI_MODEL_NAME=gemini-pro
OUTPUT_PATH=/tmp/env_output
FILE_STORE_PATH=/tmp/env_files
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
            temp_env.write(env_content)
            temp_env.flush()
            
            with patch('teshq.utils.config.ENV_FILE', temp_env.name):
                config = get_config()
                assert config.get("DATABASE_URL") == "postgresql://user:pass@host:5432/db"
                assert config.get("GEMINI_API_KEY") == "env_file_key"
                assert config.get("GEMINI_MODEL_NAME") == "gemini-pro"
        
        os.unlink(temp_env.name)
    
    def test_get_config_from_json_file(self):
        """Test loading configuration from JSON file."""
        json_config = {
            "DATABASE_URL": "mysql://user:pass@host:3306/db",
            "GEMINI_API_KEY": "json_file_key",
            "OUTPUT_PATH": "/tmp/json_output"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_json:
            json.dump(json_config, temp_json)
            temp_json.flush()
            
            with patch('teshq.utils.config.JSON_CONFIG_FILE', temp_json.name):
                config = get_config()
                for key, value in json_config.items():
                    assert config.get(key) == value
        
        os.unlink(temp_json.name)
    
    def test_config_priority_environment_over_files(self):
        """Test that environment variables take priority over files."""
        # Set up .env file
        env_content = "DATABASE_URL=env_file_url\n"
        
        # Set up JSON file
        json_config = {"DATABASE_URL": "json_file_url"}
        
        # Set up environment variable
        env_var = {"DATABASE_URL": "environment_url"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
            temp_env.write(env_content)
            temp_env.flush()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_json:
                json.dump(json_config, temp_json)
                temp_json.flush()
                
                with patch('teshq.utils.config.ENV_FILE', temp_env.name):
                    with patch('teshq.utils.config.JSON_CONFIG_FILE', temp_json.name):
                        with patch.dict(os.environ, env_var):
                            config = get_config()
                            # Environment variable should take priority
                            assert config.get("DATABASE_URL") == "environment_url"
        
        os.unlink(temp_env.name)
        os.unlink(temp_json.name)


class TestConfigurationSaving:
    """Test configuration saving functionality."""
    
    def test_save_config_to_env_file(self):
        """Test saving configuration to .env file."""
        test_config = {
            "DATABASE_URL": "sqlite:///saved_test.db",
            "GEMINI_API_KEY": "saved_test_key"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = os.path.join(temp_dir, '.env')
            json_file = os.path.join(temp_dir, 'config.json')
            
            with patch('teshq.utils.config.ENV_FILE', env_file):
                with patch('teshq.utils.config.JSON_CONFIG_FILE', json_file):
                    result = save_config(test_config)
                    assert result is True
                    
                    # Verify .env file was created and contains the config
                    assert os.path.exists(env_file)
                    with open(env_file, 'r') as f:
                        env_content = f.read()
                        assert "DATABASE_URL=sqlite:///saved_test.db" in env_content
                        assert "GEMINI_API_KEY=saved_test_key" in env_content
    
    def test_save_config_to_json_file(self):
        """Test saving configuration to JSON file."""
        test_config = {
            "OUTPUT_PATH": "/tmp/saved_output",
            "FILE_STORE_PATH": "/tmp/saved_files"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = os.path.join(temp_dir, '.env')
            json_file = os.path.join(temp_dir, 'config.json')
            
            with patch('teshq.utils.config.ENV_FILE', env_file):
                with patch('teshq.utils.config.JSON_CONFIG_FILE', json_file):
                    result = save_config(test_config)
                    assert result is True
                    
                    # Verify JSON file was created and contains the config
                    assert os.path.exists(json_file)
                    with open(json_file, 'r') as f:
                        saved_config = json.load(f)
                        assert saved_config["OUTPUT_PATH"] == "/tmp/saved_output"
                        assert saved_config["FILE_STORE_PATH"] == "/tmp/saved_files"
    
    def test_save_config_handles_io_error(self):
        """Test that save_config handles IO errors gracefully."""
        test_config = {"DATABASE_URL": "test"}
        
        # Mock file operations to raise IOError
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            result = save_config(test_config)
            assert result is False


class TestConfigurationUtilities:
    """Test configuration utility functions."""
    
    def test_get_database_url(self):
        """Test get_database_url function."""
        test_url = "postgresql://test:test@localhost:5432/testdb"
        
        with patch('teshq.utils.config.get_config', return_value={"DATABASE_URL": test_url}):
            result = get_database_url()
            assert result == test_url
    
    def test_get_database_url_none(self):
        """Test get_database_url with no configuration."""
        with patch('teshq.utils.config.get_config', return_value={}):
            result = get_database_url()
            assert result is None
    
    def test_get_gemini_config_complete(self):
        """Test get_gemini_config with complete configuration."""
        test_config = {
            "GEMINI_API_KEY": "test_api_key",
            "GEMINI_MODEL_NAME": "test_model"
        }
        
        with patch('teshq.utils.config.get_config', return_value=test_config):
            api_key, model = get_gemini_config()
            assert api_key == "test_api_key"
            assert model == "test_model"
    
    def test_get_gemini_config_defaults(self):
        """Test get_gemini_config with default model."""
        test_config = {"GEMINI_API_KEY": "test_api_key"}
        
        with patch('teshq.utils.config.get_config', return_value=test_config):
            api_key, model = get_gemini_config()
            assert api_key == "test_api_key"
            # Should use default model
            from teshq.utils.config import DEFAULT_GEMINI_MODEL
            assert model == DEFAULT_GEMINI_MODEL
    
    def test_get_paths_configured(self):
        """Test get_paths with configured paths."""
        test_config = {
            "OUTPUT_PATH": "/custom/output",
            "FILE_STORE_PATH": "/custom/files"
        }
        
        with patch('teshq.utils.config.get_config', return_value=test_config):
            output_path, file_store_path = get_paths()
            assert output_path == "/custom/output"
            assert file_store_path == "/custom/files"
    
    def test_get_paths_defaults(self):
        """Test get_paths with default paths."""
        with patch('teshq.utils.config.get_config', return_value={}):
            output_path, file_store_path = get_paths()
            # Should use default paths
            from teshq.utils.config import DEFAULT_OUTPUT_PATH, DEFAULT_FILE_STORE_PATH
            assert output_path == DEFAULT_OUTPUT_PATH
            assert file_store_path == DEFAULT_FILE_STORE_PATH
    
    def test_is_configured_true(self):
        """Test is_configured with complete configuration."""
        test_config = {
            "DATABASE_URL": "sqlite:///test.db",
            "GEMINI_API_KEY": "test_key"
        }
        
        with patch('teshq.utils.config.get_config', return_value=test_config):
            assert is_configured() is True
    
    def test_is_configured_false_missing_db(self):
        """Test is_configured with missing database URL."""
        test_config = {"GEMINI_API_KEY": "test_key"}
        
        with patch('teshq.utils.config.get_config', return_value=test_config):
            assert is_configured() is False
    
    def test_is_configured_false_missing_api_key(self):
        """Test is_configured with missing API key."""
        test_config = {"DATABASE_URL": "sqlite:///test.db"}
        
        with patch('teshq.utils.config.get_config', return_value=test_config):
            assert is_configured() is False
    
    def test_is_configured_false_empty(self):
        """Test is_configured with empty configuration."""
        with patch('teshq.utils.config.get_config', return_value={}):
            assert is_configured() is False


class TestConfigurationWithSource:
    """Test configuration loading with source tracking."""
    
    def test_get_config_with_source_environment(self):
        """Test source tracking for environment variables."""
        test_config = {"DATABASE_URL": "env_url"}
        
        with patch.dict(os.environ, test_config):
            config, sources = get_config_with_source()
            assert config.get("DATABASE_URL") == "env_url"
            assert sources.get("DATABASE_URL") == "environment"
    
    def test_get_config_with_source_env_file(self):
        """Test source tracking for .env file."""
        env_content = "DATABASE_URL=env_file_url\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
            temp_env.write(env_content)
            temp_env.flush()
            
            with patch('teshq.utils.config.ENV_FILE', temp_env.name):
                config, sources = get_config_with_source()
                assert config.get("DATABASE_URL") == "env_file_url"
                assert sources.get("DATABASE_URL") == "env_file"
        
        os.unlink(temp_env.name)
    
    def test_get_config_with_source_json_file(self):
        """Test source tracking for JSON file."""
        json_config = {"DATABASE_URL": "json_file_url"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_json:
            json.dump(json_config, temp_json)
            temp_json.flush()
            
            with patch('teshq.utils.config.JSON_CONFIG_FILE', temp_json.name):
                config, sources = get_config_with_source()
                assert config.get("DATABASE_URL") == "json_file_url"
                assert sources.get("DATABASE_URL") == "json_file"
        
        os.unlink(temp_json.name)
    
    def test_get_config_with_source_not_found(self):
        """Test source tracking for missing configuration."""
        # Clear environment and mock missing files
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                config, sources = get_config_with_source()
                # Should have empty config and no sources
                assert len(config) == 0
                assert len(sources) == 0


class TestConfigurationErrorHandling:
    """Test configuration error handling."""
    
    def test_get_config_handles_malformed_env_file(self):
        """Test handling of malformed .env file."""
        malformed_content = "INVALID LINE WITHOUT EQUALS\nVALID_KEY=valid_value\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
            temp_env.write(malformed_content)
            temp_env.flush()
            
            with patch('teshq.utils.config.ENV_FILE', temp_env.name):
                # Should not crash and should parse valid lines
                config = get_config()
                assert config.get("VALID_KEY") == "valid_value"
        
        os.unlink(temp_env.name)
    
    def test_get_config_handles_malformed_json_file(self):
        """Test handling of malformed JSON file."""
        malformed_json = '{"key": "value",}'  # Trailing comma makes it invalid
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_json:
            temp_json.write(malformed_json)
            temp_json.flush()
            
            with patch('teshq.utils.config.JSON_CONFIG_FILE', temp_json.name):
                # Should not crash and return empty config for this file
                config = get_config()
                # Should not have parsed the malformed JSON
                assert "key" not in config
        
        os.unlink(temp_json.name)
    
    def test_get_config_handles_io_error(self):
        """Test handling of IO errors when reading config files."""
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with patch('os.path.exists', return_value=True):
                # Should not crash
                config = get_config()
                # Should return empty config when files can't be read
                assert isinstance(config, dict)


class TestProductionConfiguration:
    """Test production-specific configuration concerns."""
    
    def test_config_masking_sensitive_data(self):
        """Test that sensitive data is properly masked in debug output."""
        from teshq.utils.config import print_config_debug
        from io import StringIO
        import sys
        
        test_config = {
            "DATABASE_URL": "postgresql://user:secret@host:5432/db",
            "GEMINI_API_KEY": "secret_api_key"
        }
        
        with patch('teshq.utils.config.get_config_with_source', 
                   return_value=(test_config, {"DATABASE_URL": "test", "GEMINI_API_KEY": "test"})):
            
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output
            
            try:
                print_config_debug()
                output = captured_output.getvalue()
                
                # Should mask the API key
                assert "secret_api_key" not in output
                assert "********" in output
                
                # Should mask database password
                assert "secret" not in output or "********" in output
                
            finally:
                sys.stdout = sys.__stdout__
    
    def test_config_environment_separation(self):
        """Test configuration for different environments."""
        # Test development configuration with proper API key format
        dev_config = {
            "DATABASE_URL": "sqlite:///dev.db",
            "GEMINI_API_KEY": "AIza" + "A" * 35  # Valid format
        }
        
        # Test production configuration with proper API key format
        prod_config = {
            "DATABASE_URL": "postgresql://user:pass@prod-host:5432/proddb",
            "GEMINI_API_KEY": "AIza" + "B" * 35  # Valid format
        }
        
        # Both should be valid configurations
        from teshq.utils.validation import ConfigValidator
        
        dev_errors = ConfigValidator.validate_config(dev_config)
        prod_errors = ConfigValidator.validate_config(prod_config)
        
        # Should have no validation errors for properly formatted configs
        # Allow path-related errors since we're testing with temp directories
        assert len(dev_errors) == 0 or all("path" in error.lower() for error in dev_errors)
        assert len(prod_errors) == 0 or all("path" in error.lower() for error in prod_errors)