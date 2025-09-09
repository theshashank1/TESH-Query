"""
Database connection pooling and timeout management for production workloads.

Provides connection pooling, timeout configuration, and resource management
to ensure reliable database operations under production conditions.
"""

import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import Pool, QueuePool, StaticPool

from teshq.utils.logging import log_operation, logger, metrics
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

    def _setup_metrics_listeners(self, engine_name: str):
        """Set up event listeners for metrics for a given engine."""

        @event.listens_for(Pool, "connect")
        def connect(dbapi_connection, connection_record):
            metrics.increment_counter("db_connections_total", tags={"engine": engine_name})

        @event.listens_for(Pool, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            metrics.increment_counter("db_checkouts_total", tags={"engine": engine_name})
            pool = connection_proxy.dbapi_connection.pool
            metrics.set_gauge("db_pool_connections", pool.size(), tags={"engine": engine_name})
            metrics.set_gauge("db_pool_checkedout", pool.checkedout(), tags={"engine": engine_name})

        @event.listens_for(Pool, "checkin")
        def checkin(dbapi_connection, connection_record):
            pool = dbapi_connection.pool
            metrics.set_gauge("db_pool_checkedin", pool.checkedin(), tags={"engine": engine_name})

        @event.listens_for(Pool, "soft_invalidate")
        def soft_invalidate(dbapi_connection, connection_record, exception):
            metrics.increment_counter("db_connection_invalidated_total", tags={"engine": engine_name})

    def get_engine(self, database_url: str, engine_name: str = "default") -> Engine:
        """Get or create a database engine with connection pooling."""
        if engine_name in self._engines:
            return self._engines[engine_name]

        with log_operation("create_database_engine", engine_name=engine_name):
            is_sqlite = database_url.startswith("sqlite")
            engine_args = self._get_engine_args(database_url)

            engine = create_engine(database_url, **engine_args)
            self._engines[engine_name] = engine

            # Set up listeners only once per engine
            self._setup_metrics_listeners(engine_name)

            log_info = {
                "pool_class": "StaticPool" if is_sqlite else "QueuePool",
                "engine_name": engine_name,
            }
            if not is_sqlite:
                log_info.update(
                    {
                        "pool_size": self.config.pool_size,
                        "max_overflow": self.config.max_overflow,
                        "connect_timeout": self.config.connect_timeout,
                    }
                )

            logger.info("Database engine created", **log_info)
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
            with log_operation("get_database_connection", engine_name=engine_name):
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

                tags = {"engine": engine_name, "status": "success"}
                metrics.add_point("db_query_execution_time", execution_time, tags)
                metrics.add_point("db_query_row_count", len(rows), tags)
                metrics.increment_counter("db_queries_total", tags=tags)

                logger.info(
                    "Query executed successfully",
                    execution_time_seconds=execution_time,
                    row_count=len(rows),
                    engine_name=engine_name,
                )
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                execution_time = time.time() - start_time
                tags = {"engine": engine_name, "status": "error"}
                metrics.increment_counter("db_queries_total", tags=tags)
                logger.error(
                    "Query execution failed", error=e, execution_time_seconds=execution_time, engine_name=engine_name
                )
                raise

    def test_connection(self, database_url: str, engine_name: str = "default") -> bool:
        """Test database connectivity."""
        try:
            with self.get_connection(database_url, engine_name) as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful", engine_name=engine_name)
            return True
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
