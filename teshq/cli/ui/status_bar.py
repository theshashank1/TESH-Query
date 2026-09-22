"""
TESH-Query — Ambient Status Bar.

A single-line status bar providing system awareness at a glance.
Shows database connection, AI engine, schema state, session stats,
and keyboard hint — all in one compact line.
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text

from teshq.cli.ui.theme import Colors, Icons, console, status_dot


def render_status_bar(
    db_status: str = "Not Connected",
    db_type: str = "Database",
    db_name: str = "",
    llm_model: str = "Gemini 1.5",
    schema_tables_count: Optional[int] = None,
    session_queries: int = 0,
    show_palette_hint: bool = True,
) -> Text:
    """
    Render a compact single-line status bar.

    Example:
      ● SQLite fmcg_enterprise · ◎ Gemini 1.5 Pro · 12 tables · 3 queries · Ctrl+K
    """
    bar = Text()
    bar.append("  ", style="")

    # ── Database status ───────────────────────────────────────────────
    is_error = "error" in db_status.lower() or "not" in db_status.lower()
    if is_error:
        bar.append_text(Text.from_markup(status_dot("error")))
    else:
        bar.append_text(Text.from_markup(status_dot("ok")))

    bar.append(" ", style="")

    db_display = db_type
    if db_name:
        db_display = f"{db_type} {db_name}"
    bar.append(db_display, style=f"bold {Colors.TEXT_SECONDARY}")

    # ── Separator ─────────────────────────────────────────────────────
    bar.append(f" {Icons.separator()} ", style=f"{Colors.TEXT_GHOST}")

    # ── AI Engine ─────────────────────────────────────────────────────
    bar.append_text(Text.from_markup(status_dot("ai")))
    bar.append(f" {llm_model}", style=f"{Colors.TEXT_SECONDARY}")

    # ── Schema ────────────────────────────────────────────────────────
    if schema_tables_count is not None and schema_tables_count > 0:
        bar.append(f" {Icons.separator()} ", style=f"{Colors.TEXT_GHOST}")
        bar.append(
            f"{schema_tables_count} table{'s' if schema_tables_count != 1 else ''}",
            style=f"{Colors.TEXT_TERTIARY}",
        )

    # ── Session queries ───────────────────────────────────────────────
    if session_queries > 0:
        bar.append(f" {Icons.separator()} ", style=f"{Colors.TEXT_GHOST}")
        bar.append(
            f"{session_queries} quer{'ies' if session_queries != 1 else 'y'}",
            style=f"{Colors.TEXT_TERTIARY}",
        )

    # ── Palette hint ──────────────────────────────────────────────────
    if show_palette_hint:
        bar.append(f" {Icons.separator()} ", style=f"{Colors.TEXT_GHOST}")
        bar.append("/help", style=f"dim {Colors.PRIMARY}")

    return bar


def print_status_bar(
    db_status: str = "Not Connected",
    db_type: str = "Database",
    db_name: str = "",
    llm_model: str = "Gemini 1.5",
    schema_tables_count: Optional[int] = None,
    session_queries: int = 0,
    show_palette_hint: bool = True,
) -> None:
    """Print the status bar to console."""
    console.print(render_status_bar(
        db_status=db_status,
        db_type=db_type,
        db_name=db_name,
        llm_model=llm_model,
        schema_tables_count=schema_tables_count,
        session_queries=session_queries,
        show_palette_hint=show_palette_hint,
    ))
