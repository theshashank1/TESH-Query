"""
TESH-Query — Unified Cinematic CLI UI Engine.

Single import surface for the entire design system:
  - theme:   Colors, Icons, gradients, box styles, micro-components
  - banner:  Hero banner, HUD, suggested prompts, cognitive steps
  - cards:   SQL cards, execution metrics, empathetic error panels
  - tables:  Results grid with auto-alignment and pagination
  - helpers: status spinner, success, warning, error, tip, info
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
from teshq.cli.ui.theme import (
    Colors,
    Icons,
    ROUNDED_BOX,
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
)

# ---------------------------------------------------------------------------
# Section Headers / Footers
# ---------------------------------------------------------------------------


def print_header(title: str, level: int = 1) -> None:
    """Print a styled section header.

    Args:
        title: The header text to display.
        level: 1 = top-level banner (Rule), 2 = sub-section.
    """
    if level == 1:
        console.print()
        console.print(Rule(f"[bold {Colors.PRIMARY}]{title}[/bold {Colors.PRIMARY}]", style=Colors.BORDER))
        console.print()
    else:
        console.print()
        console.print(f"[bold {Colors.PRIMARY_LIGHT}]{Icons.chevron()} {title}[/bold {Colors.PRIMARY_LIGHT}]")
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
        console.print(Rule(f"[dim {Colors.MUTED}]{text}[/dim {Colors.MUTED}]", style=Colors.BORDER_SUBTLE))
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
) -> Generator[None, None, None]:
    """Context manager that displays a stylish spinner while work is in progress.

    Args:
        message: Text shown while the spinner is active.
        success_message: Text shown on success (green checkmark prefix).
        spinner: Rich spinner name (default 'dots').
    """
    with Status(f"[{Colors.PRIMARY}]{message}[/{Colors.PRIMARY}]", spinner=spinner, console=console) as _s:
        try:
            yield
        except Exception:
            raise

    if success_message:
        console.print(f"[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] [bold {Colors.TEXT}]{success_message}[/bold {Colors.TEXT}]")


# ---------------------------------------------------------------------------
# Message Printers
# ---------------------------------------------------------------------------


def error(message: str) -> None:
    """Print an error message to stderr in rose red."""
    err_console.print(f"[bold {Colors.ERROR}]{Icons.cross()} Error:[/bold {Colors.ERROR}] {message}")


def warning(message: str) -> None:
    """Print a warning message to stderr in amber."""
    err_console.print(f"[bold {Colors.WARNING}]{Icons.warn()} Warning:[/bold {Colors.WARNING}] {message}")


def tip(message: str) -> None:
    """Print a helpful tip / info message in soft cyan."""
    console.print(f"[{Colors.INFO}]{Icons.info()} {message}[/{Colors.INFO}]")


def success(message: str) -> None:
    """Print a success message in vibrant emerald green."""
    console.print(f"[bold {Colors.SUCCESS}]{Icons.check()}[/bold {Colors.SUCCESS}] {message}")


def info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[{Colors.MUTED}]{message}[/{Colors.MUTED}]")


def handle_error(
    exc: Exception,
    context: str = "Command",
    suggest_action: Optional[str] = None,
    show_traceback: bool = False,
) -> None:
    """Display an empathetic, self-healing error card."""
    print_error_card(exc, context=context, suggest_action=suggest_action, show_traceback=show_traceback)


# Backward-compatible aliases
print_sql = print_sql_card
