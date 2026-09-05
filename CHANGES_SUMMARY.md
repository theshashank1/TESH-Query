# Subscription Client - Configuration Changes Summary

## Overview
Updated the subscription client to use the project's config system instead of environment variables, making it suitable for open source distribution.

## Changes Made

### 1. Configuration Source (subscription_client.py)

**Before (Environment Variables):**
```python
def __init__(self, cli_version: str = "1.0.0", timeout: int = 15):
    self.api_base_url = os.getenv("TESHQ_API_BASE_URL", self.DEFAULT_API_BASE_URL)
    self.admin_api_key = os.getenv("TESHQ_ADMIN_API_KEY")
    self.timeout = timeout or int(os.getenv("TESHQ_API_TIMEOUT", self.DEFAULT_TIMEOUT))
```

**After (Config System + Parameters):**
```python
def __init__(
    self,
    cli_version: str = "1.0.0",
    timeout: Optional[int] = None,
    api_base_url: Optional[str] = None,
    admin_api_key: Optional[str] = None
):
    # Priority: constructor args > config file > defaults
    from teshq.utils.config import get_config
    config = get_config()

    self.api_base_url = api_base_url or config.get("TESHQ_API_BASE_URL") or self.DEFAULT_API_BASE_URL
    self.admin_api_key = admin_api_key or config.get("TESHQ_ADMIN_API_KEY")
    # ... timeout logic
```

### 2. Configuration Priority

Configuration is now loaded in this priority order:
1. **Constructor parameters** (highest priority)
2. **Config file** (config.json or .env file)
3. **Sensible defaults** (lowest priority)

### 3. Usage Examples

**Using constructor parameters:**
```python
from teshq.utils.subscription_client import SubscriberClient

client = SubscriberClient(
    api_base_url="https://custom-api.example.com",
    timeout=15,
    admin_api_key="secret-key"
)
```

**Using config file (config.json):**
```json
{
    "TESHQ_API_BASE_URL": "https://custom-api.example.com",
    "TESHQ_API_TIMEOUT": 15,
    "TESHQ_ADMIN_API_KEY": "secret-key"
}
```

**Using config file (.env):**
```
TESHQ_API_BASE_URL=https://custom-api.example.com
TESHQ_API_TIMEOUT=15
TESHQ_ADMIN_API_KEY=secret-key
```

**Using defaults (no configuration needed):**
```python
from teshq.utils.subscription_client import SubscriberClient

# Uses https://teshq-public-api.onrender.com with 10s timeout
client = SubscriberClient()
```

### 4. CLI Updates (subscribe.py)

Updated error messages to reference configuration commands instead of environment variables:

**Before:**
```python
info("Set the TESHQ_ADMIN_API_KEY environment variable:", dim=True)
info("  export TESHQ_ADMIN_API_KEY=your_admin_key", indent=1)
```

**After:**
```python
info("Configure the admin API key using:", dim=True)
info("  teshq config --admin-api-key", indent=1)
space()
info("Or edit config.json and add:", dim=True)
info('  {"TESHQ_ADMIN_API_KEY": "your_admin_key"}', indent=1)
```

### 5. Diagnostic Function Updates

Updated to read from config instead of environment variables:

**Before:**
```python
api_url = os.getenv('TESHQ_API_BASE_URL', 'not set')
admin_key = os.getenv('TESHQ_ADMIN_API_KEY')
```

**After:**
```python
from teshq.utils.config import get_config
config = get_config()
api_url = config.get('TESHQ_API_BASE_URL', 'not set')
admin_key = config.get('TESHQ_ADMIN_API_KEY')
```

## Benefits for Open Source

1. **No external dependencies**: Works out of the box with sensible defaults
2. **User-friendly**: Configuration through familiar config files
3. **Flexible**: Multiple ways to configure (CLI, config.json, .env, constructor)
4. **Secure**: No environment variable exposure in shell history
5. **Consistent**: Uses the same config system as the rest of the project

## Default Values

| Setting | Default Value | Description |
|---------|---------------|-------------|
| `TESHQ_API_BASE_URL` | `https://teshq-public-api.onrender.com` | API endpoint |
| `TESHQ_API_TIMEOUT` | `10` | Request timeout in seconds |
| `TESHQ_ADMIN_API_KEY` | `None` | Admin API key (optional) |

## Production Features (Still Included)

- ✅ Structured logging (no env var dependency)
- ✅ Connection pooling
- ✅ Context manager support
- ✅ Proper resource cleanup
- ✅ Comprehensive error handling
- ✅ Security headers
- ✅ Retry logic
