"""
teshq.telemetry.events — Typed event helpers for local JSONL analytics.

Usage::

    from teshq.telemetry.events import track_query_event, track_command, track_error

All tracking functions are no-ops if telemetry is opted out.
All events are written to a single file: ~/.teshq/metrics/usage_metrics.jsonl
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPT_OUT_ENV = "TESHQ_NO_TELEMETRY"
_OPT_OUT_FILE = Path.home() / ".teshq" / "telemetry_opt_out"
# Single canonical metrics file path (for telemetry status display)
_LOCAL_LOG = Path.home() / ".teshq" / "metrics" / "usage_metrics.jsonl"


def _metrics_file() -> Path:
    from teshq.config.paths import TESHQ_DIR
    metrics_dir = TESHQ_DIR / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    return metrics_dir / "usage_metrics.jsonl"


# ---------------------------------------------------------------------------
# Opt-out management
# ---------------------------------------------------------------------------

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
# Core write helper — single file, single format
# ---------------------------------------------------------------------------

def _record_local(event_type: str, **data: object) -> None:
    """Append one JSONL line to the single local metrics file."""
    record = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": event_type,
        **data,
    }
    try:
        with open(_metrics_file(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass  # never crash the CLI due to metrics


# ---------------------------------------------------------------------------
# Public event API
# ---------------------------------------------------------------------------

def track_command(
    name: str,
    success: bool = True,
    error_type: Optional[str] = None,
    **flags: Any,
) -> None:
    """
    Track a CLI command invocation (privacy-safe: no query text).

    Extra keyword flags are recorded as safe booleans.
    """
    if _is_opted_out():
        return

    try:
        import teshq
        version = getattr(teshq, "__version__", "unknown")
    except ImportError:
        version = "unknown"

    safe_flags = {k: bool(v) for k, v in flags.items()}
    _record_local(
        "command_invoked",
        command=name,
        cli_version=version,
        success=success,
        error_type=error_type,
        **safe_flags,
    )


def track_query_event(
    plan_ms: int,
    sql_ms: int,
    exec_ms: int,
    success: bool,
    error_type: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> None:
    """
    Record a full query pipeline event to the local metrics file.

    Used by TeshEngine after each query. Records 2-stage timings,
    token counts, and model information for analytics.
    """
    if _is_opted_out():
        return

    total_tokens = prompt_tokens + completion_tokens

    event: dict = {
        "plan_ms": plan_ms,
        "sql_ms": sql_ms,
        "exec_ms": exec_ms,
        "total_ms": plan_ms + sql_ms + exec_ms,
        "success": success,
        "tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if error_type is not None:
        event["error_type"] = error_type
    if model:
        event["model"] = model
    if provider:
        event["provider"] = provider

    _record_local("query", **event)


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
# Legacy compat shims (kept for external callers / tests)
# ---------------------------------------------------------------------------

def track_query(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: float = 0.0,
    success: bool = True,
) -> None:
    """Legacy API shim — delegates to track_query_event."""
    track_query_event(
        plan_ms=0,
        sql_ms=int(latency_ms),
        exec_ms=0,
        success=success,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
    )


def get_query_metrics() -> list:
    """Read all query events from the local metrics file."""
    path = _metrics_file()
    if not path.exists():
        return []
    events = []
    try:
        with open(path, "r", encoding="utf-8") as f:
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

