# TESH-Query Documentation Hub

Welcome to the official documentation for **TESH-Query (TESHQ)** — the autonomous natural-language-to-SQL compiler, AST security firewall, and multi-database execution harness.

---

## 🗺️ Documentation Directory

| Document | Description | Target Audience |
| :--- | :--- | :--- |
| **[01. Overview](01_overview.md)** | Mission, core capabilities, cognitive pipeline summary, and key differentiators. | All Users |
| **[02. Installation & Drivers](02_installation.md)** | Package installation, driver bundles (`postgres`, `mysql`, `mssql`, `data`, `local`, `all-databases`), and GPU acceleration. | Developers, DevOps |
| **[03. Harness Architecture](03_architecture.md)** | Deep-dive into the 6-stage cognitive execution pipeline, SchemaGraph, and TF-IDF pruner. | Architects, Engineers |
| **[04. Universal Database Dialects](04_database_dialects.md)** | Comprehensive guide to all SQLAlchemy-supported databases: Cloud Warehouses, OLAP, Relational, compound URLs, and views. | DBAs, Data Engineers |
| **[05. Multi-DB Federation](05_multi_database_federation.md)** | Named database connections, credential masking, parallel subqueries via thread pools, and vectorized DataFrame joins. | Data Engineers, Architects |
| **[06. AST Security Firewall](06_security_firewall.md)** | Abstract Syntax Tree parsing, read-only enforcement, destructive token blocking, parameter binding, and credential redaction. | Security Engineers, DBAs |
| **[07. CLI Reference & Terminal](07_cli_reference.md)** | Complete CLI reference: `teshq chat` REPL, HUD, slash commands, query flags (`--dry-run`, `--explain`, `--save-*`), and db commands. | Analysts, Developers |
| **[08. Python SDK & Modern Analytics](08_python_sdk.md)** | Zero-copy Polars, Apache Arrow, Pandas, multi-turn `TeshChatSession`, async execution, streaming, and BYOE engine pooling. | Data Scientists, Developers |
| **[09. Offline & Air-Gapped Mode](09_offline_local_inference.md)** | 100% offline local inference via GGUF models (`llama.cpp`), CUDA/Metal acceleration, and GBNF grammar constraints. | Enterprise, Security |
| **[10. Configuration & Secrets](10_configuration_and_secrets.md)** | Pydantic V2 layered configuration priority chain, credential masking, `.env`, and YAML configurations. | DevOps, SysAdmins |
| **[11. Self-Healing & Resilience](11_self_healing_and_resilience.md)** | Closed-loop syntax recovery, compiler error re-prompting, jittered exponential backoff, and exception hierarchy. | Backend Engineers |
| **[12. Testing & E-Commerce Fixture](12_testing_and_benchmarks.md)** | Amazon-scale synthetic database fixture (45 tables, 1.12M rows), financial invariant verification, and benchmarks. | QA, Benchmarkers |
| **[13. Production Deployment](13_production_deployment.md)** | Production deployment blueprints: Docker, Docker Compose, FastAPI microservices, and Celery background workers. | DevOps, Platform Engineers |
| **[14. Troubleshooting & FAQ](14_troubleshooting.md)** | Common errors, database connectivity issues, driver compilation, LLM rate limits, and debugging tips. | All Users |

---

## 🚀 Navigation by Persona

### For Data Analysts & Business Users
1. Start with the **[Overview](01_overview.md)** to understand how natural language is converted to SQL.
2. Read the **[CLI Reference & Interactive Terminal](07_cli_reference.md)** to learn how to use `teshq chat`, run slash commands (`/tables`, `/copy`, `/explain`), and export data to CSV/Excel/SQLite.
3. Review **[Universal Database Dialects](04_database_dialects.md)** to verify your database connection strings.

### For Data Engineers & Python Developers
1. Follow the **[Installation & Driver Guide](02_installation.md)** to install drivers for your database stack.
2. Explore the **[Python SDK & Modern Analytics](08_python_sdk.md)** for native zero-copy querying with **Polars**, **Apache Arrow**, and **Pandas**.
3. Learn how to configure named multi-database environments and run cross-database queries in **[Multi-Database Federation](05_multi_database_federation.md)**.

### For Security, Platform & Database Administrators
1. Review the **[AST Security Firewall](06_security_firewall.md)** to understand AST token inspection, read-only guarantees, and credential sanitization.
2. Read **[Configuration & Secrets](10_configuration_and_secrets.md)** for secure key management and environment variable priority.
3. Inspect **[Production Deployment](13_production_deployment.md)** for Docker containerization and background worker orchestration.

---

## ⚡ Quick Links & Cheatsheet

```bash
# 1. Start the interactive chat terminal
teshq chat

# 2. Run a one-off query with a limit
teshq query "top 10 customers by spend" -n 10

# 3. Target a specific registered connection
teshq query -c warehouse "daily active users for last 30 days"

# 4. Dry-run without executing SQL
teshq query "churn rate by plan tier" --dry-run

# 5. Run health diagnostics
teshq health
```

---

[← Return to Repository README](../README.md)
