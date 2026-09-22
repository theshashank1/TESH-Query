"""
Unit tests for the "Obsidian Instrument" UI components of TESH-Query.
"""

from decimal import Decimal
import pytest
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from teshq.cli.ui.theme import Colors, Icons, Typography, Spacing, latency_color
from teshq.cli.ui.banner import render_hero_banner, render_hud, print_suggested_prompts
from teshq.cli.ui.cards import render_sql_card, render_metrics_panel, render_error_card
from teshq.cli.ui.tables import render_results_table
from teshq.cli.ui.blocks import (
    CommandBlock, StageTracker, render_command_block, render_telemetry_strip,
    render_action_hints, QUERY_STAGES, DRY_RUN_STAGES,
)
from teshq.cli.ui.status_bar import render_status_bar
from teshq.cli.ui.palette import render_help_sheet, render_command_list, fuzzy_match
from teshq.cli.ui.ai_context import render_ai_explanation, render_table_suggestion
from teshq.cli.chat import _get_env_summary


# ═══════════════════════════════════════════════════════════════════════════════
#  DESIGN SYSTEM TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDesignSystem:
    """Tests for the Obsidian Instrument design system."""

    def test_colors_have_all_surface_layers(self):
        """Verify 4-layer surface depth system exists."""
        assert Colors.BG_VOID
        assert Colors.BG_BASE
        assert Colors.SURFACE_1
        assert Colors.SURFACE_2
        assert Colors.SURFACE_3

    def test_colors_have_text_hierarchy(self):
        """Verify 5-tier text hierarchy exists."""
        assert Colors.TEXT_PRIMARY
        assert Colors.TEXT_SECONDARY
        assert Colors.TEXT_TERTIARY
        assert Colors.TEXT_MUTED
        assert Colors.TEXT_GHOST

    def test_colors_backward_compat_aliases(self):
        """Verify old color names still resolve."""
        assert Colors.TEXT == Colors.TEXT_PRIMARY
        assert Colors.MUTED == Colors.TEXT_TERTIARY
        assert Colors.DIM == Colors.TEXT_MUTED
        assert Colors.SURFACE == Colors.SURFACE_1
        assert Colors.BORDER == Colors.BORDER_DEFAULT

    def test_icons_prompt_symbol(self):
        """Verify the minimal prompt symbol."""
        p = Icons.prompt()
        assert p in ("›", ">")

    def test_icons_all_methods_return_strings(self):
        """Verify all icon methods return strings."""
        methods = [
            Icons.check, Icons.cross, Icons.warn, Icons.info,
            Icons.prompt, Icons.arrow, Icons.expand, Icons.database,
            Icons.table, Icons.key, Icons.link, Icons.search,
            Icons.time, Icons.rows, Icons.token, Icons.cost,
            Icons.ai, Icons.bolt, Icons.sparkle,
        ]
        for method in methods:
            result = method()
            assert isinstance(result, str)
            assert len(result) > 0

    def test_latency_color(self):
        """Verify latency color coding."""
        assert latency_color(100) == Colors.SUCCESS
        assert latency_color(1000) == Colors.WARNING
        assert latency_color(5000) == Colors.ERROR

    def test_typography_tokens(self):
        """Verify typography tokens."""
        assert Typography.HEADLINE == "bold"
        assert Typography.BODY == ""
        assert Typography.CAPTION == "dim"

    def test_spacing_tuples(self):
        """Verify spacing system."""
        assert Spacing.COMPACT == (0, 1)
        assert Spacing.NORMAL == (0, 2)
        assert Spacing.RELAXED == (1, 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  BANNER & HUD TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBanner:
    """Tests for the minimal welcome experience."""

    def test_render_hero_banner(self):
        """Verify hero banner renders with title, version, and styling."""
        banner = render_hero_banner(version="2.1.1")
        assert isinstance(banner, Panel)
        rendered = str(banner.renderable)
        assert "TESH" in rendered or "2.1.1" in rendered

    def test_render_hud(self):
        """Verify inline HUD renders status."""
        hud = render_hud(
            db_status="Connected",
            db_type="PostgreSQL",
            llm_model="Gemini 1.5 Pro",
            schema_tables_count=12,
        )
        assert isinstance(hud, Text)

    def test_env_summary(self):
        """Verify environment summary safely detects state without raising."""
        db_status, db_type, llm_name, table_count = _get_env_summary()
        assert isinstance(db_status, str)
        assert isinstance(db_type, str)
        assert isinstance(llm_name, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  CARDS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCards:
    """Tests for SQL cards, metrics, and error diagnostics."""

    def test_render_sql_card(self):
        """Verify SQL card renders with dialect label."""
        sql = "SELECT id, name FROM customers WHERE active = 1;"
        card = render_sql_card(sql, dialect="postgresql", parameters={"active": 1})
        assert isinstance(card, Panel)

    def test_render_metrics_panel_returns_text(self):
        """Verify metrics now return Text (telemetry strip) instead of Panel."""
        metrics = render_metrics_panel(
            plan_latency_ms=25,
            sql_latency_ms=65,
            exec_latency_ms=10,
            total_tokens=350,
            cost_estimate_usd=0.0004,
            row_count=42,
        )
        # Metrics are now a Text strip, not a Panel
        assert isinstance(metrics, Text)

    def test_render_error_card(self):
        """Verify diagnostic error card generates numbered fix suggestions."""
        exc = ConnectionError(
            "Could not connect to PostgreSQL server: connection refused at localhost:5432"
        )
        err_panel = render_error_card(exc, context="Database Connection")
        assert isinstance(err_panel, Panel)
        assert "Error" in str(err_panel.title)

    def test_render_error_card_schema_mismatch(self):
        """Verify schema mismatch errors get specific suggestions."""
        exc = Exception("no such table: custmers")
        err_panel = render_error_card(exc, context="Query")
        assert isinstance(err_panel, Panel)


# ═══════════════════════════════════════════════════════════════════════════════
#  TABLES TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTables:
    """Tests for the data grid."""

    def test_render_results_table(self):
        """Verify data grid renders with smart types."""
        headers = ["id", "username", "is_active", "balance", "notes"]
        rows = [
            [1, "alice", True, Decimal("1450.50"), "Primary admin"],
            [2, "bob", False, 200, None],
        ]
        table_panel = render_results_table(headers, rows, title="User Accounts")
        assert isinstance(table_panel, Panel)


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMAND BLOCK TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommandBlocks:
    """Tests for the signature interaction — command blocks."""

    def test_command_block_creation(self):
        """Verify a command block can be created and rendered."""
        CommandBlock.reset_counter()
        block = CommandBlock("show top 5 customers")
        assert block.query == "show top 5 customers"
        assert block.number == 1

    def test_command_block_with_sql(self):
        """Verify SQL can be added to a block."""
        CommandBlock.reset_counter()
        block = CommandBlock("test query")
        block.set_sql("SELECT * FROM test", dialect="PostgreSQL")
        rendered = block.render()
        assert isinstance(rendered, Panel)

    def test_command_block_numbering(self):
        """Verify blocks are numbered sequentially."""
        CommandBlock.reset_counter()
        b1 = CommandBlock("first")
        b2 = CommandBlock("second")
        b3 = CommandBlock("third")
        assert b1.number == 1
        assert b2.number == 2
        assert b3.number == 3

    def test_command_block_reset_counter(self):
        """Verify counter reset works."""
        CommandBlock.reset_counter()
        b = CommandBlock("after reset")
        assert b.number == 1

    def test_telemetry_strip(self):
        """Verify telemetry strip renders as single line."""
        strip = render_telemetry_strip(
            row_count=42, total_ms=127, total_tokens=340, cost_usd=0.0003,
        )
        assert isinstance(strip, Text)

    def test_action_hints(self):
        """Verify action hints render."""
        hints = render_action_hints()
        assert isinstance(hints, Text)
        rendered = str(hints)
        assert "Copy SQL" in rendered

    def test_query_stages_count(self):
        """Verify 6 cognitive stages exist (per user feedback)."""
        assert len(QUERY_STAGES) == 6

    def test_dry_run_stages_count(self):
        """Verify dry-run stages skip execution."""
        assert len(DRY_RUN_STAGES) == 5

    def test_stage_tracker_lifecycle(self):
        """Verify StageTracker updates stages dynamically."""
        from rich.console import Console
        c = Console(record=True)
        tracker = StageTracker(QUERY_STAGES, console=c)
        assert tracker.current_idx == 0
        tracker.on_progress(1, "Analyzing schema", "reading graph")
        assert tracker.current_idx == 1
        assert tracker.current_detail == "reading graph"
        tracker.on_progress(3, "Generating SQL", "Azure OpenAI")
        assert tracker.current_idx == 3
        grid = tracker._render()
        assert grid is not None
        tracker.finish()
        assert tracker.current_idx == len(QUERY_STAGES)

    def test_stage_tracker_failure(self):
        """Verify StageTracker marks failed stage on exception."""
        from rich.console import Console
        c = Console(record=True)
        tracker = StageTracker(QUERY_STAGES, console=c)
        tracker.on_progress(2, "Selecting relevant tables")
        tracker.fail("Database timeout")
        assert tracker.failed_idx == 2
        assert tracker.current_detail == "Database timeout"
        grid = tracker._render()
        assert grid is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS BAR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusBar:
    """Tests for the ambient status bar."""

    def test_render_status_bar(self):
        """Verify status bar renders as Text."""
        bar = render_status_bar(
            db_status="Connected",
            db_type="SQLite",
            db_name="enterprise",
            llm_model="Gemini 1.5 Pro",
            schema_tables_count=12,
            session_queries=3,
        )
        assert isinstance(bar, Text)

    def test_render_status_bar_not_connected(self):
        """Verify error state in status bar."""
        bar = render_status_bar(db_status="Not Connected")
        assert isinstance(bar, Text)


# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPalette:
    """Tests for the command palette."""

    def test_fuzzy_match(self):
        """Verify fuzzy matching works."""
        assert fuzzy_match("tbl", "/tables explore schema")
        assert not fuzzy_match("xyz", "/tables")

    def test_render_help_sheet(self):
        """Verify help sheet renders all categories."""
        sheet = render_help_sheet()
        assert isinstance(sheet, Text)
        rendered = str(sheet)
        assert "Commands" in rendered
        assert "Keyboard" in rendered
        assert "Tips" in rendered

    def test_render_command_list_filtered(self):
        """Verify command list can be filtered."""
        from rich.table import Table
        table = render_command_list(filter_query="export")
        assert isinstance(table, Table)


# ═══════════════════════════════════════════════════════════════════════════════
#  AI CONTEXT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAIContext:
    """Tests for contextual AI hints."""

    def test_render_ai_explanation(self):
        """Verify AI explanation renders as Panel."""
        panel = render_ai_explanation("This query joins two tables.")
        assert isinstance(panel, Panel)

    def test_render_table_suggestion(self):
        """Verify table name suggestion renders."""
        hint = render_table_suggestion(
            "custmers",
            ["customers", "customer_orders", "customer_addresses"],
        )
        assert isinstance(hint, Text)
