"""
CLI UI helpers for TESH-Query.

Provides Rich-based terminal output utilities used across all CLI commands:
  - print_header / print_footer  — section banners
  - status                       — spinner context manager
  - error / warning / tip        — styled message printers
  - handle_error                 — structured exception display
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Generator, Optional

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

# Single shared console instance for the whole CLI
console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Section headers / footers
# ---------------------------------------------------------------------------


def print_header(title: str, level: int = 1) -> None:
    """Print a styled section header.

    Args:
        title: The header text to display.
        level: 1 = top-level banner (Rule), 2 = sub-section (Panel lite).
    """
    if level == 1:
        from rich.rule import Rule
        console.print()
        console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))
        console.print()
    else:
        console.print()
        console.print(f"[bold blue]▸ {title}[/bold blue]")
        console.print()


def print_footer(message: str = "") -> None:
    """Print a styled footer / completion line."""
    from rich.rule import Rule
    console.print()
    if message:
        console.print(Rule(f"[dim]{message}[/dim]", style="dim"))
    else:
        console.print(Rule(style="dim"))
    console.print()


# ---------------------------------------------------------------------------
# Status spinner context manager
# ---------------------------------------------------------------------------


@contextmanager
def status(
    message: str,
    success_message: Optional[str] = None,
    spinner: str = "dots",
) -> Generator[None, None, None]:
    """Context manager that shows a spinner while work is in progress.

    On clean exit it prints the *success_message* (if provided) in green.
    On exception the spinner stops and the caller is responsible for
    printing the error via ``handle_error()``.

    Args:
        message: Text shown while the spinner is active.
        success_message: Text shown on success (green checkmark prefix).
        spinner: Rich spinner name (default ``"dots"``).
    """
    with Status(f"[cyan]{message}[/cyan]", spinner=spinner, console=console) as _s:
        try:
            yield
        except Exception:
            raise  # let the caller handle it

    if success_message:
        console.print(f"[green]✓[/green] {success_message}")


# ---------------------------------------------------------------------------
# Message printers
# ---------------------------------------------------------------------------


def error(message: str) -> None:
    """Print an error message to stderr in red."""
    err_console.print(f"[bold red]✗ Error:[/bold red] {message}")


def warning(message: str) -> None:
    """Print a warning message to stderr in yellow."""
    err_console.print(f"[bold yellow]⚠ Warning:[/bold yellow] {message}")


def tip(message: str) -> None:
    """Print a helpful tip / info message to stdout in dim cyan."""
    console.print(f"[dim cyan]ℹ {message}[/dim cyan]")


# ---------------------------------------------------------------------------
# Structured exception display
# ---------------------------------------------------------------------------


def handle_error(
    exc: Exception,
    context: str = "Command",
    suggest_action: Optional[str] = None,
) -> None:
    """Display a structured error panel for an unhandled exception.

    Args:
        exc: The exception that was raised.
        context: Human-readable name for the operation that failed.
        suggest_action: Optional actionable advice shown below the error.
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    lines = [
        f"[bold]{context}[/bold] failed",
        "",
        f"[dim]{exc_type}:[/dim] {exc_msg}",
    ]
    if suggest_action:
        lines += ["", f"[italic]{suggest_action}[/italic]"]

    panel = Panel(
        "\n".join(lines),
        title="[bold red]Error[/bold red]",
        border_style="red",
        padding=(1, 2),
    )
    err_console.print(panel)
