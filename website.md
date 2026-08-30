---
title: TESH-Query (TESHQ) - The Open-Source Conversational Database Engine
description: Bridge the gap between human thought and enterprise data with secure, self-healing, natural language querying.
---

# 🌐 TESH-Query (TESHQ)

**Talk to your database. Safely. Instantly.**

## 🚀 The Next-Generation Conversational Database Engine

**Turn Natural Language into Safe, Executable SQL in Milliseconds.**

TESH-Query (TESHQ) eliminates the SQL bottleneck. Ask questions in plain English and let our intelligent engine introspect your schema, generate deterministic SQL, validate it against destructive operations, and return pandas DataFrames—all natively within Python or via a rich CLI.

Powered by **Google Gemini**, **Azure OpenAI**, or **100% Offline Local Models (GGUF/Llama.cpp)**.

[ **pip install teshq** ](https://pypi.org/project/teshq/) | [ **Read the Documentation** ](https://www.notion.so/theshashank1/TESH-Query-20172c79e02080a287bcdff73f694a6b) | [ **Star on GitHub ⭐** ](https://github.com/theshashank1/TESH-Query)

---

## 🛑 The Problem: The Data Silo Bottleneck
* **For Business Teams:** Waiting days for a data analyst to write a simple SQL report.
* **For Developers:** Wasting hours writing boilerplate queries, handling complex joins, and managing database connections.
* **For Security:** Reluctant to use LLMs because they hallucinate, leak data, or attempt to `DROP` production tables.

## 💡 The Solution: TESH-Query
TESH-Query acts as a secure, intelligent firewall between your users and your data. It understands complex database topologies (even 500+ tables), writes the SQL for you, self-corrects if it makes a syntax mistake, and **never** sends your actual row data to the cloud.

---

## 💻 Experience the Interactive CLI

*Built for speed. Beautiful by default.*

```bash
$ teshq query "Show me the top 5 customers by lifetime revenue this year"

  🔍 Schema Analysis: TF-IDF context pruning... [OK - 4 tables selected]
  🧠 Planning query & generating Postgres SQL...
  🛡️ AST Security Scan: PASSED (READ-ONLY OPERATIONS ONLY)
  
  ┌──────────────┬────────────────────────┬────────────────┬──────────────┐
  │ customer_id  │ name                   │ total_orders   │ ltv_revenue  │
  ├──────────────┼────────────────────────┼────────────────┼──────────────┤
  │ CUST-8821    │ Acorn Logistics Ltd    │ 142            │ $89,450.00   │
  │ CUST-1049    │ Apex Global Retail     │ 98             │ $74,210.50   │
  │ CUST-3312    │ Horizon Systems Inc    │ 84             │ $68,900.00   │
  │ CUST-5590    │ Zenith Health Corp     │ 61             │ $52,180.00   │
  │ CUST-9023    │ BlueWave Media LLC     │ 47             │ $49,850.00   │
  └──────────────┴────────────────────────┴────────────────┴──────────────┘
  ✓ 5 rows returned in 234ms | Exported to CSV/Excel
```

---

## 🌟 Uncompromising Capabilities

### 🧠 Intelligent Context Pruning (TF-IDF)
**Scale to massive enterprise schemas without context overflow.**  
Feeding a 500-table schema to an LLM is slow, expensive, and error-prone. TESHQ uses local TF-IDF vector retrieval to dynamically select only the 3-5 tables relevant to your specific question before generating SQL.

### 🛡️ Ironclad AST Safety Guard
**Destructive queries are physically impossible to execute.**  
We don't rely on "prompt engineering" for safety. Every generated query is parsed into an Abstract Syntax Tree (AST). If operations like `DROP`, `DELETE`, `TRUNCATE`, or `ALTER` are detected, execution is hard-blocked at the AST level.

### 🔄 Autonomous Self-Healing Retry
**Graceful recovery from syntax and logic mismatches.**  
If the generated SQL encounters a database constraint or syntax error, TESHQ catches the database stack trace, feeds it back to the LLM as an error-correction prompt, and executes the repaired query transparently.

### 🔒 100% Offline Local AI (Air-gapped)
**Zero cloud dependency for maximum compliance.**  
Need absolute privacy? Run TESHQ entirely offline. We support local `llama.cpp` / GGUF models coupled with strict GBNF grammar constraints to guarantee valid SQL syntax without ever sending a packet over the internet.

---

## 🏗️ The Execution Pipeline

How TESH-Query processes a request from English to Data in milliseconds:

```mermaid
flowchart TD
    User([User Asks Question]) --> Context
    
    subgraph Engine [TESH-Query Core Engine]
        Context(fa:fa-search 1. Schema Retriever\nTF-IDF isolates relevant tables) --> Planner
        Planner(fa:fa-brain 2. AI Query Planner\nLLM formulates dialect-specific SQL) --> Validator
        Validator(fa:fa-shield-halved 3. AST Validator\nBlocks destructive DROP/DELETE commands) --> Executor
        Executor(fa:fa-rotate-right 4. Database Executor\nRuns SQL and Self-Heals on errors)
    end
    
    Executor --> Output([Pandas DataFrame / CSV / JSON])
    
    style Engine fill:#f9f9f9,stroke:#333,stroke-width:2px
    style Validator fill:#e8f4f8,stroke:#0366d6
```

---

## 🛠️ Built for Developers: Python SDK Showcase

TESH-Query isn't just a CLI tool—it's a robust Python SDK designed for asynchronous web backends (FastAPI, Django) and data science notebooks (Jupyter, Streamlit).

### Seamless Synchronous Integration
```python
import teshq

# Initialize client (Zero-config connection pooling built-in)
client = teshq.TeshQuery(
    db_url="postgresql://user:password@localhost/ecommerce_db",
    gemini_api_key="your-google-gemini-key"
)

# Compile schema locally (runs once)
client.introspect_database()

# Natural Language to Data in one line
result = client.query("Show monthly revenue growth for Q3, grouped by region")

# Access native Pandas DataFrame immediately
df = result.dataframe
df.plot(kind='bar', x='region', y='revenue')
```

### High-Performance Async Integration (FastAPI)
```python
@app.get("/api/v1/ask")
async def ask_database(question: str):
    # Non-blocking query execution for high-concurrency environments
    result = await client.aquery(question)
    
    return {
        "sql_executed": result.sql,
        "execution_time_ms": result.duration_ms,
        "data": result.to_dict()
    }
```

---

## 🌍 Ecosystem & Compatibility

TESH-Query speaks your database's exact dialect.

* **Databases Supported:**
  * PostgreSQL (Native Dialect)
  * MySQL & MariaDB
  * Microsoft SQL Server (T-SQL)
  * Oracle Database
  * SQLite (Zero config)
* **Intelligence Providers:**
  * Google Gemini (1.5 Pro / Flash / 2.0)
  * Azure OpenAI (GPT-4o, enterprise endpoints)
  * Local LLMs (via Llama.cpp / GGUF with GBNF grammar)

---

## ⚖️ Why Choose TESH-Query?

| Capability | Standard LLM Prompts (ChatGPT) | Traditional BI Tools | **TESH-Query (TESHQ)** |
| :--- | :--- | :--- | :--- |
| **Data Privacy** | ❌ May leak row data | ✅ Secure | ✅ **Sends ONLY Schema Metadata** |
| **Schema Scalability** | ❌ Context window overflow | ⚠️ Requires manual dashboarding | ✅ **Dynamic TF-IDF Indexing** |
| **SQL Safety Guarantee** | ❌ Prone to hallucinating `DROP` | ⚠️ Read-only replica required | ✅ **Ironclad AST Firewall** |
| **Error Recovery** | ❌ Manual prompting required | ❌ Fails silently on bad joins | ✅ **Automatic Self-Healing** |
| **Air-gapped Deployment** | ❌ Cloud only | ❌ SaaS dependency | ✅ **100% Local / Offline Support** |

---

## ❓ Frequently Asked Questions

<details>
<summary><strong>Does TESH-Query send my actual database records to Google/Azure?</strong></summary>
<p><strong>Absolutely not.</strong> TESH-Query only sends your compressed database <em>schema</em> (table names, column names, relationships, and data types). Your actual rows and sensitive data are queried locally on your machine/server and never touch an external API.</p>
</details>

<details>
<summary><strong>What happens if the LLM tries to delete a table?</strong></summary>
<p>TESH-Query incorporates a strict Abstract Syntax Tree (AST) parser. Before any generated SQL is executed, the AST is scanned. If it detects a non-whitelisted operation (like <code>DROP</code>, <code>DELETE</code>, <code>ALTER</code>), it raises a <code>SecurityException</code> and blocks execution completely.</p>
</details>

<details>
<summary><strong>My database has 800 tables. Will this blow up the token limit?</strong></summary>
<p>No. TESH-Query features a built-in TF-IDF Schema Retriever. When you ask a question, it searches the local schema index and extracts only the 3-5 tables most relevant to your question, passing only that micro-schema to the LLM. It's incredibly fast and token-efficient.</p>
</details>

<details>
<summary><strong>Can I run this without internet access?</strong></summary>
<p><strong>Yes.</strong> By installing <code>teshq[local]</code>, you can leverage <code>llama.cpp</code> and run GGUF models directly on your hardware. We even enforce strict GBNF grammar rules so the local model is physically constrained to outputting valid SQL syntax.</p>
</details>

---

## 🚀 Ready to Transform Your Data Workflow?

Join the open-source revolution and start chatting with your data safely in less than 60 seconds.

```bash
# 1. Install the package
pip install teshq

# 2. Configure your database interactively
teshq config --db

# 3. Start querying
teshq query "Which products are running out of stock?"
```

<div align="center">
  <br/>
  <a href="https://github.com/theshashank1/TESH-Query" target="_blank"><strong>[ View Source on GitHub ]</strong></a> &nbsp;|&nbsp; 
  <a href="https://www.notion.so/theshashank1/TESH-Query-20172c79e02080a287bcdff73f694a6b" target="_blank"><strong>[ Explore Documentation ]</strong></a>
</div>
