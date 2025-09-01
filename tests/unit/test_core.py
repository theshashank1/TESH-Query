"""Unit tests for core modules."""

import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest
from sqlalchemy.exc import SQLAlchemyError

from teshq.core.llm import SQLQueryGenerator, SQLQueryResponse
from teshq.core.query import execute_sql_query


class TestSQLQueryGenerator:
    """Test cases for SQLQueryGenerator class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Mock environment variable
        os.environ["GOOGLE_API_KEY"] = "test_api_key"
        
    def teardown_method(self):
        """Clean up after each test method."""
        # Clean up environment variable
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]

    @patch("teshq.core.llm.ChatGoogleGenerativeAI")
    def test_init_with_api_key(self, mock_chat_google):
        """Test SQLQueryGenerator initialization with API key."""
        generator = SQLQueryGenerator(api_key="test_key", model_name="test_model")
        
        assert generator.model_name == "test_model"
        mock_chat_google.assert_called_once_with(model="test_model", temperature=0.1)

    @patch("teshq.core.llm.ChatGoogleGenerativeAI")
    def test_init_default_model(self, mock_chat_google):
        """Test SQLQueryGenerator initialization with default model."""
        generator = SQLQueryGenerator(api_key="test_key")
        
        assert generator.model_name == SQLQueryGenerator.DEFAULT_MODEL_NAME
        mock_chat_google.assert_called_once_with(
            model=SQLQueryGenerator.DEFAULT_MODEL_NAME, 
            temperature=0.1
        )

    def test_init_no_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]
            
        with pytest.raises(ValueError, match="GOOGLE_API_KEY must be set"):
            SQLQueryGenerator()

    @patch("teshq.core.llm.ChatGoogleGenerativeAI")
    def test_load_schema(self, mock_chat_google):
        """Test schema loading from file."""
        generator = SQLQueryGenerator(api_key="test_key")
        
        # Create a temporary schema file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("CREATE TABLE users (id INT, name VARCHAR(50));")
            schema_file = f.name
        
        try:
            schema = generator.load_schema(schema_file)
            assert schema == "CREATE TABLE users (id INT, name VARCHAR(50));"
        finally:
            os.unlink(schema_file)

    @patch("teshq.core.llm.ChatGoogleGenerativeAI")
    def test_load_schema_file_not_found(self, mock_chat_google):
        """Test schema loading with non-existent file."""
        generator = SQLQueryGenerator(api_key="test_key")
        
        with pytest.raises(FileNotFoundError):
            generator.load_schema("non_existent_file.txt")


class TestExecuteSQLQuery:
    """Test cases for execute_sql_query function."""

    @patch("teshq.core.query.get_db_url")
    @patch("teshq.core.query.create_engine")
    def test_execute_sql_query_success(self, mock_create_engine, mock_get_db_url):
        """Test successful SQL query execution."""
        # Setup mocks
        mock_get_db_url.return_value = "sqlite:///:memory:"
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        # Mock connection and result using context manager
        mock_conn = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_conn)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context_manager
        
        # Mock query result
        mock_row1 = Mock()
        mock_row1._mapping = {"id": 1, "name": "John"}
        mock_row2 = Mock()
        mock_row2._mapping = {"id": 2, "name": "Jane"}
        
        mock_result = [mock_row1, mock_row2]
        mock_conn.execute.return_value = mock_result
        
        # Execute query
        result = execute_sql_query(
            db_url=None,
            query="SELECT * FROM users",
            parameters={}
        )
        
        # Verify results
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "John"}
        assert result[1] == {"id": 2, "name": "Jane"}
        
        # Verify mocks were called correctly
        mock_get_db_url.assert_called_once()
        mock_create_engine.assert_called_once_with("sqlite:///:memory:")

    @patch("teshq.core.query.get_db_url")
    @patch("teshq.core.query.create_engine")
    def test_execute_sql_query_sqlalchemy_error(self, mock_create_engine, mock_get_db_url):
        """Test SQL query execution with SQLAlchemy error."""
        # Setup mocks
        mock_get_db_url.return_value = "sqlite:///:memory:"
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        # Mock connection to raise SQLAlchemyError
        mock_conn = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_conn)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context_manager
        
        mock_conn.execute.side_effect = SQLAlchemyError("Database connection failed")
        
        # Execute query and expect empty result
        result = execute_sql_query(
            db_url=None,
            query="SELECT * FROM users",
            parameters={}
        )
        
        # Should return empty list on error
        assert result == []

