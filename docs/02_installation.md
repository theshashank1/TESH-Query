# Installation

## Prerequisites

- Python 3.10 or newer
- A supported database (PostgreSQL, MySQL, SQLite, etc.)
- An API key for Google Gemini **or** Azure OpenAI

## Install with pip

```bash
pip install teshq
```

### Optional database drivers

SQLite works out of the box. For other databases install the appropriate extra:

```bash
# PostgreSQL (pure-Python, recommended)
pip install "teshq[postgres]"

# PostgreSQL (binary wheel — Python ≤ 3.12)
pip install "teshq[postgres-binary]"

# MySQL
pip install "teshq[mysql]"

# Microsoft SQL Server
pip install "teshq[mssql]"

# All drivers that don't need system libs
pip install "teshq[all]"
```

### Development install

```bash
pip install "teshq[dev]"
```

## Install with UV (recommended for speed)

```bash
uv pip install teshq
# or with extras
uv pip install "teshq[postgres,dev]"
```

## Authentication Setup

### Google Gemini (default provider)

```bash
# Interactive prompt
teshq config --gemini

# Or set the environment variable directly
export GEMINI_API_KEY="your-api-key"
```

### Azure OpenAI

```bash
# Interactive prompt
teshq config --azure

# Or set environment variables
export LLM_PROVIDER=azure
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"
export AZURE_OPENAI_API_VERSION="2024-02-01"
```

### Database URL

```bash
teshq config --db

# Or set directly
export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
```

## Verify Installation

```bash
teshq --version
teshq health          # checks DB connectivity and LLM availability
```

## Configuration File Locations

| File | Purpose |
|---|---|
| `~/.teshq/.env` | Secrets (API keys, DATABASE_URL) |
| `~/.teshq/config.yaml` | Non-secret settings (model name, provider) |

See [04_configuration.md](04_configuration.md) for the full priority chain.
