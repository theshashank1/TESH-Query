# 100% Offline & Air-Gapped Mode (Local GGUF)

For zero-data-leakage environments, regulated enterprises (HIPAA, GDPR, SOC2), and defense systems, TESH-Query can run completely on your local workstation or private air-gapped server without sending a single byte to external cloud APIs.

---

## 🔒 Security & Privacy Guarantees

- **Zero Cloud Network Calls:** All prompt compilation and SQL synthesis occur entirely in-process using local CPU/GPU hardware.
- **Physical Grammar Constraint (GBNF):** Local models are physically restricted at the token sampling level by [sql_grammar.gbnf](teshq/core/sql_grammar.gbnf). The model cannot emit arbitrary text or conversational hallucinations; token logits are masked so only syntactically valid SQL can be generated.
- **Local Model Storage:** Models are downloaded directly from Hugging Face and stored locally in `~/.teshq/models/`.

---

## ⚡ Hardware Acceleration

Inspect your system hardware, available CPU threads, RAM, and GPU accelerators:

```bash
teshq local status
```

### Supported Hardware Backends

| Backend | Hardware | Flag |
| :--- | :--- | :--- |
| **Apple Silicon** | M1, M2, M3, M4 (MacBook, Mac Studio) | Metal (`-DGGML_METAL=on`) |
| **NVIDIA GPU** | RTX 30/40 Series, A100, H100, L4 | CUDA (`-DGGML_CUDA=on`) |
| **CPU Only** | Intel / AMD x86_64, ARM64 | OpenBLAS / AVX2 / AVX-512 |

---

## 🤖 Model Management (`teshq model`)

TESH-Query includes an automated Hugging Face GGUF model manager:

```bash
# List recommended models, local status, and RAM requirements
teshq model list

# Download recommended model (includes progress bar and checksum check)
teshq model download qwen3b-coder
```

### Recommended Models Matrix

| Model | Parameters | Quantization | Recommended RAM | Best For |
| :--- | :---: | :---: | :---: | :--- |
| `qwen1.5b-coder` | 1.5B | Q4_K_M | 6 GB | Laptops and memory-constrained environments. |
| `qwen3b-coder` | 3.0B | Q4_K_M | 8 GB | **Recommended** sweet spot for high speed and accuracy. |
| `qwen7b-coder` | 7.0B | Q4_K_M | 16 GB | High-complexity multi-join enterprise schemas. |

---

## 📐 GBNF Context-Free Grammar Enforcement

Cloud LLMs rely on prompt engineering or JSON schemas to format SQL output. When small local models are prompted, they often include markdown code fences (```sql) or conversational preambles ("Here is your query:").

TESH-Query enforces **GBNF (GGML BNF)** grammar constraints:
- The grammar defines the formal lexical structure of SQL (SELECT, FROM, WHERE, GROUP BY, ORDER BY, LIMIT).
- During token sampling, tokens violating the grammar are assigned $-\infty$ probability.
- Hallucinations and invalid syntax are prevented at the model generation step.

---

## 🚀 Running Local Inference

### 1. Via CLI Flag
Force local inference on any query:

```bash
teshq query "Show monthly active users" --local
```

### 2. In Interactive Terminal (`teshq chat`)
Hot-swap to the local model while in session:

```text
/model local
```

### 3. In Python SDK

```python
import teshq

client = teshq.TeshQuery(
    db_url="sqlite:///analytics.db",
    local_model_path="~/.teshq/models/qwen2.5-coder-3b-instruct-q4_k_m.gguf"
)

df = client.query("Show total revenue by product category")
```

---

## 🧭 Next Steps

- **[CLI Reference](07_cli_reference.md)** — Slash commands and interactive usage.
- **[Configuration & Secrets](10_configuration_and_secrets.md)** — Manage local paths and configurations.
- **[Testing & Benchmarks](12_testing_and_benchmarks.md)** — Benchmark local model accuracy and execution latency.
