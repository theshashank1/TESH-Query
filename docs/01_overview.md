# TESH-Query — Overview

TESH-Query (TESHQ) is an AI-powered natural-language-to-SQL engine. You describe what data you need in plain English, and TESHQ introspects your database schema, generates safe, parameterised SQL, and returns the results — all from a single CLI command or SDK call.

## Key Features

| Feature | Description |
|---|---|
| **Natural Language → SQL** | Two-stage LLM pipeline (Query Planning → SQL Generation) for accurate, deterministic SQL. |
| **Multi-Provider LLM** | Google Gemini and Azure OpenAI out of the box. |
| **Multi-Database** | PostgreSQL, MySQL, MariaDB, MSSQL, Oracle, Cassandra, SQLite. |
| **Self-Healing Retry** | If the generated SQL fails, the engine re-invokes the LLM with the error message and retries automatically. |
| **Schema Retriever** | TF-IDF vector-similarity retrieval prunes large schemas (100+ tables) down to the most relevant subset before hitting the LLM. |
| **Async SDK** | `TeshQuery.aquery()` and `TeshEngine.aquery()` for non-blocking usage in FastAPI, Celery, and other async frameworks. |
| **Custom Exceptions** | Typed exception hierarchy (`TeshqConfigurationError`, `SQLGenerationError`, `LLMRateLimitError`, …) — never leaks raw stack traces. |
| **Exponential Backoff** | Transient DB errors and LLM rate-limit (HTTP 429) responses are retried with jittered exponential backoff. |
| **Typer CLI** | Rich, interactive command-line interface with progress bars, syntax highlighting, and table output. |
| **Pydantic Settings** | Layered configuration: environment variables → `~/.teshq/.env` → `config.yaml` → defaults. |

## Project Goals

1. **Zero-friction data access** — ask a question, get an answer; no SQL expertise required.
2. **Production resilience** — graceful error handling, retries, and observability built in.
3. **Enterprise extensibility** — plug in your own LLM provider, database driver, or telemetry backend.

## Repository Layout

```
teshq/
├── cli/          # Typer-based CLI commands
├── config/       # Pydantic V2 BaseSettings, YAML loader
├── core/         # Business logic: engine, introspect, retriever, sql_gen, models
├── api.py        # Public SDK interface (TeshQuery class)
├── utils/        # Connection pooling, retry, validation, logging
└── telemetry/    # Privacy-safe usage metrics
```

## Quick Start

```bash
pip install teshq
teshq config --db           # set your DATABASE_URL
teshq config --gemini       # set your Gemini API key
teshq query "show me all users who signed up last week"
```

See [02_installation.md](02_installation.md) for detailed setup instructions.
