# Harness Architecture & Cognitive Execution Engine

TESH-Query operates as a complete execution and safety harness mediating between natural language prompts, Large Language Models (LLMs), and production database engines.

```
 User Question: "Show active customers with orders > $1,000 in Q3"
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
 │                                           │  Stage 2: Dialect Generator (compiled SQL query)
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

---

## 🧩 Core Architecture Components

### 1. Schema Introspection & Graph Modeling (`teshq/core/introspect.py`)

Rather than relying on naive text dumps of `CREATE TABLE` scripts, TESH-Query uses SQLAlchemy's reflection engine coupled with inspector fallback mechanisms:
- **Resilient Bulk & Table-by-Table Reflection:** Dialects that do not support bulk reflection gracefully degrade to table-by-table reflection.
- **Physical Tables & Database Views:** Introspects both physical base tables (`get_table_names()`) and analytical database views (`get_view_names()`), deduplicating across multi-schema environments.
- **Primary & Foreign Key Topology:** Builds a connected `SchemaGraph` tracking referential integrity constraints, primary keys, and foreign-key join paths.
- **Statistical Profiling:** Samples row counts and distinct values without locking production tables (`SELECT COUNT(*)` with dialect-specific optimizations).
- **Leak-Free Engine Disposal:** Guarantees connection cleanup via `engine.dispose()` to prevent socket and file descriptor leaks.

---

### 2. In-Memory TF-IDF Schema Vector Pruner (`teshq/core/retriever.py`)

In real-world enterprise databases with 50 to 500+ tables, providing the entire database schema to an LLM:
- Slashes model attention and accuracy
- Exceeds model context limits
- Drives token costs up exponentially

TESH-Query includes an in-memory **TF-IDF vector retriever**:
1. **Document Synthesis:** Each table is converted into a structured document containing its table name, column names, column descriptions, and data types.
2. **Cosine Similarity Search:** When a user prompt arrives, the retriever tokenizes the query and computes cosine similarity against all table documents.
3. **Graph Neighbor Expansion:** The retriever selects the Top-$K$ (typically 3–5) highest-scoring tables and automatically traverses `SchemaGraph` edges to include foreign-key linked neighbors (e.g., if `order_items` matches, `orders` and `products` are included).
4. **Engine-Level Index Caching:** In `teshq/core/engine.py`, TF-IDF index structures are cached in memory per connection URL (`self._retrievers[db_url]`), eliminating redundant index construction on repeat queries.

---

### 3. Two-Stage LLM Compilation Pipeline (`teshq/core/sql_gen.py`)

A single-step prompt from natural language to SQL often hallucinates join conditions or skips WHERE clauses. TESH-Query decouples query synthesis into two distinct cognitive stages:

#### Stage 1: Query Planning (`QueryPlanner`)
- **Input:** Natural language request + Top-$K$ pruned schema graph.
- **Cognitive Task:** Determine business intent, target tables, join pathways (`INNER`, `LEFT`), filter conditions, aggregation metrics, and grouping columns.
- **Output:** A structured, dialect-agnostic `QueryPlan` object.

#### Stage 2: Dialect Generation (`SQLGenerator`)
- **Input:** `QueryPlan` + Target Database Dialect (`PostgreSQL`, `Snowflake`, `MySQL`, `Oracle`, `DuckDB`, etc.).
- **Cognitive Task:** Synthesize dialect-accurate SQL conforming to exact engine nuances (e.g. `ILIKE` vs `LOWER(x) LIKE`, `DATE_TRUNC` vs `STRFTIME`, backtick vs double-quote identifier quoting).
- **Output:** Structured `SQLQuery` containing parameter bindings (`:named_param`).

---

### 4. Abstract Syntax Tree (AST) Security Firewall (`teshq/core/sql_validator.py`)

Before any SQL statement is sent to the database connection pool, it must clear the AST Security Firewall:
- **AST Parsing:** Deconstructs the statement using `sqlglot` and lexical tokenizers.
- **Read-Only Enforcement:** Enforces that statements begin with `SELECT` or `WITH` CTE expressions unless explicit update permissions are active.
- **Destructive Operation Blocking:** Unconditionally rejects statements containing `DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `REPLACE`, `GRANT`, or `REVOKE`.
- **Unconstrained Update Protection:** Prohibits `UPDATE` or `DELETE` operations lacking an explicit `WHERE` clause to prevent accidental catastrophic data wipes.
- **Schema Boundary Whitelisting:** Validates that referenced table names belong to the introspected schema graph.

---

### 5. Multi-Database Federation Engine (`teshq/core/federation.py`)

For modern data stacks where information is distributed across independent databases:
- **`NamedConnectionManager`:** Manages $N$ named database connections with isolated connection pools and credential masking.
- **`CrossDatabaseOrchestrator`:** Accepts a `CrossDatabasePlan` with independent `SubquerySpec` definitions.
- **Concurrent Execution:** Dispatches subqueries concurrently using `concurrent.futures.ThreadPoolExecutor(max_workers=min(len(subqueries), 8))`.
- **Vectorized In-Memory Joins:** Executes vectorized DataFrame joins in memory (`inner`, `left`, `right`, `outer`), sanitizing join keys with vector operations.

---

### 6. Closed-Loop Self-Healing Recovery (`teshq/core/engine.py`)

If a query passes the AST firewall but fails at database runtime (e.g. database dialect type mismatch or division by zero):
1. The engine catches the database error code.
2. The error message is sanitized to remove internal paths and credentials.
3. The engine crafts an `error_hint` prompt containing the failing SQL and compiler diagnostic.
4. Stage 2 (SQL Generator) is re-invoked with the corrective feedback.
5. Retries are governed by jittered exponential backoff.

---

## 🧭 Next Steps

- **[Universal Database Dialects](04_database_dialects.md)** — In-depth driver configuration for all SQLAlchemy databases.
- **[Multi-Database Federation](05_multi_database_federation.md)** — Cross-database query routing and orchestration.
- **[AST Security Firewall](06_security_firewall.md)** — Deep dive into query validation and safety rules.
