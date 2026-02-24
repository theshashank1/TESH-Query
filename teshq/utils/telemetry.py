"""
Privacy-safe anonymous usage telemetry for TESH-Query.

Telemetry is **enabled by default** and can be opted out at any time via:

    teshq telemetry --disable

What IS collected (anonymous, aggregated):
  - Command names (e.g. "query", "config", "analytics session")
  - Feature flags used (e.g. --save-csv)
  - Error types (e.g. "SQLAlchemyError") — NOT error messages
  - CLI version

What is NEVER collected:
  - Raw SQL queries
  - Natural-language query text
  - Database URLs or credentials
  - Personally-identifiable information
  - File contents

All events are sent to Logfire when LOGFIRE_TOKEN is configured.
Events are also stored locally in ~/.teshq/telemetry.jsonl for transparency.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Opt-out persistence
# ---------------------------------------------------------------------------

_OPT_OUT_ENV = "TESHQ_TELEMETRY_DISABLE"
_OPT_OUT_FILE = Path.home() / ".teshq" / "telemetry_opt_out"
_LOCAL_LOG = Path.home() / ".teshq" / "telemetry.jsonl"

# Stable anonymous device ID (created once, never changes)
_DEVICE_ID_FILE = Path.home() / ".teshq" / ".device_id"


def _get_device_id() -> str:
    """Return a stable, anonymous device ID (created on first use)."""
    try:
        _DEVICE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _DEVICE_ID_FILE.exists():
            return _DEVICE_ID_FILE.read_text().strip()
        device_id = str(uuid.uuid4())
        _DEVICE_ID_FILE.write_text(device_id)
        return device_id
    except OSError:
        return "anonymous"


def is_telemetry_enabled() -> bool:
    """Return True unless the user has opted out."""
    if os.getenv(_OPT_OUT_ENV, "").lower() in ("1", "true", "yes"):
        return False
    return not _OPT_OUT_FILE.exists()


def set_telemetry_enabled(enabled: bool) -> None:
    """Persist the user's opt-in/out preference."""
    _OPT_OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        _OPT_OUT_FILE.unlink(missing_ok=True)
    else:
        _OPT_OUT_FILE.touch()


# ---------------------------------------------------------------------------
# Logfire integration (optional)
# ---------------------------------------------------------------------------

try:
    import logfire as _logfire

    if os.getenv("LOGFIRE_TOKEN") or os.getenv("LOGFIRE_PROJECT_NAME"):
        _logfire.configure()
        _LOGFIRE_AVAILABLE = True
    else:
        _LOGFIRE_AVAILABLE = False
except Exception:
    _logfire = None  # type: ignore[assignment]
    _LOGFIRE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Core telemetry event emitter
# ---------------------------------------------------------------------------

def _get_cli_version() -> str:
    try:
        from importlib.metadata import version
        return version("teshq")
    except Exception:
        return "unknown"


def _emit(event_name: str, properties: Dict[str, Any]) -> None:
    """
    Emit a single telemetry event.

    Writes to local JSONL log for transparency, and forwards to Logfire
    when configured.  Silently swallowed on any error so telemetry never
    disrupts normal operation.
    """
    if not is_telemetry_enabled():
        return

    try:
        payload: Dict[str, Any] = {
            "event": event_name,
            "device_id": _get_device_id(),
            "cli_version": _get_cli_version(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **properties,
        }

        # Local transparency log
        try:
            _LOCAL_LOG.parent.mkdir(parents=True, exist_ok=True)
            with _LOCAL_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) + "\n")
        except OSError:
            pass

        # Forward to Logfire
        if _LOGFIRE_AVAILABLE and _logfire is not None:
            _logfire.info(event_name, **payload)

    except Exception:
        # Telemetry must NEVER crash the application
        pass


# ---------------------------------------------------------------------------
# Public helpers called from CLI commands
# ---------------------------------------------------------------------------

def track_command(command: str, **flags: Any) -> None:
    """Track that a CLI command was invoked (no query text, no credentials)."""
    safe_flags = {k: bool(v) if not isinstance(v, bool) else v for k, v in flags.items()}
    _emit("command_invoked", {"command": command, "flags": safe_flags})


def track_error(command: str, error_type: str) -> None:
    """Track an error type (NOT the error message or stack trace)."""
    _emit("command_error", {"command": command, "error_type": error_type})


def track_feature(feature: str) -> None:
    """Track usage of an optional feature (e.g. 'save_csv', 'analytics')."""
    _emit("feature_used", {"feature": feature})
