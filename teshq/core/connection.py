"""
Database connection pooling and timeout management for production workloads.

Provides connection pooling, timeout configuration, and resource management
to ensure reliable database operations under production conditions.
"""

import atexit
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool, StaticPool


from teshq.config.paths import CONNECTIONS_FILE, ensure_teshq_dir
from teshq.core.connectors import UnifiedDatabaseConnector
from teshq.core.dialect import detect_dialect
from teshq.utils.logging import log_operation, logger, metrics
from teshq.core.retry import retry_database_operation


def mask_database_url(url_or_text: str) -> str:
    """Mask password and credentials in a database URL or free-form text for safe logging and display."""
    if not url_or_text:
        return ""
    try:
        u = make_url(url_or_text)
        return u.render_as_string(hide_password=True)
    except Exception:
        pass
    # Fallback regex masking for passwords in URI format user:password@host
    res = re.sub(r":([^:@/ \t\n\r]+)@([a-zA-Z0-9_.-]+)", r":***@\2", url_or_text)
    # Regex masking for key-value connection strings like password=...
    res = re.sub(r"(?i)(password|pwd|secret)\s*=\s*['\"]?[^'\";\s]+['\"]?", r"\1=***", res)
    return res


def expand_connection_url(url: str) -> str:
    """Resolve environment variables like ${DB_PASSWORD} or ${DB_HOST:-localhost} in a database URL."""
    if not url:
        return ""

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1) or match.group(3)
        default_val = match.group(2) if match.group(2) is not None else ""
        val = os.environ.get(var_name)
        if val is None:
            try:
                from teshq.config.secrets import load_secrets
                secrets = load_secrets()
                val = secrets.get(var_name)
            except Exception:
                val = None
        if val is None or val == "":
            return default_val
        return val

    return re.sub(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}|\$([A-Za-z0-9_]+)", replace_var, url)


