"""
TESH-Query — Contextual AI Hints.

AI surfaces at the moment of need and then recedes.
Not a sidebar, not a chat panel — an intelligent overlay
that appears when errors occur or when the user asks.
"""

from __future__ import annotations

from typing import List, Optional

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from teshq.cli.ui.theme import (
    Colors,
    Icons,
    Spacing,
    ROUNDED_BOX,
    console,
)


def render_ai_explanation(
    explanation: str,
    title: str = "Explanation",
) -> Panel:
    """
    Render an AI explanation block with violet accent.

    Used for /explain command or contextual AI responses.
    """
    content = Text()
    for line in explanation.strip().split("\n"):
        content.append(f"  {line}\n", style=f"{Colors.TEXT_SECONDARY}")

    return Panel(
        content,
        title=f"[{Colors.AI_ACCENT}]{Icons.ai()} {title}[/{Colors.AI_ACCENT}]",
        title_align="left",
        border_style=Colors.AI_ACCENT,
        box=ROUNDED_BOX,
        padding=Spacing.COMPACT,
    )


def print_ai_explanation(
    explanation: str,
    title: str = "Explanation",
) -> None:
    """Print an AI explanation to console."""
    console.print(render_ai_explanation(explanation, title))
    console.print()


def render_table_suggestion(
    attempted_name: str,
    suggestions: List[str],
) -> Text:
    """
    Render a 'did you mean?' suggestion for table names.

    Used when a query references a nonexistent table.
    """
    hint = Text()
    hint.append(f"\n  [{Colors.AI_ACCENT}]Did you mean?[/{Colors.AI_ACCENT}]  ")
    for i, name in enumerate(suggestions[:5]):
        if i > 0:
            hint.append(f" {Icons.separator()} ", style=f"{Colors.TEXT_GHOST}")
        hint.append(name, style=f"bold {Colors.TEXT_SECONDARY}")
    return hint


def render_error_context_hint(
    error_msg: str,
    fix_suggestions: Optional[List[str]] = None,
) -> Panel:
    """
    Render contextual AI-assisted error context.

    Shows what went wrong and suggests specific fixes
    based on error pattern matching.
    """
    content = Text()

    # If we can extract a "did you mean" from the error
    if fix_suggestions:
        content.append(f"  {Icons.ai()} ", style=f"bold {Colors.AI_ACCENT}")
        content.append("Suggested fix\n\n", style=f"bold {Colors.AI_ACCENT}")
        for i, fix in enumerate(fix_suggestions, 1):
            content.append(f"    {i}. ", style=f"{Colors.TEXT_TERTIARY}")
            content.append(f"{fix}\n", style=f"{Colors.TEXT_SECONDARY}")
    else:
        content.append(f"  {Icons.ai()} ", style=f"bold {Colors.AI_ACCENT}")
        content.append(
            "Use /explain for AI-assisted debugging\n",
            style=f"{Colors.TEXT_TERTIARY}",
        )

    return Panel(
        content,
        border_style=Colors.AI_ACCENT,
        box=ROUNDED_BOX,
        padding=Spacing.COMPACT,
    )
