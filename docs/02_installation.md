# Installation & Database Drivers Guide

TESH-Query requires **Python 3.10 or higher**. It is designed with a lightweight core package and modular installation extras so you only install the drivers and computational libraries required for your specific data stack.

---

## 📦 Core Package Installation

The core installation includes SQLite support and the Google Gemini provider out of the box:

```bash
# Using standard pip
pip install teshq

# Or using uv (recommended for ultra-fast resolution)
uv pip install teshq
```

Verify your installation:

```bash
teshq --version
teshq health
```

---

## 🔌 Installation Extras & Driver Bundles

### 1. Database Drivers

Install the exact database connector required for your environment:

| Database | Extra Flag | Underlying Drivers |
| :--- | :--- | :--- |
| **PostgreSQL (Pure Python)** | `pip install "teshq[postgres]"` | `asyncpg` (Works on Python 3.10–3.14+) |
| **PostgreSQL (Binary)** | `pip install "teshq[postgres-binary]"` | `psycopg2-binary` |
| **MySQL / MariaDB** | `pip install "teshq[mysql]"` | `PyMySQL`, `mysql-connector-python` |
| **Microsoft SQL Server** | `pip install "teshq[mssql]"` | `pymssql` |
| **Oracle Database** | `pip install oracledb` | `oracledb` (Thin & Thick modes) |
| **DuckDB (OLAP)** | `pip install duckdb-engine` | `duckdb`, `duckdb-engine` |
| **ClickHouse (OLAP)** | `pip install clickhouse-connect` | `clickhouse-connect` |
| **Snowflake** | `pip install snowflake-sqlalchemy` | `snowflake-connector-python` |
| **Google BigQuery** | `pip install sqlalchemy-bigquery` | `google-cloud-bigquery` |
| **Databricks Spark SQL** | `pip install databricks-sql-connector` | `databricks-sql-connector` |
| **Amazon Redshift** | `pip install sqlalchemy-redshift` | `redshift-connector` |

### 2. High-Performance Modern Analytics

For zero-copy exports and high-speed in-memory vector operations:

```bash
# Polars and Apache Arrow integration
pip install "teshq[data]"

# Machine learning & local OLAP bundle (Polars + Arrow + DuckDB)
pip install "teshq[ml]"
```

### 3. Comprehensive Driver Bundles

```bash
# All standard pure-Python drivers & tools
pip install "teshq[all]"

# Complete enterprise suite (Cloud Warehouses + OLAP + Relational)
pip install "teshq[all-databases]"
```

---

## ⚡ Offline Local Inference (`teshq[local]`)

To run TESH-Query in air-gapped or 100% offline environments without sending data or prompts to external cloud APIs, install the local inference engine powered by `llama.cpp`:

```bash
pip install "teshq[local]"
```

### Hardware Acceleration Flags

To maximize token generation speed using GPU acceleration, compile `llama-cpp-python` with native hardware flags:

#### Apple Silicon (M1 / M2 / M3 / M4 - Metal)

```bash
CMAKE_ARGS="-DGGML_METAL=on" pip install --upgrade --force-reinstall --no-cache-dir llama-cpp-python
```

#### NVIDIA GPU (CUDA)

```bash
CMAKE_ARGS="-DGGML_CUDA=on" pip install --upgrade --force-reinstall --no-cache-dir llama-cpp-python
```

#### CPU Multi-Threading (OpenBLAS / AVX2)

```bash
CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" pip install --upgrade --force-reinstall --no-cache-dir llama-cpp-python
```

Verify your hardware acceleration status:

```bash
teshq local status
```

---

## 🛠️ Development & Editable Installation

To contribute to TESH-Query or run the internal test suite:

```bash
# 1. Clone the repository
git clone https://github.com/theshashank1/TESH-Query.git
cd TESH-Query

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install in editable mode with development dependencies
pip install -e ".[dev]"

# 4. Run the test suite (425+ unit & integration tests)
pytest tests/unit/
```

---

## 🧭 Next Steps

- **[Universal Database Dialects Guide](04_database_dialects.md)** — Connection string formats, compound URLs, and dialect-specific setup.
- **[Configuration & Secrets](10_configuration_and_secrets.md)** — Configure your database credentials and AI providers.
- **[CLI Reference](07_cli_reference.md)** — Start querying from the command line.
