"""
Cinematic Data Grid & Table Formatter for TESH-Query.

Auto-aligned columns, intelligent number formatting, NULL pills,
zebra striping, and pagination — wrapped in a premium card shell.
"""

from decimal import Decimal
from typing import Any, List, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console


# ═══════════════════════════════════════════════════════════════════════════════
#  CELL VALUE FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════════

def _is_number(val: Any) -> bool:
    """Check if a value is numeric."""
    return isinstance(val, (int, float, Decimal))


def _format_cell_value(val: Any) -> Text:
    """
    Format individual table cell values with appropriate styling.

    - NULL → dim pill with dash
    - Booleans → check/cross with color
    - Integers → comma-separated
    - Floats → 2 decimal places, trimmed
    - Strings → truncated at 60 chars
    """
    if val is None:
        return Text("  null  ", style=f"dim italic {Colors.DIM}")

    if isinstance(val, bool):
        if val:
            return Text(f" {Icons.check()} true ", style=f"bold {Colors.SUCCESS}")
        return Text(f" {Icons.cross()} false ", style=f"dim {Colors.ERROR}")

    if isinstance(val, int):
        return Text(f"{val:,}", style=Colors.TEXT)

    if isinstance(val, (float, Decimal)):
        formatted = f"{float(val):,.2f}".rstrip("0").rstrip(".")
        return Text(formatted, style=Colors.TEXT)

    # String or generic object
    s = str(val)
    if len(s) > 60:
        s = s[:57] + "…"
    return Text(s, style=Colors.TEXT_BODY)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS TABLE
# ═══════════════════════════════════════════════════════════════════════════════

def render_results_table(
    headers: List[str],
    rows: List[List[Any]],
    title: str = "Results",
    summary: str = "",
    max_display: int = 25,
) -> Panel:
    """
    Render a premium data grid inside a card panel.

    Features:
      - Auto-detection of numeric columns for right-alignment
      - Zebra striping with surface color alternation
      - Compact index column
      - Pagination footer when rows exceed max_display
    """
    total_rows = len(rows)
    display_rows = rows[:max_display] if total_rows > max_display else rows

    # ── Detect column alignment from first few non-null values ─────────────
    alignments = []
    for col_idx in range(len(headers)):
        col_is_num = False
        for r in display_rows[:5]:
            if col_idx < len(r) and _is_number(r[col_idx]):
                col_is_num = True
                break
        alignments.append("right" if col_is_num else "left")

    # ── Build Rich Table ───────────────────────────────────────────────────
    table = Table(
        show_header=True,
        header_style=f"bold {Colors.PRIMARY}",
        border_style=Colors.BORDER_SUBTLE,
        box=ROUNDED_BOX,
        expand=False,
        show_lines=False,
        row_styles=["", f"on {Colors.SURFACE}"],
    )

    # Index column
    table.add_column(
        "#",
        style=f"dim {Colors.DIM}",
        justify="right",
        width=4,
        no_wrap=True,
    )

    # Data columns
    for h, align in zip(headers, alignments):
        table.add_column(
            h,
            justify=align,
            style=Colors.TEXT,
            overflow="fold",
        )

    # Data rows
    for idx, row in enumerate(display_rows, 1):
        formatted = [_format_cell_value(item) for item in row]
        table.add_row(str(idx), *formatted)

    # ── Card title ─────────────────────────────────────────────────────────
    count_str = f"{total_rows:,} record{'s' if total_rows != 1 else ''}"
    card_title = (
        f"[bold {Colors.TEXT}]{Icons.table()} {title}[/bold {Colors.TEXT}]"
        f"  [{Colors.DIM}]({count_str})[/{Colors.DIM}]"
    )

    # ── Footer ─────────────────────────────────────────────────────────────
    footer = None
    if total_rows > max_display:
        footer = (
            f"[italic {Colors.MUTED}]{Icons.info()} Showing {max_display} of "
            f"{total_rows:,} records · Use --limit or --save-csv to view all[/italic {Colors.MUTED}]"
        )
    elif summary:
        footer = f"[dim {Colors.DIM}]{summary}[/dim {Colors.DIM}]"

    return Panel(
        table,
        title=card_title,
        title_align="left",
        subtitle=footer,
        subtitle_align="right" if footer else "left",
        border_style=Colors.BORDER,
        box=ROUNDED_BOX,
        padding=(0, 1),
    )


def print_results_table(
    headers: List[str],
    rows: List[List[Any]],
    title: str = "Results",
    summary: str = "",
    max_display: int = 25,
) -> None:
    """Print the results table to console."""
    console.print(render_results_table(headers, rows, title, summary, max_display))
