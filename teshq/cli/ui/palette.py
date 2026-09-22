"""
TESH-Query — Command Palette / Inline Search.

Fuzzy-search interface for slash commands, history, and schema.
Since we're using Rich (not Textual), this is implemented as a
prompted inline search with formatted results.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console


# ── Slash command registry ────────────────────────────────────────────────────

SLASH_COMMANDS: List[Tuple[str, str]] = [
    ("/tables",          "Explore database schema tree"),
    ("/schema [name]",   "Inspect columns and foreign keys"),
    ("/sql",             "Show last generated SQL"),
    ("/copy [sql|results]", "Copy SQL or results to clipboard"),
    ("/rerun",           "Rerun last query"),
    ("/export <fmt>",    "Export results (csv, excel)"),
    ("/explain",         "Show execution breakdown"),
    ("/search <text>",   "Search command history"),
    ("/history",         "Show session command history"),
    ("/model [name]",    "Show or switch AI provider"),
    ("/clear",           "Clear screen & command history"),
    ("/help",            "Show command guide"),
]


def fuzzy_match(query: str, text: str) -> bool:
    """Simple fuzzy match: all chars of query appear in order in text."""
    query = query.lower()
    text = text.lower()
    qi = 0
    for char in text:
        if qi < len(query) and char == query[qi]:
            qi += 1
    return qi == len(query)


def render_command_list(
    filter_query: str = "",
    extra_items: Optional[List[Tuple[str, str]]] = None,
) -> Table:
    """
    Render a filtered list of available commands.

    Used for /help and as inline search results.
    """
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=False,
    )
    table.add_column(style=f"bold {Colors.PRIMARY}", width=20, no_wrap=True)
    table.add_column(style=f"{Colors.TEXT_TERTIARY}")

    items = list(SLASH_COMMANDS)
    if extra_items:
        items.extend(extra_items)

    for cmd, desc in items:
        if filter_query and not fuzzy_match(filter_query, f"{cmd} {desc}"):
            continue
        table.add_row(cmd, desc)

    return table


def render_help_sheet() -> Text:
    """
    Render the complete inline help guide.

    Categorized: Commands, Keyboard, Tips
    """
    output = Text()

    # ── Commands ──────────────────────────────────────────────────────
    output.append("\n  Commands\n", style=f"bold {Colors.TEXT_PRIMARY}")
    for cmd, desc in SLASH_COMMANDS:
        output.append(f"    {cmd:<20s}", style=f"bold {Colors.PRIMARY}")
        output.append(f" {desc}\n", style=f"{Colors.TEXT_TERTIARY}")

    # ── Keyboard ──────────────────────────────────────────────────────
    output.append("\n  Keyboard\n", style=f"bold {Colors.TEXT_PRIMARY}")
    shortcuts = [
        ("Ctrl+C",  "Cancel current operation"),
        ("Ctrl+D",  "Exit session"),
        ("↑ / ↓",   "Navigate command history"),
    ]
    for key, desc in shortcuts:
        output.append(f"    {key:<20s}", style=f"bold {Colors.PRIMARY}")
        output.append(f" {desc}\n", style=f"{Colors.TEXT_TERTIARY}")

    # ── Tips ──────────────────────────────────────────────────────────
    output.append("\n  Tips\n", style=f"bold {Colors.TEXT_PRIMARY}")
    tips = [
        "Follow-up queries automatically use context from your last query.",
        'Use "now filter by..." or "also show..." for refinements.',
        "Type exit, quit, or :q to leave the session.",
    ]
    for tip_text in tips:
        output.append(f"    {Icons.bullet()} ", style=f"{Colors.TEXT_MUTED}")
        output.append(f"{tip_text}\n", style=f"{Colors.TEXT_TERTIARY}")

    return output


def print_help_sheet() -> None:
    """Print the help guide to console."""
    console.print(render_help_sheet())
    console.print()
