"""
Database connection pooling and timeout management for production workloads.

Provides connection pooling, timeout configuration, and resource management
to ensure reliable database operations under production conditions.
"""

import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool, StaticPool

from teshq.utils.database_connectors import UnifiedDatabaseConnector
from teshq.utils.logging import logger
from teshq.utils.retry import retry_database_operation


class ConnectionConfig:
    """Configuration for database connections and pooling."""

    def __init__(
        self,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,  # 1 hour
        connect_timeout: int = 10,
        query_timeout: int = 300,  # 5 minutes
        pool_pre_ping: bool = True,
        echo: bool = False,
    ):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.connect_timeout = connect_timeout
        self.query_timeout = query_timeout
        self.pool_pre_ping = pool_pre_ping
        self.echo = echo


class ConnectionManager:
    """Manages database connections with pooling and timeout configuration."""

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self._engines: Dict[str, Engine] = {}

    def get_engine(self, database_url: str, engine_name: str = "default") -> Engine:
        """Get or create a database engine with the unified connector system."""
        if engine_name in self._engines:
            return self._engines[engine_name]

        logger.info("Creating database engine", engine_name=engine_name)
        # Use unified connector system for enhanced database support
        config_dict = {
            "pool_size": self.config.pool_size,
            "max_overflow": self.config.max_overflow,
            "pool_timeout": self.config.pool_timeout,
            "pool_recycle": self.config.pool_recycle,
            "connect_timeout": self.config.connect_timeout,
            "pool_pre_ping": self.config.pool_pre_ping,
            "echo": self.config.echo,
        }

        try:
            engine = UnifiedDatabaseConnector.create_engine(database_url, config_dict)
            self._engines[engine_name] = engine

            db_type = UnifiedDatabaseConnector.detect_database_type(database_url)
            logger.info(
                "Database engine created",
                engine_name=engine_name,
                database_type=db_type,
                supports_pooling=db_type != "sqlite",
            )

            return engine

        except ValueError as e:
            # Fallback to original implementation for unsupported databases
            logger.warning(f"Using fallback connection method: {e}")
            engine_args = self._get_engine_args(database_url)
            engine = create_engine(database_url, **engine_args)
            self._engines[engine_name] = engine

            logger.info("Database engine created (fallback mode)", engine_name=engine_name)
            return engine

    def _get_engine_args(self, database_url: str) -> Dict[str, Any]:
        """Get the appropriate arguments for creating a SQLAlchemy engine."""
        if database_url.startswith("sqlite"):
            return {
                "poolclass": StaticPool,
                "echo": self.config.echo,
                "connect_args": {"check_same_thread": False},
            }
        else:
            # Append connect_timeout to the URL for non-SQLite databases
            if "?" not in database_url:
                database_url += f"?connect_timeout={self.config.connect_timeout}"
            else:
                database_url += f"&connect_timeout={self.config.connect_timeout}"
            return {
                "poolclass": QueuePool,
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "pool_timeout": self.config.pool_timeout,
                "pool_recycle": self.config.pool_recycle,
                "pool_pre_ping": self.config.pool_pre_ping,
                "echo": self.config.echo,
            }

    @contextmanager
    def get_connection(self, database_url: str, engine_name: str = "default"):
        """Get a database connection with automatic cleanup."""
        engine = self.get_engine(database_url, engine_name)
        connection = None

        try:
            logger.debug("Getting database connection", engine_name=engine_name)
            connection = engine.connect()
            if not database_url.startswith("sqlite"):
                try:
                    connection.execute(text(f"SET statement_timeout = {self.config.query_timeout * 1000}"))
                except SQLAlchemyError:
                    pass  # Some dialects might not support this
            yield connection
        except Exception as e:
            logger.error("Database connection error", error=e, engine_name=engine_name)
            raise
        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed", engine_name=engine_name)

    @retry_database_operation("execute_query")
    def execute_query_with_timeout(
        self, database_url: str, query: str, parameters: Optional[Dict[str, Any]] = None, engine_name: str = "default"
    ):
        """Execute a query with timeout and retry logic."""
        start_time = time.time()
        with self.get_connection(database_url, engine_name) as conn:
            try:
                result = conn.execute(text(query), parameters or {})
                rows = result.fetchall()
                columns = result.keys() if hasattr(result, "keys") else []
                execution_time = time.time() - start_time

                logger.info(
                    "Query executed successfully",
                    execution_time_seconds=execution_time,
                    row_count=len(rows),
                    engine_name=engine_name,
                )
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    "Query execution failed", error=e, execution_time_seconds=execution_time, engine_name=engine_name
                )
                raise

    def test_connection(self, database_url: str, engine_name: str = "default") -> bool:
        """Test database connectivity using the unified connector system."""
        try:
            # Use unified connector for comprehensive testing
            success, message = UnifiedDatabaseConnector.test_connection(
                database_url,
                {
                    "connect_timeout": self.config.connect_timeout,
                    "echo": False,  # Disable echo for testing
                },
            )

            if success:
                logger.info("Database connection test successful", engine_name=engine_name, message=message)
            else:
                logger.error("Database connection test failed", engine_name=engine_name, message=message)

            return success

        except Exception as e:
            logger.error("Database connection test failed", error=e, engine_name=engine_name)
            return False

    def get_connection_info(self, engine_name: str = "default") -> Dict[str, Any]:
        """Get connection pool information for monitoring."""
        if engine_name not in self._engines:
            return {"status": "not_connected"}

        engine = self._engines[engine_name]
        pool = engine.pool

        if isinstance(pool, StaticPool):
            return {"status": "connected", "pool_class": "StaticPool"}

        return {
            "status": "connected",
            "pool_class": "QueuePool",
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalidated": pool.invalidated(),
        }

    def close_all_connections(self):
        """Close all database connections and engines."""
        for engine_name, engine in self._engines.items():
            try:
                engine.dispose()
                logger.info("Database engine disposed", engine_name=engine_name)
            except Exception as e:
                logger.error("Error disposing database engine", error=e, engine_name=engine_name)
        self._engines.clear()


connection_manager = ConnectionManager()


def get_production_config() -> ConnectionConfig:
    return ConnectionConfig(
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        query_timeout=int(os.getenv("DB_QUERY_TIMEOUT", "300")),
        pool_pre_ping=os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
    )


def get_development_config() -> ConnectionConfig:
    return ConnectionConfig(
        pool_size=2,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        connect_timeout=5,
        query_timeout=60,
        pool_pre_ping=True,
        echo=True,
    )


@contextmanager
def get_db_connection(database_url: str):
    with connection_manager.get_connection(database_url) as conn:
        yield conn


def execute_query_with_pooling(database_url: str, query: str, parameters: Optional[Dict[str, Any]] = None):
    return connection_manager.execute_query_with_timeout(database_url, query, parameters)
