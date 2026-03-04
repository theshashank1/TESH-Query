# Self-Healing SQL Pipeline

TESH-Query includes a self-healing mechanism that automatically recovers from SQL execution failures. When a generated query fails against the database, the engine re-invokes the LLM with the error message and retries — without any user intervention.

## How It Works

```
User Query
    │
    ▼
┌──────────────────────────────────┐
│  Stage 1: Query Planning         │
│  (QueryPlanner → QueryPlan)      │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Stage 2: SQL Generation         │
│  (SQLGenerator → SQLQuery)       │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Validate + Normalise SQL        │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Execute SQL                     │
│                                  │
│  ┌───────────┐    ┌───────────┐  │
│  │  Success   │    │  Failure  │  │
│  └─────┬─────┘    └─────┬─────┘  │
│        │                │         │
│        ▼                ▼         │
│   Return rows     ┌──────────┐   │
│                    │ Transient│   │
│                    │ DB Error?│   │
│                    └──┬───┬──┘   │
│               yes ◄───┘   └──► no│
│                │              │   │
│           Retry with      Capture │
│           Exp. Backoff    Error   │
│           (up to 3x)     Message  │
│                              │    │
│                              ▼    │
│                    ┌────────────┐ │
│                    │ Re-invoke  │ │
│                    │ Stage 2    │ │
│                    │ with       │ │
│                    │ error_hint │ │
│                    └──────┬─────┘ │
│                           │       │
│                           ▼       │
│                    ┌────────────┐ │
│                    │ Execute    │ │
│                    │ healed SQL │ │
│                    └──┬────┬───┘ │
│               success │    │fail  │
│                       ▼    ▼      │
│                 Return  Raise     │
│                 rows    SelfHeal- │
│                         Exhausted │
└──────────────────────────────────┘
```

## Step-by-Step Breakdown

### 1. Initial Execution Attempt

The engine executes the generated SQL against the database using the connection pool.

### 2. Transient Error Detection

If the execution fails with a **transient** error (connection reset, timeout, OS-level network failure), the engine retries with **exponential backoff**:

- Up to 3 retry attempts
- Base delay: 0.5 seconds, doubling each attempt
- Maximum delay capped at 8 seconds
- Jitter applied to prevent thundering herd

### 3. Self-Healing Regeneration

If the error is **not transient** (e.g., invalid column name, syntax error), the engine re-invokes the SQL Generator (Stage 2) with the original query plan plus an `error_hint` containing the database error message:

```
The previous SQL attempt raised the following error:
  (sqlite3.OperationalError) no such column: foo
Please fix the SQL to avoid this error.
```

The LLM sees the error and generates corrected SQL, which is then validated, normalised, and executed.

### 4. LLM Rate-Limit Handling

During self-healing regeneration, if the LLM returns HTTP 429 (rate limit), the engine backs off with exponential delay:

- Up to 3 attempts
- Respects the `retry-after` header from the LLM provider when available
- Falls back to 2 → 4 → 8 second delays

### 5. Exhaustion

If the self-healing retry also fails (bad SQL again, or LLM unavailable), a `SelfHealingExhaustedError` is raised with full context about both the original and retry failures.

## Exception Hierarchy

All errors are categorised through the custom exception hierarchy:

| Exception | When |
|---|---|
| `TeshqConfigurationError` | Missing API key, invalid DB URL |
| `SchemaIntrospectionError` | Cannot read schema from database |
| `SQLGenerationError` | LLM fails to produce valid SQL |
| `SQLValidationError` | Generated SQL fails safety checks |
| `ExecutionTimeoutError` | Query exceeds timeout |
| `DatabaseConnectionError` | Cannot connect to database |
| `LLMRateLimitError` | LLM provider returns HTTP 429 |
| `SelfHealingExhaustedError` | Self-healing retry loop exhausted |

## Configuration

The retry behaviour is built into `TeshEngine._execute_with_retry()` and is not currently user-configurable. The defaults are tuned for production workloads:

| Parameter | Value |
|---|---|
| DB transient retries | 3 |
| DB base delay | 0.5 s |
| DB max delay | 8.0 s |
| LLM rate-limit retries | 3 |
| LLM base delay | 2.0 s |
| Self-healing attempts | 1 (re-generate + re-execute) |
