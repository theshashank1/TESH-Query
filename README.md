# 🤖 TESH-Query

[![PyPI version](https://img.shields.io/pypi/v/teshq)](https://pypi.org/project/teshq/)
[![Python Support](https://img.shields.io/pypi/pyversions/teshq)](https://pypi.org/project/teshq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/theshashank1/TESH-Query/blob/main/LICENSE)
[![CI/CD](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml/badge.svg)](https://github.com/theshashank1/TESH-Query/actions/workflows/deploy_teshq.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Sponsor](https://img.shields.io/github/sponsors/theshashank1?)](https://github.com/sponsors/theshashank1)

<!-- Add a compelling header image or logo here for visual impact -->
<!-- ![TESH-Query](.idx/icon.png) -->

**Transform natural language into SQL queries and get instant results** — No SQL knowledge required.

TESH-Query (Text to Executable SQL Handler) is an AI-powered CLI tool that bridges the gap between human language and database queries, making data accessible to everyone on your team.

Here is detailed documentation of configuration and usage information, see the [Detailed Documentation](https://www.notion.so/theshashank1/TESH-Query-20172c79e02080a287bcdff73f694a6b?source=copy_link).

---

## ✨ See TESH-Query in Action!

Experience the power and simplicity of TESH-Query with a quick demonstration. See how easily you can get valuable data insights using just natural language.

<!-- Add your GIF or asciinema recording here to visually showcase the tool -->
<!-- ![TESH-Query Demo](link-to-your-demo.gif) -->

---

## 🎯 What TESH-Query Does

Forget writing complex SQL queries. With TESH-Query, you simply ask for the data you need in plain English, and the tool handles the rest.

```bash
# Before: Crafting intricate SQL...
$ psql my_database -c "SELECT products.name, categories.category_name, orders.order_date FROM products JOIN order_items ON products.id = order_items.product_id JOIN orders ON order_items.order_id = orders.id JOIN categories ON products.category_id = categories.id WHERE categories.category_name = 'electronics' AND orders.order_date >= current_date - interval '1 month' ORDER BY orders.order_date DESC;"

# After: Just ask TESH-Query!
$ teshq query "Show me all high-value electronics orders from last month"

# Get instant, formatted results directly in your terminal:
┌────────────┬─────────────────┬───────────┬─────────────┐
│ Order ID   │ Product Name    │ Price     │ Order Date  │
├────────────┼─────────────────┼───────────┼─────────────┤
│ 12847      │ MacBook Pro M3  │ $2,499.00 │ 2025-04-15  │
│ 12923      │ OLED Monitor    │ $899.99   │ 2025-04-18  │
└────────────┴─────────────────┴───────────┴─────────────┘
```

---

## 💡 Why Choose TESH-Query?

Accessing data shouldn't be a bottleneck. TESH-Query empowers your team by making database interaction intuitive and fast.

### Key Benefits:

- **🚀 Democratize Data Access** — Enable everyone, regardless of technical background, to retrieve data independently.
- **⚡ Boost Productivity** — Significantly reduce the time and effort required to get data insights.
- **🛡️ Reduce Errors** — Minimize human errors associated with manual SQL writing.
- **🔍 Focus on Analysis** — Spend more time understanding your data and less time wrestling with query syntax.

---

## ✨ Key Features

- **💬 Intuitive Natural Language Interface** — Seamlessly interact with your database using everyday language.
- **🧠 Intelligent SQL Generation** — Leverage the power of Google's Gemini AI (via Langchain) for accurate and context-aware SQL translation.
- **📊 Direct Data Display** — Get query results presented in clean, readable tables right in your terminal.
- **🔌 Broad Database Compatibility** — Connects natively with PostgreSQL, MySQL, and SQLite databases.
- **🛡️ Schema-Aware Queries** — TESH-Query understands your database structure to generate highly relevant queries.
- **🎨 Modern CLI Experience** — Enjoy a responsive, user-friendly, and visually appealing interface thanks to Typer and Rich.
- **🔒 Secure Credential Management** — Your sensitive database and API credentials are stored securely.
- **⚙️ Customizable Configuration** — Easily set up and manage your database connections, AI models, and other settings.

---

## ▶️ Getting Started: A Quick Walkthrough

Ready to unlock your data? Follow these simple steps:

### 1. Installation

Install TESH-Query easily using pip:

```bash
pip install teshq
```

Confirm successful installation:

```bash
teshq --version
```

### 2. Configuration (One-Time Setup)

Run the interactive configuration wizards to set up your database connection and Gemini API key:

```bash
# Interactive database setup
teshq config --db

# You can also pass a full URL directly
teshq config --db-url postgresql://myuser:********@localhost:5432/mydatabase

# Interactive Gemini API key setup
teshq config --gemini
```

Configuration is stored securely in `~/.teshq/`:

| File | Purpose |
|------|---------|
| `~/.teshq/.teshq.env` | Secrets: `DATABASE_URL`, `GEMINI_API_KEY` (permissions: 0600) |
| `~/.teshq/config.yaml` | Non-secret settings: model name, output paths |
| `~/.teshq/schema/` | Database schema cache (written by `teshq introspect`) |

> **Note**: Secrets are never stored in `config.json` or plain `.env` files in your project directory.

### 3. Database schema Introspection

```bash
# Perform database schema introspection
teshq introspect
```

### 4. Start Querying!

Once configured, you can immediately start asking questions in natural language:

```bash
teshq query "What are the names and email addresses of users who signed up last week?"
teshq query "Show me the total sales amount for each product category in the last quarter."
teshq query "Find orders placed by 'customer_email@example.com'."
```

TESH-Query takes your question, understands your database schema, generates the appropriate SQL, executes it, and displays the results in a formatted table.

> Please be aware that TESH-Query is still under development and may occasionally return incorrect data. Exercise caution and prioritize its use for **data retrieval** rather than **data manipulation**.

---

## 📚 Command Reference

Here's a quick guide to the main TESH-Query commands:

### General

```bash
# Get overall help menu
teshq --help

# Display installed version
teshq --version
```

### Configuration

```bash
# Display current configuration settings
teshq config

# Get help specific to configuration commands
teshq config --help

# Interactively configure database connection
teshq config --config-db

# Interactively configure Google Gemini API key
teshq config --config-gemini
```

### Database

```bash
# Perform database schema introspection
teshq introspect
```

### Querying

```bash
# Get help specific to query commands
teshq query --help

# Execute a natural language query against the database
teshq query "your question here"
```

---

## 💡 Example Queries

See TESH-Query in action with these practical examples across different use cases:

### Business Intelligence

```bash
teshq query "What's our monthly revenue trend for the last 6 months?"
teshq query "Which sales rep has the highest conversion rate?"
teshq query "Show me customer churn rate by region"
```

### Operations

```bash
teshq query "Find orders that haven't shipped in 3+ days"
teshq query "Which products are running low on inventory?"
teshq query "Show me all failed payment transactions today"
```

### Analytics

```bash
teshq query "Average order value by customer segment"
teshq query "Most popular products in each category"
teshq query "Customer lifetime value for premium subscribers"
```

---

## 🏗️ How It Works: Under the Hood

TESH-Query simplifies data access through a robust process:

1.  **Natural Language Input**: Your query is received via the CLI.
2.  **Configuration**: Secure database and AI credentials are loaded.
3.  **Database Connection**: A connection is made to your database using SQLAlchemy.
4.  **Schema Introspection**: TESH-Query inspects your database schema to understand tables, columns, and relationships.
5.  **AI Generation**: Your query and schema context are sent to Google Gemini (via Langchain) to generate optimized SQL.
6.  **SQL Execution**: The generated SQL is executed against your database.
7.  **Result Formatting**: Data is formatted into a clear, tabular output for the terminal.

### Architecture Overview:

The project is structured into key modules:

- **`cli/`**: Handles command-line interface logic and user interaction (Typer).
- **`config/`**: Clean, single-directory configuration system. Manages `~/.teshq/` paths, secrets (`.teshq.env`), and YAML settings.
- **`core/`**: Contains core business logic, including AI interaction, SQL execution, and schema handling.
- **`utils/`**: Provides shared utility functions (configuration façade, database helpers, formatting).
- **`api.py`**: Programmatic SDK (`TeshQuery` class) for integration into applications.

---

## 🔧 Tech Stack

TESH-Query is built using the following technologies:

| Component              | Technology                                                                       |
| ---------------------- | -------------------------------------------------------------------------------- | ------ | --- |
| **Core Language**      | Python 3.9+                                                                      |
| **CLI Framework**      | Typer, Rich                                                                      | \      |
| **Database ORM/Kit**   | SQLAlchemy                                                                       | \      |
| **Database Drivers**   | psycopg2-binary (PostgreSQL), mysql-connector-python (MySQL), sqlite3 (Built-in) | \      |
| **AI/LLM Integration** | Langchain, langchain-google-genai (Google Gemini)                                | \      |
| **Configuration**      | PyYAML, python-dotenv                                                           | \      |
| **Data Display**       | Tabulate                                                                         | \      |
| **Build & Packaging**  | Setuptools, setuptools-scm, Build, Twine                                         | \      |
| **Code Quality**       | Black, isort, Flake8 (enforced via pre-commit)                                   | \      |
| <!--                   | **Testing Framework**                                                            | Pytest | --> |

---

## 📈 Project Status & Roadmap

TESH-Query is under active development with planned future enhancements.

### ✅ Implemented Features (v1.x)

- Robust CLI with Typer.
- Secure, interactive configuration.
- Database connection management (PostgreSQL, MySQL, SQLite).
- Core NLQ -> SQL -> Table pipeline with Gemini AI.
- Dynamic database schema introspection.
- Formatted tabular output.
- Git-based versioning (`setuptools-scm`).
- Automated PyPI publishing (GitHub Actions).
- Pre-commit hooks for code quality.

### 🚧 In Development (v2.x - Near-Term)

- Enhanced Error Handling.
- Query History & Bookmarks.
- Schema Caching for performance.
- More Complex Query Handling.
- Comprehensive Testing Expansion.

### 🔮 Future Vision (v3.x+ - Long-Term)

- Interactive Query Refinement.
- Support for More Databases.
- Basic Data Visualization.
- User-Defined AI Prompts.
- Plugin Architecture.

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

Quick start:

```bash
git clone https://github.com/YOUR_USERNAME/TESH-Query.git
cd TESH-Query
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pytest tests/unit/
```

---

## 🔧 Troubleshooting & Support

Encountering issues? Here's some help:

### Common Issues

- **Connection Problems**: Use `teshq config --db`. Check credentials, host, port, network.
  - Or pass a full URL: `teshq config --db-url postgresql://myuser:password@localhost:5432/mydatabase`
- **Config file location**: All config lives in `~/.teshq/`. Run `teshq config` to view the current state.
- **AI Generation Issues**: Rephrase query, be specific, simplify requests.
- **Permission Errors**: Ensure database user has read access.

### Getting Help

- **Documentation**: `teshq --help` and command-specific help.
- **Bug Reports**: [Open a GitHub Issue](https://github.com/theshashank1/TESH-Query/issues).
- **Feature Requests**: [Start a GitHub Discussion](https://github.com/theshashank1/TESH-Query/discussions).
- **Direct Contact**: Reach out to the author ([@theshashank1](https://github.com/theshashank1)).

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](https://github.com/theshashank1/TESH-Query/blob/main/LICENSE) file.

---

## 🌟 Show Your Support

[![♡ Support Us](https://img.shields.io/badge/♡%20Support%20Us-orange?style=social&logo=heart&colour=pink)](https://github.com/sponsors/theshashank1)

Like TESH-Query? Please consider:

⭐ **Starring the repo on GitHub**
🐦 **Sharing on social media**
🗣️ **Telling your colleagues**
🤝 **Contributing to the project**

Your support is greatly appreciated!

---

**Made with ❤️ by [Shashank](https://github.com/theshashank1)**

_Passionate about democratizing data access and building intelligent developer tools._
