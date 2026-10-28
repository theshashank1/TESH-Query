# Troubleshooting & Frequently Asked Questions

This guide provides troubleshooting steps and solutions for common operational and configuration issues encountered when using TESH-Query.

---

## 🛠️ Configuration & Credential Errors

### 1. `Database URL is required`
- **Cause:** No `DATABASE_URL` is set in the environment, `~/.teshq/.env`, or passed to the client.
- **Solution:**
  ```bash
  teshq config --db
  # Or set via environment variable:
  export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
  ```

### 2. `Gemini API key is required`
- **Cause:** Provider is set to `google` (default) but no API key is detected.
- **Solution:**
  ```bash
  teshq config --gemini
  # Or export directly:
  export GEMINI_API_KEY="AIzaSy..."
  ```

### 3. `Azure OpenAI requires: azure_api_key, azure_endpoint, azure_deployment`
- **Cause:** Provider is configured as `azure` but required endpoint parameters are missing.
- **Solution:**
  ```bash
  teshq config --azure
  ```

---

## 🗄️ Database Connectivity Issues

### 1. `connection refused` or `could not connect to server`
- **Check 1:** Ensure your database service is running and accessible (`nc -zv host 5432`).
- **Check 2:** Confirm your firewall or security group allows inbound traffic on the database port.
- **Check 3:** Verify that containerized environments are sharing network namespaces (e.g. Docker bridge or host network).

### 2. `password authentication failed`
- **Solution:** Passwords containing special characters (`@`, `:`, `/`, `#`, `?`) must be URL-encoded in the connection string:
  ```python
  import urllib.parse
  encoded_password = urllib.parse.quote_plus("P@ss#w0rd!")
  # Use encoded_password in your URL
  ```

### 3. `SSL connection required`
- **Solution:** Append the appropriate SSL parameter to your `DATABASE_URL`:
  - PostgreSQL: `postgresql://user:pass@host:5432/db?sslmode=require`
  - MySQL: `mysql+pymysql://user:pass@host:3306/db?ssl={"ssl":{}}`

### 4. `sqlite3.OperationalError: database is locked`
- **Cause:** Multiple concurrent threads trying to write or lock an embedded SQLite file.
- **Solution:** TESH-Query automatically configures `check_same_thread=False` and applies `PRAGMA synchronous = NORMAL`. For heavy concurrent reads and writes, consider using PostgreSQL or DuckDB.

---

## 🛡️ AST Security Firewall Errors

### 1. `Operation 'DROP' is strictly prohibited by the TESH-Query AST Firewall`
- **Cause:** The LLM-generated SQL or user prompt contained a destructive token.
- **Behavior:** This is expected security behavior. TESH-Query prohibits data modification statements in read-only mode.

### 2. `Query references unauthorized table '...'`
- **Cause:** The generated query attempted to access a table not found in the introspected schema graph (e.g. system catalogs like `pg_shadow` or internal metadata).
- **Solution:** If the table exists in your database but was not introspected, refresh the schema cache:
  ```bash
  teshq db clear-cache
  teshq db introspect
  ```

---

## ⚡ Local GGUF & Hardware Acceleration Issues

### 1. `OutOfMemoryError` or Segmentation Fault during local model loading
- **Cause:** The selected model exceeds system physical RAM.
- **Solution:** Download a lighter model:
  ```bash
  # Switch from 7B to 3B or 1.5B
  teshq model download qwen3b-coder
  ```

### 2. Local token generation is slow on Apple Silicon
- **Cause:** `llama-cpp-python` was compiled without Apple Metal support.
- **Solution:** Reinstall with Metal acceleration:
  ```bash
  CMAKE_ARGS="-DGGML_METAL=on" pip install --upgrade --force-reinstall --no-cache-dir llama-cpp-python
  ```

---

## 🤖 LLM Rate Limits & Timeouts

### 1. `HTTP 429 Too Many Requests`
- **Behavior:** TESH-Query automatically retries HTTP 429 responses using jittered exponential backoff (up to 3 attempts).
- **Solution:** If rate limits persist, consider setting a higher-tier API key or throttling batch queries.

### 2. Query Generation Hallucinates Missing Columns
- **Solution:** TESH-Query's closed-loop self-healing will automatically feed the compiler error back to the model. If it persists, ensure you have introspected the database with column metadata:
  ```bash
  teshq db introspect --samples
  ```

---

## 🧭 Next Steps

- **[Documentation Index](README.md)** — Return to the main documentation hub.
- **[Harness Architecture](03_architecture.md)** — Learn about the self-healing engine.
- **[CLI Reference](07_cli_reference.md)** — Learn interactive debugging commands.
