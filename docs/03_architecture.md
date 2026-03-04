# Architecture

## High-Level Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          User / Client                                │
│   CLI (`teshq query "..."`)  ──or──  SDK (`TeshQuery.query(...)`)     │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     TeshEngine        │
                    │  (Orchestrator)       │
                    └──────────┬───────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
    ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐
    │ SchemaGraph   │  │ Schema        │  │ Token Counter    │
    │ (Introspect)  │  │ Retriever     │  │ (Budget Check)   │
    │               │  │ (TF-IDF)      │  │                  │
    └───────┬──────┘  └───────┬───────┘  └──────────────────┘
            │                 │
            ▼                 ▼
    ┌──────────────────────────────┐
    │  Compressed Schema (Top-K)   │
    └──────────────┬───────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
  ┌──────────────┐   ┌───────────────┐
  │ Stage 1:      │   │ Stage 2:      │
  │ QueryPlanner  │   │ SQLGenerator  │
  │ (LangChain)   │   │ (LangChain)   │
  └──────┬───────┘   └───────┬───────┘
         │                    │
         ▼                    ▼
    QueryPlan ──────────► SQLQuery
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
            ┌──────────────┐   ┌───────────────────┐
            │ SQL Validator │   │ SQL Normalizer    │
            └──────┬───────┘   └───────┬───────────┘
                   │                   │
                   └─────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ execute_sql_query │
                    │ (DB Execution)   │
                    └──────┬───────────┘
                           │
                           ▼
                      Query Results
```

## Component Responsibilities

### TeshEngine (`teshq/core/engine.py`)

The central orchestrator. Wires together every step of the pipeline:

1. **Schema Loading** — introspects the live database via SQLAlchemy reflection.
2. **Schema Retrieval** — uses the `SchemaRetriever` (TF-IDF) to select only the Top-K relevant tables.
3. **Token Budget** — estimates prompt tokens and further prunes if over threshold.
4. **Stage 1 — Query Planning** — `QueryPlanner` (LangChain) produces a structured `QueryPlan`.
5. **Stage 2 — SQL Generation** — `SQLGenerator` (LangChain) produces a parameterised `SQLQuery`.
6. **Validation & Normalisation** — safety checks and SQL formatting.
7. **Execution** — runs the query against the database with connection pooling.
8. **Self-Healing Retry** — on execution failure, re-invokes Stage 2 with the error hint.

### SchemaRetriever (`teshq/core/retriever.py`)

Lightweight TF-IDF vector-similarity index built from table names and column descriptors. For a given user query it returns the Top-K most relevant tables plus their FK-connected neighbours. This keeps the LLM context window small even for 100+ table schemas.

### Exception Hierarchy (`teshq/core/exceptions.py`)

All errors flow through typed exceptions:

```
TeshqError
├── TeshqConfigurationError
├── SchemaIntrospectionError
├── SQLGenerationError
├── SQLValidationError
├── ExecutionTimeoutError
├── DatabaseConnectionError
├── LLMRateLimitError
└── SelfHealingExhaustedError
```

### LLM Providers

| Provider | Module | Structured Output |
|---|---|---|
| Google Gemini | `langchain-google-genai` | `with_structured_output(SQLQuery)` |
| Azure OpenAI | `langchain-openai` | Plain text + manual JSON parse |

Provider selection is automatic based on which credentials are configured, or can be set explicitly via `LLM_PROVIDER`.

## Data Flow Summary

```
User Query
    │
    ▼
SchemaRetriever → Top-K tables (context reduction)
    │
    ▼
LangChain QueryPlanner → QueryPlan (tables, filters, aggregations, joins)
    │
    ▼
LangChain SQLGenerator → SQLQuery (parameterised SQL)
    │
    ▼
Validator → Normalizer → Executor → Results
    │                         │
    │   (on failure)          │
    └── Self-Healing ─────────┘
        (re-generate with error hint)
```
