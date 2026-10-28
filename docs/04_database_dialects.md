# Universal SQLAlchemy Database Support & Dialects

TESH-Query supports **every database supported by SQLAlchemy**. Whether connecting to an enterprise relational database, an in-process analytical engine, a cloud data warehouse, or a third-party distributed SQL engine, TESH-Query automatically identifies the backend, selects the appropriate dialect generator, applies optimized connection pooling, and handles dialect-specific query execution.

---

## 🌐 Supported Dialects & Matrix

| Category | Database | SQLAlchemy Driver / Extra | Example Connection URL Format |
| :--- | :--- | :--- | :--- |
| **Relational** | **PostgreSQL** | `asyncpg` / `psycopg2` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| | **MySQL / MariaDB** | `PyMySQL` | `mysql+pymysql://user:pass@host:3306/dbname` |
| | **MS SQL Server** | `pymssql` / `pyodbc` | `mssql+pymssql://user:pass@host:1433/dbname` |
| | **Oracle Database** | `oracledb` / `cx_oracle` | `oracle+oracledb://user:pass@host:1521/?service_name=XEPDB1` |
| | **SQLite** | Built-in | `sqlite:///path/to/database.db` or `sqlite:///:memory:` |
| **Cloud Warehouses**| **Snowflake** | `snowflake-sqlalchemy` | `snowflake://user:pass@account/dbname/schemaname?warehouse=wh` |
| | **Google BigQuery**| `sqlalchemy-bigquery` | `bigquery://project-id/dataset_name` |
| | **Databricks** | `databricks-sql-connector`| `databricks://token:dapi...@host:443/default?http_path=...` |
| | **Amazon Redshift**| `sqlalchemy-redshift` | `redshift+psycopg2://user:pass@cluster:5439/dbname` |
| **Real-Time OLAP** | **DuckDB** | `duckdb-engine` | `duckdb:///analytics.duckdb` or `duckdb:///:memory:` |
| | **ClickHouse** | `clickhouse-connect` | `clickhouse+native://user:pass@host:9000/default` |
| **Distributed SQL** | **CockroachDB** | `cockroachdb` | `cockroachdb://user:pass@host:26257/defaultdb` |
| | **Trino / Presto** | `trino-python-client` | `trino://user@host:8080/catalog/schema` |
| **Generic / Others**| **Any SQLAlchemy** | Any 3rd party driver | `<driver_scheme>://[user:pass@]host[:port]/database` |

---

## 🔍 Dynamic Dialect Detection

TESH-Query utilizes SQLAlchemy's `make_url()` parser to extract the canonical backend name from standard and compound connection URLs:

```python
from sqlalchemy.engine import make_url

url = "oracle+cx_oracle://user:pass@dbserver:1521/prod"
backend = make_url(url).get_backend_name().lower()
# backend -> "oracle"
```

### Dialect Mapping Logic
1. **Direct Mappings:** `postgresql`, `mysql`, `sqlite`, `oracle`, `mssql`, `snowflake`, `bigquery`, `databricks`, `redshift`, `duckdb`, `clickhouse`.
2. **Derivative Mappings:**
   - `cockroachdb` → maps to `SQLDialect.POSTGRESQL` rules.
   - `mariadb` → maps to `SQLDialect.MYSQL` rules.
3. **Universal Fallback:** Any unrecognized dialect dynamically defaults to `SQLDialect.GENERIC`, applying standard ANSI-SQL quoting, standard date functions, and cross-platform SQL constructs.

---

## 🏊 Dynamic Connection Pooling Strategy

Different database architectures require distinct pooling configurations:

| Topology | Target Databases | Pool Implementation | Configuration Details |
| :--- | :--- | :--- | :--- |
| **In-Memory** | `sqlite:///:memory:`, `duckdb:///:memory:` | `StaticPool` | Preserves table states across queries within the session. |
| **Embedded File-Based** | Local SQLite files, DuckDB database files | `NullPool` | Disables persistent pooling to prevent thread-locking and file descriptor contention. Enables `check_same_thread=False` for thread concurrency. |
| **Client-Server / Cloud** | PostgreSQL, MySQL, Oracle, Snowflake, BigQuery, MSSQL | `QueuePool` | Maintains reusable connection pools (`pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`). |

### SQLite Concurrency & Speed Optimizations
When connecting to SQLite databases, TESH-Query automatically installs a connection listener that configures high-speed concurrency pragmas:

```sql
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;    -- 64 MB memory cache
PRAGMA temp_store = MEMORY;    -- Keep temp tables and joins in RAM
PRAGMA mmap_size = 268435456;  -- 256 MB memory-mapped I/O
```

---

## 📊 Database Views & Analytical Reflection

Enterprise databases and data warehouses heavily utilize SQL Views (`CREATE VIEW`) to encapsulate business logic. 

TESH-Query introspects both physical tables and database views:
1. **Introspection Query:** Queries `inspector.get_table_names(schema=s)` and `inspector.get_view_names(schema=s)`.
2. **Deduplication:** Aggregates and deduplicates table and view names.
3. **Fallback Profiling:** When views lack primary keys or physical indexes, TESH-Query executes a direct non-locking `SELECT COUNT(*)` to estimate row cardinality without reflection errors.

---

## 🩺 Cascading Connectivity Health Checks

When testing connectivity via `teshq health` or `teshq db connection test`, different database backends require distinct probe queries:

```python
# TESH-Query executes cascading connectivity checks:
1. "SELECT 1 FROM DUAL"   # Required by Oracle Database
2. "SELECT 1"             # Standard ANSI SQL (Postgres, MySQL, MSSQL, Snowflake)
3. "SELECT version()"     # Fallback for PostgreSQL/CockroachDB
4. "SELECT sqlite_version()" # Fallback for SQLite
```

---

## ⏱️ Query Timeout Handling

TESH-Query applies statement timeouts to prevent long-running queries from blocking production databases:
- **Supported Databases:** `SET statement_timeout = 30000;` is executed for PostgreSQL, MySQL, and compatible relational engines.
- **Excluded Databases:** Engines that do not support statement timeouts (SQLite, DuckDB, Cassandra) are automatically excluded to prevent syntax errors during connection establishment.

---

## 🧭 Next Steps

- **[Multi-Database Federation](05_multi_database_federation.md)** — Join queries across multiple database dialects.
- **[AST Security Firewall](06_security_firewall.md)** — Understand how queries are validated before execution.
- **[Configuration & Secrets](10_configuration_and_secrets.md)** — Configure connection strings and environment variables.
