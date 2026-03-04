# Configuration

TESH-Query uses **Pydantic V2 BaseSettings** with a layered configuration system. Values are resolved in strict priority order — the first source that provides a value wins.

## Priority Chain (highest → lowest)

```
1. Environment variables   (export DATABASE_URL=...)
2. ~/.teshq/.env           (dotenv secrets file)
3. ~/.teshq/config.yaml    (non-secret settings)
4. Built-in defaults       (e.g. model = gemini-2.0-flash-lite)
```

## Configuration Categories

### Secrets (stored in `~/.teshq/.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | SQLAlchemy connection string |
| `GEMINI_API_KEY` | Google provider | Google Gemini API key |
| `AZURE_OPENAI_API_KEY` | Azure provider | Azure OpenAI API key |

### Non-Secret Settings (stored in `~/.teshq/config.yaml`)

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `google` | LLM provider: `google` or `azure` |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Gemini model name |
| `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI resource URL |
| `AZURE_OPENAI_DEPLOYMENT` | — | Azure OpenAI deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-02-01` | Azure API version |

## Setting Values

### Via CLI

```bash
teshq config --db                  # interactive DATABASE_URL prompt
teshq config --gemini              # interactive Gemini key prompt
teshq config --azure               # interactive Azure config prompt
teshq config --show                # display current (masked) config
```

### Via Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
export GEMINI_API_KEY="AIza..."
export LLM_PROVIDER="google"
```

### Via YAML File

Create or edit `~/.teshq/config.yaml`:

```yaml
LLM_PROVIDER: google
GEMINI_MODEL: gemini-2.0-flash-lite
```

### Via SDK

```python
from teshq import TeshQuery

client = TeshQuery(
    db_url="sqlite:///app.db",
    gemini_api_key="your-key",
    auto_save_config=True,     # persists to files
)
```

## Auto-Detection

If `LLM_PROVIDER` is not explicitly set, the provider is auto-detected:

- If `AZURE_OPENAI_API_KEY` is set → Azure
- If `GEMINI_API_KEY` is set → Google (default)

## Validation

The `Settings.is_configured` property returns `True` only when:

1. `DATABASE_URL` is set, **and**
2. At least one LLM provider has valid credentials.

You can verify configuration at any time:

```bash
teshq config --show
teshq health
```
