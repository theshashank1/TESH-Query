"""
TESH-Query — Unified CLI UI Engine.

Single import surface for the "Obsidian Instrument" design system:
  - theme:      Colors, Icons, surfaces, spacing, typography
  - banner:     Compact hero, inline HUD, suggested prompts
  - cards:      SQL cards, telemetry strip, diagnostic errors
  - tables:     Data grid with intelligent formatting
  - blocks:     Command block system (signature interaction)
  - status_bar: Ambient system awareness
  - palette:    Command palette / inline search
  - ai_context: Contextual AI hints
  - helpers:    status spinner, success, warning, error, tip, info
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from rich.panel import Panel
from rich.rule import Rule
from rich.status import Status
from rich.text import Text

from teshq.cli.ui.banner import (
    print_cognitive_step,
    print_hero_banner,
    print_hud,
    print_suggested_prompts,
    render_hero_banner,
    render_hud,
)
from teshq.cli.ui.cards import (
    print_error_card,
    print_metrics,
    print_sql_card,
    print_success_card,
    render_error_card,
    render_metrics_panel,
    render_sql_card,
)
from teshq.cli.ui.tables import (
    print_results_table,
    render_results_table,
)
from teshq.cli.ui.blocks import (
    CommandBlock,
    StageTracker,
    render_command_block,
    render_telemetry_strip,
    print_telemetry_strip,
    render_action_hints,
    render_stage_line,
    print_stages_progress,
    QUERY_STAGES,
    DRY_RUN_STAGES,
    INTROSPECT_STAGES,
)
from teshq.cli.ui.status_bar import (
    render_status_bar,
    print_status_bar,
)
from teshq.cli.ui.palette import (
    render_command_list,
    render_help_sheet,
    print_help_sheet,
    fuzzy_match,
    SLASH_COMMANDS,
)
from teshq.cli.ui.ai_context import (
    render_ai_explanation,
    print_ai_explanation,
    render_table_suggestion,
    render_error_context_hint,
)
from teshq.cli.ui.theme import (
    Colors,
    Icons,
    Typography,
    Spacing,
    ROUNDED_BOX,
    SIMPLE_BOX,
    HEAVY_BOX,
    GRADIENT_AURORA,
    GRADIENT_NEON,
    GRADIENT_OCEAN,
    GRADIENT_SUNSET,
    console,
    err_console,
    badge,
    dim_label,
    status_dot,
    progress_bar,
    gradient_text,
    latency_color,
)

# ---------------------------------------------------------------------------
# Section Headers / Footers
# ---------------------------------------------------------------------------


def print_header(title: str, level: int = 1) -> None:
    """Print a styled section header.

    Args:
        title: The header text to display.
        level: 1 = top-level (Rule), 2 = sub-section.
    """
    if level == 1:
        console.print()
        console.print(
            Rule(
                f"[bold {Colors.PRIMARY}]{title}[/bold {Colors.PRIMARY}]",
                style=Colors.BORDER_DEFAULT,
            )
        )
        console.print()
    else:
        console.print()
        console.print(
            f"[bold {Colors.PRIMARY_HOVER}]{Icons.prompt()} {title}"
            f"[/bold {Colors.PRIMARY_HOVER}]"
        )
        console.print()


def print_footer(message: str = "") -> None:
    """Print a styled footer line."""
    console.print()
    if message:
        console.print(Rule(f"[dim]{message}[/dim]", style=Colors.BORDER_SUBTLE))
    else:
        console.print(Rule(style=Colors.BORDER_SUBTLE))
    console.print()


def print_divider(text: str = "") -> None:
    """Print a styled horizontal divider line."""
    if text:
        console.print(
            Rule(
                f"[dim {Colors.TEXT_TERTIARY}]{text}[/dim {Colors.TEXT_TERTIARY}]",
                style=Colors.BORDER_SUBTLE,
            )
        )
    else:
        console.print(Rule(style=Colors.BORDER_SUBTLE))


# ---------------------------------------------------------------------------
# Status Spinner Context Manager
# ---------------------------------------------------------------------------


@contextmanager
def status(
    message: str,
    success_message: Optional[str] = None,
    spinner: str = "dots",
) -> Generator[Status, None, None]:
    """Context manager that displays a spinner while work is in progress.

    Args:
        message: Text shown while the spinner is active.
        success_message: Text shown on success (checkmark prefix).
        spinner: Rich spinner name (default 'dots').
    """
    with Status(
        f"[{Colors.PRIMARY}]{message}[/{Colors.PRIMARY}]",
        spinner=spinner,
        console=console,
    ) as _s:
        try:
            yield _s
        except Exception:
            raise

    if success_message:
        console.print(
            f"[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] "
            f"[bold {Colors.TEXT_PRIMARY}]{success_message}"
            f"[/bold {Colors.TEXT_PRIMARY}]"
        )


# ---------------------------------------------------------------------------
# Message Printers
# ---------------------------------------------------------------------------


def error(message: str) -> None:
    """Print an error message to stderr."""
    err_console.print(
        f"[bold {Colors.ERROR}]{Icons.cross()} Error:[/bold {Colors.ERROR}] {message}"
    )


def warning(message: str) -> None:
    """Print a warning message to stderr."""
    err_console.print(
        f"[bold {Colors.WARNING}]{Icons.warn()} Warning:[/bold {Colors.WARNING}] "
        f"{message}"
    )


def tip(message: str) -> None:
    """Print a helpful tip / info message."""
    console.print(f"[{Colors.INFO}]{Icons.info()} {message}[/{Colors.INFO}]")


def success(message: str) -> None:
    """Print a success message."""
    console.print(
        f"[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] {message}"
    )


def info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[{Colors.TEXT_TERTIARY}]{message}[/{Colors.TEXT_TERTIARY}]")


def handle_error(
    exc: Exception,
    context: str = "Command",
    suggest_action: Optional[str] = None,
    show_traceback: bool = False,
) -> None:
    """Display a diagnostic error card."""
    print_error_card(
        exc,
        context=context,
        suggest_action=suggest_action,
        show_traceback=show_traceback,
    )


# Backward-compatible aliases
print_sql = print_sql_card
