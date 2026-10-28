# TESH-Query — System Overview

**TESH-Query (TESHQ)** is an autonomous natural-language-to-SQL compiler, execution harness, and AST security firewall. It translates plain English questions into dialect-accurate, injection-safe SQL across 11+ databases, validates queries via an Abstract Syntax Tree (AST) firewall, executes them with connection pooling, and recovers from syntax errors in an automated closed-loop self-healing cycle.

---

## 🎯 The Core Problem

Passing raw natural language to Large Language Models (LLMs) and executing the emitted SQL directly against production databases presents severe engineering and security risks:

1. **Context Window Saturation & Cost:** In enterprise databases with 50 to 500+ tables, dumping the full database schema into the LLM prompt blows past token budgets, degrades attention, and drives massive API costs.
2. **Security & Data Destruction:** LLMs can hallucinate destructive queries (`DROP TABLE`, `TRUNCATE`, unconstrained `DELETE` without a `WHERE` clause) or introduce SQL injection vulnerabilities.
3. **Dialect Incompatibilities:** Every database dialect (Snowflake, BigQuery, PostgreSQL, MySQL, Oracle, DuckDB) has subtle syntax variations (backticks vs double quotes, date functions, pagination syntax like `LIMIT` vs `TOP` vs `FETCH FIRST`). LLMs frequently mix these up.
4. **Brittle Execution:** When a query fails due to an unexpected column name or type mismatch, naive tools crash and require manual user intervention.

TESH-Query solves these challenges by acting as a **hardened intermediary layer** between the user, the LLM, and the database.

---

## 🏗️ The 6-Stage Cognitive Pipeline

Every query submitted to TESH-Query undergoes a 6-stage lifecycle:

```
 User Question: "Show top 10 products by revenue in 2024"
                       │
                       ▼
 ┌───────────────────────────────────────────┐
 │ 1. Schema Introspection & Graph Indexing  │  Extracts tables, columns, PKs, and FKs into SchemaGraph
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 2. In-Memory TF-IDF Schema Retriever      │  Prunes 100+ tables down to Top-K relevant tables (3-5 tables)
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 3. Two-Stage LLM Compiler                 │  Stage 1: Query Planner (identifies joins, filters, measures)
 │                                           │  Stage 2: Dialect Generator (compiles dialect-accurate SQL)
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 4. AST Security Firewall                  │  Inspects parsed AST tokens; hard-blocks destructive queries
 └─────────────────────┬─────────────────────┘
                       ▼
 ┌───────────────────────────────────────────┐
 │ 5. Connection Pooling & DB Execution      │  Executes query with bound parameters (:named)
 └─────────────────────┬─────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
 [Syntax / DB Error?]          [Query Success]
 Capture compiler error,              │
 re-feed into LLM,                    ▼
 self-heal & retry (up to 3x)  Zero-Copy Polars / Arrow / Pandas DataFrame
```

---

## 🌟 Key Capabilities

### 1. Universal Database Dialect Support
TESH-Query supports **all databases supported by SQLAlchemy** — including Cloud Data Warehouses (Snowflake, BigQuery, Databricks, Redshift), Real-Time OLAP engines (DuckDB, ClickHouse), Enterprise Relational (PostgreSQL, MySQL, MariaDB, MS SQL Server, Oracle, SQLite), and Distributed SQL (CockroachDB, Trino, Presto). Compound dialect drivers like `oracle+cx_oracle://` and `clickhouse+native://` are parsed natively without scheme corruption.

### 2. Multi-Database Management & Natural Language Federation
Register multiple isolated database connections simultaneously with independent connection pools. Execute cross-database queries where subqueries run in parallel across worker threads and are joined in-memory using vectorized Pandas/Polars operations.

### 3. Abstract Syntax Tree (AST) Security Firewall
Before any SQL statement reaches the database, the AST parser analyzes the syntax tree. Destructive statements (`DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `REPLACE`, `GRANT`, `REVOKE`) are unconditionally blocked. `UPDATE` and `DELETE` statements lacking explicit `WHERE` clauses are blocked. Table accesses outside the known schema boundary are flagged.

### 4. TF-IDF Schema Vector Pruner
An in-memory TF-IDF cosine-similarity search engine tokenizes database tables, columns, and foreign keys. When a question is received, only the Top-3 to 5 most relevant tables and their foreign-key neighbors are injected into the prompt, slashing token consumption by up to 90%.

### 5. Closed-Loop Self-Healing
If the database dialect rejects a query (e.g. invalid group by clause or dialect-specific date formatting error), TESH-Query intercepts the database error code, structures a safe diagnostic prompt (`error_hint`), and prompts the model to correct its query automatically with exponential backoff.

### 6. Modern Analytics Zero-Copy SDK
Native zero-copy exports for **Polars** (`client.query_polars`), **Apache Arrow** (`client.query_arrow`), and **Pandas** (`client.query`), with direct export utilities for Parquet, JSONL, CSV, and Excel.

### 7. 100% Offline & Air-Gapped Mode
Run completely offline with zero external network connectivity using local GGUF models via `llama.cpp` and hardware acceleration (Apple Silicon Metal, NVIDIA CUDA). Employs **GBNF context-free grammars** to physically constrain LLM token generation to valid SQL syntax.

---

## 📁 Repository Structure

```
TESH-Query/
├── teshq/
│   ├── cli/             # Typer CLI commands, terminal REPL, HUD, and cards
│   ├── config/          # Pydantic V2 BaseSettings, credential storage, secrets
│   ├── core/            # Pipeline engine, AST validator, connectors, federation
│   │   ├── connection.py    # Engine factory and connection pool configuration
│   │   ├── connectors.py    # Native connectors (Postgres, MySQL, Oracle, DuckDB, etc.)
│   │   ├── dialect.py       # Dialect detection and SQL dialect rules
│   │   ├── engine.py        # Central TeshEngine orchestrator
│   │   ├── federation.py    # Multi-database connection manager and cross-DB orchestrator
│   │   ├── introspect.py    # Schema reflection, view extraction, and statistics
│   │   ├── retriever.py     # In-memory TF-IDF schema pruner
│   │   ├── sql_gen.py       # Two-stage LLM query planner and SQL generator
│   │   └── sql_validator.py # AST security firewall and syntax sanitizer
│   ├── utils/           # Modern UI components, save utilities, retry helpers
│   └── api.py           # Public Python SDK interface (TeshQuery)
├── testing/             # Synthetic Amazon-scale testing database (45 tables, 1.12M rows)
│   ├── databases/       # SQLite fixture database
│   ├── create_database.py # Synthetic generator with Faker and seed control
│   ├── verify_database.py # Integrity and financial invariant verifier
│   └── run_benchmarks.py  # Performance, pruning, and latency benchmark suite
└── docs/                # Comprehensive documentation suite
```

---

## 🧭 Next Steps

- **[Installation & Driver Setup](02_installation.md)** — Install TESH-Query and configure database drivers.
- **[Harness Architecture](03_architecture.md)** — Explore the internal engine architecture.
- **[CLI Reference](07_cli_reference.md)** — Start querying your database using `teshq chat`.
