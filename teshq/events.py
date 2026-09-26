"""
Structured Event System and Cancellation for TESH-Query.

Provides fine-grained event streaming, lifecycle hooks, and cooperative
cancellation tokens to enable high-responsiveness and real-time execution tracking.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Lifecycle event types emitted during query compilation and execution."""
    STAGE_STARTED = "stage_started"
    PLAN_READY = "plan_ready"
    SQL_READY = "sql_ready"
    VALIDATED = "validated"
    EXEC_STARTED = "exec_started"
    ROWS_READY = "rows_ready"
    FINISHED = "finished"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class QueryEvent:
    """Represents a fine-grained event emitted during query lifecycle."""
    event_type: EventType
    stage: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a JSON-serializable dictionary."""
        return {
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else str(self.event_type),
            "stage": self.stage,
            "message": self.message,
            "data": self.data or {},
            "timestamp": self.timestamp,
        }

    def to_sse(self) -> str:
        """Format the event as a Server-Sent Events (SSE) string."""
        payload = json.dumps(self.to_dict(), default=str)
        return f"event: {self.event_type.value}\ndata: {payload}\n\n"


class QueryCancelledError(Exception):
    """Raised when an in-flight query is aborted via a CancellationToken."""
    pass


class CancellationToken:
    """
    Cooperative cancellation token for aborting long-running LLM calls or DB queries.

    Example::

        token = CancellationToken()
        # In worker thread / client:
        # on cancel signal -> token.cancel()
        client.query("complex prompt", cancellation_token=token)
    """

    def __init__(self) -> None:
        self._cancelled: bool = False
        self._cancel_reason: Optional[str] = None

    def cancel(self, reason: Optional[str] = None) -> None:
        """Signal cancellation."""
        self._cancelled = True
        self._cancel_reason = reason or "Query cancelled by user or application"

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    @property
    def reason(self) -> Optional[str]:
        """Get the cancellation reason."""
        return self._cancel_reason

    def check_cancelled(self) -> None:
        """Raise QueryCancelledError if cancellation has been signaled."""
        if self._cancelled:
            raise QueryCancelledError(self._cancel_reason or "Query cancelled")
