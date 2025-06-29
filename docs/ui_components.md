# Modern UI Components Documentation

**File**: `modern_ui_simplified.py` (also known as `ui.py`)
**Author**: theshashank1
**Last Updated**: 2025-06-18 14:30:19 UTC
**Version**: Final Simplified Edition

## Overview

The Modern UI system provides a comprehensive set of components for building beautiful, interactive CLI applications with contemporary 2025 design aesthetics. It offers both Rich console features and ASCII fallbacks for maximum compatibility.

---

## Quick Start

```python
# Import the components you need
from teshq.utils.ui import (
    info, success, warning, error, tip, debug,
    print_header, print_divider, space,
    print_code, print_sql, print_json,
    print_table, print_query_results, print_config,
    status, progress, prompt, confirm, select_option,
    section, indent_context, handle_error
)

# Basic usage
info("Application starting...")
success("Connected to database successfully!")
print_header("Data Analysis Results", "Generated on 2025-06-18")
```

---

## Core Components

### 1. Message System

Display various types of messages with modern 2025 styling and icons.

#### Basic Messages

```python
# Information messages
info("Processing user data...")
info("Database connected", prefix="DB")  # With prefix
info("Loading configuration", indent=1)  # Indented

# Success messages
success("Operation completed successfully!")
success("File saved", prefix="FILE")

# Warning messages
warning("Large dataset detected (10,000 rows)")
warning("API rate limit approaching", prefix="API")

# Error messages
error("Connection failed: timeout")
error("Invalid credentials", prefix="AUTH")

# Tips and suggestions
tip("Use --verbose flag for detailed output")
tip("Consider adding an index for better performance")

# Debug messages (respects quiet mode)
debug("SQL: SELECT * FROM users WHERE active = true")
debug("Response time: 245ms", prefix="PERF")
```

#### Advanced Message Options

```python
# All message types support these parameters:
info("Message text",
     dim=True,           # Dimmed text
     prefix="PREFIX",    # Custom prefix
     indent=2)           # Indentation level

# Examples with combinations
success("Deployment complete", prefix="DEPLOY", indent=1)
warning("Memory usage high", dim=True, prefix="SYS")
```

### 2. Layout and Structure

#### Headers and Dividers

```python
# Main headers (level 1)
print_header("Application Dashboard", "Real-time metrics")
print_header("SYSTEM STATUS")  # No subtitle

# Sub-headers (level 2)
print_header("Database Configuration", level=2)
print_header("API Endpoints", "Available services", level=2)

# Dividers
print_divider()  # Simple line
print_divider("Section Break")  # With text
print_divider("Processing Complete", style="dots")  # Dotted style

# Spacing
space()      # Single line
space(3)     # Multiple lines
```

#### Sections and Context

```python
# Section context manager
with section("Data Processing"):
    info("Loading data...")
    success("Data loaded successfully")
    # Automatic spacing at end

# Indented context
info("Starting batch operations:")
with indent_context(1):
    info("Validating inputs...")
    success("Validation complete")
    with indent_context(1):  # Nested indentation
        debug("All 500 records validated")

# Manual indentation levels
info("Level 0")
info("Level 1", indent=1)
info("Level 2", indent=2)
```

### 3. Code Display

Display code with syntax highlighting and modern formatting.

#### SQL Queries

```python
sql_query = """
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at >= '2025-01-01'
GROUP BY u.name
ORDER BY order_count DESC;
"""

print_sql(sql_query)  # Basic display
print_sql(sql_query, "Customer Orders Query")  # With title
print_sql(sql_query, "Analytics Query", show_line_numbers=True)  # With line numbers
```

#### JSON Data

```python
json_data = """{
  "api_version": "v2.1",
  "endpoints": {
    "users": "/api/v2/users",
    "orders": "/api/v2/orders"
  },
  "authentication": {
    "type": "bearer_token",
    "expires_in": 3600
  }
}"""

print_json(json_data)  # Basic display
print_json(json_data, "API Configuration")  # With title
```

#### YAML Configuration

```python
yaml_content = """
database:
  host: localhost
  port: 5432
  name: production_db

redis:
  host: redis-cluster.local
  port: 6379

logging:
  level: INFO
  format: json
"""

print_yaml(yaml_content, "Application Settings")
```

