"""
TESH-Query — Minimal Welcome & First-Run Experience.

The first 30 seconds matter. No ASCII art, no giant panels.
Clean, functional, immediately usable.

The user should think: "I can start typing right now."
"""

from __future__ import annotations

from typing import List, Optional

from rich.panel import Panel
from rich.text import Text

from teshq.cli.ui.theme import (
    Colors,
    Icons,
    ROUNDED_BOX,
    console,
)

from teshq.cli.ui.status_bar import render_status_bar


def _render_wordmark(version: str = "3.0.0.dev1") -> Text:
    """Render the product identity in a single clean line."""
    mark = Text()
    mark.append("  tesh", style=f"bold {Colors.TEXT_PRIMARY}")
    mark.append("·", style=f"{Colors.TEXT_GHOST}")
    mark.append("query", style=f"bold {Colors.PRIMARY}")
    mark.append(f" v{version}", style=f"dim {Colors.TEXT_MUTED}")
    return mark


def _render_tagline(subtitle: str = "Natural Language → SQL → Insight") -> Text:
    """Render the product tagline."""
    tag = Text()
    tag.append(f"  {subtitle}", style=f"{Colors.TEXT_TERTIARY}")
    return tag


# ═══════════════════════════════════════════════════════════════════════════════
#  HERO BANNER — Iconic Gradient Wordmark & Branded Metadata Strip
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero_banner(
    version: str = "3.0.0.dev1",
    subtitle: str = "Natural Language → SQL → Insight",
) -> Panel:
    """
    Build the branded hero banner with sleek precision typography.
    Inspired by OpenCode / Antigravity minimal aesthetic.
    """
    banner = Text()
    banner.append(" ⟡  ", style=f"bold {Colors.PRIMARY_HOVER}")
    banner.append("TESH", style=f"bold {Colors.TEXT_PRIMARY}")
    banner.append("·", style=f"bold {Colors.PRIMARY}")
    banner.append("Query", style=f"bold {Colors.TEXT_PRIMARY}")
    banner.append(f"  v{version}", style=f"dim {Colors.TEXT_TERTIARY}")
    banner.append(f"   {Icons.bullet()}   ", style=f"{Colors.TEXT_GHOST}")
    banner.append("Autonomous Natural Language SQL Engine\n", style=f"{Colors.TEXT_SECONDARY}")
    banner.append(f"    {subtitle}", style=f"dim {Colors.TEXT_TERTIARY}")

    return Panel(
        banner,
        border_style=Colors.BORDER_FOCUS,
        box=ROUNDED_BOX,
        padding=(0, 2),
        expand=False,
    )


def print_hero_banner(
    version: str = "3.0.0.dev1",
    subtitle: str = "Natural Language → SQL → Insight",
) -> None:
    """Print the hero banner to console."""
    console.print()
    console.print(render_hero_banner(version=version, subtitle=subtitle))


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS HUD — Inline environment readiness
# ═══════════════════════════════════════════════════════════════════════════════

def render_hud(
    db_status: str = "Ready",
    db_type: str = "PostgreSQL",
    llm_model: str = "Gemini 1.5",
    schema_tables_count: Optional[int] = None,
) -> Text:
    """
    Render environment status as a single inline line.

    Example:
      ● SQLite Connected · ◎ Gemini 1.5 Pro · 12 tables
    """
    return render_status_bar(
        db_status=db_status,
        db_type=db_type,
        llm_model=llm_model,
        schema_tables_count=schema_tables_count,
        session_queries=0,
        show_palette_hint=False,
    )


def print_hud(
    db_status: str = "Ready",
    db_type: str = "PostgreSQL",
    llm_model: str = "Gemini 1.5",
    schema_tables_count: Optional[int] = None,
) -> None:
    """Print the inline HUD."""
    console.print(render_hud(db_status, db_type, llm_model, schema_tables_count))


# ═══════════════════════════════════════════════════════════════════════════════
#  SUGGESTED PROMPTS — Anti-blank-slate
# ═══════════════════════════════════════════════════════════════════════════════

def print_suggested_prompts(prompts: Optional[List[str]] = None) -> None:
    """
    Display example queries to eliminate blank-slate anxiety.

    3 prompts using the actual prompt character — instantly
    communicates "you can type things like this."
    """
    if not prompts:
        prompts = [
            "Show me top 5 customers by total revenue",
            "Which products are low on inventory or out of stock?",
            "Compare monthly orders this quarter vs last quarter",
        ]

    console.print()
    console.print(
        f"  [{Colors.TEXT_TERTIARY}]Ask anything in natural English:[/{Colors.TEXT_TERTIARY}]"
    )
    for prompt in prompts:
        console.print(
            f"    [{Colors.PRIMARY_HOVER}]◇[/{Colors.PRIMARY_HOVER}] "
            f"[{Colors.TEXT_SECONDARY}]\"{prompt}\"[/{Colors.TEXT_SECONDARY}]"
        )
    console.print()
    console.print(
        f"  [{Colors.TEXT_MUTED}]Commands: "
        f"[bold {Colors.PRIMARY}]/help[/bold {Colors.PRIMARY}] {Icons.separator()} "
        f"[bold {Colors.PRIMARY}]/tables[/bold {Colors.PRIMARY}] {Icons.separator()} "
        f"[bold {Colors.PRIMARY}]/sql[/bold {Colors.PRIMARY}] {Icons.separator()} "
        f"[bold {Colors.PRIMARY}]/export[/bold {Colors.PRIMARY}] {Icons.separator()} "
        f"[bold {Colors.PRIMARY}]/clear[/bold {Colors.PRIMARY}]"
        f"[/{Colors.TEXT_MUTED}]"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  COGNITIVE MILESTONES — Progress Storytelling
# ═══════════════════════════════════════════════════════════════════════════════

def print_cognitive_step(
    step_idx: int,
    total_steps: int,
    title: str,
    detail: str = "",
) -> None:
    """Render a humanized cognitive milestone step with visual progress."""
    filled = step_idx
    remaining = total_steps - step_idx
    bar = (
        f"[{Colors.PRIMARY}]{'●' * filled}[/{Colors.PRIMARY}]"
        f"[{Colors.TEXT_GHOST}]{'○' * remaining}[/{Colors.TEXT_GHOST}]"
    )

    text = Text()
    text.append(f"  {bar} ", style="")
    text.append(f" {title} ", style=f"bold {Colors.TEXT_PRIMARY}")
    if detail:
        text.append(f"— {detail}", style=f"dim {Colors.TEXT_TERTIARY}")
    console.print(text)
