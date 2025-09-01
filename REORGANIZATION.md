# TESH-Query Reorganization: CLI and Programmatic Access

This document outlines the comprehensive reorganization of TESH-Query to support both command-line interface (CLI) and programmatic access without any hassles.

## Overview

TESH-Query has been successfully reorganized to provide seamless access through both:

1. **CLI Interface** - For interactive use, scripting, and quick operations
2. **Programmatic API** - For integration into applications and automated workflows

Both interfaces share the same configuration and provide access to all core functionality.

## Key Changes Made

### 1. New Public API Structure

#### `teshq/__init__.py` - Main Package Interface

- Exports the main `TeshQuery` class for programmatic use
- Provides convenience functions `introspect()` and `query()`
- Includes version information and comprehensive docstring
- Clean, documented public API for easy import

#### `teshq/api.py` - Core Programmatic Interface

- **TeshQuery class**: Main client for all programmatic operations
- **Database introspection**: Full schema analysis with relationship detection
- **SQL generation**: Convert natural language to SQL using LLM
- **Query execution**: Execute SQL against any database
- **Configuration management**: Auto-save/load from environment and files
- **Error handling**: Comprehensive error handling with helpful messages

### 2. Enhanced Core Modules

#### `teshq/core/query.py` - Fixed Query Execution

- Fixed to properly use provided `db_url` parameter
- Maintains backward compatibility with existing CLI usage
- Supports both programmatic and CLI access patterns

#### Configuration Integration

- Seamless sharing between CLI and programmatic interfaces
- Support for environment variables, `.env` files, and `config.json`
- Auto-save capabilities for programmatic configuration

### 3. Comprehensive Documentation

#### `docs/usage-guide.md` - Complete Usage Guide

- Installation instructions for both pip and source
- Configuration methods (CLI, environment variables, config files)
- Detailed CLI usage examples
- Comprehensive programmatic API documentation
- Advanced integration examples
- Best practices and troubleshooting

#### Example Files

- **`examples.py`** - Detailed programmatic usage examples
- **`demo.py`** - Integration demo showing CLI and API working together
- **`test_api.py`** - API validation and testing

## Usage Patterns

### Programmatic Access

```python
import teshq

# Initialize client
client = teshq.TeshQuery(
    db_url="postgresql://user:pass@host:port/database",
    gemini_api_key="your-gemini-api-key"
)

# Database introspection
schema = client.introspect_database()

# Natural language to SQL
result = client.query("show me all users who registered last month")

# Generate SQL without executing
sql_info = client.generate_sql("count all active users")
```

### CLI Access (Unchanged)

```bash
# Configuration
teshq config --db --gemini --save

# Introspection
teshq introspect

# Query execution
teshq query "show me all users who registered last month"
```

### Unified Configuration

Both interfaces use the same configuration:

```bash
# Set once, use everywhere
export DATABASE_URL="postgresql://user:pass@host:port/db"
export GEMINI_API_KEY="your-api-key"

# Use in CLI
teshq query "show me all users"

# Use programmatically
python -c "import teshq; print(teshq.TeshQuery().query('show me all users'))"
```

## Benefits of the Reorganization

### 1. **Dual Access Patterns**

- **CLI**: Perfect for interactive use, testing, and scripting
- **Programmatic**: Ideal for applications, automation, and integration
- **Seamless switching**: Use whichever fits your current workflow

### 2. **Shared Configuration**

- Configure once, use in both interfaces
- Environment variables work for both CLI and programmatic access
- Automatic configuration persistence and loading

### 3. **Full Feature Parity**

- All CLI features available programmatically
- All programmatic features accessible via CLI
- No functionality gaps between interfaces

### 4. **Enhanced Integration**

- Easy to embed in Python applications
- Simple to use in Jupyter notebooks
- Perfect for data analysis pipelines
- Ideal for automated reporting systems

### 5. **Backward Compatibility**

- All existing CLI commands work unchanged
- Existing configurations continue to work
- No breaking changes for current users

## Advanced Integration Examples

### Data Analysis Pipeline

```python
import teshq
import pandas as pd

# Initialize analyzer
client = teshq.TeshQuery(db_url=db_url, gemini_api_key=api_key)

# Introspect database once
schema = client.introspect_database()

# Execute multiple analysis queries
questions = [
    "show monthly sales trends",
    "find top 10 customers by revenue",
    "calculate product performance metrics"
]

results = {}
for question in questions:
    data = client.query(question)
    results[question] = pd.DataFrame(data)

# Export results
for question, df in results.items():
    df.to_csv(f"analysis_{question.replace(' ', '_')}.csv")
```

