"""
<<<<<<< HEAD
Telemetry Events for TESH-Query v2.

Tracks AI performance metrics (latency, success, errors) to a local JSONL
file at ~/.teshq/metrics/usage_metrics.jsonl.

Never logs raw NL queries, SQL text, DB URLs, or user data.
"""

import datetime
import json
from pathlib import Path
from typing import Optional

# Local metrics file path (user home directory)
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
    Record a query event to the local metrics file.

    Args:
        plan_ms: Time spent in query planning (ms).
        sql_ms: Time spent in SQL generation (ms).
        exec_ms: Time spent executing the SQL (ms).
        success: Whether the query completed successfully.
        error_type: Class name of the error if one occurred.
    """
    # Never log NL queries, SQL text, DB URLs, or user data
    event = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": "query",
        "plan_ms": plan_ms,
        "sql_ms": sql_ms,
        "exec_ms": exec_ms,
        "success": success,
    }
    if error_type is not None:
        event["error_type"] = error_type

    try:
        _ensure_metrics_dir()
        with open(_METRICS_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        # Telemetry must never block primary commands
        pass


def get_query_metrics() -> list:
    """
    Read all query events from the local metrics file.

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
=======
teshq.telemetry.events — Typed event helpers for Logfire + local JSONL.

Usage::

    from teshq.telemetry.events import track_query, track_command

All tracking functions are no-ops if telemetry is opted out.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Opt-out check
# ---------------------------------------------------------------------------

def _is_opted_out() -> bool:
    """Return True if the user has disabled telemetry."""
    import os
    if os.getenv("TESHQ_NO_TELEMETRY", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from teshq.config.settings import get_settings
        return get_settings().no_telemetry
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Logfire (cloud telemetry) — optional
# ---------------------------------------------------------------------------

def _logfire_info(msg: str, **kwargs: object) -> None:
    try:
        import logfire
        logfire.info(msg, **kwargs)
    except Exception:
        pass


def _logfire_error(msg: str, **kwargs: object) -> None:
    try:
        import logfire
        logfire.error(msg, **kwargs)
    except Exception:
        pass


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
    record = {"ts": time.time(), "event": event_type, **data}
    try:
        with open(_metrics_file(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass  # never crash the CLI due to metrics


# ---------------------------------------------------------------------------
# Public event API
# ---------------------------------------------------------------------------

def track_command(name: str, success: bool, error_type: Optional[str] = None) -> None:
    """Track a CLI command invocation."""
    if _is_opted_out():
        return
    _logfire_info("command", name=name, success=success, error_type=error_type)
    _record_local("command", name=name, success=success, error_type=error_type)


def track_query(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    success: bool,
) -> None:
    """Track a query execution — no raw SQL or NL queries are sent."""
    if _is_opted_out():
        return
    total = prompt_tokens + completion_tokens
    _logfire_info(
        "query",
        model=model,
        tokens=total,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        success=success,
    )
    _record_local(
        "query",
        model=model,
        tokens=total,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        success=success,
    )


def track_error(command: str, error_type: str) -> None:
    """Track an error — only the exception class name, never the message."""
    if _is_opted_out():
        return
    _logfire_error("error", command=command, error_type=error_type)
    _record_local("error", command=command, error_type=error_type)
>>>>>>> copilot/redesign-package-management
