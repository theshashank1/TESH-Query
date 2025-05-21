<!-- # TESH-Query
A CLI tool that converts natural language queries into SQL and executes them on your database. -->
# 🤖 TESH-Query

**TESH-Query** (Text to Executable SQL Handler) is an AI-powered CLI tool that lets you query your database using natural language — and instantly get the **actual table data** you're asking for.

> **Ask**: *"Show me the list of employees in Bangalore with salary above 1 lakh"*
> **Get**: 🧾 A neatly printed table with exactly those results — **no SQL writing required**.

## ✨ What it does

- 💬 Turn **natural language** into working SQL queries
- 🔍 **Find exactly the data** you need without SQL knowledge
- 🔌 Work with **PostgreSQL, MySQL, SQLite** databases
- ⚡ **Lightning-fast CLI** experience

## 🚧 Development Status

TESH-Query is currently in **early-stage development**. Here's what's actively being worked on:

- ✅ **CLI foundation** with Typer
- ✅ **Database configuration** with secure credential storage
- ✅ **Connection management** utilities
- 🔄 **Natural language understanding** pipeline (in progress)
- 🔄 **Schema introspection** for query context (in progress)

## 📦 Basic Usage (Coming Soon)

```bash
# Configure your database connection
teshq config

# Connect to your database
teshq database --connect

# Ask questions in plain English
teshq query "List all customers who made a purchase last month"
```

## 🔧 Tech Stack

- **Python** - Core language
- **Typer** - Modern CLI framework
- **SQLAlchemy** - Database interaction
- **dotenv/JSON** - Configuration handling
- **LLM Integration** - Natural language processing (coming soon)

## 👤 Made By

**[Shashank](https://github.com/theshashank1)** — Building intelligent tools for developers.

## ⭐ Stay in the Loop

Star this repo to follow along — AI-driven database access is coming soon.
