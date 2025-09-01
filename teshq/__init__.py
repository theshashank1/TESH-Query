"""
TESH-Query: Natural Language to SQL Converter

A powerful library and CLI tool that converts natural language queries into SQL
and executes them on your database using AI (Google Gemini).

## Programmatic Usage

```python
import teshq

# Initialize the client
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@host:port/dbname",
    gemini_api_key="your-gemini-api-key"
)

# Introspect database schema
schema = client.introspect_database()

# Execute natural language queries
results = client.query("show me all users who registered last month")

# Generate SQL without executing
sql_info = client.generate_sql("count all active users")
print(sql_info['query'])
```

## CLI Usage

```bash
# Configure database and API credentials
teshq config --db --gemini

# Introspect database schema
teshq introspect

# Execute natural language queries
teshq query "show me all users who registered last month"
```

For more information, visit: https://github.com/theshashank1/TESH-Query
"""

# Import main API classes and functions
from .api import TeshQuery, introspect, query

# Import version information
try:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("teshq")
    except PackageNotFoundError:
        __version__ = "unknown"
except ImportError:
    __version__ = "unknown"

# Public API
__all__ = ["TeshQuery", "introspect", "query", "__version__"]
