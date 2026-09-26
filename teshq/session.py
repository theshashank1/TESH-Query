"""
Stateful Multi-Turn Conversation & Session Management for TESH-Query.

Empowers client workflows and programmatic integrations to maintain
conversational context, execute follow-ups, and persist session history without
having to reimplement prompt stitching manually.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Union

if TYPE_CHECKING:
    from teshq.api import TeshQuery
    from teshq.events import QueryEvent


FOLLOW_UP_TRIGGERS = (
    "and",
    "or",
    "also",
    "now",
    "filter",
    "sort",
    "order",
    "group",
    "only",
    "show",
    "what about",
    "limit",
    "where",
    "having",
    "instead",
    "exclude",
    "include",
    "change",
    "add",
    "remove",
)


@dataclass
class ChatTurn:
    """Represents a single query-response turn in a conversation."""
    turn_id: int
    prompt: str
    sql: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    row_count: int = 0
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TeshChatSession:
    """
    Manages a stateful conversation session for TESH-Query.

    Automatically handles contextual follow-ups, tracks query history, and
    provides easy serialization for saving and restoring user chat sessions.

    Example::

        session = client.create_session()
        df1 = session.ask("top 5 sales reps by revenue")
        df2 = session.ask("filter by north region only")  # Auto-threads previous SQL context!
        history_json = session.export_json()
    """

    def __init__(
        self,
        client: TeshQuery,
        session_id: Optional[str] = None,
        history: Optional[List[ChatTurn]] = None,
    ) -> None:
        self.client = client
        self.session_id = session_id or str(uuid.uuid4())
        self.history: List[ChatTurn] = history or []

    @property
    def last_turn(self) -> Optional[ChatTurn]:
        """Return the most recent chat turn, if any."""
        return self.history[-1] if self.history else None

    @property
    def last_sql(self) -> Optional[str]:
        """Return the SQL generated in the last turn."""
        return self.last_turn.sql if self.last_turn else None

    @property
    def last_prompt(self) -> Optional[str]:
        """Return the user prompt from the last turn."""
        return self.last_turn.prompt if self.last_turn else None

    def _build_request_text(self, prompt: str) -> str:
        """Stitch previous context if the prompt appears to be a follow-up."""
        cleaned = prompt.strip()
        if self.last_turn and any(
            cleaned.lower().startswith(trigger) for trigger in FOLLOW_UP_TRIGGERS
        ):
            return (
                f"Context from previous query '{self.last_prompt}' "
                f"with SQL: {self.last_sql}. Follow-up request: {cleaned}"
            )
        return cleaned

    def ask(
        self,
        prompt: str,
        output_format: str = "dataframe",
        **kwargs: Any,
    ) -> Any:
        """
        Execute a prompt within the conversational session.

        Args:
            prompt: User question or follow-up request.
            output_format: Desired output format ("dataframe", "dict", "arrow", "polars").
            **kwargs: Extra parameters passed to client.query / client.query_advanced.

        Returns:
            The query result in the requested format.
        """
        request_text = self._build_request_text(prompt)
        start_time = time.time()

        try:
            adv_result = self.client.query_advanced(request_text, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)

            turn = ChatTurn(
                turn_id=len(self.history) + 1,
                prompt=prompt,
                sql=adv_result.query,
                parameters=adv_result.parameters,
                row_count=len(adv_result),
                duration_ms=duration_ms,
                success=True,
            )
            self.history.append(turn)

            if output_format == "dataframe":
                return adv_result.dataframe
            elif output_format == "dict":
                return adv_result.results
            elif output_format == "arrow":
                return adv_result.arrow
            elif output_format == "polars":
                return adv_result.polars
            elif output_format == "advanced":
                return adv_result
            return adv_result.dataframe

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            turn = ChatTurn(
                turn_id=len(self.history) + 1,
                prompt=prompt,
                sql="",
                duration_ms=duration_ms,
                success=False,
                error=str(exc),
            )
            self.history.append(turn)
            raise

    async def aask(
        self,
        prompt: str,
        output_format: str = "dataframe",
        **kwargs: Any,
    ) -> Any:
        """Async counterpart of ask()."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.ask(prompt, output_format=output_format, **kwargs)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state and history to a dictionary."""
        return {
            "session_id": self.session_id,
            "turns": [turn.to_dict() for turn in self.history],
        }

    def export_json(self, indent: int = 2) -> str:
        """Export session to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, client: TeshQuery, data: Dict[str, Any]) -> TeshChatSession:
        """Restore a session from a serialized dictionary."""
        session_id = data.get("session_id")
        raw_turns = data.get("turns", [])
        turns = [ChatTurn(**turn_data) for turn_data in raw_turns]
        return cls(client=client, session_id=session_id, history=turns)

    def clear(self) -> None:
        """Reset conversation history."""
        self.history.clear()
