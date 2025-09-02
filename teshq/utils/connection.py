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
from sqlalchemy.pool import QueuePool, StaticPool

from teshq.utils.logging import logger, log_operation, metrics
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
        echo: bool = False
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
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up SQLAlchemy event listeners for logging."""
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
            logger.debug(
                "Executing SQL query",
                statement=statement[:200] + "..." if len(statement) > 200 else statement,
                parameters=parameters if len(str(parameters)) < 500 else "..."
            )
        
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            metrics.record_metric("db_query_execution_time", total)
            
            if total > 1.0:  # Log slow queries
                logger.warning(
                    "Slow query detected",
                    execution_time_seconds=total,
                    statement=statement[:200] + "..." if len(statement) > 200 else statement
                )
    
    def get_engine(self, database_url: str, engine_name: str = "default") -> Engine:
        """Get or create a database engine with connection pooling."""
        if engine_name in self._engines:
            return self._engines[engine_name]
        
        with log_operation("create_database_engine", engine_name=engine_name):
            # Parse database URL to add timeout parameters
            if "?" in database_url:
                database_url += f"&connect_timeout={self.config.connect_timeout}"
            else:
                database_url += f"?connect_timeout={self.config.connect_timeout}"
            
            # Choose appropriate pooling strategy
            if database_url.startswith("sqlite"):
                # SQLite uses StaticPool for thread safety
                poolclass = StaticPool
                pool_size = 1
                max_overflow = 0
            else:
                poolclass = QueuePool
                pool_size = self.config.pool_size
                max_overflow = self.config.max_overflow
            
            engine = create_engine(
                database_url,
                poolclass=poolclass,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pool_pre_ping,
                echo=self.config.echo,
                # Additional connection arguments
                connect_args={
                    "connect_timeout": self.config.connect_timeout
                } if not database_url.startswith("sqlite") else {}
            )
            
            self._engines[engine_name] = engine
            
            logger.info(
                "Database engine created",
                engine_name=engine_name,
                pool_size=pool_size,
                max_overflow=max_overflow,
                connect_timeout=self.config.connect_timeout
            )
            
            return engine
    
    @contextmanager
    def get_connection(self, database_url: str, engine_name: str = "default"):
        """Get a database connection with automatic cleanup."""
        engine = self.get_engine(database_url, engine_name)
        connection = None
        
        try:
            with log_operation("get_database_connection", engine_name=engine_name):
                connection = engine.connect()
                
                # Set query timeout if supported
                if not database_url.startswith("sqlite"):
                    try:
                        connection.execute(text(f"SET statement_timeout = {self.config.query_timeout * 1000}"))
                    except SQLAlchemyError:
                        # Some databases don't support this, continue anyway
                        pass
                
                yield connection
                
        except Exception as e:
            logger.error(
                "Database connection error",
                error=e,
                engine_name=engine_name
            )
            raise
        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed", engine_name=engine_name)
    
    @retry_database_operation("execute_query")
    def execute_query_with_timeout(
        self,
        database_url: str,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        engine_name: str = "default"
    ):
        """Execute a query with timeout and retry logic."""
        start_time = time.time()
        
        with self.get_connection(database_url, engine_name) as conn:
            try:
                if parameters:
                    result = conn.execute(text(query), parameters)
                else:
                    result = conn.execute(text(query))
                
                # Fetch all results to ensure query completion
                rows = result.fetchall()
                columns = result.keys() if hasattr(result, 'keys') else []
                
                execution_time = time.time() - start_time
                
                logger.info(
                    "Query executed successfully",
                    execution_time_seconds=execution_time,
                    row_count=len(rows),
                    engine_name=engine_name
                )
                
                metrics.record_metric("db_query_success", 1, {"engine": engine_name})
                metrics.record_metric("db_query_execution_time", execution_time, {"engine": engine_name})
                metrics.record_metric("db_query_row_count", len(rows), {"engine": engine_name})
                
                return [dict(zip(columns, row)) for row in rows]
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.error(
                    "Query execution failed",
                    error=e,
                    execution_time_seconds=execution_time,
                    engine_name=engine_name
                )
                
                metrics.record_metric("db_query_error", 1, {"engine": engine_name})
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
        
        info = {
            "status": "connected",
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalidated": pool.invalidated()
        }
        
        if hasattr(pool, "_pool"):
            info["available_connections"] = pool._pool.qsize()
        
        return info
    
    def close_all_connections(self):
        """Close all database connections and engines."""
        for engine_name, engine in self._engines.items():
            try:
                engine.dispose()
                logger.info("Database engine disposed", engine_name=engine_name)
            except Exception as e:
                logger.error("Error disposing database engine", error=e, engine_name=engine_name)
        
        self._engines.clear()


# Global connection manager instance
connection_manager = ConnectionManager()


def get_production_config() -> ConnectionConfig:
    """Get production-optimized connection configuration."""
    return ConnectionConfig(
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        query_timeout=int(os.getenv("DB_QUERY_TIMEOUT", "300")),
        pool_pre_ping=os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
        echo=os.getenv("DB_ECHO", "false").lower() == "true"
    )


def get_development_config() -> ConnectionConfig:
    """Get development-optimized connection configuration."""
    return ConnectionConfig(
        pool_size=2,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        connect_timeout=5,
        query_timeout=60,
        pool_pre_ping=True,
        echo=True
    )


@contextmanager
def get_db_connection(database_url: str):
    """Convenience function to get a database connection."""
    with connection_manager.get_connection(database_url) as conn:
        yield conn


def execute_query_with_pooling(database_url: str, query: str, parameters: Optional[Dict[str, Any]] = None):
    """Execute a query using the connection pool."""
    return connection_manager.execute_query_with_timeout(database_url, query, parameters)