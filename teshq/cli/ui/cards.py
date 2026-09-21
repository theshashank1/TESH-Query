"""
Cinematic Card & Panel Components for TESH-Query.

SQL display cards, execution telemetry dashboards, and empathetic self-healing
error dialogs — each designed to feel like a premium developer tool, not raw output.
"""

from typing import Any, Dict, List, Optional
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns

from teshq.cli.ui.theme import (
    Colors, Icons, ROUNDED_BOX, HEAVY_BOX,
    console, err_console,
    badge, dim_label, status_dot, progress_bar,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SQL CARD  — Syntax-Highlighted Query Display
# ═══════════════════════════════════════════════════════════════════════════════

def render_sql_card(
    sql: str,
    dialect: str = "SQL",
    parameters: Optional[Dict[str, Any]] = None,
    title: str = "Generated SQL Query",
) -> Panel:
    """
    Render a syntax-highlighted SQL query inside an elegant card.

    The card uses Monokai syntax highlighting with a dialect badge and
    optional parameter display.
    """
    clean_sql = sql.strip()

    syntax = Syntax(
        clean_sql,
        "sql",
        theme="monokai",
        line_numbers=clean_sql.count("\n") > 2,
        word_wrap=True,
        padding=(1, 2),
    )

    # ── Title with dialect badge ───────────────────────────────────────────
    dialect_badge = badge(dialect.upper(), Colors.PRIMARY)
    panel_title = (
        f"[bold {Colors.TEXT}]{Icons.table()} {title}[/bold {Colors.TEXT}]"
        f"  {dialect_badge}"
    )

    # ── Parameters subtitle ────────────────────────────────────────────────
    subtitle = None
    if parameters:
        param_strs = [f"[{Colors.MUTED}]{k}[/{Colors.MUTED}]=[{Colors.PRIMARY_LIGHT}]{repr(v)}[/{Colors.PRIMARY_LIGHT}]" for k, v in parameters.items()]
        subtitle = f"  [{Colors.DIM}]{Icons.gear()} Params: {', '.join(param_strs)}[/{Colors.DIM}]  "

    return Panel(
        syntax,
        title=panel_title,
        title_align="left",
        subtitle=subtitle,
        subtitle_align="right",
        border_style=Colors.BORDER,
        box=ROUNDED_BOX,
        padding=(0, 1),
    )


def print_sql_card(
    sql: str,
    dialect: str = "SQL",
    parameters: Optional[Dict[str, Any]] = None,
    title: str = "Generated SQL Query",
) -> None:
    """Print the SQL card to console."""
    console.print(render_sql_card(sql, dialect, parameters, title))


# ═══════════════════════════════════════════════════════════════════════════════
#  EXECUTION METRICS  — Telemetry Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def _format_latency(ms: int) -> str:
    """Format milliseconds with color coding based on speed."""
    if ms < 500:
        color = Colors.SUCCESS
    elif ms < 2000:
        color = Colors.WARNING
    else:
        color = Colors.ERROR
    return f"[bold {color}]{ms:,}ms[/bold {color}]"


def render_metrics_panel(
    plan_latency_ms: int = 0,
    sql_latency_ms: int = 0,
    exec_latency_ms: int = 0,
    total_tokens: int = 0,
    cost_estimate_usd: float = 0.0,
    row_count: Optional[int] = None,
) -> Panel:
    """
    Render a sleek execution telemetry dashboard.

    Shows timing breakdown with color-coded performance indicators,
    token usage, cost estimate, and row count in a compact layout.
    """
    total_ms = plan_latency_ms + sql_latency_ms + exec_latency_ms

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(justify="left", ratio=2)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right", ratio=1)

    # ── Column 1: Timing Breakdown ─────────────────────────────────────────
    timing = Text()
    timing.append(f" {Icons.clock()} ", style=f"bold {Colors.PRIMARY}")
    timing.append(f"{total_ms:,}ms ", style=f"bold {Colors.TEXT}")
    timing.append("total ", style=f"dim {Colors.MUTED}")

    # Sub-breakdown
    parts = []
    if plan_latency_ms:
        parts.append(f"Plan {plan_latency_ms}ms")
    if sql_latency_ms:
        parts.append(f"Gen {sql_latency_ms}ms")
    if exec_latency_ms:
        parts.append(f"Exec {exec_latency_ms}ms")
    if parts:
        timing.append(f"({' · '.join(parts)})", style=f"dim {Colors.DIM}")

    # ── Column 2: Tokens & Cost ────────────────────────────────────────────
    tokens = Text()
    tokens.append(f"{Icons.token()} ", style=f"bold {Colors.SECONDARY}")
    tokens.append(f"{total_tokens:,} ", style=f"bold {Colors.TEXT}")
    tokens.append("tokens ", style=f"dim {Colors.MUTED}")
    if cost_estimate_usd > 0:
        tokens.append(f"{Icons.cost()} ", style=f"dim {Colors.SUCCESS}")
        tokens.append(f"${cost_estimate_usd:.4f}", style=f"dim {Colors.SUCCESS}")

    # ── Column 3: Row Count ────────────────────────────────────────────────
    rows_text = Text()
    if row_count is not None:
        rows_text.append(f"{Icons.rows()} ", style=f"bold {Colors.TEAL}")
        rows_text.append(f"{row_count:,} ", style=f"bold {Colors.TEXT}")
        rows_text.append("rows", style=f"dim {Colors.MUTED}")
    else:
        rows_text.append(f"{Icons.check()} Done", style=f"bold {Colors.SUCCESS}")

    grid.add_row(timing, tokens, rows_text)

    return Panel(
        grid,
        border_style=Colors.BORDER_SUBTLE,
        box=ROUNDED_BOX,
        padding=(0, 1),
    )


def print_metrics(
    plan_latency_ms: int = 0,
    sql_latency_ms: int = 0,
    exec_latency_ms: int = 0,
    total_tokens: int = 0,
    cost_estimate_usd: float = 0.0,
    row_count: Optional[int] = None,
) -> None:
    """Print the execution metrics card to console."""
    console.print(
        render_metrics_panel(
            plan_latency_ms,
            sql_latency_ms,
            exec_latency_ms,
            total_tokens,
            cost_estimate_usd,
            row_count,
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  ERROR CARD  — Empathetic, Self-Healing Error Dialog
# ═══════════════════════════════════════════════════════════════════════════════

def render_error_card(
    exc: Exception,
    context: str = "Operation",
    suggest_action: Optional[str] = None,
    show_traceback: bool = False,
) -> Panel:
    """
    Build an empathetic, humanized, self-healing error panel.

    Instead of raw stack traces, this card explains WHAT happened,
    WHY it likely happened, and HOW to fix it — reducing user anxiety.
    """
    exc_type = type(exc).__name__
    raw_msg = str(exc).strip() or "An unexpected issue occurred."

    # ── Contextual guidance based on error signature ───────────────────────
    headline = f"Could not complete {context.lower()}"
    suggestions: List[str] = []

    msg_lower = raw_msg.lower()
    if "connection" in msg_lower or "refused" in msg_lower or "password" in msg_lower:
        headline = "Database Connection Failed"
        suggestions = [
            "Ensure your database server is running (docker ps / systemctl status postgresql)",
            "Verify credentials: run  teshq config --db",
            "Test connectivity:  teshq health",
        ]
    elif "api key" in msg_lower or "gemini" in msg_lower or "unauthorized" in msg_lower:
        headline = "AI Provider Authentication Issue"
        suggestions = [
            "Verify your API key: run  teshq config --gemini  or check GEMINI_API_KEY",
            "Ensure your account has quota or credits available",
            "Run  teshq health  to check API endpoint connectivity",
        ]
    elif "schema" in msg_lower or "no such table" in msg_lower or "relation" in msg_lower:
        headline = "Database Schema Mismatch"
        suggestions = [
            "Run  teshq db introspect  to refresh your cached schema",
            "Use  teshq db explore  to inspect all detected tables and columns",
        ]
    elif suggest_action:
        suggestions = [suggest_action]
    else:
        suggestions = [
            "Check the query phrasing or options and try again",
            "Run  teshq health  to verify all system components",
            "Use  --verbose  to write detailed logs to ~/.teshq/logs/",
        ]

    content = Text()

    # ── Headline ───────────────────────────────────────────────────────────
    content.append(f"  {headline}\n\n", style=f"bold {Colors.TEXT}")

    # ── What happened ──────────────────────────────────────────────────────
    content.append(f"  {Icons.cross()} ", style=f"bold {Colors.ERROR}")
    content.append("What happened\n", style=f"bold {Colors.ERROR}")
    short_msg = "\n".join(raw_msg.split("\n")[:3])
    content.append(f"    {short_msg}\n\n", style=f"{Colors.TEXT_MUTED}")

    # ── How to fix it ──────────────────────────────────────────────────────
    content.append(f"  {Icons.sparkle()} ", style=f"bold {Colors.SUCCESS}")
    content.append("How to fix it\n", style=f"bold {Colors.SUCCESS}")
    for i, step in enumerate(suggestions, 1):
        content.append(f"    {Icons.chevron()} ", style=f"{Colors.PRIMARY}")
        content.append(f"{step}\n", style=f"{Colors.TEXT_BODY}")

    # ── Error code footer ──────────────────────────────────────────────────
    content.append("\n")
    content.append(
        f"    [{Icons.info()} {exc_type}  •  Use --verbose for full trace]",
        style=f"dim italic {Colors.DIM}",
    )

    # ── Optional traceback ─────────────────────────────────────────────────
    if show_traceback:
        import traceback
        tb = traceback.format_exc()
        if tb and "NoneType: None" not in tb:
            content.append(f"\n\n  Traceback:\n{tb}", style=f"dim {Colors.MUTED}")

    return Panel(
        content,
        title=f"[bold {Colors.ERROR}]{Icons.shield()} {context} Error[/bold {Colors.ERROR}]",
        title_align="left",
        border_style=Colors.ERROR,
        box=ROUNDED_BOX,
        padding=(1, 2),
    )


def print_error_card(
    exc: Exception,
    context: str = "Operation",
    suggest_action: Optional[str] = None,
    show_traceback: bool = False,
) -> None:
    """Print the empathetic error card to stderr console."""
    err_console.print(render_error_card(exc, context, suggest_action, show_traceback))


# ═══════════════════════════════════════════════════════════════════════════════
#  SUCCESS / COMPLETION CARD
# ═══════════════════════════════════════════════════════════════════════════════

def print_success_card(
    title: str,
    details: Optional[List[str]] = None,
) -> None:
    """Print a compact success confirmation panel."""
    content = Text()
    content.append(f"  {Icons.check()} ", style=f"bold {Colors.SUCCESS}")
    content.append(title, style=f"bold {Colors.TEXT}")

    if details:
        content.append("\n")
        for d in details:
            content.append(f"\n    {Icons.bullet()} ", style=f"{Colors.DIM}")
            content.append(d, style=f"{Colors.TEXT_MUTED}")

    console.print(Panel(
        content,
        border_style=Colors.SUCCESS_DARK,
        box=ROUNDED_BOX,
        padding=(0, 1),
    ))
