# Repository Analysis 🚀

This document provides a detailed analysis of the repository's structure, application flow, core methods, CLI integration, and data flow, with the goal of making it easy for anyone to understand the project.

## 📂 Repository Structure

The repository is organized into a clean and logical directory hierarchy.

### Directory Hierarchy

```
.
├── teshq/               # Main source code
│   ├── cli/             # Command-line interface logic
│   ├── core/            # Core business logic
│   └── utils/           # Shared utility functions
├── tests/               # Application tests
│   ├── e2e/             # End-to-end tests
│   ├── integration/     # Integration tests
│   └── unit/            # Unit tests
├── docs/                # Documentation files
├── .github/             # GitHub Actions workflows
└── pyproject.toml       # Project metadata and dependencies
```

### Key Files and Their Purposes

- **`teshq/cli/main.py`**: The main entry point for the CLI application. This is where the `teshq` command is defined.
- **`teshq/cli/query.py`**: Handles the `query` command, taking a natural language query from the user.
- **`teshq/core/query.py`**: The brain of the operation. It orchestrates the process of turning a natural language query into a database result.
- **`teshq/core/llm.py`**: Communicates with a large language model (LLM) to translate a user's query into a SQL query.
- **`teshq/core/db.py`**: Manages all database interactions, including connecting to the database and executing queries.
- **`teshq/core/introspect.py`**: "Looks inside" the database to understand its structure (schema).
- **`teshq/utils/config.py`**: Manages configuration settings, like database credentials and API keys.
- **`teshq/utils/save.py`**: Provides functionality to save query results to different file formats (CSV, Excel, etc.).

## 🌊 Application Flow

The application's flow is designed to be a simple, linear process from the user's query to the final output.

### Entry Points

The primary entry point is the `teshq` command in the terminal. The most important subcommand is `query`, which is used to ask questions in natural language.

### Program Execution Flow

Here is a visual representation of what happens when you run a query:

```
User               CLI (main.py)      Core (query.py)       LLM (llm.py)        Database (db.py)
 │                    │                      │                     │                    │
 │─> teshq query "..."│                      │                     │                    │
 │                    │                      │                     │                    │
 │                    ├─> process_query() ─> │                     │                    │
 │                    │                      │                     │                    │
 │                    │                      ├─> get_sql() ───────>│─> Generate SQL   │
 │                    │                      │<────────────────────│<─┤ from NL Query  │
 │                    │                      │                     │                    │
 │                    │                      ├─> execute_query() ─>│──────────────────>│─> Execute SQL
 │                    │                      │<────────────────────│<──────────────────│<─┤ and return data
 │                    │<─────────────────────│                     │                    │
 │<───────────────────│                      │                     │                    │
 Display Results
```

### Step-by-Step Breakdown

1.  **User Input**: The user runs a command like `teshq query "show me all customers"`.
2.  **CLI Handling**: `teshq/cli/main.py` passes the control to the `query` command function in `teshq/cli/query.py`.
3.  **Core Orchestration**: The `query` function calls `process_query` in `teshq/core/query.py`.
4.  **AI Magic**: `process_query` sends the database schema and the user's query to the language model via `teshq/core/llm.py` to get a SQL query.
5.  **Database Interaction**: The generated SQL query is executed on the database using functions from `teshq/core/db.py`.
6.  **Display Results**: The results are returned to the CLI, which then formats and displays them to the user.

## 🛠️ Core Methods and Functions

The core logic is intentionally separated from the user interface, making the code easier to maintain and test.

### `teshq.core.query.process_query`

- **Signature**: `process_query(query: str, db_type: str, db_path: str, db_credentials: dict, config: dict) -> pd.DataFrame`
- **Description**: This is the conductor of the orchestra. It calls all the other core functions in the correct order to get the job done.

### `teshq.core.llm.get_sql`

- **Signature**: `get_sql(schema: str, query: str, config: dict) -> str`
- **Description**: Takes the database structure and a user's question and asks the AI to write a SQL query.

### `teshq.core.db.execute_query`

- **Signature**: `execute_query(connection: connection, query: str) -> pd.DataFrame`
- **Description**: Takes a SQL query, runs it on the database, and returns the results neatly packaged in a Pandas DataFrame.

## 💻 CLI Integration

The CLI is designed to be user-friendly and intuitive.

- **Command Mapping**: CLI commands are directly mapped to core functions. For example, the `teshq query` command calls the `process_query` function.
- **Parameter Parsing**: The `typer` library is used to handle command-line arguments and options, making it easy to pass information from the user to the application.
- **Output Formatting**: The `rich` library is used to display the results in beautiful, easy-to-read tables in the terminal.

## 🔧 Utils and Their Usage

The `teshq/utils/` directory contains helper functions that are used throughout the application.

- **`config.py`**: A centralized place to manage all configuration.
- **`formater.py`**: Functions to format data for display.
- **`save.py`**: Handles the logic for saving results to files.
- **`ui.py`**: Provides reusable UI components for the CLI.

## 💾 Data Flow and Storage

The application is designed to work with various data sources and formats.

- **Data Structures**: The primary data structure for handling data is the Pandas DataFrame, which is flexible and powerful.
- **Supported Databases**: The application can connect to PostgreSQL, MySQL, and SQLite databases.
- **Data Storage**: You can save your query results to CSV, Excel, or a new SQLite database file.

This improved analysis should give everyone a much clearer understanding of the repository and how the application works.
