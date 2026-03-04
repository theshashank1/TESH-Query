# CLI Usage Guide

TESH-Query ships a rich Typer-based CLI. After installation, all commands are available under the `teshq` entry point.

## Quick Reference

```bash
teshq --help               # list all commands
teshq --version            # show version
teshq query "..."          # natural-language query
teshq db introspect        # introspect database schema
teshq config --show        # show current configuration
teshq health               # system health check
```

## `teshq query`

Convert a natural-language question into SQL, execute it, and display results.

```bash
# Basic query
teshq query "show me all users who registered last month"

# Dry run — generate SQL without executing
teshq query "count orders by status" --dry-run

# Save results to CSV
teshq query "top 10 customers by revenue" --save results.csv

# Choose output format
teshq query "list products" --format json
teshq query "list products" --format table   # default
```

### Options

| Flag | Description |
|---|---|
| `--dry-run` | Generate and display SQL without executing |
| `--save PATH` | Save results to a CSV or Excel file |
| `--format` | Output format: `table` (default), `json`, `csv` |
| `--verbose` | Show detailed timing and token usage |

## `teshq db`

Database inspection commands.

```bash
# Full schema introspection
teshq db introspect

# Save schema to files
teshq db introspect --save

# Include sample data rows
teshq db introspect --samples
```

## `teshq config`

Manage configuration interactively.

```bash
# Set database URL
teshq config --db

# Set Google Gemini credentials
teshq config --gemini

# Set Azure OpenAI credentials
teshq config --azure

# Display current configuration (secrets are masked)
teshq config --show
```

## `teshq health`

Run system health checks — verifies database connectivity, LLM availability, and configuration completeness.

```bash
teshq health
```

Example output:

```
✅ Database: connected (PostgreSQL 15.4)
✅ LLM Provider: google (gemini-2.0-flash-lite)
✅ Configuration: complete
```

## Environment Variables

You can skip interactive prompts by setting environment variables before running any command:

```bash
export DATABASE_URL="sqlite:///app.db"
export GEMINI_API_KEY="AIza..."
teshq query "show tables"
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error (invalid config, SQL failure, etc.) |
| `2` | Invalid CLI arguments |
