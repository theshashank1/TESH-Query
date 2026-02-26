"""
teshq.subscriptions.state — Subscription state machine.

State transitions::

    NEVER_SHOWN  → show prompt immediately
    DECLINED     → show again after next_prompt_after date
    SUBSCRIBED   → never show again
    OPTED_OUT    → never show again
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional


class SubscriptionState(str, Enum):
    NEVER_SHOWN = "NEVER_SHOWN"
    DECLINED = "DECLINED"
    SUBSCRIBED = "SUBSCRIBED"
    OPTED_OUT = "OPTED_OUT"


def _state_file() -> Path:
    from teshq.config.paths import TESHQ_DIR
    return TESHQ_DIR / "subscription.json"


def _load() -> dict:
    path = _state_file()
    if not path.exists():
        return {"state": SubscriptionState.NEVER_SHOWN, "last_prompted": None, "next_prompt_after": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"state": SubscriptionState.NEVER_SHOWN, "last_prompted": None, "next_prompt_after": None}


def _save(data: dict) -> None:
    import os
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get_state() -> SubscriptionState:
    raw = _load().get("state", SubscriptionState.NEVER_SHOWN)
    try:
        return SubscriptionState(raw)
    except ValueError:
        return SubscriptionState.NEVER_SHOWN


def should_show_prompt() -> bool:
    """Return True if it's time to show the subscription prompt."""
    data = _load()
    raw_state = data.get("state", SubscriptionState.NEVER_SHOWN)
    try:
        state = SubscriptionState(raw_state)
    except ValueError:
        state = SubscriptionState.NEVER_SHOWN

    if state in (SubscriptionState.SUBSCRIBED, SubscriptionState.OPTED_OUT):
        return False

    if state == SubscriptionState.NEVER_SHOWN:
        return True

    # DECLINED — check if cooldown has passed
    next_after = data.get("next_prompt_after")
    if next_after is None:
        return True
    try:
        next_date = date.fromisoformat(str(next_after))
        return date.today() >= next_date
    except ValueError:
        return True


def mark_declined() -> None:
    """User declined — set random 1–3 day cooldown."""
    days = random.randint(1, 3)
    _save({
        "state": SubscriptionState.DECLINED,
        "last_prompted": date.today().isoformat(),
        "next_prompt_after": (date.today() + timedelta(days=days)).isoformat(),
    })


def mark_subscribed(name: str, email: str) -> None:
    """User subscribed — never prompt again. Does not persist raw PII."""
    _save({
        "state": SubscriptionState.SUBSCRIBED,
        "last_prompted": date.today().isoformat(),
        "next_prompt_after": None,
        # Store only a masked email (first char + domain) to confirm subscription without storing PII
        "email_domain": email.split("@")[-1] if "@" in email else "unknown",
    })


def mark_opted_out() -> None:
    """User opted out permanently — never prompt again."""
    _save({
        "state": SubscriptionState.OPTED_OUT,
        "last_prompted": date.today().isoformat(),
        "next_prompt_after": None,
    })
