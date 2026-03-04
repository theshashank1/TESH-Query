# Troubleshooting

Common errors and how to fix them.

## Configuration Errors

### `Database URL is required`

**Cause:** No `DATABASE_URL` is set in environment variables, `~/.teshq/.env`, or passed to the SDK.

**Fix:**

```bash
teshq config --db
# Or set the env var directly:
export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
```

### `Gemini API key is required`

**Cause:** Using the Google provider (default) but no API key is configured.

**Fix:**

```bash
teshq config --gemini
# Or:
export GEMINI_API_KEY="AIza..."
```

### `Azure OpenAI requires: azure_api_key, azure_endpoint, azure_deployment`

**Cause:** Provider is set to `azure` but one or more required Azure fields are missing.

**Fix:**

```bash
teshq config --azure
```

Or set all required environment variables:

```bash
export LLM_PROVIDER=azure
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"
```

## Database Errors

### `connection refused` / `could not connect to server`

**Cause:** Database server is unreachable.

**Fix:**
1. Verify the host and port in your `DATABASE_URL`.
2. Ensure the database server is running.
3. Check network/firewall rules.

### `password authentication failed`

**Cause:** Incorrect credentials in the connection string.

**Fix:** Update `DATABASE_URL` with correct username and password:

```bash
teshq config --db
```

### `SSL connection required`

**Cause:** The database requires an SSL connection but the URL doesn't include SSL parameters.

**Fix:** Append `?sslmode=require` (PostgreSQL) or equivalent to your `DATABASE_URL`.

## LLM / API Errors

### Azure `400 BadRequest` — "Invalid JSON schema"

**Cause:** Azure OpenAI's strict JSON Schema mode rejects `Dict[str, Any]` or other flexible types in structured output.

**Fix:** TESH-Query handles this automatically by using plain-text invocation with manual JSON parsing for Azure. If you still see this error:

1. Ensure you are on `teshq >= 2.0.0`.
2. Check that your Azure deployment supports the chat completions API.
3. Try a different model deployment (e.g., `gpt-4o` instead of `gpt-35-turbo`).

### `429 Too Many Requests` / Rate Limit

**Cause:** The LLM provider is rate-limiting your requests.

**Fix:** TESH-Query includes automatic exponential backoff for 429 errors. If you still encounter this:

1. Wait a few minutes and retry.
2. Upgrade your API plan for higher rate limits.
3. Reduce query frequency in batch scripts.

### `Content filter triggered` (Azure)

**Cause:** Azure's content safety filters blocked the request or response.

**Fix:**
1. Rephrase your query to be more specific.
2. Check your Azure content filter policy in the Azure portal.

## SQL Generation Errors

### `no such column` / `column does not exist`

**Cause:** The LLM generated SQL referencing a column that doesn't exist.

**Fix:** This should trigger the self-healing mechanism automatically. If it persists:

1. Run `teshq db introspect` to verify the schema.
2. Be more specific in your query (name exact columns or tables).

### `SQL validation failed`

**Cause:** The generated SQL contains unsafe statements (DROP, TRUNCATE, etc.).

**Fix:** This is a safety mechanism. TESH-Query only allows SELECT queries by default. If you need write operations, use `client.execute_query()` directly.

## Import / Installation Errors

### `ModuleNotFoundError: No module named 'psycopg2'`

**Cause:** PostgreSQL driver not installed.

**Fix:**

```bash
pip install "teshq[postgres]"
# Or for binary wheel:
pip install "teshq[postgres-binary]"
```

### `ModuleNotFoundError: No module named 'langchain_google_genai'`

**Cause:** Core dependency missing.

**Fix:**

```bash
pip install --upgrade teshq
```

## Performance Issues

### Slow query generation

**Possible causes:**
1. Large schema (100+ tables) — the retriever should handle this, but if all tables match, the context may still be large.
2. Slow LLM response time.

**Fix:**
1. Use the `SchemaRetriever` (automatically used in the engine) to reduce schema size.
2. Use `gemini-2.0-flash-lite` (default) for fastest responses.
3. Check your network latency to the LLM provider.

## Getting Help

1. Run `teshq health` to check system status.
2. Enable verbose logging: `teshq query "..." --verbose`
3. Check the log file at `logs/teshq.log` for detailed error traces.
4. Open an issue at [github.com/theshashank1/TESH-Query/issues](https://github.com/theshashank1/TESH-Query/issues).