class ConnectionDict(dict):
    """Dictionary representing connection metadata with attribute access."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'ConnectionDict' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


@dataclass
class DatabaseConnection:
    """Represents a named database connection configuration."""

    name: str
    db_url: str  # fully resolved URL
    dialect: str
    is_default: bool = False
    description: str = ""
    created_at: float = field(default_factory=time.time)
    raw_url: str = ""  # original unresolved URL (may contain ${VAR})

    @property
    def masked_url(self) -> str:
        return mask_database_url(self.db_url)

    def to_dict(self, mask_secret: bool = True) -> Dict[str, Any]:
        target_url = self.masked_url if mask_secret else self.db_url
        return ConnectionDict({
            "name": self.name,
            "url": target_url,
            "db_url": target_url,
            "masked_url": self.masked_url,
            "raw_url": self.raw_url or self.db_url,
            "dialect": self.dialect,
            "is_default": self.is_default,
            "description": self.description,
            "created_at": self.created_at,
        })

    def __repr__(self) -> str:
        return (
            f"DatabaseConnection(name='{self.name}', dialect='{self.dialect}', "
            f"db_url='{self.masked_url}', is_default={self.is_default})"
        )


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
    """Manages database connections with pooling, named connections, and timeout configuration."""

    def __init__(self, config: Optional[ConnectionConfig] = None, auto_load: bool = True):
        self.config = config or ConnectionConfig()
        self._lock = threading.RLock()
        self._engines: Dict[str, Engine] = {}
        self._connections: Dict[str, DatabaseConnection] = {}
        self._default_connection_name: Optional[str] = None
        if auto_load:
            self._load_saved_connections()

    def _setup_metrics_listeners(self, engine: Engine, engine_name: str):
        """Set up event listeners for metrics for a given engine's pool."""
        # Prevent double-registering if get_engine is called multiple times for the same engine
        if getattr(engine, "_metrics_listeners_installed", False):
            return

        @event.listens_for(engine.pool, "connect")
        def connect(dbapi_connection, connection_record):
            metrics.increment_counter("db_connections_total", tags={"engine": engine_name})

        @event.listens_for(engine.pool, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            metrics.increment_counter("db_checkouts_total", tags={"engine": engine_name})
            # dbapi_connection can be None when a failed connection is being cleaned up
            if dbapi_connection is None:
                return
            try:
                pool = connection_proxy._pool
                metrics.set_gauge("db_pool_connections", pool.size(), tags={"engine": engine_name})
                metrics.set_gauge("db_pool_checkedout", pool.checkedout(), tags={"engine": engine_name})
            except Exception:
                pass  # Never crash the CLI due to metrics

        @event.listens_for(engine.pool, "checkin")
        def checkin(dbapi_connection, connection_record):
            # dbapi_connection is None when SQLAlchemy cleans up after a failed checkout
            if dbapi_connection is None:
                return
            try:
                pool = connection_record._pool
                metrics.set_gauge("db_pool_checkedin", pool.checkedin(), tags={"engine": engine_name})
            except Exception:
                pass  # Never crash the CLI due to metrics

        @event.listens_for(engine.pool, "soft_invalidate")
        def soft_invalidate(dbapi_connection, connection_record, exception):
            metrics.increment_counter("db_connection_invalidated_total", tags={"engine": engine_name})

        engine._metrics_listeners_installed = True

    def _setup_sqlite_optimizations(self, engine: Engine):
        """Configure SQLite pragmas for maximum query performance and memory caching."""
        if getattr(engine, "_sqlite_optimizations_installed", False):
            return

        @event.listens_for(engine, "connect")
        def _optimize_sqlite_connection(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                for pragma in (
                    "PRAGMA synchronous = NORMAL",
                    "PRAGMA cache_size = -64000",
                    "PRAGMA temp_store = MEMORY",
                    "PRAGMA mmap_size = 268435456",
                ):
                    try:
                        cursor.execute(pragma)
                    except Exception:
                        pass
                cursor.close()
            except Exception:
                pass

        engine._sqlite_optimizations_installed = True

    def get_engine(self, database_url: str, engine_name: str = "default") -> Engine:
        """Get or create a database engine with the unified connector system."""
        cache_key = f"{engine_name}:{database_url}"
        with self._lock:
            if cache_key in self._engines:
                return self._engines[cache_key]

            with log_operation("create_database_engine", engine_name=engine_name):
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
                    self._engines[cache_key] = engine

                    # Set up listeners only once per engine
                    self._setup_metrics_listeners(engine, engine_name)

                    db_type = UnifiedDatabaseConnector.detect_database_type(database_url)
                    if db_type == "sqlite":
                        self._setup_sqlite_optimizations(engine)

                    logger.info(
                        "Database engine created",
                        engine_name=engine_name,
                        database_type=db_type,
                        supports_pooling=db_type != "sqlite"
                    )

                    return engine

                except ValueError as e:
                    # Safety fallback — should rarely trigger now that GenericSQLAlchemyConnector exists
                    logger.warning(f"Connector fallback triggered: {e}")
                    database_url, engine_args = self._get_engine_args(database_url)
                    engine = create_engine(database_url, **engine_args)
                    self._engines[cache_key] = engine
                    self._setup_metrics_listeners(engine, engine_name)
                    if database_url.startswith("sqlite"):
                        self._setup_sqlite_optimizations(engine)

                    logger.info("Database engine created (fallback mode)", engine_name=engine_name)
                    return engine

    def _get_engine_args(self, database_url: str) -> tuple[str, Dict[str, Any]]:
        """Get the appropriate database_url and arguments for creating a SQLAlchemy engine."""
        if database_url.startswith("sqlite"):
            return database_url, {
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
            return database_url, {
                "poolclass": QueuePool,
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "pool_timeout": self.config.pool_timeout,
                "pool_recycle": self.config.pool_recycle,
                "pool_pre_ping": self.config.pool_pre_ping,
                "echo": self.config.echo,
            }

    @staticmethod
    def _set_query_timeout(connection, database_url: str, timeout_seconds: int) -> None:
        """Set a per-connection query timeout using dialect-appropriate SQL.

        Args:
            connection: Active SQLAlchemy connection.
            database_url: Database URL (used for dialect detection).
            timeout_seconds: Maximum query execution time in seconds.
        """
        from teshq.core.connectors import UnifiedDatabaseConnector
        db_type = UnifiedDatabaseConnector.detect_database_type(database_url)
        timeout_ms = timeout_seconds * 1000

        try:
            if db_type == "postgresql":
                connection.execute(text(f"SET statement_timeout = {timeout_ms}"))
            elif db_type == "mysql":
                # MAX_EXECUTION_TIME is in milliseconds (MySQL 5.7.8+)
                connection.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {timeout_ms}"))
            elif db_type == "mssql":
                # Apply query_timeout through the SQL Server driver's mechanism
                try:
                    dbapi_conn = connection.connection.dbapi_connection
                    if hasattr(dbapi_conn, "timeout"):
                        dbapi_conn.timeout = timeout_seconds
                except Exception:
                    logger.debug("Query timeout configuration not supported on this MSSQL connection")
            elif db_type not in ("sqlite", "cassandra", "duckdb"):
                # Best-effort for unknown databases (Snowflake, CockroachDB, etc.)
                # Many PostgreSQL-compatible DBs support statement_timeout
                try:
                    connection.execute(text(f"SET statement_timeout = {timeout_ms}"))
                except Exception:
                    logger.debug(f"Query timeout not available for '{db_type}'")
        except SQLAlchemyError:
            try:
                connection.rollback()
            except Exception:
                pass

    @contextmanager
    def get_connection(self, database_url_or_name: str, engine_name: str = "default"):
        """Get a database connection with automatic cleanup.

        Supports both raw database URLs and registered named connections.
        """
        target_url = database_url_or_name
        target_engine_name = engine_name
        if database_url_or_name in self._connections:
            target_url = self._connections[database_url_or_name].db_url
            target_engine_name = database_url_or_name

        engine = self.get_engine(target_url, target_engine_name)
        connection = None

        try:
            with log_operation("get_database_connection", engine_name=target_engine_name):
                connection = engine.connect()
                if not target_url.startswith("sqlite"):
                    self._set_query_timeout(connection, target_url, self.config.query_timeout)
                yield connection
        except Exception as e:
            logger.error("Database connection error", error=e, engine_name=target_engine_name)
            raise
        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed", engine_name=target_engine_name)

    def _is_read_only(self, query: str) -> bool:
        if not query or not query.strip():
            return True

        # Strip SQL comments to avoid false-positives (e.g., SELECT /* UPDATE */ id FROM users)
        try:
            import sqlparse
            cleaned_query = sqlparse.format(query, strip_comments=True)
        except Exception:
            cleaned_query = query

        # Strip string literals to avoid false positives (e.g., SELECT 'update')
        stripped_query = re.sub(r"'(?:''|[^'])*'", "''", cleaned_query).upper()

        mutating_keywords = {
            "INSERT", "UPDATE", "DELETE", "DROP",
            "ALTER", "CREATE", "TRUNCATE", "REPLACE", "MERGE"
        }

        for kw in mutating_keywords:
            if re.search(rf"\b{kw}\b", stripped_query):
                return False

        return True

    def execute_query_with_timeout(
        self,
        database_url_or_name: str,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        engine_name: str = "default",
    ):
        """Execute a query with timeout and retry logic."""
        target_url = database_url_or_name
        target_engine_name = engine_name
        if database_url_or_name in self._connections:
            target_url = self._connections[database_url_or_name].db_url
            target_engine_name = database_url_or_name

        def _execute():
            start_time = time.time()
            with self.get_connection(target_url, target_engine_name) as conn:
                try:
                    result = conn.execute(text(query), parameters or {})
                    rows = result.fetchall() if result.returns_rows else []
                    columns = result.keys() if hasattr(result, "keys") else []
                    execution_time = time.time() - start_time

                    tags = {"engine": target_engine_name, "status": "success"}
                    metrics.add_point("db_query_execution_time", execution_time, tags)
                    metrics.add_point("db_query_row_count", len(rows), tags)
                    metrics.increment_counter("db_queries_total", tags=tags)

                    logger.info(
                        "Query executed successfully",
                        execution_time_seconds=execution_time,
                        row_count=len(rows),
                        engine_name=target_engine_name,
                    )
                    return [dict(zip(columns, row)) for row in rows]
                except Exception as e:
                    execution_time = time.time() - start_time
                    tags = {"engine": target_engine_name, "status": "error"}
                    metrics.increment_counter("db_queries_total", tags=tags)
                    logger.error(
                        "Query execution failed",
                        error=e,
                        execution_time_seconds=execution_time,
                        engine_name=target_engine_name,
                    )
                    raise

        if self._is_read_only(query):
            decorated = retry_database_operation("execute_query")(_execute)
            return decorated()
        return _execute()

    def test_connection(self, database_url_or_name: str, engine_name: str = "default") -> bool:
        """Test database connectivity using the unified connector system."""
        target_url = database_url_or_name
        target_engine_name = engine_name
        if database_url_or_name in self._connections:
            target_url = self._connections[database_url_or_name].db_url
            target_engine_name = database_url_or_name
        try:
            success, message = UnifiedDatabaseConnector.test_connection(
                target_url,
                {
                    "connect_timeout": self.config.connect_timeout,
                    "echo": False,
                }
            )

            if success:
                logger.info("Database connection test successful", engine_name=target_engine_name, details=message)
            else:
                logger.error("Database connection test failed", engine_name=target_engine_name, details=message)

            return success
        except Exception as e:
            logger.error("Database connection test failed", error=e, engine_name=target_engine_name)
            return False

    def test_named_connection(self, name: str) -> Tuple[bool, str]:
        """Test a named database connection and return (success, message)."""
        try:
            conn = self.get_named_connection(name)
        except KeyError:
            return False, f"Connection '{name}' not found."

        try:
            success, message = UnifiedDatabaseConnector.test_connection(
                conn.db_url,
                {
                    "connect_timeout": self.config.connect_timeout,
                    "echo": False,
                }
            )
            return success, message or ("Connected successfully" if success else "Connection failed")
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Named Connection Management
    # ------------------------------------------------------------------

    def add_connection(
        self,
        name: str,
        db_url: str,
        is_default: bool = False,
        set_as_default: bool = False,
        description: str = "",
        overwrite: bool = False,
        persist: bool = False,
    ) -> DatabaseConnection:
        """Add and register a named database connection."""
        is_default = is_default or set_as_default
        if not name or not isinstance(name, str):
            raise ValueError("Connection name must be a non-empty string.")

        name = name.strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValueError(f"Invalid connection name '{name}'. Use letters, numbers, hyphens, and underscores.")

        if name in self._connections and not overwrite:
            raise ValueError(f"Connection '{name}' already exists. Pass overwrite=True to replace it.")

        if not db_url or not isinstance(db_url, str):
            raise ValueError("Database URL must be a non-empty string.")

        raw_url = db_url.strip()
        resolved_url = expand_connection_url(raw_url)

        try:
            make_url(resolved_url)
        except Exception as e:
            raise ValueError(f"Invalid database URL for connection '{name}': {mask_database_url(resolved_url)}") from e

        with self._lock:
            # If overwriting, dispose existing engine(s)
            if name in self._connections:
                to_dispose = [k for k in list(self._engines.keys()) if k.startswith(f"{name}:") or k == name]
                for k in to_dispose:
                    try:
                        self._engines[k].dispose()
                    except Exception:
                        pass
                    del self._engines[k]

            dialect = detect_dialect(resolved_url)

            # Handle default flag
            if is_default or not self._connections:
                for c in self._connections.values():
                    c.is_default = False
                is_default = True
                self._default_connection_name = name
            elif not self._default_connection_name:
                self._default_connection_name = name
                is_default = True

            conn = DatabaseConnection(
                name=name,
                db_url=resolved_url,
                dialect=dialect,
                is_default=is_default,
                description=description,
                raw_url=raw_url,
            )
            self._connections[name] = conn

            if persist:
                self.save_connections()

            logger.info(
                "Registered named database connection",
                connection_name=name,
                dialect=dialect,
                is_default=is_default,
            )
            return conn

    def get_named_connection(self, name: Optional[str] = None) -> DatabaseConnection:
        """Retrieve a registered named database connection."""
        with self._lock:
            if name is None or name == "default":
                if self._default_connection_name and self._default_connection_name in self._connections:
                    return self._connections[self._default_connection_name]
                if "default" in self._connections:
                    return self._connections["default"]

                # Fallback to single configured database_url if available
                try:
                    from teshq.config.loader import get_database_url
                    configured_url = get_database_url()
                    if configured_url:
                        resolved = expand_connection_url(configured_url)
                        return DatabaseConnection(
                            name="default",
                            db_url=resolved,
                            dialect=detect_dialect(resolved),
                            is_default=True,
                            description="Default configured database",
                            raw_url=configured_url,
                        )
                except Exception:
                    pass

                if len(self._connections) == 1:
                    return next(iter(self._connections.values()))

                raise KeyError("No default database connection configured. Specify a connection name.")

            if name in self._connections:
                return self._connections[name]

            # Check if requested name is "default" and can be resolved
            if name == "default":
                return self.get_named_connection(None)

            available = list(self._connections.keys())
            raise KeyError(f"Database connection '{name}' not found. Available connections: {available}")

    def get_connection_metadata(self, name: Optional[str] = None) -> DatabaseConnection:
        """Alias for get_named_connection."""
        return self.get_named_connection(name)

    def list_connections(self, as_dict: bool = False) -> Any:
        """List all registered named connections with masked credentials."""
        with self._lock:
            if as_dict:
                return {name: conn.to_dict(mask_secret=True) for name, conn in self._connections.items()}
            return [conn.to_dict(mask_secret=True) for conn in self._connections.values()]

    def remove_connection(self, name: str, persist: bool = False) -> bool:
        """Remove a named database connection and dispose its engine and connection pool."""
        with self._lock:
            if name not in self._connections:
                raise KeyError(f"Connection '{name}' not found.")

            conn = self._connections[name]
            db_url = conn.db_url

            # Dispose of engine(s) associated with this connection or URL
            to_dispose = [
                k for k in list(self._engines.keys())
                if k.startswith(f"{name}:") or k == name or k == db_url
            ]
            for k in to_dispose:
                try:
                    self._engines[k].dispose()
                    logger.info("Disposed engine for removed connection", engine_name=name)
                except Exception as e:
                    logger.warning("Error disposing engine", error=str(e), engine_name=name)
                self._engines.pop(k, None)

            del self._connections[name]

            if self._default_connection_name == name:
                self._default_connection_name = next(iter(self._connections.keys()), None)
                if self._default_connection_name:
                    self._connections[self._default_connection_name].is_default = True

            if persist:
                self.save_connections()
            return True

    def clear_all(self) -> None:
        """Clear all connections and dispose of all active engines."""
        with self._lock:
            for engine in list(self._engines.values()):
                try:
                    engine.dispose()
                except Exception:
                    pass
            self._engines.clear()
            self._connections.clear()
            self._default_connection_name = None

    def set_default_connection(self, name: str, persist: bool = False) -> None:
        """Set the default connection name."""
        with self._lock:
            if name not in self._connections:
                raise KeyError(f"Connection '{name}' not found.")
            for conn in self._connections.values():
                conn.is_default = (conn.name == name)
            self._default_connection_name = name
            if persist:
                self.save_connections()

    def save_connections(self, file_path: Optional[Path] = None) -> bool:
        """Save registered named connections to YAML configuration file."""
        import yaml
        from teshq.config.secrets import save_secrets
        dest = file_path or CONNECTIONS_FILE
        ensure_teshq_dir()
        try:
            data = {"connections": {}, "default_connection": self._default_connection_name}
            secrets_to_save: Dict[str, Optional[str]] = {}

            for name, conn in self._connections.items():
                url_to_store = conn.raw_url or conn.db_url
                try:
                    u = make_url(conn.db_url)
                    if u.password and not ("${" in url_to_store or "$" in url_to_store):
                        secret_key = f"TESHQ_DB_{name.upper().replace('-', '_')}_URL"
                        secrets_to_save[secret_key] = conn.db_url
                        url_to_store = f"${{{secret_key}}}"
                except Exception:
                    pass

                dialect_str = conn.dialect.value if hasattr(conn.dialect, "value") else str(conn.dialect)
                data["connections"][name] = {
                    "db_url": url_to_store,
                    "dialect": dialect_str,
                    "is_default": conn.is_default,
                    "description": conn.description,
                    "created_at": conn.created_at,
                }

            if secrets_to_save:
                save_secrets(secrets_to_save)

            # Atomic write with 0o600 permissions to prevent file corruption or race conditions
            temp_file = dest.with_name(f".{dest.name}.tmp.{os.getpid()}")
            temp_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            try:
                os.chmod(temp_file, 0o600)
            except Exception:
                pass
            os.replace(temp_file, dest)
            return True
        except Exception as e:
            logger.error("Failed to save connections to file", error=str(e), path=str(dest))
            return False

    def _load_saved_connections(self, file_path: Optional[Path] = None) -> None:
        """Load saved named connections from YAML configuration file."""
        import yaml
        src = file_path or CONNECTIONS_FILE
        if not src.exists():
            return
        try:
            raw = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
            conns = raw.get("connections", {})
            default_conn = raw.get("default_connection")
            for name, item in conns.items():
                raw_url = item.get("db_url", "")
                resolved_url = expand_connection_url(raw_url)
                if not resolved_url:
                    continue
                dialect = item.get("dialect") or detect_dialect(resolved_url)
                is_def = item.get("is_default", False) or (name == default_conn)
                self._connections[name] = DatabaseConnection(
                    name=name,
                    db_url=resolved_url,
                    dialect=dialect,
                    is_default=is_def,
                    description=item.get("description", ""),
                    created_at=item.get("created_at", time.time()),
                    raw_url=raw_url,
                )
            if default_conn and default_conn in self._connections:
                self._default_connection_name = default_conn
            elif self._connections:
                for n, c in self._connections.items():
                    if c.is_default:
                        self._default_connection_name = n
                        break
                if not self._default_connection_name:
                    self._default_connection_name = next(iter(self._connections.keys()))
                    self._connections[self._default_connection_name].is_default = True
        except Exception as e:
            logger.warning("Failed to load connections configuration", error=str(e), path=str(src))

    def get_connection_info(self, engine_name: str = "default") -> Dict[str, Any]:
        """Get connection pool information for monitoring."""
        prefix = f"{engine_name}:"
        found_engine = None
        for key, engine in self._engines.items():
            if key.startswith(prefix) or key == engine_name:
                found_engine = engine
                break

        if not found_engine:
            return {"status": "not_connected"}

        pool = found_engine.pool

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
        with self._lock:
            for cache_key, engine in list(self._engines.items()):
                safe_name = cache_key.split(":")[0] if ":" in cache_key else cache_key
                try:
                    engine.dispose()
                    logger.info("Database engine disposed", engine_name=safe_name)
                except Exception as e:
                    logger.error("Error disposing database engine", error=e, engine_name=safe_name)
            self._engines.clear()

    dispose_all = close_all_connections


connection_manager = ConnectionManager()
atexit.register(connection_manager.close_all_connections)


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