#### General Code

```python
python_code = """
def calculate_metrics(data):
    total = sum(data)
    average = total / len(data)
    return {
        'total': total,
        'average': average,
        'count': len(data)
    }
"""

print_code(python_code, "python", "Metrics Calculator")
print_code(python_code, "python", "Code Review", line_numbers=True)

# Supported languages: python, sql, json, yaml, javascript, bash, etc.
```

### 4. Tables and Data Display

#### Basic Tables

```python
# Simple table
headers = ["Name", "Age", "City", "Status"]
rows = [
    ["Alice Johnson", 28, "New York", "Active"],
    ["Bob Smith", 35, "San Francisco", "Active"],
    ["Carol White", 42, "Chicago", "Inactive"]
]

print_table("User Directory", headers, rows)
print_table("Employees", headers, rows, caption="Updated 2025-06-18")
```

#### Query Results

```python
# Database query results with metrics
headers = ["Product", "Sales", "Revenue", "Growth"]
rows = [
    ["Laptop Pro", 1250, "$1,875,000", "+15%"],
    ["Tablet Max", 890, "$712,000", "+8%"],
    ["Phone Ultra", 2100, "$1,470,000", "+22%"]
]

print_query_results(
    headers=headers,
    rows=rows,
    title="Q2 Sales Report",
    summary="Top 3 products by revenue performance",
    execution_time=0.045
)
```

#### Configuration Tables

```python
# Configuration display with masking
config = {
    "database_host": "prod-db-cluster.local",
    "database_port": 5432,
    "api_key": "sk-1234567890abcdef",
    "debug_mode": False,
    "max_connections": 100,
    "timeout": 30.0
}

print_config(config, "Production Settings")
print_config(config, "Database Config", mask_keys=["api_key"])
print_config(config, "Full Config", mask_keys=["api_key"], show_types=True)
```

#### Lists

```python
# Simple lists
features = [
    "Real-time data processing",
    "Advanced analytics dashboard",
    "Automated report generation",
    "Multi-user collaboration"
]

print_list(features, "Available Features")
print_list(features, "Product Features", numbered=True)

# Empty lists
print_list([], "No items available")  # Shows warning message
```

### 5. Progress and Status

#### Status Indicators

```python
# Simple status
with status("Connecting to database"):
    time.sleep(2)  # Your operation here

# Status with success message
with status("Processing data", "Data processing complete"):
    process_large_dataset()

# Status with custom spinner
with status("Analyzing...", "Analysis complete", spinner="bouncingBar"):
    run_analysis()
```

#### Progress Bars

```python
# Determinate progress (known total)
with progress("Downloading files", total=100) as progress_data:
    if progress_data:
        prog, task = progress_data
        for i in range(100):
            time.sleep(0.1)
            prog.update(task, advance=1)

# Indeterminate progress (unknown total)
with progress("Processing...") as progress_data:
    if progress_data:
        prog, task = progress_data
        # Progress bar will show spinner + elapsed time
        long_running_operation()
```

### 6. Interactive Components

#### Prompts

```python
# Basic text input
name = prompt("Enter your name")
name = prompt("Enter your name", default="theshashank1")

# Type validation
age = prompt("Enter your age", expected_type=int)
port = prompt("API port", default=8000, expected_type=int)

# Choice validation
env = prompt("Environment", choices=["dev", "staging", "prod"])
env = prompt("Environment", choices=["dev", "staging", "prod"], default="dev")

# Custom validation
email = prompt("Email address", validate=lambda x: "@" in x)
password = prompt("Password", password=True, validate=lambda x: len(x) >= 8)

# Complex validation
def validate_port(port):
    return 1024 <= port <= 65535

api_port = prompt(
    "API port number",
    default=8080,
    expected_type=int,
    validate=validate_port
)
```

#### Confirmations

```python
# Basic confirmation
if confirm("Save changes?"):
    save_configuration()

# With default
if confirm("Continue processing?", default=True):
    continue_operation()

# Danger confirmation (red styling)
if confirm("Delete all data?", danger=True):
    delete_database()

# Combination
proceed = confirm("This will modify production data. Continue?",
                 default=False, danger=True)
```

