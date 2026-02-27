"""
teshq.telemetry.logfire_setup — Centralized Logfire initialization.

Call ``init_logfire()`` once at CLI startup (in ``cli/main.py``).
All subsequent ``logfire.info()`` / ``logfire.span()`` calls throughout
the codebase will automatically flow to the configured backend.

When ``LOGFIRE_TOKEN`` is absent Logfire runs in **local-only** mode
(``send_to_logfire=False``) so no data ever leaves the machine.

Opt-out: set ``TESHQ_NO_TELEMETRY=1`` or run ``teshq telemetry --disable``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def init_logfire(
    *,
    project_name: str = "teshq",
    service_version: Optional[str] = None,
) -> bool:
    """
    Initialize Logfire for the current process.

    Returns ``True`` if Logfire was successfully configured, ``False`` if
    telemetry is disabled or Logfire is unavailable.

    This function is idempotent — safe to call multiple times.
    """
    # ----- Opt-out check -----
    if os.getenv("TESHQ_NO_TELEMETRY", "").lower() in ("1", "true", "yes"):
        return False

    try:
        from teshq.config.settings import get_settings

        if get_settings().no_telemetry:
            return False
    except Exception:
        pass

    # ----- Resolve version -----
    if service_version is None:
        try:
            from importlib.metadata import version

            service_version = version("teshq")
        except Exception:
            service_version = "dev"

    # ----- Configure Logfire -----
    try:
        import logfire

        has_token = bool(
            os.getenv("LOGFIRE_TOKEN") or os.getenv("LOGFIRE_PROJECT_NAME")
        )

        logfire.configure(
            service_version=service_version,
            send_to_logfire="if-token-present" if has_token else False,
            console=False,  # don't pollute the CLI's Rich output
        )
        return True

    except Exception:
        return False


def logfire_span(name: str, **attributes: object):
    """
    Context-manager wrapper that yields a Logfire span.

    If Logfire is not available or telemetry is disabled, yields a no-op
    context manager so callers never need to guard imports.

    Usage::

        with logfire_span("query.generate", model="gemini-2.0") as span:
            result = llm.invoke(...)
            span.set_attribute("tokens", result.usage.total_tokens)
    """
    try:
        import logfire

        return logfire.span(name, **attributes)
    except Exception:
        from contextlib import nullcontext

        return nullcontext()
