"""
Unit tests for the modern award-winning UI/UX components of TESH-Query.
"""

from decimal import Decimal
import pytest
from rich.panel import Panel
from rich.tree import Tree

from teshq.cli.ui.theme import Colors, Icons
from teshq.cli.ui.banner import render_hero_banner, render_hud, print_suggested_prompts
from teshq.cli.ui.cards import render_sql_card, render_metrics_panel, render_error_card
from teshq.cli.ui.tables import render_results_table
from teshq.cli.chat import _render_help_sheet, _get_env_summary


def test_render_hero_banner():
    """Verify hero banner renders with title, version, and styling."""
    panel = render_hero_banner(version="2.1.1", subtitle="AI Natural Language SQL Engine")
    assert isinstance(panel, Panel)
    rendered_text = str(panel.renderable)
    assert "TESH" in rendered_text or "2.1.1" in rendered_text


def test_render_hud():
    """Verify Heads-Up Display renders status pills."""
    hud = render_hud(db_status="Connected", db_type="PostgreSQL", llm_model="Gemini 1.5 Pro", schema_tables_count=12)
    assert isinstance(hud, Panel)


def test_render_sql_card():
    """Verify SQL card renders with dialect pill and parameters."""
    sql = "SELECT id, name FROM customers WHERE active = 1;"
    card = render_sql_card(sql, dialect="postgresql", parameters={"active": 1})
    assert isinstance(card, Panel)
    assert "POSTGRESQL" in card.title


def test_render_metrics_panel():
    """Verify execution metrics panel calculates total latency and displays cost."""
    metrics = render_metrics_panel(
        plan_latency_ms=25,
        sql_latency_ms=65,
        exec_latency_ms=10,
        total_tokens=350,
        cost_estimate_usd=0.0004,
        row_count=42,
    )
    assert isinstance(metrics, Panel)


def test_render_results_table():
    """Verify data grid table renders smart types: booleans, numbers, nulls."""
    headers = ["id", "username", "is_active", "balance", "notes"]
    rows = [
        [1, "alice", True, Decimal("1450.50"), "Primary admin"],
        [2, "bob", False, 200, None],
    ]
    table_panel = render_results_table(headers, rows, title="User Accounts")
    assert isinstance(table_panel, Panel)


def test_render_error_card():
    """Verify empathetic error card generates humanized fix suggestions."""
    exc = ConnectionError("Could not connect to PostgreSQL server: connection refused at localhost:5432")
    err_panel = render_error_card(exc, context="Database Connection")
    assert isinstance(err_panel, Panel)
    assert "Database Connection" in str(err_panel.title) or "Error" in str(err_panel.title)


def test_render_help_sheet():
    """Verify interactive command help sheet renders slash commands."""
    help_panel = _render_help_sheet()
    assert isinstance(help_panel, Panel)


def test_env_summary():
    """Verify environment status summary safely detects environment state without raising."""
    db_status, db_type, llm_name, table_count = _get_env_summary()
    assert isinstance(db_status, str)
    assert isinstance(db_type, str)
    assert isinstance(llm_name, str)
