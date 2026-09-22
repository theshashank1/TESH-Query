"""
TESH-Query — Command Block System.

The signature interaction: every query execution becomes a structured,
addressable unit with inline actions and collapsible sections.

A command block contains:
  - The natural language query (prompt)
  - Cognitive progress stages
  - Generated SQL
  - Query results table
  - Execution telemetry (single-line strip)
  - Action hints
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from rich.columns import Columns
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import (
    Colors,
    Icons,
    Spacing,
    Typography,
    ROUNDED_BOX,
    console,
    latency_color,
    status_dot,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  COGNITIVE STAGES — Progress Narrative
# ═══════════════════════════════════════════════════════════════════════════════

# 6 stages so the user feels the engine working (per user feedback)
QUERY_STAGES = [
    "Parsing natural language",
    "Analyzing schema",
    "Selecting relevant tables",
    "Generating SQL",
    "Validating query",
    "Executing against database",
]

DRY_RUN_STAGES = [
    "Parsing natural language",
    "Analyzing schema",
    "Selecting relevant tables",
    "Generating SQL",
    "Validating query",
]

INTROSPECT_STAGES = [
    "Connecting to database",
    "Reading table metadata",
    "Detecting relationships",
    "Building schema graph",
    "Writing schema cache",
]


def render_stage_line(stage_text: str, state: str = "active") -> Text:
    """
    Render a single cognitive stage line.

    States: 'active' (spinning), 'done' (check), 'pending' (dim)
    """
    line = Text()
    if state == "done":
        line.append(f"  {Icons.check()} ", style=f"bold {Colors.SUCCESS}")
        line.append(stage_text, style=f"{Colors.TEXT_TERTIARY}")
    elif state == "active":
        line.append(f"  {Icons.dot_pulse()} ", style=f"bold {Colors.PRIMARY}")
        line.append(stage_text, style=f"{Colors.TEXT_SECONDARY}")
    else:  # pending
        line.append(f"  {Icons.dot_empty()} ", style=f"{Colors.TEXT_GHOST}")
        line.append(stage_text, style=f"{Colors.TEXT_GHOST}")
    return line


def print_stages_progress(stages: List[str], current_idx: int) -> None:
    """Print all stages with appropriate states."""
    for i, stage in enumerate(stages):
        if i < current_idx:
            console.print(render_stage_line(stage, "done"))
        elif i == current_idx:
            console.print(render_stage_line(stage, "active"))
        else:
            console.print(render_stage_line(stage, "pending"))


# ═══════════════════════════════════════════════════════════════════════════════
#  LIVE COGNITIVE STAGE TRACKER — Dynamic Operation Display
# ═══════════════════════════════════════════════════════════════════════════════

class StageTracker:
    """
    Live cognitive progress display for query execution.

    Renders each stage with its true operational state in a pixel-aligned grid:
      ✓ Completed stages (emerald checkmark, dimmed text, operation detail)
      ⠋ Active stage (animated spinner, bold text, live operation description)
      ◦ Pending stages (ghost hollow dot, dim text)
      ✗ Failed stage (red cross, error message)
    """

    def __init__(
        self,
        stages: Optional[List[str]] = None,
        console: Optional[Any] = None,
    ):
        from teshq.cli.ui.theme import console as default_console
        self.stages = list(stages or QUERY_STAGES)
        self.console = console or default_console
        self.current_idx = 0
        self.current_detail = ""
        self.stage_details: Dict[int, str] = {}
        self.failed_idx: Optional[int] = None
        self._live: Optional[Live] = None

    def _render(self) -> Table:
        grid = Table.grid(padding=(0, 1))
        grid.add_column(width=4, justify="right")
        grid.add_column()

        for i, s in enumerate(self.stages):
            if self.failed_idx is not None and i == self.failed_idx:
                grid.add_row(
                    Text(Icons.cross(), style=f"bold {Colors.ERROR}"),
                    Text.assemble(
                        (s, f"bold {Colors.ERROR}"),
                        (f" — {self.current_detail}" if self.current_detail else "", f"dim {Colors.ERROR_DIM}"),
                    ),
                )
            elif i < self.current_idx:
                d = self.stage_details.get(i, "")
                label = Text()
                label.append(s, style=f"{Colors.TEXT_TERTIARY}")
                if d and not d.startswith("analyzing") and not d.startswith("ranking"):
                    label.append(f" ({d})", style=f"dim {Colors.TEXT_MUTED}")
                grid.add_row(
                    Text(Icons.check(), style=f"bold {Colors.SUCCESS}"),
                    label,
                )
            elif i == self.current_idx and self.failed_idx is None:
                msg = Text()
                msg.append(s, style=f"bold {Colors.TEXT_PRIMARY}")
                if self.current_detail:
                    msg.append(f" — {self.current_detail}", style=f"italic {Colors.PRIMARY_HOVER}")
                grid.add_row(
                    Spinner("dots", style=f"bold {Colors.PRIMARY}"),
                    msg,
                )
            else:
                grid.add_row(
                    Text(Icons.dot_empty(), style=f"dim {Colors.TEXT_GHOST}"),
                    Text(s, style=f"dim {Colors.TEXT_GHOST}"),
                )
        return grid

    def start(self) -> "StageTracker":
        self.console.print()
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=12,
            transient=False,
        )
        self._live.start()
        return self

    def on_progress(self, step_idx: int, stage_name: str = "", detail: Optional[str] = None) -> None:
        if self.current_idx < step_idx and self.current_detail:
            self.stage_details[self.current_idx] = self.current_detail
        self.current_idx = step_idx
        self.current_detail = detail or ""
        if self._live:
            self._live.update(self._render())

    def finish(self) -> None:
        if self.current_detail and self.current_idx not in self.stage_details:
            self.stage_details[self.current_idx] = self.current_detail
        self.current_idx = len(self.stages)
        self.current_detail = ""
        if self._live:
            self._live.update(self._render())
            self._live.stop()
            self._live = None
        self.console.print()

    def fail(self, error_msg: str = "") -> None:
        self.failed_idx = self.current_idx
        self.current_detail = error_msg
        if self._live:
            self._live.update(self._render())
            self._live.stop()
            self._live = None
        self.console.print()

    def __enter__(self) -> "StageTracker":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.fail(str(exc_val))
        else:
            self.finish()


# ═══════════════════════════════════════════════════════════════════════════════
#  TELEMETRY STRIP — Single-line execution metrics
# ═══════════════════════════════════════════════════════════════════════════════

def render_telemetry_strip(
    row_count: Optional[int] = None,
    total_ms: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    success: bool = True,
) -> Text:
    """
    Render a compact single-line telemetry strip.

    Example: ✓ 5 rows · 127ms · 340 tokens · $0.0003
    """
    strip = Text()

    if success:
        strip.append(f"  {Icons.check()} ", style=f"bold {Colors.SUCCESS}")
    else:
        strip.append(f"  {Icons.cross()} ", style=f"bold {Colors.ERROR}")

    parts = []

    if row_count is not None:
        parts.append(f"{row_count:,} row{'s' if row_count != 1 else ''}")

    if total_ms > 0:
        color = latency_color(total_ms)
        parts.append(f"[{color}]{total_ms:,}ms[/{color}]")

    if total_tokens > 0:
        parts.append(f"{total_tokens:,} tokens")

    if cost_usd > 0:
        parts.append(f"${cost_usd:.4f}")

    strip.append_text(Text.from_markup(
        f" {Icons.separator()} ".join(parts),
        style=f"{Colors.TEXT_TERTIARY}",
    ))

    return strip


def print_telemetry_strip(
    row_count: Optional[int] = None,
    total_ms: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    success: bool = True,
) -> None:
    """Print the telemetry strip to console."""
    console.print(render_telemetry_strip(
        row_count=row_count,
        total_ms=total_ms,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        success=success,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
#  ACTION HINTS — Discoverable inline actions
# ═══════════════════════════════════════════════════════════════════════════════

def render_action_hints(
    actions: Optional[List[str]] = None,
) -> Text:
    """
    Render inline action hints below a command block.

    Actions are displayed as bracketed text hints:
      [Copy SQL] [Export CSV] [Explain] [Rerun]
    """
    if actions is None:
        actions = ["Copy SQL", "Copy Results", "Export CSV", "Explain", "Rerun"]

    hints = Text("  ")
    for i, action in enumerate(actions):
        if i > 0:
            hints.append(" ", style="")
        hints.append(f"[{action}]", style=f"{Colors.TEXT_MUTED}")
    return hints


def render_error_action_hints() -> Text:
    """Action hints for error blocks."""
    return render_action_hints(["Copy Error", "Explain", "Retry", "Docs"])


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMAND BLOCK — The atomic unit of terminal history
# ═══════════════════════════════════════════════════════════════════════════════

class CommandBlock:
    """
    A structured command execution unit.

    Encapsulates: prompt → SQL → results → metrics → actions
    into a single visual block with a left-border indicator.
    """

    _counter = 0  # Session-wide block numbering

    def __init__(
        self,
        query: str,
        block_number: Optional[int] = None,
    ):
        CommandBlock._counter += 1
        self.query = query
        self.number = block_number or CommandBlock._counter
        self._sql: Optional[str] = None
        self._dialect: str = "SQL"
        self._parameters: Optional[Dict[str, Any]] = None
        self._results_table: Optional[Table] = None
        self._row_count: Optional[int] = None
        self._total_ms: int = 0
        self._total_tokens: int = 0
        self._cost_usd: float = 0.0
        self._success: bool = True
        self._error: Optional[str] = None

    @classmethod
    def reset_counter(cls) -> None:
        """Reset block numbering (e.g., on session start)."""
        cls._counter = 0

    def set_sql(
        self,
        sql: str,
        dialect: str = "SQL",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> "CommandBlock":
        self._sql = sql.strip()
        self._dialect = dialect
        self._parameters = parameters
        return self

    def set_results(self, table: Table, row_count: int) -> "CommandBlock":
        self._results_table = table
        self._row_count = row_count
        return self

    def set_metrics(
        self,
        total_ms: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> "CommandBlock":
        self._total_ms = total_ms
        self._total_tokens = total_tokens
        self._cost_usd = cost_usd
        return self

    def set_error(self, error_msg: str) -> "CommandBlock":
        self._success = False
        self._error = error_msg
        return self

    def render(self) -> Panel:
        """Render the complete command block as a Rich Panel with left-border."""
        parts: List[Any] = []

        # ── Query prompt ──────────────────────────────────────────────
        prompt_line = Text()
        prompt_line.append(f" {Icons.prompt()} ", style=f"bold {Colors.PRIMARY}")
        prompt_line.append(self.query, style=f"bold {Colors.TEXT_PRIMARY}")
        parts.append(prompt_line)
        parts.append(Text(""))  # spacer

        # ── SQL ───────────────────────────────────────────────────────
        if self._sql:
            sql_syntax = Syntax(
                self._sql,
                "sql",
                theme="monokai",
                line_numbers=self._sql.count("\n") > 4,
                word_wrap=True,
                padding=(0, 1),
            )
            dialect_label = self._dialect.upper()
            sql_panel = Panel(
                sql_syntax,
                title=f"[{Colors.TEXT_TERTIARY}]SQL[/{Colors.TEXT_TERTIARY}]",
                title_align="left",
                subtitle=f"[{Colors.TEXT_MUTED}]{dialect_label}[/{Colors.TEXT_MUTED}]",
                subtitle_align="right",
                border_style=Colors.BORDER_SUBTLE,
                box=ROUNDED_BOX,
                padding=Spacing.COMPACT,
            )
            parts.append(sql_panel)

            # Parameters
            if self._parameters:
                param_strs = [
                    f"[{Colors.TEXT_MUTED}]{k}[/{Colors.TEXT_MUTED}]="
                    f"[{Colors.PRIMARY_HOVER}]{repr(v)}[/{Colors.PRIMARY_HOVER}]"
                    for k, v in self._parameters.items()
                ]
                params_text = Text.from_markup(
                    f"  [{Colors.TEXT_GHOST}]Params: {', '.join(param_strs)}[/{Colors.TEXT_GHOST}]"
                )
                parts.append(params_text)

            parts.append(Text(""))  # spacer

        # ── Results table ─────────────────────────────────────────────
        if self._results_table is not None:
            parts.append(self._results_table)
            parts.append(Text(""))  # spacer

        # ── Telemetry strip ───────────────────────────────────────────
        if self._success:
            strip = render_telemetry_strip(
                row_count=self._row_count,
                total_ms=self._total_ms,
                total_tokens=self._total_tokens,
                cost_usd=self._cost_usd,
                success=True,
            )
            parts.append(strip)
        elif self._error:
            err_strip = Text()
            err_strip.append(f"  {Icons.cross()} ", style=f"bold {Colors.ERROR}")
            err_strip.append(self._error, style=f"{Colors.TEXT_SECONDARY}")
            parts.append(err_strip)

        # ── Action hints ──────────────────────────────────────────────
        if self._success and self._sql:
            parts.append(Text(""))
            parts.append(render_action_hints())

        # ── Compose block ─────────────────────────────────────────────
        border_color = Colors.PRIMARY if self._success else Colors.ERROR
        block_title = (
            f"[{Colors.TEXT_GHOST}]#{self.number}[/{Colors.TEXT_GHOST}]"
        )

        return Panel(
            Group(*parts),
            border_style=border_color,
            box=ROUNDED_BOX,
            padding=Spacing.NORMAL,
            title=block_title,
            title_align="right",
            expand=True,
        )

    def print(self) -> None:
        """Print the command block to console."""
        console.print(self.render())
        console.print()  # breathing space after block


def render_command_block(
    query: str,
    sql: Optional[str] = None,
    dialect: str = "SQL",
    parameters: Optional[Dict[str, Any]] = None,
    results_table: Optional[Table] = None,
    row_count: Optional[int] = None,
    total_ms: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    block_number: Optional[int] = None,
) -> Panel:
    """Convenience function to build and render a command block."""
    blk = CommandBlock(query, block_number=block_number)
    if sql:
        blk.set_sql(sql, dialect, parameters)
    if results_table is not None and row_count is not None:
        blk.set_results(results_table, row_count)
    blk.set_metrics(total_ms, total_tokens, cost_usd)
    return blk.render()
