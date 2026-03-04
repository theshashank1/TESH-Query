# SDK Usage Guide

The `TeshQuery` class provides a programmatic Python API for embedding TESH-Query in applications, scripts, and data pipelines.

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

## Asynchronous Usage

`TeshQuery.aquery()` runs the full pipeline in a thread-pool executor, making it safe to call from an async context without blocking the event loop.

### FastAPI Example

```python
from fastapi import FastAPI
from teshq import TeshQuery

app = FastAPI()
client = TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/mydb",
    gemini_api_key="your-api-key",
)


@app.get("/query")
async def run_query(q: str):
    results = await client.aquery(q)
    return {"results": results}
```

### Plain asyncio

```python
import asyncio
from teshq import TeshQuery

async def main():
    client = TeshQuery(
        db_url="sqlite:///app.db",
        gemini_api_key="your-key",
    )
    results = await client.aquery("list all products")
    print(results)

asyncio.run(main())
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
