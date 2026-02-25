"""
Unified database connector interface for enhanced database compatibility.

This module provides a standardized interface for connecting to various database systems
with optimized configurations and error handling for each database type.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool, StaticPool

from teshq.utils.logging import logger


class DatabaseConnector(ABC):
    """Abstract base class for database connectors."""
    
    @abstractmethod
    def get_engine_args(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get SQLAlchemy engine arguments specific to this database type."""
        pass
    
    @abstractmethod
    def test_connection_query(self) -> str:
        """Get a simple query to test database connectivity."""
        pass
    
    @abstractmethod
    def get_introspection_config(self) -> Dict[str, Any]:
        """Get configuration for database introspection."""
        pass
    
    @abstractmethod
    def normalize_url(self, url: str) -> str:
        """Normalize the database URL for this connector."""
        pass
    
    @abstractmethod
    def get_required_packages(self) -> List[str]:
        """Get list of required packages for this database."""
        pass


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector."""
    
    def get_engine_args(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get PostgreSQL-specific engine arguments."""
        return {
            "poolclass": QueuePool,
            "pool_size": config.get("pool_size", 10),
            "max_overflow": config.get("max_overflow", 20),
            "pool_timeout": config.get("pool_timeout", 30),
            "pool_recycle": config.get("pool_recycle", 3600),
            "pool_pre_ping": config.get("pool_pre_ping", True),
            "echo": config.get("echo", False),
            "connect_args": {
                "connect_timeout": config.get("connect_timeout", 10),
                "options": "-c statement_timeout=300000",  # 5 minutes
            }
        }
    
    def test_connection_query(self) -> str:
        return "SELECT version()"
    
    def get_introspection_config(self) -> Dict[str, Any]:
        return {
            "supports_foreign_keys": True,
            "supports_indexes": True,
            "supports_check_constraints": True,
            "supports_sequences": True,
            "information_schema_available": True,
        }
    
    def normalize_url(self, url: str) -> str:
        """Ensure proper PostgreSQL URL format."""
        if url.startswith("postgres://"):
            # Update deprecated postgres:// to postgresql://
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    
    def get_required_packages(self) -> List[str]:
        return ["psycopg2-binary"]


