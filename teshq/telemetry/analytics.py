"""
teshq.telemetry.analytics — Read and aggregate local usage_metrics.jsonl.

Used by `teshq analytics show`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _metrics_file() -> Path:
    from teshq.config.paths import TESHQ_DIR
    return TESHQ_DIR / "metrics" / "usage_metrics.jsonl"


def load_events(event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load all events from the local JSONL file, optionally filtered by type."""
    path = _metrics_file()
    if not path.exists():
        return []
    events = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if event_type is None or record.get("event_type") == event_type:
                    events.append(record)
            except json.JSONDecodeError:
                continue
    return events


def get_summary() -> Dict[str, Any]:
    """Return an aggregated analytics summary for `teshq analytics show`."""
    all_events = load_events()
    queries = [e for e in all_events if e.get("event_type") == "query"]
    commands = [e for e in all_events if e.get("event_type") == "command"]
    errors = [e for e in all_events if e.get("event_type") == "error"]

    total_tokens = sum(e.get("tokens", 0) for e in queries)
    successful_queries = sum(1 for e in queries if e.get("success"))
    failed_queries = len(queries) - successful_queries

    avg_latency = (
        sum(e.get("latency_ms", 0) for e in queries) / len(queries)
        if queries
        else 0
    )

    # Cost estimate: gemini-2.0-flash-lite pricing
    INPUT_COST_PER_1K = 0.000075
    OUTPUT_COST_PER_1K = 0.0003
    total_cost = sum(
        (e.get("prompt_tokens", 0) / 1000 * INPUT_COST_PER_1K)
        + (e.get("completion_tokens", 0) / 1000 * OUTPUT_COST_PER_1K)
        for e in queries
    )

    command_counts: Dict[str, int] = {}
    for cmd in commands:
        name = cmd.get("name", "unknown")
        command_counts[name] = command_counts.get(name, 0) + 1

    return {
        "total_queries": len(queries),
        "successful_queries": successful_queries,
        "failed_queries": failed_queries,
        "total_tokens": total_tokens,
        "avg_latency_ms": round(avg_latency, 1),
        "estimated_cost_usd": round(total_cost, 6),
        "total_commands": len(commands),
        "command_breakdown": command_counts,
        "total_errors": len(errors),
    }


def reset_metrics() -> bool:
    """Delete the local metrics file (used by `teshq analytics reset`)."""
    path = _metrics_file()
    try:
        if path.exists():
            path.unlink()
        return True
    except OSError:
        return False
