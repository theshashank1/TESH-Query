# Configuration & Secrets Management

TESH-Query utilizes **Pydantic V2 BaseSettings** with a deterministic, layered configuration system. Settings and sensitive secrets are resolved in strict priority order.

---

## 🏔️ The Layered Resolution Priority Chain

When resolving any configuration parameter, TESH-Query queries sources in strict priority order (highest to lowest):

```
1. CLI Flags & Explicit SDK Parameters    (e.g. teshq query --local or TeshQuery(db_url=...))
                     │
                     ▼
2. System Environment Variables          (e.g. export DATABASE_URL="...")
                     │
                     ▼
3. Local Dotenv Secrets                  (~/.teshq/.env)
                     │
                     ▼
4. Non-Secret YAML Configuration         (~/.teshq/config.yaml)
                     │
                     ▼
5. Built-in Production Defaults          (e.g. gemini-2.0-flash-lite, timeout=30s)
```

---

## 🔒 Configuration Categories

### 1. Secrets (Stored in `~/.teshq/.env`)

Sensitive credentials and tokens are stored in the user's home directory with restrictive POSIX file permissions (`0600`):

| Variable | Required For | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | All (if no named DBs) | Canonical database connection URL. |
| `GEMINI_API_KEY` | Google Gemini Provider | Google Gemini API key. |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI Provider | Azure OpenAI service key. |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI Provider | Azure OpenAI resource endpoint URL. |

### 2. General Settings (Stored in `~/.teshq/config.yaml`)

Non-sensitive operational parameters:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `google` | Active LLM provider: `google`, `azure`, or `local`. |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Model name for Google Gemini provider. |
| `AZURE_OPENAI_DEPLOYMENT`| — | Deployment name on Azure OpenAI. |
| `AZURE_OPENAI_API_VERSION`| `2024-02-01` | Azure OpenAI REST API version. |
| `QUERY_TIMEOUT_SECONDS` | `30` | Statement execution timeout in seconds. |
| `MAX_RETRIES` | `3` | Maximum self-healing retry attempts. |
| `SCHEMA_RETRIEVAL_TOP_K`| `5` | Maximum tables selected by TF-IDF retriever. |

---

## 🛠️ Setting Values

### 1. Interactive 30-Second Setup Wizard

```bash
teshq config --wizard
```

Guides you through database connectivity testing and AI provider selection interactively.

### 2. Setting Individual Fields

```bash
teshq config --db          # Prompts for database connection string
teshq config --gemini      # Prompts for Gemini API key
teshq config --azure       # Prompts for Azure endpoint, key, and deployment
teshq config --local       # Prompts for local GGUF model path
```

### 3. Inspecting Active Settings (Credential Masking)

```bash
teshq config --show
```
*All passwords, secrets, and auth tokens are masked with `***`.*

### 4. Running Production Readiness Validation

```bash
teshq config validate
```
Validates database ping, credential validity, pool readiness, and filesystem write access.

---

## 🐳 Production Container Environments (Docker / K8s)

In containerized deployments, avoid interactive configuration by supplying environment variables directly:

```bash
# Docker run
docker run -d \
  -e DATABASE_URL="postgresql://user:pass@postgres.prod:5432/analytics" \
  -e GEMINI_API_KEY="AIzaSy..." \
  -e LLM_PROVIDER="google" \
  -p 8000:8000 \
  my-teshq-service:latest
```

In Kubernetes, inject credentials from a `Secret`:

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: url
  - name: GEMINI_API_KEY
    valueFrom:
      secretKeyRef:
        name: ai-credentials
        key: api-key
```

---

## 🧭 Next Steps

- **[Universal Database Dialects](04_database_dialects.md)** — Format connection URLs for your database.
- **[Security Firewall](06_security_firewall.md)** — Understand credential redaction and AST safety.
- **[Production Deployment](13_production_deployment.md)** — Deploy TESH-Query in production clusters.
