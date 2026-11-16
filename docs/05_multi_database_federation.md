# Multi-Database Management & Cross-Database Federation

TESH-Query supports managing $N$ isolated database connections simultaneously and orchestrating cross-database queries where subqueries are dispatched concurrently across heterogeneous database engines and combined in memory.

---

## 🗄️ Named Database Connections

Rather than being limited to a single `DATABASE_URL`, TESH-Query allows you to register multiple named database connections. Each registered connection maintains:
- Its own isolated SQLAlchemy `Engine` and connection pool
- Independent schema introspection graphs
- Automatic credential masking in logs and terminal outputs

### 1. Managing Connections via CLI

```bash
# Add named connections
teshq db connection add ecommerce "sqlite:///testing/databases/ecommerce.sqlite"
teshq db connection add analytics "postgresql://user:secret@warehouse.prod:5432/analytics_db"

# List all configured connections (credentials automatically masked)
teshq db connection list

# Test connectivity and measure latency
teshq db connection test ecommerce
teshq db connection test analytics

# Set the active default connection
teshq db connection default ecommerce

# Remove a connection and safely dispose its engine pool
teshq db connection remove analytics
```

### 2. Managing Connections via Python SDK

```python
import teshq

client = teshq.TeshQuery(gemini_api_key="your-api-key")

# Register connections dynamically
client.add_connection(name="ecommerce", db_url="sqlite:///testing/databases/ecommerce.sqlite")
client.add_connection(name="analytics", db_url="postgresql://user:pass@localhost:5432/analytics")

# List registered connections
for conn in client.list_connections():
    print(f"[{conn.name}] {conn.dialect} -> {conn.masked_url} (Default: {conn.is_default})")

# Test named connection health
healthy, msg = client.test_named_connection("ecommerce")
print(f"Status: {healthy} ({msg})")

# Safely dispose engine and unregister
client.remove_connection("analytics")
```

---

## ⚡ Cross-Database Natural Language Federation

When data is partitioned across disparate database engines (e.g. transactional ecommerce data in SQLite/PostgreSQL and financial revenue records in Snowflake/BigQuery), TESH-Query executes cross-database query plans without requiring distributed SQL engines (like Trino or Presto).

```
                      Cross-Database Query Plan
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       Subquery 1 (ecommerce)           Subquery 2 (analytics)
      SQLite / PostgreSQL               Snowflake / BigQuery
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                ThreadPoolExecutor (Parallel Execution)
                                  │
                                  ▼
                Vectorized In-Memory DataFrame Join
                     (Inner / Left / Outer / Cross)
                                  │
                                  ▼
                     Unified Result Set & Polars /
                         Pandas / Arrow Output
```

---

## 🧵 Parallel Subquery Execution

Subqueries defined within a `CrossDatabasePlan` are executed concurrently using Python's `concurrent.futures.ThreadPoolExecutor`:

```python
# From teshq/core/federation.py
max_workers = min(len(plan.subqueries), 8)
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {
        executor.submit(self._run_subquery, subquery): subquery
        for subquery in plan.subqueries
    }
```

### Key Performance Benefits
- **Zero Sequential Wait:** If Subquery 1 takes 80ms and Subquery 2 takes 120ms, the combined execution completes in ~125ms instead of 200ms.
- **Deterministic Ordering:** Subquery results preserve the exact order specified in the plan.
- **Thread-Safe Pooling:** Embedded engines like SQLite are configured with `check_same_thread=False` and `NullPool` to eliminate thread deadlocks.

---

## 🔗 Vectorized In-Memory DataFrame Joins

Once subqueries return their respective result sets, `CrossDatabaseOrchestrator` combines them in memory:

```python
from teshq.core.federation import CrossDatabasePlan, SubquerySpec

# Define the federation plan
plan = CrossDatabasePlan(
    description="Reconcile ecommerce sales against finance revenue",
    subqueries=[
        SubquerySpec(
            connection_name="ecommerce",
            sql="SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS ecom_sales FROM orders GROUP BY month;",
            alias="ecom"
        ),
        SubquerySpec(
            connection_name="analytics",
            sql="SELECT fiscal_month AS month, recognized_revenue AS fin_rev FROM ledger_monthly;",
            alias="fin"
        )
    ],
    join_key="month",
    join_type="inner"
)

result = client.query_cross_db(
    request="Reconcile ecommerce sales against finance revenue",
    subqueries=plan.subqueries,
    join_key="month",
    join_type="inner"
)

# Access combined results
print(result.dataframe.head())
print("Source Attribution:", result.source_attribution)
```

### Type-Safe Join Key Sanitization
Different databases format string keys with varied whitespace and types. TESH-Query uses vectorized Pandas/Polars string cleaning:

```python
clean[col] = clean[col].astype(str).str.strip().where(clean[col].notna(), None)
```

This prevents mismatched joins between trailing spaces in `CHAR` fields and `VARCHAR` fields across different databases.

---

## 🔒 Credential Redaction & Security

All named database connection configurations mask credentials at all times:
- Passwords and auth tokens in connection URLs are replaced with `***` in terminal cards, `list_connections()` payloads, and execution logs.
- Safe deserialization ensures that raw credentials stored in `~/.teshq/` are never exposed in traceback strings or logging outputs.

---

## 🧭 Next Steps

- **[AST Security Firewall](06_security_firewall.md)** — Learn how generated SQL is verified for read-only safety.
- **[Python SDK Reference](08_python_sdk.md)** — Explore Polars, Arrow, and asynchronous querying.
- **[Testing & Benchmarks](12_testing_and_benchmarks.md)** — Explore the synthetic Amazon-scale e-commerce database.
