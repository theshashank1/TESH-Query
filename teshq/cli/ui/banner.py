"""
Cinematic Hero Banner, Status HUD, and Cognitive Flow Visuals for TESH-Query.

Creates a breathtaking, award-winning first impression — a terminal splash
that feels like launching a premium developer tool, not a college assignment.
"""

from typing import List, Optional
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.rule import Rule

from teshq.cli.ui.theme import (
    Colors, Icons, GRADIENT_AURORA, GRADIENT_NEON,
    ROUNDED_BOX, HEAVY_BOX, console,
    badge, dim_label, status_dot, gradient_text,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  ASCII WORDMARK — Refined lettering for maximum terminal impact
# ═══════════════════════════════════════════════════════════════════════════════

_WORDMARK = r"""
 ████████╗ ███████╗ ███████╗ ██╗  ██╗       ██████╗  ██╗   ██╗
 ╚══██╔══╝ ██╔════╝ ██╔════╝ ██║  ██║      ██╔═══██╗ ██║   ██║
    ██║    █████╗   ███████╗ ███████║█████╗ ██║   ██║ ██║   ██║
    ██║    ██╔══╝   ╚════██║ ██╔══██║╚════╝ ██║▄▄ ██║ ██║   ██║
    ██║    ███████╗ ███████║ ██║  ██║       ╚██████╔╝ ╚██████╔╝
    ╚═╝    ╚══════╝ ╚══════╝ ╚═╝  ╚═╝        ╚══▀▀═╝   ╚═════╝
"""


def render_hero_banner(
    version: str = "2.1.1",
    subtitle: str = "Natural Language → SQL → Insight",
) -> Panel:
    """
    Build the branded hero banner with gradient wordmark and metadata strip.

    The banner is the *identity moment* — the user should feel like they just
    launched something important and beautiful.
    """
    banner = Text()

    # ── Gradient Wordmark ──────────────────────────────────────────────────
    lines = _WORDMARK.strip("\n").split("\n")
    for i, line in enumerate(lines):
        color = GRADIENT_AURORA[i % len(GRADIENT_AURORA)]
        banner.append(f"{line}\n", style=f"bold {color}")

    # ── Breathing space ────────────────────────────────────────────────────
    banner.append("\n")

    # ── Tagline row ────────────────────────────────────────────────────────
    banner.append(f"    {Icons.sparkle()} ", style=f"bold {Colors.ACCENT}")
    banner.append(subtitle, style=f"bold {Colors.TEXT}")
    banner.append(f"  {Icons.wave()} ", style=f"{Colors.DIM}")
    banner.append(f"v{version}", style=f"dim italic {Colors.MUTED}")
    banner.append("\n")

    # ── Credit line ────────────────────────────────────────────────────────
    banner.append(f"    by ", style=f"dim {Colors.DIM}")
    banner.append("Shashank", style=f"dim italic {Colors.PRIMARY_LIGHT}")
    banner.append(f"  {Icons.arrow_r()} ", style=f"dim {Colors.DIM}")
    banner.append("github.com/theshashank1/TESH-Query", style=f"dim underline {Colors.DIM}")

    return Panel(
        banner,
        border_style=Colors.BORDER,
        box=ROUNDED_BOX,
        padding=(1, 3),
        title=f"[bold {Colors.PRIMARY}]{Icons.bolt()} TESH-QUERY[/bold {Colors.PRIMARY}]",
        title_align="left",
        subtitle=f"[dim {Colors.DIM}]Autonomous SQL Engine[/dim {Colors.DIM}]",
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
#  STATUS HUD  — Environment Readiness Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def render_hud(
    db_status: str = "Ready",
    db_type: str = "PostgreSQL",
    llm_model: str = "Gemini 1.5",
    schema_tables_count: Optional[int] = None,
) -> Panel:
    """
    Render a 3-pill status bar showing database, AI engine, and schema status.

    Each pill uses semantic coloring so users can glance-and-know.
    """
    grid = Table.grid(expand=True, padding=(0, 3))
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right", ratio=1)

    # ── Database Pill ──────────────────────────────────────────────────────
    is_error = "error" in db_status.lower() or "not" in db_status.lower()
    db_dot = status_dot("error" if is_error else "ok")
    db_cell = Text.from_markup(
        f"{db_dot} [{Colors.DIM}]DATABASE[/{Colors.DIM}]  "
        f"[bold {Colors.TEXT}]{db_type}[/bold {Colors.TEXT}] "
        f"[dim {Colors.MUTED}]{Icons.bullet()} {db_status}[/dim {Colors.MUTED}]"
    )

    # ── AI Engine Pill ─────────────────────────────────────────────────────
    ai_dot = f"[bold {Colors.SECONDARY}]{Icons.brain()}[/bold {Colors.SECONDARY}]"
    llm_cell = Text.from_markup(
        f"{ai_dot} [{Colors.DIM}]AI ENGINE[/{Colors.DIM}]  "
        f"[bold {Colors.PRIMARY_LIGHT}]{llm_model}[/bold {Colors.PRIMARY_LIGHT}]"
    )

    # ── Schema Pill ────────────────────────────────────────────────────────
    if schema_tables_count is not None and schema_tables_count > 0:
        schema_label = f"{schema_tables_count} tables"
        s_dot = status_dot("ok")
    else:
        schema_label = "run introspect"
        s_dot = status_dot("warn")
    schema_cell = Text.from_markup(
        f"{s_dot} [{Colors.DIM}]SCHEMA[/{Colors.DIM}]  "
        f"[bold {Colors.TEXT_MUTED}]{schema_label}[/bold {Colors.TEXT_MUTED}]"
    )

    grid.add_row(db_cell, llm_cell, schema_cell)

    return Panel(
        grid,
        border_style=Colors.BORDER_SUBTLE,
        box=ROUNDED_BOX,
        padding=(0, 2),
    )


def print_hud(
    db_status: str = "Ready",
    db_type: str = "PostgreSQL",
    llm_model: str = "Gemini 1.5",
    schema_tables_count: Optional[int] = None,
) -> None:
    """Print the Heads-Up Display to console."""
    console.print(render_hud(db_status, db_type, llm_model, schema_tables_count))


# ═══════════════════════════════════════════════════════════════════════════════
#  SUGGESTED PROMPTS  — Anti-blank-slate anxiety
# ═══════════════════════════════════════════════════════════════════════════════

def print_suggested_prompts(prompts: Optional[List[str]] = None) -> None:
    """
    Display inspirational example queries to eliminate the blank-slate anxiety.

    Psychologically, showing 3 examples triggers "if they can do it, so can I" thinking.
    """
    if not prompts:
        prompts = [
            "Show me top 5 customers by total revenue",
            "Which products are low on inventory or out of stock?",
            "Compare monthly orders this quarter vs last quarter",
        ]

    console.print()
    console.print(
        f"  [{Colors.MUTED}]{Icons.sparkles()} Try asking anything in plain English:[/{Colors.MUTED}]"
    )
    console.print()
    for prompt in prompts:
        console.print(
            f"    [{Colors.PRIMARY}]{Icons.chevron()}[/{Colors.PRIMARY}] "
            f"[italic {Colors.TEXT_BODY}]\"{prompt}\"[/italic {Colors.TEXT_BODY}]"
        )
    console.print()
    console.print(
        f"    [{Colors.DIM}]{Icons.info()} Type [bold {Colors.PRIMARY}]/help[/bold {Colors.PRIMARY}] "
        f"for shortcuts · [bold {Colors.PRIMARY}]/tables[/bold {Colors.PRIMARY}] "
        f"for schema · [bold {Colors.PRIMARY}]exit[/bold {Colors.PRIMARY}] to quit[/{Colors.DIM}]"
    )
    console.print()


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
    # Mini progress indicator
    filled = step_idx
    remaining = total_steps - step_idx
    bar = f"[{Colors.PRIMARY}]{'●' * filled}[/{Colors.PRIMARY}][{Colors.GHOST}]{'○' * remaining}[/{Colors.GHOST}]"

    text = Text()
    text.append(f"  {bar} ", style="")
    text.append(f" {title} ", style=f"bold {Colors.TEXT}")
    if detail:
        text.append(f"— {detail}", style=f"dim {Colors.MUTED}")
    console.print(text)
