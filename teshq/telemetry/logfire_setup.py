"""
teshq.telemetry.logfire_setup — Stub module kept for import compatibility.

Logfire tracing has been removed. All functions here are no-ops.
Use teshq.telemetry.events for local JSONL telemetry.
"""

from __future__ import annotations

from contextlib import nullcontext


def init_logfire(**kwargs) -> bool:
    """No-op — logfire has been removed."""
    return False


def logfire_span(name: str, **attributes: object):
    """No-op context manager — logfire has been removed."""
    return nullcontext()
