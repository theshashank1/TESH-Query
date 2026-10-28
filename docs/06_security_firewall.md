# AST Security Firewall & Safety Harness

The primary danger of LLM-generated SQL is the execution of unconstrained, destructive, or malicious operations against production databases. TESH-Query implements a multi-tier **AST Security Firewall** (`teshq/core/sql_validator.py`) that inspects queries prior to compilation and execution.

---

## 🛡️ Threat Model & Defense In Depth

| Threat Vector | Attack / Failure Scenario | TESH-Query Defense |
| :--- | :--- | :--- |
| **Destructive Commands** | LLM hallucinates `DROP TABLE users` or `TRUNCATE orders`. | **Hard-blocked** at AST level before execution. |
| **Catastrophic Updates** | `DELETE FROM customers` without a `WHERE` clause. | **Blocked** unless an explicit WHERE clause is detected. |
| **SQL Injection** | Attacker injects malicious SQL into natural language prompt (`' OR 1=1; DROP TABLE...`). | **Parameter binding (`:named`)** + AST multi-statement prohibition. |
| **Schema Exfiltration** | Attacker asks LLM to query system catalogs (`pg_shadow`, `sys.tables`). | **Schema Boundary Whitelisting** flags tables outside introspected schema. |
| **Credential Leakage** | Database error messages leak passwords, hostnames, or auth tokens. | **Automatic Redaction Engine (`***`)** masks credentials in logs and outputs. |

---

## 🔬 Why AST Parsing Instead of Regex?

Regular expressions are fundamentally incapable of securing SQL queries because:
1. **Comment Obfuscation:** Attackers can bypass regex using SQL comments (e.g. `DR/**/OP TABLE`).
2. **Quoted Literals:** A benign string matching a keyword (e.g. `WHERE status = 'drop'`) triggers false positives in regex.
3. **Nested & Dynamic CTEs:** Complex queries with multiple subqueries require structural parsing to identify the true root expression.

TESH-Query utilizes full **Abstract Syntax Tree (AST)** parsing powered by `sqlglot` to inspect query semantics structurally.

---

## 🚫 Hard-Blocked Operations

The following statements are unconditionally rejected with a `SQLValidationError`:

```sql
-- All of the following operations are rejected by the AST Firewall:
DROP TABLE users;
TRUNCATE TABLE transactions;
ALTER TABLE accounts ADD COLUMN leaked TEXT;
CREATE TABLE backdoor (id INT);
GRANT ALL PRIVILEGES ON DATABASE prod TO anonymous;
REVOKE SELECT ON ALL TABLES FROM app_user;
REPLACE INTO configuration VALUES ('malicious');
```

When an unauthorized statement is detected:
```
[SQLValidationError] Operation 'DROP' is strictly prohibited by the TESH-Query AST Firewall.
```

---

## 🔒 Read-Only Enforcement & CTEs

By default, TESH-Query operates in strict **Read-Only Mode**:
- Root expressions must evaluate to `SELECT` statements or `WITH ... SELECT` Common Table Expressions (CTEs).
- Multi-statement execution (e.g. `SELECT 1; DROP TABLE x;`) is explicitly prohibited.

---

## ⚠️ Unconstrained UPDATE & DELETE Protection

In environments where update operations are explicitly enabled, the firewall enforces mandatory constraint checks:

```python
# Permitted (contains explicit WHERE clause constraint):
DELETE FROM cart_items WHERE session_id = 'abc-123';

# Blocked by Firewall (unconstrained bulk deletion):
DELETE FROM cart_items;
# -> Raises SQLValidationError: "DELETE statement missing mandatory WHERE clause."
```

---

## 📋 Schema Boundary Whitelisting

When introspecting a database, TESH-Query constructs a whitelist of known tables. If an LLM-generated query attempts to access tables outside this boundary (e.g. attempting to read internal system tables or schemas):

```python
is_valid, reason = validator.validate_query(
    sql="SELECT * FROM pg_catalog.pg_shadow;",
    allowed_tables=["orders", "products", "customers"]
)
# is_valid -> False
# reason -> "Query references unauthorized table 'pg_shadow'."
```

---

## 🔐 Bound Parameters & SQL Injection Resistance

TESH-Query compiles queries using parameterized bindings (`:named_param`):
```sql
-- Raw literal values are replaced with bound parameters:
SELECT * FROM orders WHERE customer_id = :customer_id AND total_amount > :min_amount;
```
This guarantees that user-provided input strings cannot break out of SQL literals or alter the query syntax tree.

---

## 🧭 Next Steps

- **[CLI Reference Guide](07_cli_reference.md)** — Learn how to inspect queries using `--dry-run` and `--explain`.
- **[Python SDK Guide](08_python_sdk.md)** — Integrate secure querying into data pipelines.
- **[Configuration & Secrets](10_configuration_and_secrets.md)** — Manage environment variables and credential security.
