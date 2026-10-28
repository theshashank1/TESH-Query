# Production Deployment & Integration Guide

This guide details best practices for deploying TESH-Query as an enterprise analytics service, REST microservice, or background processing pipeline.

---

## 🐳 Docker Deployment

### 1. Production Dockerfile

```dockerfile
# Multi-stage production build
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY teshq/ ./teshq/

# Install core and production drivers
RUN pip install --no-cache-dir ".[data,postgres]"

# Final runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

RUN useradd -m -u 1000 teshquser
USER teshquser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/teshq /usr/local/bin/teshq

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["teshq"]
CMD ["health"]
```

### 2. Docker Compose with Production PostgreSQL

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: analytics_ro
      POSTGRES_PASSWORD: securepassword
      POSTGRES_DB: enterprise_dw
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  teshq-service:
    build: .
    environment:
      DATABASE_URL: "postgresql+asyncpg://analytics_ro:securepassword@db:5432/enterprise_dw"
      GEMINI_API_KEY: "${GEMINI_API_KEY}"
      LLM_PROVIDER: "google"
    depends_on:
      - db
    command: ["health"]

volumes:
  postgres_data:
```

---

## ⚡ FastAPI REST Microservice Integration

Expose TESH-Query via a high-performance REST API:

```python
# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import teshq

app = FastAPI(title="Enterprise Natural Language Query Service")

# Initialize SDK client with connection pooling
client = teshq.TeshQuery(
    db_url="postgresql+asyncpg://user:pass@warehouse:5432/analytics",
    gemini_api_key="your-api-key"
)

class QueryRequest(BaseModel):
    prompt: str
    limit: int = 100

@app.post("/api/v1/query")
async def execute_query(req: QueryRequest):
    try:
        # Non-blocking async execution
        result = client.query_advanced(req.prompt)
        return {
            "sql": result.sql,
            "columns": result.columns,
            "rows": result.paginate(page=1, page_size=req.limit)["rows"],
            "chart_hints": result.to_payload()["chart_hints"],
            "execution_ms": result.execution_time_ms
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/health")
def health():
    return {"status": "healthy"}
```

Run with Uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🛡️ Database Least-Privilege Grants

In production, configure the database user with **strict read-only permissions**:

```sql
-- PostgreSQL example:
CREATE USER teshq_ro WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE analytics TO teshq_ro;
GRANT USAGE ON SCHEMA public TO teshq_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO teshq_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO teshq_ro;

-- Explicitly revoke write permissions:
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, DROP, ALTER ON ALL TABLES IN SCHEMA public FROM teshq_ro;
```

---

## 🩺 Kubernetes Liveness & Readiness Probes

Use `teshq health` for automated container orchestrator probes:

```yaml
livenessProbe:
  exec:
    command:
      - teshq
      - health
  initialDelaySeconds: 10
  periodSeconds: 30
```

---

## 🧭 Next Steps

- **[Configuration & Secrets](10_configuration_and_secrets.md)** — Environment variable configuration.
- **[Troubleshooting & FAQ](14_troubleshooting.md)** — Diagnose common production issues.
- **[Documentation Index](README.md)** — Back to the main documentation hub.
