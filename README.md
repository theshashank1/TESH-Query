<div align="center">

# TESH-Query

**A Python SDK and CLI for converting natural language into SQL queries.**
<!-- 
![TESH-Query Banner](docs/assets/banner.jpg) -->

[![PyPI version](https://img.shields.io/pypi/v/teshq?color=blue)](https://pypi.org/project/teshq/)
[![Python Support](https://img.shields.io/pypi/pyversions/teshq)](https://pypi.org/project/teshq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/theshashank1/TESH-Query/blob/main/LICENSE)
[![CI/CD](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml/badge.svg)](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Documentation](https://www.notion.so/theshashank1/TESH-Query-20172c79e02080a287bcdff73f694a6b?source=copy_link) · [Issue Tracker](https://github.com/theshashank1/TESH-Query/issues) · [Discussions](https://github.com/theshashank1/TESH-Query/discussions)

</div>

---

TESH-Query (Text to Executable SQL Handler) lets you query any relational database using plain English. Powered by **Google Gemini** or **Azure OpenAI**, it analyzes your database schema, generates SQL, validates it for safety, and returns results — all from a single command or a few lines of Python.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Python SDK](#python-sdk)
- [How It Works](#how-it-works)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Natural Language Querying** — Ask questions in plain English, get SQL and results back instantly.
- **Google Gemini & Azure OpenAI** — Choose your preferred LLM provider at configuration time.
- **Broad Database Support** — PostgreSQL, MySQL, SQLite, MSSQL, MariaDB, and Oracle via SQLAlchemy.
- **Safe Execution** — All generated SQL is AST-validated before execution. Destructive commands (`DROP`, `DELETE`, `ALTER`, `TRUNCATE`) are blocked by default.
- **Flexible Exports** — Save results to CSV, Excel (`.xlsx`), or SQLite with a single flag.
- **Dry Run & Explain Modes** — Inspect generated SQL before it touches your database.
- **Python SDK** — Integrate NL-to-SQL into your own applications.
- **Token & Cost Analytics** — Track LLM usage and estimated costs per query.

---

## Installation

Requires Python 3.10 or higher.

```bash
pip install teshq
```

**With database driver extras:**

```bash
# PostgreSQL
pip install "teshq[postgres]"

# MySQL / MariaDB
pip install "teshq[mysql]"

# Microsoft SQL Server
pip install "teshq[mssql]"

# Everything (no system dependencies required)
pip install "teshq[all]"
```

---

## Quick Start

![TESH-Query CLI Demo](docs/assets/demo.svg)

### Step 1 — Configure your database and LLM provider

```bash
# Interactive database setup
teshq config --db

# Set up your LLM provider (choose one)
teshq config --gemini     # Google Gemini
teshq config --azure      # Azure OpenAI
```

All credentials are stored securely at `~/.teshq/` and are transmitted only to the configured provider endpoint when authenticating requests.

### Step 2 — Introspect your database schema

This step analyzes your tables, columns, and relationships. It only needs to be run once, or whenever your schema changes.

```bash
teshq introspect
```

### Step 3 — Start querying

```bash
teshq query "Show me the top 10 customers by total revenue this year"
teshq query "Which products are running low on inventory?"
teshq query "Monthly sales breakdown for Q1 2024"
```

---

## CLI Reference

### `teshq query`

Run a natural language query against your database.

```
teshq query [OPTIONS] "Your question in plain English"
```

| Option | Description |
|--------|-------------|
| `--save-csv <file>` | Save results to a CSV file |
| `--save-excel <file>` | Save results to an Excel (`.xlsx`) file |
| `--save-sqlite <file>` | Save results to a SQLite database |
| `-n, --limit <N>` | Limit the number of rows returned |
| `--dry-run` | Generate and validate SQL but **do not execute** it |
| `--explain` | Print the query plan, selected tables, generated SQL, and execution time |
| `--schema-preview` | Print the compressed schema that will be sent to the LLM, then exit |
| `--full-schema` | Use the full verbose schema for highest accuracy (requires `teshq db introspect --all`) |
| `--verbose` | Write detailed debug logs to `~/.teshq/logs/` |

**Examples:**

```bash
# Basic query
teshq query "Find all users who registered in the last 7 days"

# Inspect generated SQL without running it
teshq query "Total orders by country" --dry-run

# Save output to Excel
teshq query "Monthly revenue trend" --save-excel revenue_report

# Limit results
teshq query "Recent orders" --limit 50
```

### Other Commands

| Command | Description |
|---------|-------------|
| `teshq config` | View current configuration |
| `teshq config --db` | Interactively configure database connection |
| `teshq config --gemini` | Configure Google Gemini API key |
| `teshq config --azure` | Configure Azure OpenAI credentials |
| `teshq introspect` | Refresh local database schema (alias for `teshq db introspect`) |
| `teshq db introspect` | Introspect database schema |
| `teshq health` | Run system diagnostics (DB connectivity, API, configuration) |
| `teshq analytics` | View LLM token usage and estimated query costs |
| `teshq telemetry` | Manage anonymous usage telemetry settings |
| `teshq --version` | Display installed version |

---

## Python SDK

TESH-Query can be used directly in Python applications for building AI-powered data tools.

```python
import teshq

# Connect with Google Gemini
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/mydb",
    gemini_api_key="your-api-key"
)

# Or connect with Azure OpenAI
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/mydb",
    provider="azure",
    azure_api_key="your-azure-key",
    azure_endpoint="https://your-resource.openai.azure.com/",
    azure_deployment="gpt-4o",
)

# Introspect the database schema once
client.introspect_database()

# Ask a natural language question
result = client.query("Show the top 5 customers by lifetime value")

# Access results as a Pandas DataFrame
print(result.dataframe)

# Or get raw rows
print(result.rows)

# Generate SQL without executing it
sql_info = client.generate_sql("Count all active users")
print(sql_info["query"])
```

---

## How It Works

TESH-Query processes every query through a structured pipeline designed for accuracy and safety:

```
User Query (natural language)
        │
        ▼
┌───────────────────┐
│  Schema Retrieval │  Loads your compressed schema from the local cache
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   AI Planning     │  Identifies the relevant tables and joins needed
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  SQL Generation   │  Produces dialect-specific SQL via structured LLM output
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    Validation     │  AST scan: blocks DROP, DELETE, ALTER, TRUNCATE
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    Execution      │  Runs SQL via SQLAlchemy, returns DataFrame or table
└───────────────────┘
```

---

## Contributing

We welcome contributions — bug fixes, new database support, and documentation improvements are all appreciated.

```bash
# 1. Fork and clone the repository
git clone https://github.com/theshashank1/TESH-Query.git
cd TESH-Query

# 2. Install development dependencies
pip install -e ".[dev]"

# 3. Run the test suite before making changes
pytest tests/unit/

# 4. Create a feature branch and submit a Pull Request
git checkout -b feature/your-feature-name
```

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for our code of conduct and contribution process.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built by <a href="https://github.com/theshashank1">Shashank</a> · <a href="https://github.com/theshashank1/TESH-Query/issues">Report a bug</a> · <a href="https://github.com/theshashank1/TESH-Query/discussions">Start a discussion</a></sub>
</div>
