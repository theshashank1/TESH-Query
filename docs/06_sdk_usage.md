# SDK Usage Guide

The `TeshQuery` class provides a programmatic Python API for embedding TESH-Query in internal data analysis, notebooks, and ETL pipelines.

## Synchronous Usage

### Basic Query

```python
from teshq import TeshQuery

client = TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/mydb",
    gemini_api_key="your-api-key",
)

# Full pipeline: NL → SQL → execute → results
results = client.query("show me all users who registered last month")
for row in results:
    print(row)
```

### High-Performance Data Formats (Polars & Apache Arrow)

```python
result = client.query_advanced("top 10 products by quarterly revenue")

# Native Pandas DataFrame
df = result.dataframe

# High-performance Polars DataFrame (zero-copy)
polars_df = result.polars

# Apache Arrow Table (interoperable across PyData)
arrow_table = result.arrow
```

### Stateful Conversational Sessions

```python
# Maintain conversational context across multi-turn queries
session = client.create_session()

res1 = session.ask("Show top 5 sales reps by deal volume")
# Follow-up automatically threads previous context and SQL:
res2 = session.ask("filter by west region only")

# Export session state to JSON
session_json = session.export_json()
```

### Generate SQL Without Executing

```python
sql_info = client.generate_sql("count all active users")
print(sql_info["query"])       # SELECT COUNT(...) ...
print(sql_info["parameters"])  # {}
```

### Advanced Query (Rich Result Object)

```python
result = client.query_advanced("top 10 customers by revenue")
print(result.results)          # list of dicts
print(result.query)            # the SQL that was executed
print(result.parameters)       # bound parameters
```

### Execute Raw SQL

```python
result = client.execute_query(
    "SELECT id, name FROM users WHERE id = :user_id",
    parameters={"user_id": 42},
)
print(result.results)
```

### Schema Introspection

```python
schema = client.introspect_database(include_sample_data=True)
for table_name, table_info in schema["tables"].items():
    print(f"{table_name}: {len(table_info['columns'])} columns")
```

### Health Check

```python
report = client.health_check()
print(report)
```

## Asynchronous Usage & Event Streaming

`TeshQuery.aquery()` executes asynchronously without blocking the event loop, ideal for concurrent data jobs.

### Async Pipeline Worker

```python
import asyncio
from teshq import TeshQuery

async def run_pipeline(prompts: list[str]):
    client = TeshQuery(
        db_url="postgresql://user:pass@localhost:5432/mydb",
        gemini_api_key="your-api-key",
    )
    tasks = [client.aquery(p) for p in prompts]
    return await asyncio.gather(*tasks)

asyncio.run(run_pipeline(["count users", "active subscriptions"]))
```

### Real-Time Event Streaming

```python
# Stream pipeline lifecycle events for observability
for event in client.stream_query("calculate customer lifetime value"):
    print(f"[{event.stage}] {event.message}")
```

## Azure OpenAI Provider

```python
client = TeshQuery(
    db_url="postgresql://user:pass@host:5432/db",
    provider="azure",
    azure_api_key="your-azure-key",
    azure_endpoint="https://your-resource.openai.azure.com/",
    azure_deployment="gpt-4o",
)

results = client.query("show me recent orders")
```

## Module-Level Convenience Functions

For quick one-off operations without creating a client:

```python
import teshq

# Introspect (no LLM key needed)
schema = teshq.introspect(db_url="sqlite:///app.db")

# Query (needs LLM key)
results = teshq.query(
    "show all users",
    db_url="sqlite:///app.db",
    gemini_api_key="your-key",
)

# Health check
report = teshq.health_check()
```
