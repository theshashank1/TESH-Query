"""
Unit tests for TESH-Query streaming events, cancellation, and client payload utilities:
- EventType, QueryEvent, SSE serialization
- CancellationToken & cooperative query abortion
- TeshChatSession multi-turn conversational context & persistence
- QueryResult pagination and structured payload generation with chart hints
- Exporting to JSONL and Parquet
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from teshq.events import CancellationToken, EventType, QueryCancelledError, QueryEvent
from teshq.session import ChatTurn, TeshChatSession
from teshq.utils.output import QueryResult


class TestEventsAndCancellation:
    """Verify QueryEvent and CancellationToken behaviors."""

    def test_query_event_serialization(self):
        evt = QueryEvent(
            event_type=EventType.SQL_READY,
            stage="sql_gen",
            message="SQL query synthesized",
            data={"sql": "SELECT 1", "parameters": {}},
        )
        as_dict = evt.to_dict()
        assert as_dict["event_type"] == "sql_ready"
        assert as_dict["stage"] == "sql_gen"
        assert as_dict["data"]["sql"] == "SELECT 1"

        sse = evt.to_sse()
        assert sse.startswith("event: sql_ready\ndata: {")
        assert sse.endswith("}\n\n")

    def test_cancellation_token_lifecycle(self):
        token = CancellationToken()
        assert not token.is_cancelled

        # Calling check_cancelled while active does not raise
        token.check_cancelled()

        # Signal cancellation
        token.cancel("User clicked Stop button")
        assert token.is_cancelled
        assert token.reason == "User clicked Stop button"

        with pytest.raises(QueryCancelledError, match="User clicked Stop button"):
            token.check_cancelled()


class TestTeshChatSession:
    """Verify conversational memory and follow-up stitching in TeshChatSession."""

    def test_single_turn_and_follow_up_stitching(self):
        mock_client = MagicMock()
        mock_advanced = MagicMock()
        mock_advanced.query = "SELECT * FROM sales WHERE year = 2025"
        mock_advanced.parameters = {}
        mock_advanced.__len__ = MagicMock(return_value=10)
        mock_advanced.dataframe = "df_result"
        mock_client.query_advanced.return_value = mock_advanced

        session = TeshChatSession(client=mock_client, session_id="test-session-1")

        # Turn 1: Initial query
        res1 = session.ask("show sales for 2025")
        assert res1 == "df_result"
        assert len(session.history) == 1
        assert session.last_sql == "SELECT * FROM sales WHERE year = 2025"
        mock_client.query_advanced.assert_called_with("show sales for 2025")

        # Turn 2: Follow-up query starting with 'filter'
        session.ask("filter by electronics category")
        assert len(session.history) == 2
        last_call_arg = mock_client.query_advanced.call_args[0][0]
        assert "Context from previous query 'show sales for 2025'" in last_call_arg
        assert "filter by electronics category" in last_call_arg

    def test_session_serialization_and_restore(self):
        mock_client = MagicMock()
        session = TeshChatSession(client=mock_client, session_id="test-session-123")
        turn = ChatTurn(
            turn_id=1,
            prompt="count users",
            sql="SELECT COUNT(*) FROM users",
            row_count=1,
            duration_ms=45,
            success=True,
        )
        session.history.append(turn)

        data = session.to_dict()
        assert data["session_id"] == "test-session-123"
        assert len(data["turns"]) == 1
        assert data["turns"][0]["sql"] == "SELECT COUNT(*) FROM users"

        restored = TeshChatSession.from_dict(client=mock_client, data=data)
        assert restored.session_id == "test-session-123"
        assert len(restored.history) == 1
        assert restored.last_sql == "SELECT COUNT(*) FROM users"


class TestQueryResultPayloadAndPagination:
    """Verify pagination, typing, and automatic chart hints."""

    def test_paginate_results(self):
        rows = [{"id": i, "val": f"item_{i}"} for i in range(1, 106)]  # 105 rows
        result = QueryResult(results=rows, query="SELECT * FROM items")

        # Page 1 of 50
        page1 = result.paginate(page=1, page_size=50)
        assert page1["page"] == 1
        assert page1["total_rows"] == 105
        assert page1["total_pages"] == 3
        assert page1["has_next"] is True
        assert page1["has_prev"] is False
        assert len(page1["data"]) == 50
        assert page1["data"][0]["id"] == 1

        # Page 3 of 50
        page3 = result.paginate(page=3, page_size=50)
        assert page3["page"] == 3
        assert page3["has_next"] is False
        assert page3["has_prev"] is True
        assert len(page3["data"]) == 5

    def test_to_payload_with_bar_chart_hint(self):
        rows = [
            {"department": "Engineering", "headcount": 45},
            {"department": "Sales", "headcount": 30},
            {"department": "Marketing", "headcount": 15},
        ]
        result = QueryResult(results=rows, query="SELECT department, COUNT(*) FROM emp GROUP BY department")
        payload = result.to_payload()

        assert payload["total_rows"] == 3
        assert len(payload["columns"]) == 2
        col_types = {c["name"]: c["type"] for c in payload["columns"]}
        assert col_types["department"] == "string"
        assert col_types["headcount"] == "numeric"

        chart_hint = payload["chart_hints"]
        assert chart_hint["type"] == "bar"
        assert chart_hint["x_axis"] == "department"
        assert chart_hint["y_axis"] == "headcount"

    def test_to_payload_with_line_chart_hint(self):
        rows = [
            {"created_at": "2026-01-01", "revenue": 1000.0},
            {"created_at": "2026-01-02", "revenue": 1500.0},
        ]
        result = QueryResult(results=rows, query="SELECT created_at, revenue FROM rev")
        payload = result.to_payload()

        chart_hint = payload["chart_hints"]
        assert chart_hint["type"] == "line"
        assert chart_hint["x_axis"] == "created_at"
        assert chart_hint["y_axis"] == "revenue"

    def test_to_jsonl_export(self, tmp_path):
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        result = QueryResult(results=rows, query="SELECT a, b FROM t")
        out_file = tmp_path / "test.jsonl"

        result.to_jsonl(out_file)
        lines = out_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1, "b": "x"}
        assert json.loads(lines[1]) == {"a": 2, "b": "y"}
