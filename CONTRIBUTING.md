# Contributing to TESH-Query

## Quick Setup (using `uv` — recommended)

```powershell
# 1. Clone the repo
git clone https://github.com/theshashank1/TESH-Query.git
cd TESH-Query

# 2. Install the project + dev dependencies (no PostgreSQL system packages needed)
uv sync --extra dev

# 3. Run the CLI directly
python -m teshq.cli.main --help

# 4. Run tests
python -m pytest tests/ -v
```

> **No PostgreSQL installed?** That's fine. The core package no longer requires `pg_config`.
> PostgreSQL support is an optional extra you can add when needed (see below).

---

## PostgreSQL Support (optional)

| Extra | Driver | Requires system libs? |
|-------|--------|-----------------------|
| `postgres` | `asyncpg` (pure Python) | ❌ No |
| `postgres-binary` | `psycopg2-binary` (pre-built wheel) | ❌ No (Python 3.9–3.12 only) |

```powershell
# Pure-Python async driver (works on all Python versions)
uv sync --extra dev --extra postgres

# Pre-built psycopg2 binary (Python 3.9–3.12 only)
uv sync --extra dev --extra postgres-binary
```

---

## Database Driver Extras

| Extra | Databases | Requires system libs? |
|-------|-----------|----------------------|
| `mysql` | MySQL, MariaDB | ❌ No |
| `mssql` | SQL Server | ❌ No |
| `oracle` | Oracle | ⚠️ Yes (Oracle Instant Client) |
| `export` | Excel export | ❌ No |

```powershell
# Example: dev + MySQL + Excel export
uv sync --extra dev --extra mysql --extra export
```

---

## Running the CLI from Source

```powershell
# No install needed — runs from your working directory
python -m teshq.cli.main --help
python -m teshq.cli.main config --azure
python -m teshq.cli.main health
```

---

## Running Tests

```powershell
# All tests
python -m pytest tests/ -v

# Unit tests only (fast, no DB required)
python -m pytest tests/unit/ -v

# With coverage
python -m pytest tests/ --cov=teshq --cov-report=term-missing
```

---

## Common Issues

### `psycopg2-binary` build error (`pg_config not found`)
The package is no longer a required dependency. Run:
```powershell
uv sync --extra dev
```
This skips psycopg2 entirely. Add `--extra postgres` if you specifically need PostgreSQL.

### `uv sync` still tries to build psycopg2
The `[tool.uv] no-build-package` list in `pyproject.toml` instructs uv to only use pre-built wheels. If you see a build attempt, regenerate the lockfile:
```powershell
uv lock --upgrade
uv sync --extra dev
```

### Python 3.14+ compatibility
Some dependencies (e.g. pydantic v1 shim via langchain-core) show warnings on Python 3.14. These are upstream issues being tracked. Use Python 3.11 or 3.12 for the smoothest experience.

---

## Pre-commit Hooks

```powershell
uv run pre-commit install
uv run pre-commit run --all-files
```

---

## Project Structure

```
teshq/
├── cli/          # Typer CLI commands (main.py, config.py, query.py, …)
├── config/       # Settings, secrets, paths
├── core/         # SQL generation, introspection, validation
├── telemetry/    # Event tracking, analytics
├── subscriptions/# Subscription state machine
└── utils/        # Shared utilities (logging, health, save, ui)
tests/
├── unit/         # Fast, no DB required
└── integration/  # Require a live database or config
scripts/          # bump_version.py, etc.
```
