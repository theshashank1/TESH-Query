"""
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
