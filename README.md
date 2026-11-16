<div align="center">

# TESH-Query

**Autonomous Natural Language to SQL Execution & Safety Harness**

[![PyPI version](https://img.shields.io/pypi/v/teshq?color=blue)](https://pypi.org/project/teshq/)
[![Python Support](https://img.shields.io/pypi/pyversions/teshq)](https://pypi.org/project/teshq/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI/CD](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml/badge.svg)](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Quick Start](#quick-start) • [Interactive Terminal](#interactive-terminal-teshq-chat) • [Documentation Hub](docs/README.md) • [Universal Dialects](docs/04_database_dialects.md) • [CLI Reference](#cli-reference) • [Python SDK](#python-sdk) • [Architecture](#the-harness-architecture)

</div>

---

**TESH-Query (TESHQ)** is a production-grade text-to-SQL compiler and execution harness. It translates plain English into dialect-accurate, injection-safe SQL across 11+ databases, validates queries via an AST firewall, and self-heals syntax errors in an automated closed loop.

Whether through the **interactive terminal (`teshq chat`)**, **scriptable CLI**, or **zero-copy Python SDK (Polars / PyArrow / Pandas)**, TESH-Query mediates the entire lifecycle between LLMs and production databases.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TESHQ HUD  •  PostgreSQL Connected (14ms)  •  Gemini 2.0  •  42 Tables    │
├─────────────────────────────────────────────────────────────────────────────┤
│  › top 10 products by revenue in 2024                                       │
│  [1/6] Schema Context  ✓ Top-4 tables pruned via TF-IDF                     │
│  [2/6] Query Planning  ✓ Identified INNER JOIN orders ON products.id        │
│  [3/6] SQL Synthesis   ✓ Compiled PostgreSQL dialect with :named params     │
│  [4/6] AST Firewall    ✓ Passed (Read-only SELECT, 0 destructive tokens)    │
│  [5/6] DB Execution    ✓ 10 rows returned in 18ms                           │
│  [6/6] Output Delivery ✓ Rendered tabular view                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Precision Interactive Terminal (`teshq chat`)** — Ambient status HUD, 6-stage cognitive progress tracker, and slash commands (`/tables`, `/copy`, `/model`, `/export`, `/explain`). [Read CLI Guide →](docs/07_cli_reference.md)
- **100% Offline & Air-Gapped Mode** — Run locally with GGUF models via `llama.cpp` and hardware acceleration (CUDA, Metal, CPU). Enforces **GBNF context-free grammar** to physically constrain LLM tokens to valid SQL. [Read Offline Guide →](docs/09_offline_local_inference.md)
- **AST Security Firewall** — Parses the Abstract Syntax Tree before execution. Hard-blocks destructive operations (`DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `REPLACE`, and unconstrained `DELETE`/`UPDATE`). [Read Security Guide →](docs/06_security_firewall.md)
- **TF-IDF Schema Vector Pruner** — Uses in-memory TF-IDF cosine similarity to index and extract only the 3–5 relevant tables from 100+ table databases, preventing context window overflow and slashing token costs. [Read Architecture Guide →](docs/03_architecture.md)
- **Closed-Loop Self-Healing** — Intercepts database dialect errors, re-prompts the model with compiler feedback, and repairs SQL automatically with exponential backoff. [Read Resilience Guide →](docs/11_self_healing_and_resilience.md)
- **Zero-Copy Modern Analytics SDK** — First-class outputs for **Polars** (`result.polars`), **Apache Arrow** (`result.arrow`), and **Pandas** (`result.dataframe`), plus Parquet and JSONL exports. [Read SDK Guide →](docs/08_python_sdk.md)
- **Multi-Database Management & Federation** — Manage $N$ isolated database connections and execute parallel cross-database federated queries with vectorized in-memory joins. [Read Federation Guide →](docs/05_multi_database_federation.md)
- **Universal SQLAlchemy Database Support** — Native connectors for all databases supported by SQLAlchemy: Cloud Warehouses (Snowflake, BigQuery, Databricks, Redshift), Real-Time OLAP (DuckDB, ClickHouse), Relational (PostgreSQL, MySQL, MSSQL, Oracle, SQLite), and Distributed SQL (CockroachDB, Trino, Presto). [Read Dialects Guide →](docs/04_database_dialects.md)

---

## 📚 Documentation Hub

TESH-Query includes comprehensive, production-grade documentation organized in [`/docs`](docs/README.md):

| Document | Topic & Scope | Link |
| :--- | :--- | :--- |
| **System Overview** | Core mission, architecture pillars, and capabilities | [docs/01_overview.md](docs/01_overview.md) |
| **Installation & Drivers** | Driver extras, pure-Python asyncpg, and CUDA/Metal setup | [docs/02_installation.md](docs/02_installation.md) |
| **Harness Architecture** | 6-stage cognitive pipeline, SchemaGraph, and TF-IDF pruner | [docs/03_architecture.md](docs/03_architecture.md) |
| **Universal Dialects** | All SQLAlchemy databases, compound URLs, views, and pooling | [docs/04_database_dialects.md](docs/04_database_dialects.md) |
| **Multi-DB Federation** | Named connections, thread pools, and vectorized DataFrame joins | [docs/05_multi_database_federation.md](docs/05_multi_database_federation.md) |
| **AST Security Firewall** | Token AST parsing, read-only guarantees, and parameter binding | [docs/06_security_firewall.md](docs/06_security_firewall.md) |
| **CLI Reference** | `teshq chat` REPL, HUD, slash commands, and query flags | [docs/07_cli_reference.md](docs/07_cli_reference.md) |
| **Python SDK** | Zero-copy Polars, Arrow, multi-turn sessions, and BYOE engines | [docs/08_python_sdk.md](docs/08_python_sdk.md) |
| **Offline Mode (Local GGUF)** | Zero-network inference, GBNF grammars, and model manager | [docs/09_offline_local_inference.md](docs/09_offline_local_inference.md) |
| **Configuration & Secrets** | Layered resolution priority chain, credential masking, and .env | [docs/10_configuration_and_secrets.md](docs/10_configuration_and_secrets.md) |
| **Self-Healing & Resilience** | Closed-loop syntax recovery, jittered backoff, and exceptions | [docs/11_self_healing_and_resilience.md](docs/11_self_healing_and_resilience.md) |
| **Testing & Benchmarks** | Amazon-scale synthetic fixture (45 tables, 1.12M rows) | [docs/12_testing_and_benchmarks.md](docs/12_testing_and_benchmarks.md) |
| **Production Deployment** | Docker containers, FastAPI microservices, and K8s probes | [docs/13_production_deployment.md](docs/13_production_deployment.md) |
| **Troubleshooting & FAQ** | Connectivity diagnostics, SSL setup, and error resolutions | [docs/14_troubleshooting.md](docs/14_troubleshooting.md) |

---

## The Harness Architecture

A raw LLM cannot safely query a production database. TESH-Query operates as a complete execution and safety harness:

```
 User Question: "Show active customers with orders > $1,000"
                       │
                       ▼
 ┌───────────────────────────────────────────┐
 │ 1. Schema Introspection & Graph Indexing  │  Extracts PK/FK relationships into SchemaGraph
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 2. In-Memory TF-IDF Schema Retriever      │  Prunes 100+ tables down to Top-K relevant tables
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 3. Two-Stage LLM Compiler                 │  Stage 1: Query Planner (tables, joins, filters)
 │                                           │  Stage 2: Dialect Generator (Gemini / Azure / GGUF)
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 4. AST Security Firewall                  │  Blocks DROP, ALTER, TRUNCATE, injection
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 5. Execution & Dialect Driver             │  Executes with bound parameters (:named)
 └─────────────────────┬─────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
 [Syntax Error?]              [Query Success]
 Capture error code,                  │
 re-feed into LLM,                    ▼
 self-heal & retry            DataFrame / Arrow / Polars
```

> 📖 **Architecture Deep Dive:** For complete details on graph indexing, TF-IDF cosine similarity, token budgeting, and closed-loop self-healing, see [docs/03_architecture.md](docs/03_architecture.md).

---

## Quick Start

### 1. Installation

Requires Python 3.10+.

```bash
# Core package (SQLite + Google Gemini out of the box)
pip install teshq

# Or install with specific database drivers
pip install "teshq[postgres]"    # PostgreSQL (asyncpg)
pip install "teshq[mysql]"       # MySQL / MariaDB (PyMySQL)
pip install "teshq[mssql]"       # Microsoft SQL Server (pymssql)
pip install "teshq[data]"        # High-performance Polars & PyArrow
pip install "teshq[local]"       # Offline GGUF inference (llama-cpp-python)
pip install "teshq[all]"         # All pure-Python drivers & tools
```

### 2. 30-Second Guided Configuration

Run the interactive Quick Setup Wizard:

```bash
teshq config --wizard
```

Or configure components directly:

```bash
# Configure your database connection
teshq config --db

# Choose your AI provider:
teshq config --gemini            # Google Gemini API key
teshq config --azure             # Azure OpenAI credentials
teshq config --local             # Local offline GGUF model
```

*All settings and credentials are encrypted/stored locally at `~/.teshq/`.*

### 3. Introspect Schema

Scan tables, columns, primary keys, and foreign-key relationships into the local graph cache:

```bash
teshq db introspect
```

### 4. Query Your Data

Launch the interactive terminal:

```bash
teshq chat
```

Or run a single query directly:

```bash
teshq query "Show monthly revenue by product category for Q3"
```

---

## Interactive Terminal (`teshq chat`)

`teshq chat` (alias: `teshq repl`) provides a dedicated conversational REPL designed for iterative data exploration.

```bash
teshq chat
```

### In-Session Slash Commands

| Command | Action |
| :--- | :--- |
| `/help` or `/?` | Open the interactive command palette |
| `/tables` or `/schema` | Display an ASCII visual tree of all tables and columns |
| `/sql` | Inspect the last generated SQL query with bound parameters |
| `/explain` | Ask the AI to explain the query plan, business logic, and joins |
| `/export csv [file]` | Export current results to CSV (auto-resolves filename if omitted) |
| `/export excel [file]`| Export current results to Excel (`.xlsx`) |
| `/export sqlite [file]`| Save current results directly into a SQLite database |
| `/copy sql` | Copy generated SQL directly to the system clipboard (Windows, macOS, Linux) |
| `/copy results` | Copy formatted results table to the system clipboard |
| `/model [name]` | Hot-swap active LLM provider live in session (`google`, `azure`, `local`) |
| `/clear` or `/cls` | Clear terminal screen and restore the ambient HUD |
| `/history` | View recent prompts executed during this session |
| `exit` or `quit` | Exit session with runtime statistics (queries, latency, tokens) |

> 📖 **Interactive Terminal Guide:** Learn more about ambient HUDs, custom themes, and keyboard bindings in [docs/07_cli_reference.md](docs/07_cli_reference.md).

---

## 100% Offline & Air-Gapped Mode (Local GGUF)

For zero-data-leak environments, TESH-Query can run entirely on your local machine with no external network calls.

### 1. Check Hardware Acceleration

```bash
teshq local status
```

Inspects your CPU threads, system RAM, and detects available GPU acceleration (NVIDIA CUDA or Apple Silicon Metal).

### 2. Manage & Download Models

TESH-Query includes an automated Hugging Face GGUF model manager:

```bash
# List recommended models and local download status
teshq model list

# Download recommended model (downloads to ~/.teshq/models/ with progress bar)
teshq model download qwen3b-coder
```

| Model | Parameters | Quantization | Recommended RAM | Description |
| :--- | :---: | :---: | :---: | :--- |
| `qwen1.5b-coder` | 1.5B | Q4_K_M | 6 GB | Ultra-lightweight; runs on low-end machines and laptops |
| `qwen3b-coder` | 3.0B | Q4_K_M | 8 GB | **Recommended** sweet spot for speed and accuracy |
| `qwen7b-coder` | 7.0B | Q4_K_M | 16 GB | High-accuracy SQL generation for complex multi-join schemas |

### 3. GBNF Grammar Enforcement

Local models are physically constrained at the token sampling level by [sql_grammar.gbnf](teshq/core/sql_grammar.gbnf). The model cannot emit arbitrary text or hallucinations; it is mathematically forced to generate syntactically valid SQL statements.

> 📖 **Air-Gapped & GBNF Guide:** See [docs/09_offline_local_inference.md](docs/09_offline_local_inference.md) for custom GBNF grammars, GPU acceleration setup, and model quantization options.

---

## CLI Reference

### `teshq query`

Convert a natural language prompt into SQL and execute it.

```bash
teshq query [OPTIONS] [REQUEST]
```

*If `REQUEST` is omitted, TESHQ launches an interactive prompt.*

| Flag | Description |
| :--- | :--- |
| `-c, --connection <NAME>` | Target a registered named database connection |
| `--dry-run` | Generate and validate SQL, but **do not execute** it |
| `-i, --confirm` | Interactively inspect and confirm generated SQL before running |
| `--explain` | Print execution plan, selected tables, SQL, and timing breakdown |
| `-n, --limit <N>` | Append `LIMIT N` to the generated SQL |
| `--save-csv <FILE>` | Save query results to a CSV file |
| `--save-excel <FILE>` | Save query results to an Excel spreadsheet (`.xlsx`) |
| `--save-sqlite <FILE>` | Save query results to a SQLite table |
| `--schema-preview` | Print the exact TF-IDF compressed schema sent to the LLM, then exit |
| `--full-schema` | Use verbose schema (including row counts and index metadata) |
| `--local` | Force local GGUF model inference for this query |
| `--cloud` | Force cloud LLM inference (Gemini or Azure) for this query |
| `--verbose` | Write detailed execution logs to `~/.teshq/logs/` |

**Examples:**

```bash
# Query a specific named connection
teshq query -c ecommerce "What are the top 10 products by revenue?"

# Dry run: check generated SQL without executing
teshq query "Which customers have overdue invoices?" --dry-run

# Export results directly to Excel
teshq query "Top 20 sales representatives by deal value" --save-excel sales_q3.xlsx

# Interactive review mode before execution
teshq query "Update inventory counts for inactive items" -i
```

---

### Other Core Commands

| Command | Usage | Description |
| :--- | :--- | :--- |
| `teshq db connection add` | `teshq db connection add <name> <url>` | Register a named database connection with credentials |
| `teshq db connection list` | `teshq db connection list` | List all registered connections with masked credentials |
| `teshq db connection test` | `teshq db connection test <name>` | Verify health and connectivity of a named connection |
| `teshq db connection remove`| `teshq db connection remove <name>` | Unregister connection and safely dispose its engine pool |
| `teshq db connection default`| `teshq db connection default <name>` | Set the active default database connection |
| `teshq config` | `teshq config --wizard` | Interactive configuration wizard (DB + AI in 30 seconds) |
| `teshq config validate`| `teshq config validate` | Validate database connectivity, pooling, and production readiness |
| `teshq db explore` | `teshq db explore` | Interactive visual schema explorer |
| `teshq db show-schema` | `teshq db show-schema` | Display cached database schema |
| `teshq db clear-cache` | `teshq db clear-cache` | Reset cached schema in `~/.teshq/schemas/` |
| `teshq health` | `teshq health` | Run end-to-end diagnostics (DB ping, config, LLM latency) |
| `teshq bench run` | `teshq bench run` | Run Text-to-SQL benchmark suite measuring accuracy and cost |
| `teshq analytics` | `teshq analytics --days 7` | View token consumption and estimated query costs |

> 📖 **Complete CLI Reference:** For exhaustive command specifications, exit codes, and automated flags, see [docs/07_cli_reference.md](docs/07_cli_reference.md).

---

## Python SDK

TESH-Query provides a high-performance, asynchronous Python SDK for data analysts, data engineers, and machine learning pipelines.

> 📖 **Python SDK Guide:** For Polars/Arrow zero-copy usage, streaming, pagination, and multi-turn sessions, see [docs/08_python_sdk.md](docs/08_python_sdk.md).

### 1. Basic & Analytical Querying

```python
import teshq

# Initialize client (Zero-config connection pooling)
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/analytics_db",
    gemini_api_key="your-gemini-api-key"
)

# Compile schema locally (runs once, cached to ~/.teshq/)
client.introspect_database()


# 1. Natural language query returning Pandas DataFrame
df = client.query("Show weekly active users for past 6 months")

# 2. Native High-Performance Polars DataFrame (Zero-copy)
polars_df = client.query_polars("Monthly churn rate by plan tier")

# 3. Apache Arrow Table (Interoperable with PyData, DuckDB, Parquet)
arrow_table = client.query_arrow("Top 100 products by inventory turnover")
```

### 2. Multi-Turn Conversational Sessions

`TeshChatSession` maintains conversational memory and automatically stitches context for follow-up prompts:

```python
session = client.create_session()

# Turn 1: Initial query
df1 = session.ask("Show top 5 sales reps by total revenue")

# Turn 2: Automatic follow-up context threading!
df2 = session.ask("filter by west region only and sort descending")

# Inspect session state & export history
print(session.last_sql)
session_json = session.export_json()
```

### 3. Asynchronous Execution & Real-Time Event Streaming

```python
import asyncio

# Non-blocking async execution
async def run_pipeline():
    result = await client.aquery("Calculate customer lifetime value by acquisition cohort")
    print(result)

# Real-time lifecycle event streaming
for event in client.stream_query("Summarize quarterly revenue growth"):
    # event.stage: "schema_pruning", "planning", "sql_gen", "validation", "execution"
    print(f"[{event.stage}] {event.message}")
```

### 4. Bring-Your-Own-Engine (BYOE) & Business Context

Pass custom connection pools, SSL certificates, IAM authentication tokens, and business definitions directly:

```python
from sqlalchemy import create_engine
import teshq

custom_engine = create_engine(
    "postgresql://user:pass@db:5432/prod",
    pool_size=20,
    max_overflow=10,
    connect_args={"sslmode": "verify-full"}
)

client = teshq.TeshQuery(
    engine=custom_engine,  # Pass pre-configured engine
    business_context={
        "mrr": "SUM(amount) WHERE plan_type != 'trial' AND status = 'active'",
        "churned_user": "users with no login activity in 60 days"
    },
    gemini_api_key="your-api-key"
)
```

### 5. Advanced Query Results & Pagination

```python
result = client.query_advanced("SELECT department, headcount FROM company_stats")

# Pagination for large result sets
page_1 = result.paginate(page=1, page_size=25)
print(f"Page {page_1['page']} of {page_1['total_pages']} (Total rows: {page_1['total_rows']})")

# Export directly to Parquet or JSONL
result.to_parquet("company_stats.parquet")
result.to_jsonl("company_stats.jsonl")

# Structured payload with automatic chart recommendation hints (bar, line, scatter)
payload = result.to_payload()
print(payload["chart_hints"])  # e.g., {'type': 'bar', 'x_axis': 'department', 'y_axis': 'headcount'}
```

### 6. Named Multi-Database Connections & Routing

Manage $N$ isolated database connections simultaneously with independent connection pools, schema caches, and credential masking:

```python
import teshq

client = teshq.TeshQuery(gemini_api_key="your-gemini-api-key")

# Register named connections
client.add_connection(name="ecommerce", db_url="sqlite:///testing/databases/ecommerce.sqlite")
client.add_connection(name="analytics", db_url="postgresql://user:${DB_PASSWORD}@warehouse:5432/analytics")

# List all configured connections (credentials automatically masked)
for conn in client.list_connections():
    print(f"[{conn.name}] {conn.dialect} -> {conn.masked_url} (Default: {conn.is_default})")

# Query specific databases by name
ecom_df = client.query("What are the top 10 products by revenue?", connection="ecommerce")
fin_df = client.query("Total recognized revenue by fiscal quarter", connection="analytics")

# Test connectivity and dispose connection pool
is_healthy, msg = client.test_named_connection("ecommerce")
client.remove_connection("analytics")  # Safely disposes SQLAlchemy engine and connection pool
```

### 7. Cross-Database Natural Language Federation

Orchestrate complex cross-source queries across independent databases without distributed database joins:

```python
from teshq.core.federation import CrossDatabasePlan, SubquerySpec

# Execute a structured cross-database query plan
result = client.query_cross_db(
    "Compare monthly ecommerce GMV against finance ledger revenue",
    subqueries=[
        SubquerySpec(
            connection_name="ecommerce",
            sql="SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS ecom_gmv FROM orders GROUP BY month;",
            alias="ecom"
        ),
        SubquerySpec(
            connection_name="analytics",
            sql="SELECT fiscal_month AS month, recognized_revenue AS fin_rev FROM ledger_monthly_revenue;",
            alias="fin"
        )
    ],
    join_key="month",
    join_type="inner"
)

# Access combined records, Pandas DataFrame, and source attribution metadata
print(result.dataframe.head())
print("Source attribution:", result.source_attribution)
```

> 📖 **Multi-DB Federation Guide:** For thread-pool parallelism, source attribution, and join algorithms, see [docs/05_multi_database_federation.md](docs/05_multi_database_federation.md).

---

## Supported Databases & Dialects

TESH-Query supports **all databases supported by SQLAlchemy** — automatically detecting dialect features, selecting optimal pooling, and handling syntax specifics:

| Category | Database | Driver / Extra | Dialect Features Supported |
| :--- | :--- | :--- | :--- |
| **Cloud Warehouses** | **Snowflake** | `snowflake-sqlalchemy` | Native Snowflake dialect, case-sensitive identifiers |
| | **Google BigQuery** | `sqlalchemy-bigquery` | Google Standard SQL, backtick quoting |
| | **Databricks** | `databricks-sql-connector` | Spark SQL dialect, Delta Lake catalogs |
| | **Amazon Redshift** | `sqlalchemy-redshift` | Redshift dialect, distkey/sortkey aware |
| **Real-Time OLAP** | **DuckDB** | `duckdb-engine` | In-process vectorized analytics, Parquet/CSV scanning |
| | **ClickHouse** | `clickhouse-connect` | ClickHouse SQL, specialized aggregations |
| **Relational** | **PostgreSQL** | `teshq[postgres]` (`asyncpg`) | CTEs, Window functions, JSONB operators |
| | **MySQL / MariaDB** | `teshq[mysql]` (`PyMySQL`) | Backtick escaping, MySQL 8.0+ window functions |
| | **Microsoft SQL Server** | `teshq[mssql]` (`pymssql`) | T-SQL dialect, `TOP` syntax, `@@VERSION` diagnostics |
| | **Oracle** | `oracledb` | PL/SQL, ROWNUM pagination |
| | **SQLite** | Built-in | Zero-config, in-memory or file-based |
| **Distributed SQL** | **CockroachDB** | `cockroachdb` | PostgreSQL-compatible wire protocol, distributed tables |
| | **Trino / Presto** | `trino-python-client` | ANSI SQL, cross-catalog federated tables |
| **Universal** | **Any SQLAlchemy Dialect** | Any 3rd party driver | Automatic dialect discovery, ANSI standard fallback |
| **NoSQL** | **Apache Cassandra** | `cassandra-driver` | CQL (Cassandra Query Language) |

> 📖 **Universal Database Guide:** See [docs/04_database_dialects.md](docs/04_database_dialects.md) for compound URL schemes (`oracle+cx_oracle`, `clickhouse+native`), analytical view reflection, and dynamic connection pools.

---

## Installation Extras Reference

Install only what you need:

```bash
# Data science & high-performance analytics
pip install "teshq[data]"           # pyarrow, polars

# Machine learning & local OLAP
pip install "teshq[ml]"             # pyarrow, polars, duckdb

# Database drivers
pip install "teshq[postgres]"       # Pure-Python asyncpg (Python 3.10–3.14+)
pip install "teshq[postgres-binary]"# psycopg2-binary
pip install "teshq[mysql]"          # PyMySQL & mysql-connector-python
pip install "teshq[mssql]"          # pymssql (MS SQL Server)

# Offline local inference
pip install "teshq[local]"          # llama-cpp-python

# Comprehensive driver bundles
pip install "teshq[all]"            # All pre-built drivers (MySQL, MSSQL, Excel)
pip install "teshq[all-databases]"  # All database drivers (Cloud Warehouses + Relational)
```

---

## Verification & Diagnostics

TESH-Query includes an automated self-test and verification suite:

```bash
# Run complete system diagnostic health check
teshq health

# Run configuration and production readiness assessment
teshq config validate

# Run unit and integration tests (400+ tests)
pytest tests/unit/ tests/integration/
```

---

## Testing & Fixture Database (`/testing`)

TESH-Query includes a realistic, Amazon-scale ecommerce testing database fixture (`testing/databases/ecommerce.sqlite`) with **45 normalized relational tables**, **38 explicit secondary indexes**, and **1,123,500+ rows** of synthetic data for testing schema pruning, query generation, complex joins, and cross-database federation.

See [testing/README.md](testing/README.md) for full architecture and schema details.

> 📖 **Testing Fixture Architecture:** See [docs/12_testing_and_benchmarks.md](docs/12_testing_and_benchmarks.md) for full relational taxonomy, schema diagrams, and financial invariant specifications.

### Generate Synthetic Fixture
```bash
# Standard profile (~1.12M rows, 93 MB in ~4s)
python testing/create_database.py --profile standard --seed 42 --force

# Large profile (~10M rows, ~900 MB in ~45s)
python testing/create_database.py --profile large --seed 42 --force
```

### Verify Integrity & Financial Invariants
```bash
python testing/verify_database.py
```
Validates SQLite integrity, 0 foreign-key violations, 45 domain tables, 38 indexes, minimum row counts, synthetic email purity, and 7 business invariants (order totals, payment reconciliation, line total reconciliation, refund ceilings, chronological sequence).

### Run Scalability & Execution Latency Benchmarks
```bash
python testing/run_benchmarks.py
```
Measures schema introspection time, graph retrieval latency, and query execution times across 32 natural language benchmark queries.

---

## Contributing

We welcome contributions! Please review [CONTRIBUTING.md](CONTRIBUTING.md) and our [Contributor License Agreement (CLA)](CLA.md).

```bash
# 1. Clone repository
git clone https://github.com/theshashank1/TESH-Query.git
cd TESH-Query

# 2. Install editable package with dev dependencies
pip install -e ".[dev]"

# 3. Run test suite
pytest tests/unit/
```

---

## License

TESH-Query is open-source software licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) file for the full text.

```
Copyright 2025-2026 Shashank Gundas

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

<div align="center">
<sub>Built with precision by <a href="https://github.com/theshashank1">Shashank</a> • <a href="https://github.com/theshashank1/TESH-Query/issues">Report an issue</a> • <a href="https://github.com/theshashank1/TESH-Query/discussions">Join discussions</a></sub>
</div>
