"""
TESH-Query — Data Grid & Table Formatter.

Clean, high-density data presentation with intelligent formatting.
NULL as em-dash, booleans as symbols, right-aligned numbers,
subtle zebra striping, and caption-position row count.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import Colors, Icons, Spacing, ROUNDED_BOX, console


# ═══════════════════════════════════════════════════════════════════════════════
#  CELL VALUE FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════════

def _is_number(val: Any) -> bool:
    """Check if a value is numeric."""
    return isinstance(val, (int, float, Decimal))


def _format_cell_value(val: Any) -> Text:
    """
    Format individual table cell values with appropriate styling.

    - NULL → em-dash (—)
    - Booleans → ✓ / ✗ (symbol, not color-dependent)
    - Integers → comma-separated
    - Floats → 2 decimal places, trimmed
    - Strings → truncated at 80 chars
    """
    if val is None:
        return Text("—", style=f"dim {Colors.TEXT_MUTED}")

    if isinstance(val, bool):
        if val:
            return Text(Icons.check(), style=f"bold {Colors.SUCCESS}")
        return Text(Icons.cross(), style=f"dim {Colors.TEXT_MUTED}")

    if isinstance(val, int):
        return Text(f"{val:,}", style=Colors.TEXT_SECONDARY)

    if isinstance(val, (float, Decimal)):
        formatted = f"{float(val):,.2f}".rstrip("0").rstrip(".")
        return Text(formatted, style=Colors.TEXT_SECONDARY)

    # String or generic object
    s = str(val)
    if len(s) > 80:
        s = s[:77] + "…"
    return Text(s, style=Colors.TEXT_SECONDARY)


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
    Render a clean data grid inside a panel.

    Features:
      - Auto-detection of numeric columns for right-alignment
      - Subtle zebra striping with surface color alternation
      - Compact index column
      - Row count in caption position
      - Pagination footer when rows exceed max_display
    """
    total_rows = len(rows)
    display_rows = rows[:max_display] if total_rows > max_display else rows

    # ── Detect column alignment from first few non-null values ────────
    alignments = []
    for col_idx in range(len(headers)):
        col_is_num = False
        for r in display_rows[:5]:
            if col_idx < len(r) and _is_number(r[col_idx]):
                col_is_num = True
                break
        alignments.append("right" if col_is_num else "left")

    # ── Build Rich Table ──────────────────────────────────────────────
    table = Table(
        show_header=True,
        header_style=f"bold {Colors.PRIMARY}",
        border_style=Colors.BORDER_SUBTLE,
        box=ROUNDED_BOX,
        expand=False,
        show_lines=False,
        row_styles=["", f"on {Colors.SURFACE_1}"],
    )

    # Index column
    table.add_column(
        "#",
        style=f"dim {Colors.TEXT_MUTED}",
        justify="right",
        width=4,
        no_wrap=True,
    )

    # Data columns
    for h, align in zip(headers, alignments):
        table.add_column(
            h,
            justify=align,
            style=Colors.TEXT_SECONDARY,
            overflow="fold",
        )

    # Data rows
    for idx, row in enumerate(display_rows, 1):
        formatted = [_format_cell_value(item) for item in row]
        table.add_row(str(idx), *formatted)

    # ── Card title ────────────────────────────────────────────────────
    count_str = f"{total_rows:,} record{'s' if total_rows != 1 else ''}"
    card_title = (
        f"[{Colors.TEXT_TERTIARY}]{title}[/{Colors.TEXT_TERTIARY}]"
        f"  [{Colors.TEXT_MUTED}]({count_str})[/{Colors.TEXT_MUTED}]"
    )

    # ── Footer ────────────────────────────────────────────────────────
    footer = None
    if total_rows > max_display:
        footer = (
            f"[{Colors.TEXT_MUTED}]Showing {max_display} of "
            f"{total_rows:,} records {Icons.separator()} "
            f"Use --limit or /export to view all[/{Colors.TEXT_MUTED}]"
        )
    elif summary:
        footer = f"[{Colors.TEXT_MUTED}]{summary}[/{Colors.TEXT_MUTED}]"

    return Panel(
        table,
        title=card_title,
        title_align="left",
        subtitle=footer,
        subtitle_align="right" if footer else "left",
        border_style=Colors.BORDER_SUBTLE,
        box=ROUNDED_BOX,
        padding=Spacing.COMPACT,
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
