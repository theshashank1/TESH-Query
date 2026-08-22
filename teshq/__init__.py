"""
TESH-Query v2.1.0 — Natural Language to SQL Converter

A production-grade library and CLI tool that converts natural language queries
into SQL and executes them on your database using AI.

Supported LLM providers:
  - Google Gemini (default)
  - Azure OpenAI

## Programmatic Usage

```python
import teshq

# Google Gemini (default)
client = teshq.TeshQuery(
    db_url="sqlite:///my_database.db",
    gemini_api_key="your-gemini-api-key"
)

# Azure OpenAI
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@host:port/dbname",
    provider="azure",
    azure_api_key="your-azure-key",
    azure_endpoint="https://your-resource.openai.azure.com/",
    azure_deployment="gpt-4o",
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
# Configure database and Gemini credentials
teshq config --db --gemini

# Or configure for Azure OpenAI
teshq config --db --azure

# Introspect database schema
teshq db introspect

# Execute natural language queries
teshq query "show me all users who registered last month"
```

All configuration, schema cache, logs, and state are stored under ~/.teshq/.
For more information, visit: https://github.com/theshashank1/TESH-Query
"""

# Suppress LangChain / Pydantic V1 compatibility warnings on Python 3.14+.
# These are internal LangChain warnings, not actionable by end-users.
import warnings as _warnings
_warnings.filterwarnings("ignore", message=r".*Pydantic V1 functionality.*", category=UserWarning)
_warnings.filterwarnings("ignore", message=r".*pydantic\.v1.*", category=UserWarning)
del _warnings

# Import main API classes and functions
from .api import TeshQuery, health_check, introspect, query

# Import version information
try:
    from ._version import __version__
except ImportError:
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            __version__ = version("teshq")
        except PackageNotFoundError:
            __version__ = "0.0.0.dev0"
    except ImportError:
        __version__ = "0.0.0.dev0"

# Public API
__all__ = ["TeshQuery", "health_check", "introspect", "query", "__version__"]
