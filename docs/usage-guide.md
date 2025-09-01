# TESH-Query Usage Guide: CLI and Programmatic Access

This guide demonstrates how to use TESH-Query both through the command-line interface (CLI) and programmatically in your Python applications.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [CLI Usage](#cli-usage)
4. [Programmatic Usage](#programmatic-usage)
5. [Advanced Examples](#advanced-examples)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Installation

### From PyPI (Recommended)
```bash
pip install teshq
```

### From Source
```bash
git clone https://github.com/theshashank1/TESH-Query.git
cd TESH-Query
pip install -e .
```

## Configuration

TESH-Query requires two main configurations:

1. **Database Connection**: URL to your database
2. **Gemini API Key**: Google Gemini API key for natural language processing

### Method 1: Using CLI Configuration
```bash
# Interactive database configuration
teshq config --db

# Interactive Gemini API configuration  
teshq config --gemini

# Configure both at once
teshq config --db --gemini --save
```

### Method 2: Environment Variables
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
export GEMINI_API_KEY="your-gemini-api-key"
export GEMINI_MODEL_NAME="gemini-2.0-flash-lite"  # Optional
```

### Method 3: Configuration Files
Create a `.env` file in your project root:
```env
DATABASE_URL=postgresql://user:password@host:port/database
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL_NAME=gemini-2.0-flash-lite
```

## CLI Usage

### Basic Commands

#### 1. Test Database Connection
```bash
teshq database connect
```

#### 2. Introspect Database Schema
```bash
# Basic introspection
teshq introspect

# Advanced introspection with samples
teshq introspect --include-sample-data --sample-size 5 --output-dir ./schema_output
```

#### 3. Execute Natural Language Queries
```bash
# Simple query
teshq query "show me all users"

# Query with output saving
teshq query "find top 10 customers by order amount" --save-csv results.csv --save-excel results.xlsx
```

#### 4. Configuration Management
```bash
# View current configuration
teshq config

# Configure database only
teshq config --db-url "postgresql://localhost:5432/mydb" --save

# Configure Gemini API
teshq config --gemini-api-key "your-key" --gemini-model "gemini-2.0-flash-lite" --save
```

### Advanced CLI Usage

#### Batch Processing
```bash
# Save multiple query results
teshq query "monthly sales report" --save-sqlite analytics.db
teshq query "user activity summary" --save-sqlite analytics.db
```

#### Schema Management
```bash
# Introspect with relationships
teshq introspect --detect-relationships --include-indexes

# Export schema for external use
teshq introspect --output-dir ./exports --json-filename schema.json
```

## Programmatic Usage

### Basic Setup

```python
import teshq

# Method 1: Explicit configuration
client = teshq.TeshQuery(
    db_url="postgresql://user:password@host:port/database",
    gemini_api_key="your-gemini-api-key"
)

# Method 2: Use existing configuration
client = teshq.TeshQuery()  # Loads from config files/env vars

# Method 3: Auto-save configuration
client = teshq.TeshQuery(
    db_url="postgresql://localhost:5432/mydb",
    gemini_api_key="your-key",
    auto_save_config=True  # Saves config for future use
)
```

### Core Operations

#### 1. Database Introspection
```python
# Basic introspection
schema_info = client.introspect_database()

# Advanced introspection
schema_info = client.introspect_database(
    detect_relationships=True,
    include_indexes=True,
    include_sample_data=True,
    sample_size=3,
    save_to_files=True,
    output_dir="./schema_output"
)

# Access schema information
print(f"Tables found: {len(schema_info['tables'])}")
for table_name, table_info in schema_info['tables'].items():
    print(f"Table: {table_name}")
    print(f"  Columns: {list(table_info['columns'].keys())}")
```

#### 2. SQL Generation
```python
# Generate SQL from natural language
sql_info = client.generate_sql("show me all active users")
print(f"Generated SQL: {sql_info['query']}")
print(f"Parameters: {sql_info['parameters']}")

# Use custom schema
schema_text = """
Table: users
  - id: INTEGER PRIMARY KEY
  - name: VARCHAR(255)
  - email: VARCHAR(255)
  - is_active: BOOLEAN
"""

sql_info = client.generate_sql(
    "count active users",
    schema=schema_text
)
```

#### 3. Query Execution
```python
# Execute SQL directly
results = client.execute_query(
    "SELECT * FROM users WHERE is_active = :active",
    parameters={"active": True}
)

# Complete workflow: natural language to results
results = client.query("show me all active users")

# Get both SQL and results
complete_info = client.query(
    "find users who registered last month",
    return_sql=True
)
print(f"SQL: {complete_info['sql']}")
print(f"Results: {complete_info['results']}")
```

### Convenience Functions

```python
# Quick introspection
schema_info = teshq.introspect("postgresql://localhost:5432/mydb")

# Quick query execution
results = teshq.query(
    "show me all users",
    db_url="postgresql://localhost:5432/mydb",
    gemini_api_key="your-key"
)
```

## Advanced Examples

### 1. Automated Report Generation

```python
import teshq
import pandas as pd
from datetime import datetime

def generate_monthly_report(db_url, api_key):
    client = teshq.TeshQuery(db_url=db_url, gemini_api_key=api_key)
    
    queries = [
        "count total users registered this month",
        "calculate total revenue for current month", 
        "find top 10 products by sales volume",
        "show customer satisfaction scores average"
    ]
    
    report = {}
    for query in queries:
        try:
            result = client.query(query, return_sql=True)
            report[query] = {
                'sql': result['sql'],
                'data': result['results'],
                'timestamp': datetime.now()
            }
        except Exception as e:
            report[query] = {'error': str(e)}
    
    return report

# Usage
report = generate_monthly_report(
    db_url="postgresql://localhost:5432/analytics",
    api_key="your-gemini-key"
)
```

### 2. Schema Documentation Generator

```python
import teshq
import json

def generate_schema_docs(db_url, output_file):
    client = teshq.TeshQuery(db_url=db_url, gemini_api_key="dummy")
    
    schema_info = client.introspect_database(
        detect_relationships=True,
        include_indexes=True,
        include_sample_data=True
    )
    
    # Generate documentation
    docs = {
        'database_summary': {
            'total_tables': len(schema_info.get('tables', {})),
            'introspection_date': schema_info.get('introspection_date'),
            'data_model_summary': schema_info.get('data_model_summary')
        },
        'tables': {}
    }
    
    for table_name, table_info in schema_info.get('tables', {}).items():
        docs['tables'][table_name] = {
            'description': table_info.get('description'),
            'column_count': len(table_info.get('columns', {})),
            'primary_keys': table_info.get('primary_keys', []),
            'foreign_keys': table_info.get('foreign_keys', []),
            'indexes': table_info.get('indexes', {}),
            'sample_data': table_info.get('sample_data', [])
        }
    
    with open(output_file, 'w') as f:
        json.dump(docs, f, indent=2, default=str)
    
    return docs

# Usage
docs = generate_schema_docs(
    db_url="postgresql://localhost:5432/mydb",
    output_file="database_documentation.json"
)
```

### 3. Data Analysis Pipeline

```python
import teshq
import pandas as pd

class DataAnalyzer:
    def __init__(self, db_url, gemini_api_key):
        self.client = teshq.TeshQuery(
            db_url=db_url,
            gemini_api_key=gemini_api_key
        )
    
    def analyze(self, questions):
        """Analyze data based on natural language questions."""
        results = {}
        
        for question in questions:
            try:
                # Get results
                data = self.client.query(question)
                
                # Convert to DataFrame for analysis
                df = pd.DataFrame(data)
                
                results[question] = {
                    'data': data,
                    'dataframe': df,
                    'summary': {
                        'rows': len(df),
                        'columns': list(df.columns) if not df.empty else [],
                        'numeric_columns': df.select_dtypes(include=['number']).columns.tolist()
                    }
                }
                
            except Exception as e:
                results[question] = {'error': str(e)}
        
        return results
    
    def export_results(self, results, output_dir="./analysis_output"):
        """Export analysis results to files."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        for i, (question, result) in enumerate(results.items()):
            if 'dataframe' in result:
                df = result['dataframe']
                filename = f"analysis_{i+1}.csv"
                df.to_csv(f"{output_dir}/{filename}", index=False)
                print(f"Exported {question} -> {filename}")

# Usage
analyzer = DataAnalyzer(
    db_url="postgresql://localhost:5432/analytics",
    gemini_api_key="your-key"
)

questions = [
    "show monthly sales trends",
    "find customers with highest lifetime value",
    "calculate product performance metrics",
    "analyze user engagement patterns"
]

results = analyzer.analyze(questions)
analyzer.export_results(results)
```

## Best Practices

### 1. Configuration Management
- Use environment variables in production
- Store sensitive information (API keys) securely
- Use the CLI config for development setup
- Validate configuration before executing queries

### 2. Error Handling
```python
import teshq

def safe_query(client, nl_query):
    try:
        # Test connection first
        if not client.test_connection():
            return {"error": "Database connection failed"}
        
        # Execute query
        result = client.query(nl_query, return_sql=True)
        return {
            "success": True,
            "sql": result['sql'],
            "results": result['results'],
            "row_count": len(result['results'])
        }
        
    except ValueError as e:
        return {"error": f"Configuration error: {e}"}
    except Exception as e:
        return {"error": f"Query execution failed: {e}"}

# Usage
client = teshq.TeshQuery()
result = safe_query(client, "show me all users")
if "error" in result:
    print(f"Error: {result['error']}")
else:
    print(f"Success: {result['row_count']} rows returned")
```

### 3. Performance Optimization
- Cache schema information when possible
- Use the same client instance for multiple queries
- Consider pagination for large result sets
- Monitor API usage for cost optimization

```python
# Efficient multi-query execution
client = teshq.TeshQuery(db_url=db_url, gemini_api_key=api_key)

# Introspect once and reuse
schema_info = client.introspect_database()

# Execute multiple queries using cached schema
queries = ["query 1", "query 2", "query 3"]
for query in queries:
    result = client.query(query)  # Uses cached schema
    process_result(result)
```

### 4. Schema Management
- Keep schema files updated
- Version your schema exports
- Include sample data for better SQL generation
- Document custom relationships

```python
# Regular schema updates
def update_schema_cache():
    client = teshq.TeshQuery(db_url=db_url, gemini_api_key="dummy")
    
    schema_info = client.introspect_database(
        save_to_files=True,
        output_dir="./schema_cache",
        json_filename=f"schema_{datetime.now().strftime('%Y%m%d')}.json"
    )
    
    return schema_info
```

## Troubleshooting

### Common Issues

#### 1. Import Errors
```python
# If you get import errors, ensure proper installation
try:
    import teshq
    print("✅ TESH-Query imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Try: pip install teshq")
```

#### 2. Configuration Issues
```python
# Check configuration
client = teshq.TeshQuery()
if client.test_connection():
    print("✅ Database connection OK")
else:
    print("❌ Database connection failed")
    print("Check your DATABASE_URL configuration")

# Validate API key
try:
    result = client.generate_sql("test query", schema="Table: test (id INT)")
    print("✅ Gemini API key OK")
except Exception as e:
    print(f"❌ Gemini API error: {e}")
```

#### 3. Query Generation Issues
```python
# Debug SQL generation
def debug_query(client, nl_query, schema):
    try:
        print(f"Input: {nl_query}")
        print(f"Schema length: {len(schema)} characters")
        
        result = client.generate_sql(nl_query, schema=schema)
        print(f"Generated SQL: {result['query']}")
        print(f"Parameters: {result['parameters']}")
        
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None
```

### Getting Help

1. **CLI Help**: `teshq --help` or `teshq [command] --help`
2. **GitHub Issues**: https://github.com/theshashank1/TESH-Query/issues
3. **Documentation**: Check the `docs/` directory
4. **Examples**: Run `python examples.py` for working examples

## Migration from CLI-only to Programmatic Usage

If you've been using TESH-Query only through CLI, here's how to migrate:

### Before (CLI only)
```bash
teshq config --db --gemini --save
teshq introspect
teshq query "show me all users" --save-csv users.csv
```

### After (Programmatic)
```python
import teshq

# One-time setup (optional, can use existing config)
client = teshq.TeshQuery(
    db_url="your-db-url",
    gemini_api_key="your-key",
    auto_save_config=True  # Saves for future CLI use too
)

# Same operations, now programmatic
schema = client.introspect_database()
results = client.query("show me all users")

# Save to CSV
import pandas as pd
df = pd.DataFrame(results)
df.to_csv("users.csv", index=False)
```

Both approaches can be used together - configure once with CLI, then use programmatically!

---

## Summary

TESH-Query now provides seamless access through both CLI and programmatic interfaces:

- **CLI**: Perfect for interactive use, testing, and scripting
- **Programmatic**: Ideal for applications, automation, and integration
- **Unified Configuration**: Set up once, use everywhere
- **Full Feature Parity**: All features available in both interfaces

Choose the interface that best fits your workflow, or use both as needed!