class MySQLConnector(DatabaseConnector):
    """MySQL database connector."""
    
    def get_engine_args(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get MySQL-specific engine arguments."""
        return {
            "poolclass": QueuePool,
            "pool_size": config.get("pool_size", 10),
            "max_overflow": config.get("max_overflow", 20),
            "pool_timeout": config.get("pool_timeout", 30),
            "pool_recycle": config.get("pool_recycle", 3600),
            "pool_pre_ping": config.get("pool_pre_ping", True),
            "echo": config.get("echo", False),
            "connect_args": {
                "connect_timeout": config.get("connect_timeout", 10),
                "autocommit": True,
                "charset": "utf8mb4",
            }
        }
    
    def test_connection_query(self) -> str:
        return "SELECT VERSION()"
    
    def get_introspection_config(self) -> Dict[str, Any]:
        return {
            "supports_foreign_keys": True,
            "supports_indexes": True,
            "supports_check_constraints": True,
            "supports_sequences": False,  # MySQL 5.7+ supports sequences but limited
            "information_schema_available": True,
        }
    
    def normalize_url(self, url: str) -> str:
        """Ensure proper MySQL URL format."""
        # Handle mysql+pymysql:// and mysql+mysqldb:// variants
        if url.startswith("mysql://"):
            # Default to mysql+pymysql:// for better compatibility
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        return url
    
    def get_required_packages(self) -> List[str]:
        return ["PyMySQL", "mysql-connector-python"]


class SQLiteConnector(DatabaseConnector):
    """SQLite database connector."""
    
    def get_engine_args(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get SQLite-specific engine arguments."""
        return {
            "poolclass": StaticPool,
            "echo": config.get("echo", False),
            "connect_args": {
                "check_same_thread": False,
                "timeout": config.get("connect_timeout", 20),
            }
        }
    
    def test_connection_query(self) -> str:
        return "SELECT sqlite_version()"
    
    def get_introspection_config(self) -> Dict[str, Any]:
        return {
            "supports_foreign_keys": True,  # If enabled
            "supports_indexes": True,
            "supports_check_constraints": True,
            "supports_sequences": False,
            "information_schema_available": False,  # Uses pragma statements
        }
    
    def normalize_url(self, url: str) -> str:
        """Ensure proper SQLite URL format."""
        return url
    
    def get_required_packages(self) -> List[str]:
        return []  # SQLite is built into Python


class OracleConnector(DatabaseConnector):
    """Oracle database connector."""
    
    def get_engine_args(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get Oracle-specific engine arguments."""
        return {
            "poolclass": QueuePool,
            "pool_size": config.get("pool_size", 10),
            "max_overflow": config.get("max_overflow", 20),
            "pool_timeout": config.get("pool_timeout", 30),
            "pool_recycle": config.get("pool_recycle", 3600),
            "pool_pre_ping": config.get("pool_pre_ping", True),
            "echo": config.get("echo", False),
            "connect_args": {
                "timeout": config.get("connect_timeout", 10),
            }
        }
    
    def test_connection_query(self) -> str:
        return "SELECT * FROM v$version WHERE rownum = 1"
    
    def get_introspection_config(self) -> Dict[str, Any]:
        return {
            "supports_foreign_keys": True,
            "supports_indexes": True,
            "supports_check_constraints": True,
            "supports_sequences": True,
            "information_schema_available": False,  # Uses Oracle data dictionary
        }
    
    def normalize_url(self, url: str) -> str:
        """Ensure proper Oracle URL format."""
        # Handle oracle+cx_oracle:// variants
        if url.startswith("oracle://"):
            url = url.replace("oracle://", "oracle+cx_oracle://", 1)
        return url
    
    def get_required_packages(self) -> List[str]:
        return ["cx_Oracle", "oracledb"]


class CassandraConnector(DatabaseConnector):
    """Cassandra database connector (via SQLAlchemy CQL)."""
    
    def get_engine_args(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get Cassandra-specific engine arguments."""
        return {
            "echo": config.get("echo", False),
            "connect_args": {
                "timeout": config.get("connect_timeout", 10),
            }
        }
    
    def test_connection_query(self) -> str:
        return "SELECT release_version FROM system.local"
    
    def get_introspection_config(self) -> Dict[str, Any]:
        return {
            "supports_foreign_keys": False,
            "supports_indexes": True,  # Secondary indexes
            "supports_check_constraints": False,
            "supports_sequences": False,
            "information_schema_available": False,  # Uses Cassandra system tables
        }
    
    def normalize_url(self, url: str) -> str:
        """Ensure proper Cassandra URL format."""
        if url.startswith("cassandra://"):
            url = url.replace("cassandra://", "cassandra+cqlalchemy://", 1)
        return url
    
    def get_required_packages(self) -> List[str]:
        return ["cassandra-driver", "cqlalchemy"]


class UnifiedDatabaseConnector:
    """
    Unified interface for connecting to various database systems.
    
    Provides a consistent API while handling database-specific configurations,
    optimizations, and error handling.
    """
    
    # Registry of supported database connectors
    _connectors = {
        "postgresql": PostgreSQLConnector(),
        "postgres": PostgreSQLConnector(),  # Alias
        "mysql": MySQLConnector(),
        "sqlite": SQLiteConnector(),
        "oracle": OracleConnector(),
        "cassandra": CassandraConnector(),
    }
    
    @classmethod
    def get_supported_databases(cls) -> List[str]:
        """Get list of supported database types."""
        return list(cls._connectors.keys())
    
    @classmethod
    def detect_database_type(cls, url: str) -> str:
        """Detect database type from URL."""
        # Handle edge case where some compound schemes aren't recognized by urlparse
        if "+" in url and "://" in url:
            # Extract scheme manually for compound schemes
            scheme_part = url.split("://")[0].lower()
            if "+" in scheme_part:
                scheme = scheme_part.split("+")[0]
            else:
                scheme = scheme_part
        else:
            # Use standard parsing
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
            
            # Handle compound schemes like mysql+pymysql
            if "+" in scheme:
                scheme = scheme.split("+")[0]
        
        # Handle aliases
        if scheme == "postgres":
            scheme = "postgresql"
            
        return scheme
    
    @classmethod
    def get_connector(cls, url: str) -> DatabaseConnector:
        """Get appropriate connector for database URL."""
        db_type = cls.detect_database_type(url)
        
        if db_type not in cls._connectors:
            raise ValueError(
                f"Unsupported database type: {db_type}. "
                f"Supported types: {', '.join(cls.get_supported_databases())}"
            )
        
        return cls._connectors[db_type]
    
    @classmethod
    def create_engine(
        cls, 
        url: str, 
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Engine:
        """
        Create a SQLAlchemy engine with database-specific optimizations.
        
        Args:
            url: Database connection URL
            config: Configuration dictionary
            **kwargs: Additional engine arguments
            
        Returns:
            Configured SQLAlchemy engine
            
        Raises:
            ValueError: If database type is not supported
            ImportError: If required database driver is not installed
        """
        config = config or {}
        connector = cls.get_connector(url)
        
        # Check for required packages
        required_packages = connector.get_required_packages()
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                logger.warning(
                    f"Optional database driver not installed: {package}. "
                    f"Install with: pip install {package}"
                )
        
        # Normalize URL
        normalized_url = connector.normalize_url(url)
        
        # Get database-specific engine arguments
        engine_args = connector.get_engine_args(normalized_url, config)
        
        # Merge with any additional kwargs
        engine_args.update(kwargs)
        
        logger.info(
            "Creating database engine",
            database_type=cls.detect_database_type(url),
            pool_class=engine_args.get("poolclass", "default").__name__ if engine_args.get("poolclass") else "default"
        )
        
        return create_engine(normalized_url, **engine_args)
    
    @classmethod
    def test_connection(cls, url: str, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Test database connectivity.
        
        Args:
            url: Database connection URL
            config: Configuration dictionary
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            connector = cls.get_connector(url)
            engine = cls.create_engine(url, config)
            
            test_query = connector.test_connection_query()
            
            with engine.connect() as conn:
                result = conn.execute(text(test_query))
                version_info = result.fetchone()
                
            engine.dispose()
            
            return True, f"Connection successful. Database version: {version_info[0] if version_info else 'Unknown'}"
            
        except ValueError as e:
            return False, f"Configuration error: {e}"
        except ImportError as e:
            return False, f"Missing database driver: {e}"
        except SQLAlchemyError as e:
            return False, f"Database connection failed: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    @classmethod
    def get_introspection_capabilities(cls, url: str) -> Dict[str, Any]:
        """Get introspection capabilities for the database type."""
        connector = cls.get_connector(url)
        return connector.get_introspection_config()
    
    @classmethod
    def get_database_info(cls, url: str) -> Dict[str, Any]:
        """Get comprehensive information about the database and connection."""
        try:
            db_type = cls.detect_database_type(url)
            connector = cls.get_connector(url)
            
            return {
                "database_type": db_type,
                "supported": True,
                "required_packages": connector.get_required_packages(),
                "introspection_capabilities": connector.get_introspection_config(),
                "normalized_url": connector.normalize_url(url),
            }
        except ValueError:
            return {
                "database_type": cls.detect_database_type(url),
                "supported": False,
                "error": f"Database type not supported",
                "supported_types": cls.get_supported_databases(),
            }