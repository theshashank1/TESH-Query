<div align="center">

# TESH-Query

**A Python SDK and CLI for deterministic Natural Language to SQL generation.**

[![PyPI version](https://img.shields.io/pypi/v/teshq?color=blue)](https://pypi.org/project/teshq/)
[![Python Support](https://img.shields.io/pypi/pyversions/teshq)](https://pypi.org/project/teshq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/theshashank1/TESH-Query/blob/main/LICENSE)
[![CI/CD](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml/badge.svg)](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Documentation](https://www.notion.so/theshashank1/TESH-Query-20172c79e02080a287bcdff73f694a6b?source=copy_link) · [Issue Tracker](https://github.com/theshashank1/TESH-Query/issues) · [Discussions](https://github.com/theshashank1/TESH-Query/discussions)

</div>

---

TESH-Query (Text to Executable SQL Handler) is a production-grade library that bridges natural language and relational databases. By leveraging Google Gemini or Azure OpenAI, it safely translates plain English into executable SQL, querying your database, and delivering results instantly as a Pandas DataFrame or via the CLI.

## Key Features

- **Programmatic SDK**: Integrate NL2SQL directly into Python applications via a clean API.
- **Unified Database Support**: Natively connects to PostgreSQL, MySQL, SQLite, MSSQL, MariaDB, and Oracle.
- **Intelligent Schema Awareness**: Compresses and analyzes database schemas locally to generate accurate, context-aware SQL.
- **Secure Execution**: Validates generated SQL ASTs to block destructive commands (`DROP`, `DELETE`, `ALTER`).
- **Flexible Exporting**: Save query results natively to CSV, Excel, or SQLite.
- **Observability**: Built-in LLM token usage tracking and cost analytics.

---

## Installation

TESH-Query requires Python 3.10 or higher. Install the core package via pip:

```bash
pip install teshq
```

*Note: For specialized databases like PostgreSQL or MySQL, install the required drivers natively via `pip install teshq[all]` or `pip install teshq[postgres]`.*

---

## Programmatic Usage (Python SDK)

TESH-Query provides a robust SDK for developers building AI-driven data applications.

```python
import teshq

# Initialize the client (Supports Google Gemini or Azure OpenAI)
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/analytics",
    gemini_api_key="your-api-key"
)

# 1. Introspect the database schema (caches locally)
schema = client.introspect_database()

# 2. Execute a natural language query
results = client.query("Find the average order value by region")

# 3. Access data via Pandas DataFrame
df = results.dataframe
print(df.head())

# 4. Access telemetry metadata
print(f"Tokens consumed: {results.metadata.total_tokens}")

# Export data directly to disk
results.to_csv("regional_sales.csv")
```

---

## CLI Usage

TESH-Query includes a comprehensive CLI for data analysts and database administrators.

### Configuration

Set up your database connection and AI provider interactively:

```bash
# Setup your database connection
teshq config --db

# Configure LLM provider
teshq config --gemini
# Or configure Azure OpenAI
teshq config --azure
```

### Common Commands

| Command | Description |
|---------|-------------|
| `teshq query "<query>"` | Execute a natural language query |
| `teshq query "<q>" --save-csv <path>` | Export query results directly to a CSV file |
| `teshq introspect` | Refresh local database schema intelligence |
| `teshq config` | View and manage your configuration |
| `teshq analytics` | View AI token usage, costs, and query metrics |
| `teshq health` | Run comprehensive system diagnostics and connectivity checks |

> **Note**: Use the `--verbose` flag with any command to stream internal logs and inspect the generated SQL payload before execution.

---

## Architecture

TESH-Query is designed for deterministic execution and security:

1. **Introspection Layer**: Extracts table metadata, foreign keys, and indexes, compressing them into a token-efficient schema map.
2. **AI Planning Layer**: Analyzes natural language against the schema map to identify required tables and relationships.
3. **SQL Generation Layer**: Constructs dialect-specific SQL using structured LLM outputs.
4. **Validation Layer**: Scans the generated SQL for destructive commands to prevent accidental data loss.
5. **Execution Layer**: Safely routes the query through an optimized SQLAlchemy connection pool and returns a structured payload.

---

## Contributing

We welcome contributions to TESH-Query, including bug fixes, new database dialects, and documentation improvements.

1. Clone the repository: `git clone https://github.com/theshashank1/TESH-Query.git`
2. Install development dependencies: `pip install -e ".[dev]"`
3. Run the test suite: `pytest tests/unit/`

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for full contribution guidelines.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