#### Option Selection

```python
# Menu selection
databases = ["PostgreSQL", "MySQL", "SQLite", "MongoDB"]
selected = select_option("Choose database:", databases)

# With default selection
selected = select_option("Choose database:", databases, default_idx=0)

# Without numbers (bullet points)
selected = select_option("Choose option:", options, show_numbers=False)

# Real-world example
deployment_options = [
    "Development - Local testing environment",
    "Staging - Pre-production testing",
    "Production - Live user environment"
]

choice = select_option(
    "Select deployment target:",
    deployment_options,
    default_idx=0
)
# Returns: "Development - Local testing environment"
```

### 7. Error Handling

```python
# Basic error handling
try:
    risky_operation()
except Exception as e:
    handle_error(e, "Database Operation")

# With suggestions
try:
    connect_to_api()
except Exception as e:
    handle_error(
        e,
        "API Connection",
        suggest_action="Check your internet connection and API credentials"
    )

# With traceback (for debugging)
try:
    complex_operation()
except Exception as e:
    handle_error(
        e,
        "Data Processing",
        show_traceback=True,
        suggest_action="Verify input data format and try again"
    )
```

### 8. Advanced Features

#### Markdown Display

```python
markdown_content = """
# Processing Results

The data analysis **completed successfully** with the following findings:

## Key Metrics
- **Total Records**: 15,847
- **Processing Time**: 2.3 seconds
- **Success Rate**: 99.7%

## Recommendations
1. Consider indexing the `created_at` column
2. Archive records older than 2 years
3. Implement caching for frequent queries

> **Note**: Results are cached for 1 hour
"""

print_markdown(markdown_content, "Analysis Report")
```

#### Utility Functions

```python
# Clear screen
clear_screen()

# Toggle quiet mode
set_quiet_mode(True)   # Suppress info messages
set_quiet_mode(False)  # Restore normal output

# Get console information
info_dict = get_console_info()
print_config(info_dict, "Console Capabilities")
# Shows: rich support, color support, unicode support, dimensions, etc.
```

---

## Complete Example

Here's a comprehensive example showing multiple components working together:

```python
from teshq.utils.ui import *
import time

def main():
    # Initialize
    clear_screen()
    print_header("🚀 DATA ANALYSIS PIPELINE", "Production Run - 2025-06-18")

    # Configuration
    with section("System Configuration"):
        config = {
            "environment": "production",
            "database": "postgresql://prod-cluster.local:5432/analytics",
            "api_key": "sk-abcd1234567890",
            "workers": 8,
            "memory_limit": "4GB"
        }
        print_config(config, "Runtime Configuration", mask_keys=["api_key"])

    # Interactive setup
    with section("Setup Validation"):
        if not confirm("Proceed with production analysis?", danger=True):
            error("Analysis cancelled by user")
            return

        batch_size = prompt(
            "Batch size",
            default=1000,
            expected_type=int,
            validate=lambda x: 100 <= x <= 10000
        )
        success(f"Batch size set to {batch_size}")

    # Processing with progress
    with section("Data Processing"):
        with status("Initializing connections", "Connections established"):
            time.sleep(1)

        with progress("Processing batches", total=50) as progress_data:
            if progress_data:
                prog, task = progress_data
                for i in range(50):
                    time.sleep(0.1)
                    prog.update(task, advance=1)

    # Results
    with section("Analysis Results"):
        sql_query = """
        SELECT category, COUNT(*) as count, AVG(amount) as avg_amount
        FROM transactions
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY category
        ORDER BY count DESC;
        """
        print_sql(sql_query, "Monthly Category Analysis")

        # Sample results
        headers = ["Category", "Count", "Avg Amount", "Growth"]
        rows = [
            ["Electronics", 2850, "$127.45", "+12%"],
            ["Clothing", 1920, "$67.89", "+8%"],
            ["Books", 1205, "$23.99", "-2%"]
        ]

        print_query_results(
            headers, rows,
            "Transaction Analysis",
            "Last 30 days performance",
            execution_time=0.089
        )

    # Error handling example
    with section("Data Validation"):
        try:
            # Simulate an error
            raise ValueError("Invalid data format in row 1,247")
        except Exception as e:
            handle_error(
                e,
                "Data Validation",
                suggest_action="Check source data quality and format"
            )

    # Completion
    print_divider("Pipeline Complete")
    success("🎉 Analysis pipeline completed successfully!")

    # Final tips
    with indent_context():
        tip("Results are cached for 1 hour")
        tip("Use --export flag to save results to CSV")
        info("Next scheduled run: 2025-06-19 06:00:00 UTC")

if __name__ == "__main__":
    main()
```

