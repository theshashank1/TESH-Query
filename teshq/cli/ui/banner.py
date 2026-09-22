"""
TESH-Query — Minimal Welcome & First-Run Experience.

The first 30 seconds matter. No ASCII art, no giant panels.
Clean, functional, immediately usable.

The user should think: "I can start typing right now."
"""

from __future__ import annotations

from typing import List, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import (
    Colors,
    Icons,
    Spacing,
    ROUNDED_BOX,
    console,
    status_dot,
)
from teshq.cli.ui.status_bar import render_status_bar


# ═══════════════════════════════════════════════════════════════════════════════
#  ASCII WORDMARK — Refined lettering for maximum terminal impact
# ═══════════════════════════════════════════════════════════════════════════════

_WORDMARK = r"""
 ████████╗ ███████╗ ███████╗ ██╗  ██╗  ██████╗ 
 ╚══██╔══╝ ██╔════╝ ██╔════╝ ██║  ██║ ██╔═══██╗
    ██║    █████╗   ███████╗ ███████║ ██║   ██║
    ██║    ██╔══╝   ╚════██║ ██╔══██║ ██║▄▄ ██║
    ██║    ███████╗ ███████║ ██║  ██║ ╚██████╔╝
    ╚═╝    ╚══════╝ ╚══════╝ ╚═╝  ╚═╝  ╚══▀▀═╝ 
"""


def _render_wordmark(version: str = "2.1.1") -> Text:
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
    version: str = "2.1.1",
    subtitle: str = "Natural Language → SQL → Insight",
) -> Panel:
    """
    Build the branded hero banner with gradient wordmark and metadata strip.

    The banner is the *identity moment* — the user should feel like they just
    launched something important, powerful, and beautiful.
    """
    from teshq.cli.ui.theme import GRADIENT_AURORA

    banner = Text()

    # ── Gradient Wordmark ──────────────────────────────────────────────────
    lines = _WORDMARK.strip("\n").split("\n")
    for i, line in enumerate(lines):
        color = GRADIENT_AURORA[i % len(GRADIENT_AURORA)]
        banner.append(f"  {line}\n", style=f"bold {color}")

    # ── Breathing space ────────────────────────────────────────────────────
    banner.append("\n")

    # ── Tagline row ────────────────────────────────────────────────────────
    banner.append(f"    {Icons.sparkle()} ", style=f"bold {Colors.ACCENT}")
    banner.append(subtitle, style=f"bold {Colors.TEXT_PRIMARY}")
    banner.append(f"  {Icons.wave()} ", style=f"{Colors.TEXT_MUTED}")
    banner.append(f"v{version}", style=f"dim italic {Colors.TEXT_TERTIARY}")
    banner.append("\n")

    # ── Credit line ────────────────────────────────────────────────────────
    banner.append(f"    by ", style=f"dim {Colors.TEXT_MUTED}")
    banner.append("treeex", style=f"dim italic {Colors.PRIMARY_HOVER}")
    banner.append(f"  {Icons.arrow_r()} ", style=f"dim {Colors.TEXT_MUTED}")
    banner.append("github.com/theshashank1/TESH-Query", style=f"dim underline {Colors.TEXT_MUTED}")

    return Panel(
        banner,
        border_style=Colors.BORDER_DEFAULT,
        box=ROUNDED_BOX,
        padding=(1, 3),
        title=f"[bold {Colors.PRIMARY}]{Icons.bolt()} TESHQ[/bold {Colors.PRIMARY}]",
        title_align="left",
        subtitle=f"[dim {Colors.TEXT_MUTED}]Autonomous SQL Engine[/dim {Colors.TEXT_MUTED}]",
        subtitle_align="right",
    )


def print_hero_banner(
    version: str = "2.1.1",
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
    console.print()
    for prompt in prompts:
        console.print(
            f"    [{Colors.PRIMARY}]{Icons.prompt()}[/{Colors.PRIMARY}] "
            f"[italic {Colors.TEXT_SECONDARY}]\"{prompt}\"[/italic {Colors.TEXT_SECONDARY}]"
        )
    console.print()
    console.print(
        f"    [{Colors.TEXT_MUTED}]/help shortcuts {Icons.separator()} "
        f"/tables schema {Icons.separator()} "
        f"/search history[/{Colors.TEXT_MUTED}]"
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