### Automated Reporting

```python
def generate_daily_report():
    client = teshq.TeshQuery()  # Uses environment config

    # Get today's metrics
    metrics = {
        'new_users': client.query("count users who registered today"),
        'total_orders': client.query("count orders placed today"),
        'revenue': client.query("sum of today's order amounts")
    }

    # Generate report
    report = f"""
    Daily Report - {datetime.now().date()}
    New Users: {metrics['new_users'][0]['count']}
    Orders: {metrics['total_orders'][0]['count']}
    Revenue: ${metrics['revenue'][0]['total']:.2f}
    """

    return report
```

### CLI + Programmatic Workflow

```bash
# Use CLI for setup and exploration
teshq config --db --gemini --save
teshq introspect --save-to-files --output-dir ./schema

# Use programmatically for automation
python -c "
import teshq
client = teshq.TeshQuery()
results = client.query('generate weekly summary report')
print('Weekly report generated:', len(results), 'records')
"
```

## File Structure After Reorganization

```
teshq/
├── __init__.py          # Public API exports (NEW)
├── api.py              # Main programmatic interface (NEW)
├── cli/                # CLI components (UNCHANGED)
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── query.py
│   └── ui/
├── core/               # Core functionality
│   ├── db.py
│   ├── introspect.py
│   ├── llm.py
│   └── query.py        # ENHANCED for dual access
└── utils/              # Utilities (UNCHANGED)
    ├── config.py
    ├── ui.py
    └── save.py

docs/
└── usage-guide.md      # Comprehensive guide (NEW)

examples.py             # Programmatic examples (NEW)
demo.py                # Integration demo (NEW)
test_api.py            # API validation tests (NEW)
```

## Testing and Validation

### API Tests

- ✅ Basic functionality tests
- ✅ Database connection tests
- ✅ Schema introspection tests
- ✅ SQL execution tests
- ✅ CLI integration tests

### Integration Validation

- ✅ CLI commands work unchanged
- ✅ Configuration sharing between interfaces
- ✅ Error handling in both access patterns
- ✅ Performance and memory usage

## Migration Guide

### For Existing CLI Users

No changes needed! All existing CLI commands work exactly as before.

Optional: Start using programmatic access for automation:

```python
import teshq
client = teshq.TeshQuery()  # Uses your existing config
results = client.query("your natural language query")
```

### For New Users

Choose your preferred interface or use both:

```bash
# CLI approach
teshq config --db --gemini --save
teshq query "show me all users"

# Programmatic approach
python -c "
import teshq
client = teshq.TeshQuery(db_url='...', gemini_api_key='...')
print(client.query('show me all users'))
"
```

## Best Practices

### Configuration Management

1. **Use environment variables** for production deployments
2. **Use CLI config** for development and testing
3. **Auto-save config** when setting up programmatically
4. **Validate configuration** before executing queries

### Performance Optimization

1. **Reuse client instances** for multiple operations
2. **Cache schema information** for repeated queries
3. **Use connection pooling** for high-volume applications
4. **Monitor API usage** for cost optimization

### Error Handling

1. **Always test connections** before executing queries
2. **Handle configuration errors** gracefully
3. **Provide helpful error messages** to users
4. **Log errors** for debugging and monitoring

## Future Enhancements

The reorganization provides a solid foundation for future enhancements:

1. **Web API**: Easy to add REST/GraphQL endpoints using the programmatic API
2. **GUI Interface**: Desktop or web GUI can use the same programmatic interface
3. **Plugins**: Plugin system can extend both CLI and programmatic functionality
4. **Language Bindings**: Other languages can interact with the core API
5. **Cloud Integration**: Cloud-native features can leverage the unified interface

## Conclusion

The TESH-Query reorganization successfully achieves the goal of providing seamless access through both CLI and programmatic interfaces. Users can:

- **Start with CLI** for exploration and configuration
- **Move to programmatic** for automation and integration
- **Use both together** as needed for their workflows
- **Share configuration** seamlessly between interfaces
- **Access all features** through either interface

This dual-access pattern makes TESH-Query suitable for a wide range of use cases, from interactive data exploration to automated reporting systems, without any compromises or hassles.

---

_For detailed examples and usage instructions, see `docs/usage-guide.md`, `examples.py`, and `demo.py`._
