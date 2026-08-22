<div align="center">

# 🤖 TESH-Query

**Transform natural language into SQL queries and get instant results — No SQL knowledge required.**

[![PyPI version](https://img.shields.io/pypi/v/teshq?color=blue)](https://pypi.org/project/teshq/)
[![Python Support](https://img.shields.io/pypi/pyversions/teshq)](https://pypi.org/project/teshq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/theshashank1/TESH-Query/blob/main/LICENSE)
[![CI/CD](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml/badge.svg)](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Documentation](https://www.notion.so/theshashank1/TESH-Query-20172c79e02080a287bcdff73f694a6b?source=copy_link) · [Report Bug](https://github.com/theshashank1/TESH-Query/issues) · [Request Feature](https://github.com/theshashank1/TESH-Query/discussions)

</div>

---

TESH-Query (Text to Executable SQL Handler) is an AI-powered library and CLI tool that bridges the gap between human language and databases. Powered by **Google Gemini** and **Azure OpenAI**, it seamlessly translates plain English into executable SQL, querying your database, and delivering results instantly.

## ✨ Why TESH-Query?

- **💬 Natural Language Interface** — Talk to your database. No more crafting complex JOINs or nested subqueries.
- **🔌 Unified Database Support** — Natively supports PostgreSQL, MySQL, SQLite, MSSQL, MariaDB, and Oracle.
- **🧠 Intelligent Schema Awareness** — Analyzes your database schema to generate accurate, context-aware SQL.
- **💾 Export Anywhere** — Save query results directly to `CSV`, `Excel`, or local `SQLite` databases.
- **🛡️ Secure & Private** — Secrets are managed locally. SQL is safely validated before execution.
- **📊 Telemetry & Cost Tracking** — Built-in LLM token usage tracking and cost analytics.
- **🧑‍💻 Python SDK** — Integrate NL2SQL directly into your own Python applications.

---

## 🚀 Quick Start

### 1. Installation

TESH-Query requires Python 3.10+. Install it via pip:

```bash
pip install teshq
```

*Note: For specialized databases like PostgreSQL or MySQL, you can install the required drivers natively via `pip install teshq[all]` or `pip install teshq[postgres]`.*

### 2. Configuration

Set up your database connection and AI provider interactively:

```bash
# Setup your database connection
teshq config --db

# Connect your Google Gemini API key
teshq config --gemini
# OR use Azure OpenAI
teshq config --azure
```

### 3. Introspect & Query

```bash
# 1. Analyze your database schema
teshq introspect

# 2. Ask questions in plain English!
teshq query "Show me the top 5 customers by total revenue this year"
```

<br>

<div align="center">
  <img src="https://raw.githubusercontent.com/theshashank1/TESH-Query/main/docs/assets/demo.png" alt="TESH-Query CLI Demo" width="800"/>
  <p><em>Beautiful, responsive terminal UI powered by Rich.</em></p>
</div>

---

## 💻 Programmatic Usage (Python SDK)

Build powerful AI data applications using the TESH-Query SDK.

```python
import teshq

# Initialize with Google Gemini
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@localhost:5432/analytics",
    gemini_api_key="your-api-key"
)

# 1. Introspect the database
schema = client.introspect_database()

# 2. Ask questions directly
results = client.query("Find the average order value by region")

# 3. Access pandas DataFrames or raw data
print(results.dataframe)
print(f"Tokens used: {results.metadata.total_tokens}")

# Need to export the data?
results.to_csv("regional_sales.csv")
```

---

## 🛠️ CLI Features & Commands

TESH-Query comes with a rich suite of CLI tools for developers and data analysts.

| Command | Description |
|---------|-------------|
| `teshq query "<query>"` | Execute a natural language query |
| `teshq query "<q>" --save-csv <path>` | Export query results directly to CSV |
| `teshq introspect` | Refresh local database schema intelligence |
| `teshq config` | View and manage your configuration |
| `teshq analytics` | View AI token usage, costs, and query metrics |
| `teshq health` | Run comprehensive system diagnostics |
| `teshq subscribe` | Subscribe to TESH-Query updates |

> **Pro Tip**: Use the `--verbose` flag with any command to see detailed logs and generated SQL without executing it.

---

## 🏗️ Architecture

TESH-Query is built with performance and security in mind:

1. **Introspection Layer**: Extracts table metadata, foreign keys, and indexes, compressing them into a lightweight schema map.
2. **AI Planning Layer**: Analyzes your natural language request against the schema map to identify necessary tables and relationships.
3. **SQL Generation Layer**: Constructs dialect-specific SQL using advanced LLM prompting.
4. **Validation Layer**: Scans the generated SQL for destructive commands (e.g., `DROP`, `DELETE`, `ALTER`) to prevent accidental data loss.
5. **Execution & UI**: Safely executes the query and renders the output via `Rich` or returns a `pandas` DataFrame.

---

## 📈 Roadmap

### 🚧 In Development (v2.2)
- Enhanced Error Handling & Auto-Recovery
- Query History, Caching, & Bookmarking
- Interactive Query Refinement loop

### 🔮 Future Vision (v3.0+)
- Advanced Data Visualization (Auto-charting)
- Custom User-Defined AI Prompts
- Expandable Plugin Architecture

---

## 🤝 Contributing

We welcome contributions! Whether it's fixing bugs, adding new database dialects, or improving documentation.

1. Clone the repository: `git clone https://github.com/theshashank1/TESH-Query.git`
2. Install development dependencies: `pip install -e ".[dev]"`
3. Run the tests: `pytest tests/unit/`
4. Submit a Pull Request!

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

<div align="center">
  <br>
  <b>Made with ❤️ by <a href="https://github.com/theshashank1">Shashank</a></b><br>
  <i>Passionate about democratizing data access and building intelligent developer tools.</i>
  <br><br>
  
  [![♡ Support Us](https://img.shields.io/badge/♡%20Support%20Us-orange?style=for-the-badge&logo=heart&colour=pink)](https://github.com/sponsors/theshashank1)
</div>
