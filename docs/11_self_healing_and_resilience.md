# Closed-Loop Self-Healing & Resilience Pipeline

In real-world data environments, first-pass SQL generation can fail due to dialect idiosyncrasies, unexpected schema variations, or missing group-by expressions. Rather than terminating and throwing raw database stack traces to the user, TESH-Query implements an automated **Closed-Loop Self-Healing Pipeline** (`teshq/core/engine.py`).

---

## 🔁 Self-Healing Workflow

```
 User Prompt: "Monthly sales by category for Q2"
                      │
                      ▼
 ┌─────────────────────────────────────────┐
 │ Stage 1: Query Planning                 │
 └────────────────────┬────────────────────┘
                      ▼
 ┌─────────────────────────────────────────┐
 │ Stage 2: SQL Generation                 │
 └────────────────────┬────────────────────┘
                      ▼
 ┌─────────────────────────────────────────┐
 │ AST Security Firewall Validation        │
 └────────────────────┬────────────────────┘
                      ▼
 ┌─────────────────────────────────────────┐
 │ Execute SQL against Database            │
 └────────────────────┬────────────────────┘
                      │
       ┌──────────────┴──────────────┐
       ▼                             ▼
[Query Success]               [Runtime Failure]
       │                             │
       ▼                             ▼
Return Results                ┌───────────────────────────┐
                              │ Transient Error?          │
                              │ (Connection Drop / Lock)  │
                              └─────────────┬─────────────┘
                                            │
                             ┌──────────────┴──────────────┐
                             │                             │
                           [Yes]                          [No]
                             │                             │
                             ▼                             ▼
                     Retry with Jittered           Intercept Dialect Error,
                     Exponential Backoff           Synthesize `error_hint`
                                                           │
                                                           ▼
                                                   Re-invoke Stage 2 with
                                                   Error Feedback
                                                           │
                                                           ▼
                                                   Re-execute Healed SQL
                                                   (Up to 3 iterations)
```

---

## 🩺 Diagnostic Feedback Synthesis (`error_hint`)

When the database engine rejects a query, TESH-Query intercepts the raw exception and categorizes the root cause into a structured diagnostic prompt:

```text
The previous SQL attempt failed with the following database dialect error:
  Category: Missing Group-By Column
  Details: Column 'categories.name' must appear in the GROUP BY clause or be used in an aggregate function.
  Dialect: PostgreSQL

Please repair the SQL to conform strictly to the provided schema and dialect constraints.
```

The SQL Generator receives this diagnostic hint alongside the original query plan, allowing it to pinpoint and resolve the exact syntax or structural error without losing business context.

---

## ⏳ Jittered Exponential Backoff

For transient failures (such as temporary network disconnections, database lock timeouts, or LLM HTTP 429 rate limits), TESH-Query applies randomized exponential backoff:

$$t_{\text{wait}} = \min(t_{\text{max}}, t_{\text{base}} \times 2^{\text{attempt}}) + \text{jitter}$$

- **Base delay:** 0.5s
- **Maximum delay:** 8.0s
- **Jitter:** Prevents thundering-herd problems across concurrent workers

---

## 🏛️ Exception Hierarchy (`teshq/core/exceptions.py`)

All system errors flow through typed, structured exceptions. Raw database passwords, hostnames, and internal stack traces are intercepted and redacted:

```
TeshqError
├── TeshqConfigurationError      # Missing credentials or malformed URLs
├── SchemaIntrospectionError     # Database reflection or metadata extraction failed
├── SQLGenerationError           # LLM compiler failed to emit valid query
├── SQLValidationError           # Query rejected by AST Security Firewall
├── ExecutionTimeoutError        # Query exceeded configured statement timeout
├── DatabaseConnectionError      # Network unreachable or auth failed
├── LLMRateLimitError            # HTTP 429 from AI provider
└── SelfHealingExhaustedError    # Self-healing loop exceeded max retry attempts (3x)
```

---

## 🧭 Next Steps

- **[Testing & Benchmarks](12_testing_and_benchmarks.md)** — Observe self-healing behavior in automated benchmarks.
- **[Troubleshooting & FAQ](14_troubleshooting.md)** — Solutions for common configuration and dialect errors.
- **[Production Deployment](13_production_deployment.md)** — Deploy resilient instances in production.