---

## Best Practices

### 1. **Consistent Structure**

```python
# Always start with clear headers
print_header("APPLICATION NAME", "Context or timestamp")

# Use sections to organize content
with section("Configuration"):
    # Configuration related code

with section("Processing"):
    # Main processing logic
```

### 2. **Progress Feedback**

```python
# For long operations, always show progress
with status("Loading data", "Data loaded successfully"):
    load_large_dataset()

# For iterative processes, use progress bars
with progress("Processing items", total=len(items)) as progress_data:
    if progress_data:
        prog, task = progress_data
        for item in items:
            process_item(item)
            prog.update(task, advance=1)
```

### 3. **Error Handling**

```python
# Always provide context and suggestions
try:
    risky_operation()
except Exception as e:
    handle_error(
        e,
        "Operation Context",
        suggest_action="What the user should try next"
    )
```

### 4. **User Interaction**

```python
# Validate dangerous operations
if confirm("This will delete all data. Continue?", danger=True):
    perform_deletion()

# Provide meaningful defaults
environment = prompt("Environment", choices=["dev", "prod"], default="dev")
```

### 5. **Information Hierarchy**

```python
# Use appropriate message types
info("General information")
success("Positive outcomes")
warning("Important notices")
error("Problems that occurred")
tip("Helpful suggestions")
debug("Technical details")  # Only shown in verbose mode
```

---

## Component Reference

### Message Functions

- `info(message, **kwargs)` - Information messages
- `success(message, **kwargs)` - Success messages
- `warning(message, **kwargs)` - Warning messages
- `error(message, **kwargs)` - Error messages
- `tip(message, **kwargs)` - Tips and suggestions
- `debug(message, **kwargs)` - Debug messages (respects quiet mode)

### Layout Functions

- `space(count=1)` - Add vertical spacing
- `print_header(text, subtitle="", level=1)` - Print headers
- `print_divider(text="", style="line")` - Print dividers

### Display Functions

- `print_code(code, language, title, line_numbers=False)` - Code display
- `print_sql(sql, title, show_line_numbers=False)` - SQL display
- `print_json(json_data, title)` - JSON display
- `print_yaml(yaml_data, title)` - YAML display
- `print_table(title, headers, rows, caption="")` - Table display
- `print_query_results(headers, rows, title, summary, execution_time)` - Query results
- `print_config(config, title, mask_keys=[], show_types=False)` - Configuration
- `print_list(items, title="", numbered=False)` - List display
- `print_markdown(content, title="")` - Markdown display

### Interactive Functions

- `prompt(text, default=None, password=False, validate=None, expected_type=None, choices=None)` - Input prompt
- `confirm(text, default=False, danger=False)` - Confirmation dialog
- `select_option(prompt_text, options, default_idx=0, show_numbers=True)` - Option selection

### Progress Functions

- `status(message, success_message="", spinner="dots")` - Status indicator
- `progress(description="Processing", total=None)` - Progress bar

### Context Managers

- `section(title, collapsed=False)` - Section with auto-spacing
- `indent_context(level=1)` - Indented output context

### Utility Functions

- `clear_screen()` - Clear terminal
- `set_quiet_mode(quiet)` - Toggle quiet mode
- `get_console_info()` - Get console capabilities
- `handle_error(error, context, show_traceback=False, suggest_action="")` - Error handling

---

This documentation covers all components available in the modern UI system. The simplified design makes it easy to create beautiful, functional CLI applications while maintaining the contemporary 2025 aesthetic throughout your application.
