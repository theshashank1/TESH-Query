# CLI Reference & Interactive Terminal

TESH-Query provides a comprehensive Typer-based Command Line Interface (CLI) designed for both ad-hoc interactive exploration and scriptable data workflows.

---

## ⚡ Quick Reference

```bash
teshq chat                         # Launch the interactive terminal REPL
teshq query "..."                  # Run a single natural language query
teshq query -c warehouse "..."     # Query a specific registered connection
teshq query "..." --dry-run        # Generate & validate SQL without running
teshq db connection list           # List registered connections
teshq db introspect                # Scan and cache database schema
teshq config --wizard              # 30-second interactive setup wizard
teshq health                       # End-to-end system diagnostic check
```

---

## 🖥️ Interactive Terminal (`teshq chat`)

The interactive terminal (alias: `teshq repl`) provides an ambient conversational interface with a live Heads-Up Display (HUD) and 6-stage cognitive execution tracker.

```bash
teshq chat
```

### Ambient HUD & Stage Tracker
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TESHQ HUD  •  PostgreSQL Connected (14ms)  •  Gemini 2.0  •  42 Tables    │
├─────────────────────────────────────────────────────────────────────────────┤
│  › top 10 products by revenue in 2024                                       │
│  [1/6] Schema Context  ✓ Top-4 tables pruned via TF-IDF                     │
│  [2/6] Query Planning  ✓ Identified INNER JOIN orders ON products.id        │
│  [3/6] SQL Synthesis   ✓ Compiled PostgreSQL dialect with :named params     │
│  [4/6] AST Firewall    ✓ Passed (Read-only SELECT, 0 destructive tokens)    │
│  [5/6] DB Execution    ✓ 10 rows returned in 18ms                           │
│  [6/6] Output Delivery ✓ Rendered tabular view                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Slash Commands Reference

| Command | Action | Description |
| :--- | :--- | :--- |
| `/help` or `/?` | Command Palette | Opens interactive list of all slash commands. |
| `/tables` or `/schema` | Schema Tree | Prints an ASCII tree of all introspected tables and columns. |
| `/sql` | Inspect SQL | Displays the exact SQL and bound parameters from the last query. |
| `/explain` | AI Explanation | Explains the underlying joins, business logic, and filters. |
| `/export csv [file]` | Export CSV | Exports the current result set to a CSV file. |
| `/export excel [file]` | Export Excel | Exports the current result set to an `.xlsx` workbook. |
| `/export sqlite [file]` | Export SQLite | Writes results directly into a local SQLite table. |
| `/copy sql` | Clipboard SQL | Copies the last generated SQL statement to the system clipboard. |
| `/copy results` | Clipboard Table | Copies formatted tabular results to the system clipboard. |
| `/model [name]` | Hot-Swap Model | Swaps active AI model (`google`, `azure`, `local`) live in session. |
| `/clear` or `/cls` | Clear Screen | Clears the terminal screen and restores the HUD. |
| `/history` | Query History | Displays previously executed queries in this session. |
| `exit` or `quit` | Exit Session | Terminates the REPL and displays cumulative session statistics. |

---

## 🔍 `teshq query`

Translate a natural language question into SQL and execute it.

```bash
teshq query [OPTIONS] [REQUEST]
```

### Available Options & Flags

| Flag | Description |
| :--- | :--- |
| `-c, --connection <NAME>` | Target a registered named database connection. |
| `--dry-run` | Generate and validate SQL, but **do not execute** it. |
| `-i, --confirm` | Prompt for interactive review and approval before running. |
| `--explain` | Print execution plan, selected tables, SQL, and timing breakdown. |
| `-n, --limit <N>` | Append `LIMIT N` to the generated query. |
| `--save-csv <FILE>` | Save query results to a CSV file. |
| `--save-excel <FILE>` | Save query results to an Excel spreadsheet (`.xlsx`). |
| `--save-sqlite <FILE>` | Save query results to a SQLite database table. |
| `--schema-preview` | Print the exact TF-IDF compressed schema sent to the LLM and exit. |
| `--full-schema` | Bypass TF-IDF pruner and send the full database schema. |
| `--local` | Force local offline GGUF model inference for this query. |
| `--cloud` | Force cloud LLM provider (Gemini or Azure) for this query. |
| `--verbose` | Output verbose logs and execution tracing. |

### Practical Examples

```bash
# Query a registered database connection
teshq query -c warehouse "Monthly recurring revenue by subscription tier"

# Dry run with execution plan explanation
teshq query "Which customers have overdue invoices?" --dry-run --explain

# Save query results directly to Excel
teshq query "Top 50 sales reps by closed deal volume" --save-excel sales_q3.xlsx

# Preview the exact schema slice chosen by the TF-IDF retriever
teshq query "Count refunded orders by region" --schema-preview
```

---

## 🗄️ Database Commands (`teshq db`)

Manage schemas, caching, and named database connections.

```bash
# Named connection management
teshq db connection add ecommerce "sqlite:///testing/databases/ecommerce.sqlite"
teshq db connection list
teshq db connection test ecommerce
teshq db connection default ecommerce
teshq db connection remove ecommerce

# Schema operations
teshq db introspect                 # Introspect live database schema
teshq db introspect --save          # Save schema graph to ~/.teshq/schemas/
teshq db introspect --samples       # Include statistical data samples
teshq db explore                    # Launch interactive visual schema explorer
teshq db show-schema                # Print cached database schema
teshq db clear-cache                # Reset local schema cache
```

---

## ⚙️ Configuration Commands (`teshq config`)

Manage credentials, endpoints, and deployment settings.

```bash
teshq config --wizard               # Interactive 30-second setup wizard
teshq config --db                   # Configure database connection URL
teshq config --gemini               # Configure Google Gemini API key
teshq config --azure                # Configure Azure OpenAI credentials
teshq config --local                # Configure local GGUF model path
teshq config --show                 # View current configuration (secrets masked)
teshq config validate               # Run production readiness validation
```

---

## 🩺 System Diagnostics (`teshq health`)

Runs end-to-end connectivity, credential, and latency checks across all configured components:

```bash
teshq health
```

---

## 🧭 Next Steps

- **[Python SDK Guide](08_python_sdk.md)** — Use TESH-Query programmatically in Python applications.
- **[Offline Local Inference](09_offline_local_inference.md)** — Run local GGUF models via `llama.cpp`.
- **[Configuration & Secrets](10_configuration_and_secrets.md)** — Detailed credential management guide.
