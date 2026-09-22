"""
TESH-Query — Precision Card Components.

SQL display, execution telemetry, and diagnostic error panels —
each designed as a precision instrument, not a decoration.
"""

from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

from rich.columns import Columns
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import (
    Colors,
    Icons,
    Spacing,
    ROUNDED_BOX,
    console,
    err_console,
    badge,
    dim_label,
    status_dot,
    latency_color,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SQL CARD — Clean Code View
# ═══════════════════════════════════════════════════════════════════════════════

def render_sql_card(
    sql: str,
    dialect: str = "SQL",
    parameters: Optional[Dict[str, Any]] = None,
    title: str = "SQL",
) -> Panel:
    """
    Render a syntax-highlighted SQL query in a clean panel.

    Simplified: title is "SQL" (not "Generated SQL Query"),
    dialect as right-aligned label, line numbers only for 5+ lines.
    """
    clean_sql = sql.strip()

    syntax = Syntax(
        clean_sql,
        "sql",
        theme="monokai",
        line_numbers=clean_sql.count("\n") > 4,
        word_wrap=True,
        padding=(0, 1),
    )

    dialect_label = dialect.upper()

    # Build subtitle for parameters
    subtitle = None
    if parameters:
        param_strs = [
            f"[{Colors.TEXT_MUTED}]{k}[/{Colors.TEXT_MUTED}]="
            f"[{Colors.PRIMARY_HOVER}]{repr(v)}[/{Colors.PRIMARY_HOVER}]"
            for k, v in parameters.items()
        ]
        subtitle = (
            f"[{Colors.TEXT_GHOST}]Params: {', '.join(param_strs)}"
            f"[/{Colors.TEXT_GHOST}]"
        )

    return Panel(
        syntax,
        title=f"[{Colors.TEXT_TERTIARY}]{title}[/{Colors.TEXT_TERTIARY}]",
        title_align="left",
        subtitle=(
            f"[{Colors.TEXT_MUTED}]{dialect_label}[/{Colors.TEXT_MUTED}]"
            if not subtitle
            else f"{subtitle}  [{Colors.TEXT_MUTED}]{dialect_label}[/{Colors.TEXT_MUTED}]"
        ),
        subtitle_align="right",
        border_style=Colors.BORDER_SUBTLE,
        box=ROUNDED_BOX,
        padding=Spacing.COMPACT,
    )


def print_sql_card(
    sql: str,
    dialect: str = "SQL",
    parameters: Optional[Dict[str, Any]] = None,
    title: str = "SQL",
) -> None:
    """Print the SQL card to console."""
    console.print(render_sql_card(sql, dialect, parameters, title))


# ═══════════════════════════════════════════════════════════════════════════════
#  EXECUTION METRICS — Telemetry Strip (compact)
# ═══════════════════════════════════════════════════════════════════════════════

def _format_latency(ms: int) -> str:
    """Format milliseconds with color coding based on speed."""
    color = latency_color(ms)
    return f"[bold {color}]{ms:,}ms[/bold {color}]"


def render_metrics_panel(
    plan_latency_ms: int = 0,
    sql_latency_ms: int = 0,
    exec_latency_ms: int = 0,
    total_tokens: int = 0,
    cost_estimate_usd: float = 0.0,
    row_count: Optional[int] = None,
) -> Text:
    """
    Render a compact single-line telemetry strip.

    Before: 3-column grid Panel
    After:  ✓ 5 rows · 127ms · 340 tokens · $0.0003
    """
    total_ms = plan_latency_ms + sql_latency_ms + exec_latency_ms

    strip = Text()
    strip.append(f"  {Icons.check()} ", style=f"bold {Colors.SUCCESS}")

    parts = []

    if row_count is not None:
        parts.append(f"{row_count:,} row{'s' if row_count != 1 else ''}")

    if total_ms > 0:
        color = latency_color(total_ms)
        parts.append(f"[{color}]{total_ms:,}ms[/{color}]")

    if total_tokens > 0:
        parts.append(f"{total_tokens:,} tokens")

    if cost_estimate_usd > 0:
        parts.append(f"${cost_estimate_usd:.4f}")

    # Sub-breakdown hint
    sub_parts = []
    if plan_latency_ms:
        sub_parts.append(f"Plan {plan_latency_ms}ms")
    if sql_latency_ms:
        sub_parts.append(f"Gen {sql_latency_ms}ms")
    if exec_latency_ms:
        sub_parts.append(f"Exec {exec_latency_ms}ms")

    separator = f" {Icons.separator()} "
    strip.append_text(Text.from_markup(
        separator.join(parts),
        style=f"{Colors.TEXT_TERTIARY}",
    ))

    if sub_parts:
        strip.append_text(Text.from_markup(
            f"  [{Colors.TEXT_GHOST}]({' · '.join(sub_parts)})[/{Colors.TEXT_GHOST}]"
        ))

    return strip


def print_metrics(
    plan_latency_ms: int = 0,
    sql_latency_ms: int = 0,
    exec_latency_ms: int = 0,
    total_tokens: int = 0,
    cost_estimate_usd: float = 0.0,
    row_count: Optional[int] = None,
) -> None:
    """Print the telemetry strip to console."""
    console.print(render_metrics_panel(
        plan_latency_ms,
        sql_latency_ms,
        exec_latency_ms,
        total_tokens,
        cost_estimate_usd,
        row_count,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
#  ERROR CARD — Diagnostic Instrument
# ═══════════════════════════════════════════════════════════════════════════════

def render_error_card(
    exc: Exception,
    context: str = "Operation",
    suggest_action: Optional[str] = None,
    show_traceback: bool = False,
) -> Panel:
    """
    Build a structured diagnostic error panel.

    Structure: What happened → Why → How to fix (numbered steps)
    Professional and direct — no "empathetic" language.
    """
    exc_type = type(exc).__name__
    raw_msg = str(exc).strip() or "An unexpected issue occurred."

    # ── Contextual diagnosis based on error signature ─────────────────
    headline = f"Could not complete {context.lower()}"
    suggestions: List[str] = []

    msg_lower = raw_msg.lower()
    if "connection" in msg_lower or "refused" in msg_lower or "password" in msg_lower:
        headline = "Database Connection Failed"
        suggestions = [
            "Check if your database server is running",
            "Verify credentials: teshq config --db",
            "Test connectivity: teshq health",
        ]
    elif "api key" in msg_lower or "gemini" in msg_lower or "unauthorized" in msg_lower:
        headline = "AI Provider Authentication Issue"
        suggestions = [
            "Verify your API key: teshq config --gemini",
            "Ensure your account has quota available",
            "Test API: teshq health",
        ]
    elif "schema" in msg_lower or "no such table" in msg_lower or "relation" in msg_lower:
        headline = "Database Schema Mismatch"
        suggestions = [
            "Refresh schema cache: teshq db introspect",
            "Inspect tables: teshq db explore",
        ]
    elif "no module named" in msg_lower or isinstance(exc, (ImportError, ModuleNotFoundError)):
        headline = "Missing Dependency"
        import re
        match = re.search(r"no module named ['\"]?([a-zA-Z0-9_\.-]+)['\"]?", msg_lower)
        if not match:
            match = re.search(r"requires ['\"]?([a-zA-Z0-9_\.-]+)['\"]?", msg_lower)
        pkg = match.group(1) if match else "openpyxl"
        suggestions = [
            f"Install the missing package: pip install {pkg}",
            "Reinstall project dependencies: pip install -e .",
        ]
    elif suggest_action:
        suggestions = [suggest_action]
    else:
        suggestions = [
            "Check the query phrasing and try again",
            "Verify system health: teshq health",
            "Use --verbose for detailed logs",
        ]

    content = Text()

    # ── Headline ──────────────────────────────────────────────────────
    content.append(f"  {Icons.cross()} ", style=f"bold {Colors.ERROR}")
    content.append(f"{headline}\n\n", style=f"bold {Colors.TEXT_PRIMARY}")

    # ── What happened ─────────────────────────────────────────────────
    short_msg = "\n".join(raw_msg.split("\n")[:3])
    content.append(f"  {short_msg}\n\n", style=f"{Colors.TEXT_TERTIARY}")

    # ── How to fix (numbered steps) ───────────────────────────────────
    if suggestions:
        content.append("  Try:\n", style=f"bold {Colors.TEXT_SECONDARY}")
        for i, step in enumerate(suggestions, 1):
            content.append(f"    {i}. ", style=f"{Colors.TEXT_MUTED}")
            content.append(f"{step}\n", style=f"{Colors.TEXT_SECONDARY}")

    # ── Error type footer ─────────────────────────────────────────────
    content.append(f"\n  {exc_type}", style=f"dim {Colors.TEXT_GHOST}")
    content.append(
        " · Use --verbose for full trace",
        style=f"dim {Colors.TEXT_GHOST}",
    )

    # ── Optional traceback ────────────────────────────────────────────
    if show_traceback:
        tb = traceback.format_exc()
        if tb and "NoneType: None" not in tb:
            content.append(f"\n\n  Traceback:\n{tb}", style=f"dim {Colors.TEXT_MUTED}")

    return Panel(
        content,
        title=f"[bold {Colors.ERROR}]{context} Error[/bold {Colors.ERROR}]",
        title_align="left",
        border_style=Colors.ERROR,
        box=ROUNDED_BOX,
        padding=Spacing.COMPACT,
    )


def print_error_card(
    exc: Exception,
    context: str = "Operation",
    suggest_action: Optional[str] = None,
    show_traceback: bool = False,
) -> None:
    """Print the diagnostic error card to stderr console."""
    err_console.print(render_error_card(exc, context, suggest_action, show_traceback))


# ═══════════════════════════════════════════════════════════════════════════════
#  SUCCESS CARD — Compact confirmation
# ═══════════════════════════════════════════════════════════════════════════════

def print_success_card(
    title: str,
    details: Optional[List[str]] = None,
) -> None:
    """Print a compact success confirmation."""
    content = Text()
    content.append(f"  {Icons.check()} ", style=f"bold {Colors.SUCCESS}")
    content.append(title, style=f"bold {Colors.TEXT_PRIMARY}")

    if details:
        content.append("\n")
        for d in details:
            content.append(f"\n    {Icons.bullet()} ", style=f"{Colors.TEXT_MUTED}")
            content.append(d, style=f"{Colors.TEXT_TERTIARY}")

    console.print(Panel(
        content,
        border_style=Colors.SUCCESS_DIM,
        box=ROUNDED_BOX,
        padding=Spacing.COMPACT,
    ))
