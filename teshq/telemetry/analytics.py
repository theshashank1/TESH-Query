from __future__ import annotations

import json
from datetime import datetime, timezone
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


def _parse_ts(ts_val: Any) -> Optional[datetime]:
    """Parse a timestamp field that may be ISO string or unix float."""
    if ts_val is None:
        return None
    try:
        if isinstance(ts_val, (int, float)):
            return datetime.fromtimestamp(float(ts_val), tz=timezone.utc)
        return datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
    except Exception:
        return None


def get_summary() -> Dict[str, Any]:
    """Return an aggregated analytics summary for `teshq analytics show`."""
    all_events = load_events()
    queries = [e for e in all_events if e.get("event_type") == "query"]
    # command_invoked is the correct event_type written by track_command()
    commands = [e for e in all_events if e.get("event_type") == "command_invoked"]
    errors = [e for e in all_events if e.get("event_type") == "error"]

    total_tokens = sum(e.get("tokens", 0) for e in queries)
    prompt_tokens = sum(e.get("prompt_tokens", 0) for e in queries)
    completion_tokens = sum(e.get("completion_tokens", 0) for e in queries)
    successful_queries = sum(1 for e in queries if e.get("success"))
    failed_queries = len(queries) - successful_queries

    avg_latency = (
        sum(e.get("total_ms", e.get("exec_ms", 0)) for e in queries) / len(queries)
        if queries
        else 0
    )

    # Cost estimate using known provider pricing
    try:
        from teshq.telemetry.pricing import TokenPricingCalculator
        total_cost = 0.0
        for e in queries:
            model = e.get("model", "")
            provider = e.get("provider", "")
            if not provider:
                # Infer provider from model name
                provider = "google" if "gemini" in model.lower() else "azure"
            p_tokens = e.get("prompt_tokens", 0)
            c_tokens = e.get("completion_tokens", 0)
            cost = TokenPricingCalculator.calculate_cost(provider, model, p_tokens, c_tokens)
            total_cost += cost if cost is not None else 0.0
    except Exception:
        total_cost = 0.0

    # Command breakdown
    command_counts: Dict[str, int] = {}
    for cmd in commands:
        name = cmd.get("command", "unknown")
        command_counts[name] = command_counts.get(name, 0) + 1

    # Provider breakdown
    provider_counts: Dict[str, int] = {}
    model_counts: Dict[str, int] = {}
    for q in queries:
        prov = q.get("provider") or ("google" if "gemini" in q.get("model", "").lower() else "azure")
        provider_counts[prov] = provider_counts.get(prov, 0) + 1
        model = q.get("model", "unknown")
        if model:
            model_counts[model] = model_counts.get(model, 0) + 1

    # Date range
    all_ts = [_parse_ts(e.get("ts")) for e in all_events]
    valid_ts = [t for t in all_ts if t is not None]
    first_seen = min(valid_ts).strftime("%Y-%m-%d") if valid_ts else None
    last_seen = max(valid_ts).strftime("%Y-%m-%d") if valid_ts else None

    return {
        "total_queries": len(queries),
        "successful_queries": successful_queries,
        "failed_queries": failed_queries,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "avg_latency_ms": round(avg_latency, 1),
        "estimated_cost_usd": round(total_cost, 6),
        "total_commands": len(commands),
        "command_breakdown": command_counts,
        "total_errors": len(errors),
        "provider_breakdown": provider_counts,
        "model_breakdown": model_counts,
        "first_seen": first_seen,
        "last_seen": last_seen,
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
