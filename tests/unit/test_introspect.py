"""Unit tests for database introspection module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from teshq.core.introspect import (
    introspect_db,
    detect_implicit_relationships,
    format_schema_outputs
)


class TestDatabaseIntrospection:
    """Test cases for database introspection functionality."""

    @patch('teshq.core.introspect.get_db_url')
    @patch('teshq.core.introspect.create_engine')
    @patch('teshq.core.introspect.inspect')
    def test_introspect_db_basic(self, mock_inspect_func, mock_create_engine, mock_get_db_url):
        """Test basic database introspection."""
        # Setup mocks
        mock_get_db_url.return_value = "sqlite:///:memory:"
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        mock_inspector = Mock()
        mock_inspect_func.return_value = mock_inspector
        
        # Mock table names
        mock_inspector.get_table_names.return_value = ["users", "orders"]
        
        # Mock columns for users table
        mock_inspector.get_columns.side_effect = [
            [  # users table columns
                {
                    "name": "id",
                    "type": Mock(__class__=Mock(__name__="INTEGER")),
                    "nullable": False,
                    "default": None
                },
                {
                    "name": "name",
                    "type": Mock(__class__=Mock(__name__="VARCHAR")),
                    "nullable": True,
                    "default": None
                }
            ],
            [  # orders table columns
                {
                    "name": "id",
                    "type": Mock(__class__=Mock(__name__="INTEGER")),
                    "nullable": False,
                    "default": None
                },
                {
                    "name": "user_id",
                    "type": Mock(__class__=Mock(__name__="INTEGER")),
                    "nullable": False,
                    "default": None
                }
            ]
        ]
        
        # Mock other introspection methods
        mock_inspector.get_pk_constraint.side_effect = [
            {"constrained_columns": ["id"]},  # users
            {"constrained_columns": ["id"]}   # orders
        ]
        mock_inspector.get_foreign_keys.return_value = []
        mock_inspector.get_indexes.return_value = []
        
        # Mock connection for row count
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.scalar.return_value = 5
        
        # Execute introspection
        result = introspect_db()
        
        # Verify results
        assert "tables" in result
        assert "users" in result["tables"]
        assert "orders" in result["tables"]
        
        # Check users table structure
        users_table = result["tables"]["users"]
        assert len(users_table["columns"]) == 2
        assert users_table["columns"][0]["name"] == "id"
        assert users_table["columns"][1]["name"] == "name"
        assert users_table["primary_keys"] == ["id"]

    @patch('teshq.core.introspect.get_db_url')
    @patch('teshq.core.introspect.create_engine')
    @patch('teshq.core.introspect.inspect')
    def test_introspect_db_with_error_handling(self, mock_inspect_func, mock_create_engine, mock_get_db_url):
        """Test database introspection with error handling."""
        # Setup mocks
        mock_get_db_url.return_value = "sqlite:///:memory:"
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        mock_inspector = Mock()
        mock_inspect_func.return_value = mock_inspector
        
        # Mock get_table_names to raise an exception
        mock_inspector.get_table_names.side_effect = SQLAlchemyError("Connection failed")
        
        # Execute introspection and expect it to raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to retrieve table names"):
            introspect_db()

    @patch('teshq.core.introspect.get_db_url')
    @patch('teshq.core.introspect.create_engine')
    @patch('teshq.core.introspect.inspect')
    def test_introspect_db_with_sample_data(self, mock_inspect_func, mock_create_engine, mock_get_db_url):
        """Test database introspection with sample data collection."""
        # Setup mocks
        mock_get_db_url.return_value = "sqlite:///:memory:"
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        mock_inspector = Mock()
        mock_inspect_func.return_value = mock_inspector
        
        # Mock table names
        mock_inspector.get_table_names.return_value = ["users"]
        
        # Mock columns
        mock_inspector.get_columns.return_value = [
            {
                "name": "id",
                "type": Mock(__class__=Mock(__name__="INTEGER")),
                "nullable": False,
                "default": None
            }
        ]
        
        # Mock other introspection methods
        mock_inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
        mock_inspector.get_foreign_keys.return_value = []
        mock_inspector.get_indexes.return_value = []
        
        # Mock connection for sample data
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock row count result
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 3
        
        # Mock sample data result
        mock_sample_row = Mock()
        mock_sample_row._mapping = {"id": 1}
        mock_sample_result = [mock_sample_row]
        
        # Configure execute to return different results based on query
        def mock_execute(query):
            if "COUNT" in str(query):
                return mock_count_result
            else:
                return mock_sample_result
        
        mock_conn.execute.side_effect = mock_execute
        
        # Execute introspection with sample data
        result = introspect_db(include_sample_data=True, sample_size=2)
        
        # Verify sample data was collected
        assert "tables" in result
        assert "users" in result["tables"]
        users_table = result["tables"]["users"]
        assert users_table["row_count"] == 3

    def test_detect_implicit_relationships(self):
        """Test detection of implicit relationships."""
        # Create mock schema info
        schema_info = {
            "tables": {
                "users": {
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "name", "type": "VARCHAR"}
                    ],
                    "foreign_keys": []
                },
                "orders": {
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "user_id", "type": "INTEGER"}
                    ],
                    "foreign_keys": []
                }
            }
        }
        
        all_tables = ["users", "orders"]
        primary_keys_registry = {
            "users": ["id"],
            "orders": ["id"]
        }
        
        # Execute relationship detection
        detect_implicit_relationships(schema_info, all_tables, primary_keys_registry)
        
        # Check if implicit relationship was detected
        orders_foreign_keys = schema_info["tables"]["orders"]["foreign_keys"]
        
        # Should detect user_id -> users.id relationship
        found_relationship = False
        for fk in orders_foreign_keys:
            if (fk.get("constrained_columns") == ["user_id"] and 
                fk.get("referred_table") == "users"):
                found_relationship = True
                break
        
        assert found_relationship, "Should detect implicit relationship between orders.user_id and users.id"

    def test_detect_implicit_relationships_no_match(self):
        """Test relationship detection when no patterns match."""
        # Create schema with no matching relationship patterns
        schema_info = {
            "tables": {
                "products": {
                    "columns": [
                        {"name": "product_code", "type": "VARCHAR"},
                        {"name": "price", "type": "DECIMAL"}
                    ],
                    "foreign_keys": []
                }
            }
        }
        
        all_tables = ["products"]
        primary_keys_registry = {"products": ["product_code"]}
        
        # Execute relationship detection
        detect_implicit_relationships(schema_info, all_tables, primary_keys_registry)
        
        # Should not detect any relationships
        assert len(schema_info["tables"]["products"]["foreign_keys"]) == 0

    def test_format_schema_outputs(self):
        """Test schema output formatting."""
        # Create mock schema info
        schema_info = {
            "database_type": "sqlite",
            "total_tables": 2,
            "tables": {
                "users": {
                    "columns": [
                        {"name": "id", "type": "INTEGER", "nullable": False},
                        {"name": "name", "type": "VARCHAR", "nullable": True}
                    ],
                    "primary_keys": ["id"],
                    "foreign_keys": [],
                    "indexes": [],
                    "row_count": 10,
                    "description": "User information table"
                },
                "orders": {
                    "columns": [
                        {"name": "id", "type": "INTEGER", "nullable": False},
                        {"name": "user_id", "type": "INTEGER", "nullable": False}
                    ],
                    "primary_keys": ["id"],
                    "foreign_keys": [
                        {
                            "constrained_columns": ["user_id"],
                            "referred_table": "users",
                            "referred_columns": ["id"]
                        }
                    ],
                    "indexes": [],
                    "row_count": 25,
                    "description": "Customer orders table"
                }
            }
        }
        
        # Execute formatting
        formatted_output = format_schema_outputs(schema_info)
        
        # Verify output contains expected information
        assert isinstance(formatted_output, str)
        assert "sqlite" in formatted_output.lower()
        assert "users" in formatted_output
        assert "orders" in formatted_output
        assert "id" in formatted_output
        assert "user_id" in formatted_output

    def test_format_schema_outputs_empty(self):
        """Test schema output formatting with empty schema."""
        schema_info = {
            "database_type": "sqlite",
            "total_tables": 0,
            "tables": {}
        }
        
        # Execute formatting
        formatted_output = format_schema_outputs(schema_info)
        
        # Should handle empty schema gracefully
        assert isinstance(formatted_output, str)
        assert "0" in formatted_output or "empty" in formatted_output.lower()