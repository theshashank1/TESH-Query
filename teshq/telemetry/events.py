"""
teshq.telemetry.events — Typed event helpers for Logfire + local JSONL.

Usage::

    from teshq.telemetry.events import track_query, track_command, track_error

All tracking functions are no-ops if telemetry is opted out.
Logfire spans are used for structured observability when Logfire is configured.
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Opt-out check and persistence
# ---------------------------------------------------------------------------

_OPT_OUT_ENV = "TESHQ_NO_TELEMETRY"
_OPT_OUT_FILE = Path.home() / ".teshq" / "telemetry_opt_out"
_LOCAL_LOG = Path.home() / ".teshq" / "telemetry.jsonl"
_DEVICE_ID_FILE = Path.home() / ".teshq" / ".device_id"


def _get_device_id() -> str:
    """Return a stable, anonymous device ID (created on first use)."""
    import uuid
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
    import os
    if os.getenv(_OPT_OUT_ENV, "").lower() in ("1", "true", "yes"):
        return False
    if _OPT_OUT_FILE.exists():
        return False
    return True


def set_telemetry_enabled(enabled: bool) -> None:
    """Enable or disable telemetry (persisted to disk)."""
    try:
        _OPT_OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        if enabled:
            if _OPT_OUT_FILE.exists():
                _OPT_OUT_FILE.unlink()
        else:
            _OPT_OUT_FILE.touch()
    except OSError:
        pass


def _is_opted_out() -> bool:
    """Return True if the user has disabled telemetry."""
    import os
    if not is_telemetry_enabled():
        return True
    if os.getenv("TESHQ_NO_TELEMETRY", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from teshq.config.settings import get_settings
        return getattr(get_settings(), "no_telemetry", False)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Local JSONL analytics
# ---------------------------------------------------------------------------

def _metrics_file() -> Path:
    from teshq.config.paths import TESHQ_DIR
    metrics_dir = TESHQ_DIR / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    return metrics_dir / "usage_metrics.jsonl"


def _record_local(event_type: str, **data: object) -> None:
    """Append one JSONL line to the local metrics file (privacy-safe)."""
    record = {"ts": time.time(), "event_type": event_type, **data}
    try:
        with open(_metrics_file(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass  # never crash the CLI due to metrics


# ---------------------------------------------------------------------------
# Public event API (v2) — used by CLI commands and TeshEngine
# ---------------------------------------------------------------------------

def track_command(
    name: str,
    success: bool = True,
    error_type: Optional[str] = None,
    **flags: Any,
) -> None:
    """
    Track a CLI command invocation.

    Compatible with both the v2 signature ``track_command(name, success=True)``
    and the legacy v1 signature ``track_command("query", save_csv=True)``.
    Extra keyword flags are recorded as safe booleans.
    """
    if _is_opted_out():
        return

    try:
        import teshq
        version = getattr(teshq, "__version__", "unknown")
    except ImportError:
        version = "unknown"

    device_id = _get_device_id()
    safe_flags = {k: bool(v) for k, v in flags.items()}

    _record_local(
        "command_invoked",
        command=name,
        device_id=device_id,
        cli_version=version,
        success=success,
        error_type=error_type,
        **safe_flags,
    )


def track_query(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: float = 0.0,
    success: bool = True,
) -> None:
    """Track a query execution — no raw SQL or NL queries are sent."""
    if _is_opted_out():
        return
    
    try:
        from teshq.telemetry.pricing import TokenPricingCalculator
        # For Logfire/telemetry, we don't always know the provider here, so we guess google if gemini, openai if gpt, etc.
        provider = "google" if "gemini" in model.lower() else "openai" if "gpt" in model.lower() else "anthropic"
        cost = TokenPricingCalculator.calculate_cost(provider, model, prompt_tokens, completion_tokens)
    except Exception:
        cost = 0.0

    total = prompt_tokens + completion_tokens
    _record_local(
        "query",
        model=model,
        tokens=total,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        success=success,
        cost_estimate_usd=cost,
    )


def track_error(command: str, error_type: str) -> None:
    """Track an error — only the exception class name, never the message."""
    if _is_opted_out():
        return
    _record_local("error", command=command, error_type=error_type)


def track_feature(feature: str, **properties: Any) -> None:
    """Track usage of an optional feature (e.g. 'save_csv', 'dry_run')."""
    if _is_opted_out():
        return
    safe_props = {k: v for k, v in properties.items() if isinstance(v, (bool, int, float, str))}
    _record_local("feature_used", feature=feature, **safe_props)


# ---------------------------------------------------------------------------
# Legacy API — backward compatibility with schema-intelligence-layer branch
# ---------------------------------------------------------------------------

# Legacy local metrics path (kept for backward compat)
_METRICS_DIR = Path.home() / ".teshq" / "metrics"
_METRICS_FILE = _METRICS_DIR / "usage_metrics.jsonl"


def _ensure_metrics_dir() -> None:
    """Create the metrics directory if it does not exist."""
    _METRICS_DIR.mkdir(parents=True, exist_ok=True)


def track_query_event(
    plan_ms: int,
    sql_ms: int,
    exec_ms: int,
    success: bool,
    error_type: Optional[str] = None,
) -> None:
    """
    Record a query event to the local metrics file (legacy API).

    Used by TeshEngine to record 2-stage query pipeline timings.
    """
    if _is_opted_out():
        return

    event = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": "query",
        "plan_ms": plan_ms,
        "sql_ms": sql_ms,
        "exec_ms": exec_ms,
        "success": success,
    }
    if error_type is not None:
        event["error_type"] = error_type

    # Also record to local JSONL
    try:
        _ensure_metrics_dir()
        with open(_METRICS_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass


def get_query_metrics() -> list:
    """
    Read all query events from the local metrics file (legacy API).

    Returns:
        List of event dicts. Empty list if file does not exist.
    """
    if not _METRICS_FILE.exists():
        return []

    events = []
    try:
        with open(_METRICS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass

    return events
