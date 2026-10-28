# Python SDK & Modern Analytics Guide

The TESH-Query Python SDK (`teshq`) provides a zero-copy, asynchronous interface for data scientists, data engineers, and backend developers building analytical applications.

---

## 🚀 Quick Start

```python
import teshq

# Initialize client (uses ~/.teshq/ credentials or parameters)
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/analytics",
    gemini_api_key="your-gemini-key"
)

# Run a natural language query returning a Pandas DataFrame
df = client.query("Show top 10 customers by total spend in 2024")
print(df.head())
```

---

## ⚡ Zero-Copy Modern Analytics Outputs

TESH-Query provides first-class integrations with modern vectorized data structures:

### 1. Polars DataFrame (`client.query_polars`)
Returns a native `polars.DataFrame` without intermediate Python object conversions:

```python
# Zero-copy Polars DataFrame
polars_df = client.query_polars("Monthly churn rate grouped by plan tier")
print(polars_df.schema)
```

### 2. Apache Arrow Table (`client.query_arrow`)
Returns a `pyarrow.Table`, enabling direct interoperability with PyData libraries, DuckDB, and Parquet engines:

```python
arrow_table = client.query_arrow("Top 100 products by inventory turnover ratio")
print(f"Arrow Table: {arrow_table.num_rows} rows, {arrow_table.num_columns} columns")
```

### 3. Pandas DataFrame (`client.query`)
Standard Pandas DataFrame output for existing workflows:

```python
df = client.query("Average order value by geographic region")
```

---

## 🔄 Multi-Turn Conversational Sessions (`TeshChatSession`)

`TeshChatSession` maintains conversational memory across multiple queries, allowing users to ask follow-up questions that refine previous SQL statements:

```python
session = client.create_session()

# Turn 1: Initial broad query
df1 = session.ask("Show total revenue by sales representative for Q3")

# Turn 2: Follow-up question automatically threading Turn 1 context!
df2 = session.ask("filter by west region only and sort descending")

# Turn 3: Further drilldown
df3 = session.ask("exclude trial accounts")

# Inspect generated SQL & export session history
print("Final SQL:", session.last_sql)
history = session.export_json()
```

---

## ⏱️ Asynchronous Execution & Event Streaming

### 1. Non-Blocking Async (`client.aquery`)
Ideal for integration into async web servers (FastAPI, Starlette) and Celery workers:

```python
import asyncio

async def fetch_analytics():
    df = await client.aquery("Calculate customer lifetime value (LTV) by cohort")
    return df

results = asyncio.run(fetch_analytics())
```

### 2. Real-Time Lifecycle Event Streaming (`client.stream_query`)
Stream progress events directly to frontends or WebSocket connections:

```python
for event in client.stream_query("Quarterly revenue growth by business unit"):
    # event.stage: "schema_pruning", "planning", "sql_gen", "validation", "execution"
    print(f"[{event.stage}] {event.message}")
```

---

## 🛠️ Bring-Your-Own-Engine (BYOE) & Context Ingestion

### 1. Custom SQLAlchemy Engine
Inject custom connection pools, SSL configurations, IAM auth tokens, or proxy layers:

```python
from sqlalchemy import create_engine
import teshq

custom_engine = create_engine(
    "postgresql://user:pass@dbserver:5432/prod",
    pool_size=20,
    max_overflow=10,
    connect_args={"sslmode": "verify-full"}
)

client = teshq.TeshQuery(engine=custom_engine)
```

### 2. Custom Business Context & Glossary
Provide domain-specific metric definitions so the LLM understands your business terminology:

```python
client = teshq.TeshQuery(
    db_url="postgresql://localhost:5432/prod",
    business_context={
        "mrr": "Monthly Recurring Revenue: SUM(amount) WHERE status = 'active' AND plan != 'trial'",
        "churn": "Users with no login activity in 60 days",
        "enterprise_deal": "Orders with total_amount >= 50000"
    }
)
```

---

## 📑 Advanced Results, Pagination & Exports

Use `client.query_advanced()` for fine-grained result set manipulation:

```python
result = client.query_advanced("SELECT department, headcount, budget FROM departments")

# 1. Pagination for large result sets
page_1 = result.paginate(page=1, page_size=10)
print(f"Page {page_1['page']} of {page_1['total_pages']} (Total rows: {page_1['total_rows']})")

# 2. Direct Parquet & JSONL export
result.to_parquet("departments.parquet")
result.to_jsonl("departments.jsonl")

# 3. Chart Recommendation Hints
payload = result.to_payload()
print(payload["chart_hints"])
# Output: {'type': 'bar', 'x_axis': 'department', 'y_axis': 'headcount'}
```

---

## 🗄️ Multi-Database Routing & Cross-DB Federation

```python
# Configure multiple connections
client.add_connection("ecommerce", "sqlite:///testing/databases/ecommerce.sqlite")
client.add_connection("finance", "postgresql://user:pass@localhost:5432/finance")

# Route query to specific named database
df = client.query("Top 5 selling items", connection="ecommerce")

# Execute federated cross-database query
from teshq.core.federation import SubquerySpec

cross_res = client.query_cross_db(
    request="Reconcile GMV against finance revenue",
    subqueries=[
        SubquerySpec(
            connection_name="ecommerce",
            sql="SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS gmv FROM orders GROUP BY month;",
            alias="ecom"
        ),
        SubquerySpec(
            connection_name="finance",
            sql="SELECT month, recognized_revenue FROM monthly_financials;",
            alias="fin"
        )
    ],
    join_key="month",
    join_type="inner"
)
print(cross_res.dataframe.head())
```

---

## 🧭 Next Steps

- **[Multi-Database Federation](05_multi_database_federation.md)** — In-depth cross-database orchestration.
- **[Offline Local Inference](09_offline_local_inference.md)** — Run local GGUF models.
- **[Testing & Benchmarks](12_testing_and_benchmarks.md)** — Learn about the synthetic Amazon-scale test database.
