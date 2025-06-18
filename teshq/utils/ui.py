"""
Modern UI utilities for TESH-Query CLI application - Simplified 2025 Edition
Maintained by: theshashank1
Created: 2025-06-18

Clean, maintainable design focused on reliability and ease of use
while preserving all 2025 design aesthetics and functionality.
"""

import sys
import threading
import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

import typer
from rich import box
from rich.console import Console as RichConsole
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


# --- 2025 Design System ---
class ModernTheme:
    """Contemporary 2025 color palette - simplified constants"""

    PRIMARY = "#2563EB"
    SUCCESS = "#059669"
    WARNING = "#D97706"
    ERROR = "#DC2626"
    INFO = "#0891B2"
    ACCENT = "#EC4899"
    TEXT_MUTED = "#64748B"
    BORDER = "#E2E8F0"


class Icons:
    """Modern icons with ASCII fallbacks"""

    INFO, SUCCESS, WARNING, ERROR = "ⓘ", "✓", "⚠", "✗"
    TIP, PROMPT, CHEVRON, BULLET = "💡", "❯", "▸", "•"

    # Simple fallback mapping
    FALLBACKS = {
        "ⓘ": "i",
        "✓": "+",
        "⚠": "!",
        "✗": "x",
        "💡": "*",
        "❯": ">",
        "▸": ">",
        "•": "*",
    }


class MessageType(Enum):
    """Message types with their 2025 styling"""

    INFO = (Icons.INFO, ModernTheme.INFO)
    SUCCESS = (Icons.SUCCESS, ModernTheme.SUCCESS)
    WARNING = (Icons.WARNING, ModernTheme.WARNING)
    ERROR = (Icons.ERROR, ModernTheme.ERROR)
    TIP = (Icons.TIP, ModernTheme.ACCENT)


class ModernUIManager:
    """
    Simplified Modern UI Manager for 2025
    Maintains all functionality with improved readability and maintainability
    """

    def __init__(self, use_rich_console: bool = True, quiet_mode: bool = False):
        self.quiet_mode = quiet_mode
        self._lock = threading.Lock()

        # Simple console initialization
        self._rich_console = self._setup_console() if use_rich_console else None
        self.supports_color = self._detect_color_support()
        self.supports_unicode = self._detect_unicode_support()

    def _setup_console(self) -> Optional[RichConsole]:
        """Simplified console setup with error handling"""
        try:
            console = RichConsole(
                force_terminal=True,
                color_system="auto",
                legacy_windows=False,
                safe_box=True,
                highlight=False,
            )
            console.print("", end="")  # Test functionality
            return console
        except Exception:
            return None

    def _detect_color_support(self) -> bool:
        """Simple color support detection"""
        if self._rich_console:
            return self._rich_console.color_system is not None
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _detect_unicode_support(self) -> bool:
        """Simple Unicode support detection"""
        try:
            sys.stdout.write("•")
            sys.stdout.flush()
            return True
        except (UnicodeEncodeError, UnicodeError):
            return False

    def _get_icon(self, icon: str) -> str:
        """Get icon with fallback support"""
        return icon if self.supports_unicode else Icons.FALLBACKS.get(icon, icon)

    # --- Core Message System ---

    def print_message(
        self,
        message: str,
        msg_type: MessageType,
        dim: bool = False,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        """Unified message printing with 2025 styling"""
        if self.quiet_mode and msg_type == MessageType.INFO:
            return

        with self._lock:
            icon, color = msg_type.value
            display_icon = self._get_icon(icon)

            # Build formatted message
            indent_str = "  " * indent
            prefix_str = f"{prefix} " if prefix else ""
            full_message = f"{indent_str}{prefix_str}{message}"

            if self._rich_console:
                # Rich console output
                style = f"{color}" + (" dim" if dim else "")
                self._rich_console.print(f"[{style}]{display_icon}[/] [default]{full_message}[/]")
            else:
                # Fallback output with typer
                color_map = {
                    ModernTheme.INFO: typer.colors.CYAN,
                    ModernTheme.SUCCESS: typer.colors.GREEN,
                    ModernTheme.WARNING: typer.colors.YELLOW,
                    ModernTheme.ERROR: typer.colors.RED,
                    ModernTheme.ACCENT: typer.colors.MAGENTA,
                }
                typer.secho(
                    f"{display_icon} {full_message}",
                    fg=color_map.get(color, typer.colors.WHITE),
                    dim=dim,
                )

    # Enhanced convenience methods
    def info(
        self,
        message: str,
        dim: bool = False,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        self.print_message(message, MessageType.INFO, dim, prefix, indent)

    def success(
        self,
        message: str,
        dim: bool = False,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        self.print_message(message, MessageType.SUCCESS, dim, prefix, indent)

    def warning(
        self,
        message: str,
        dim: bool = False,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        self.print_message(message, MessageType.WARNING, dim, prefix, indent)

    def error(
        self,
        message: str,
        dim: bool = False,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        self.print_message(message, MessageType.ERROR, dim, prefix, indent)

    def debug(
        self,
        message: str,
        dim: bool = True,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        if not self.quiet_mode:
            self.print_message(message, MessageType.INFO, dim, prefix, indent)

    def tip(
        self,
        message: str,
        dim: bool = False,
        prefix: Optional[str] = None,
        indent: int = 0,
    ):
        self.print_message(message, MessageType.TIP, dim, prefix, indent)

    # --- Modern Panel System ---

    def _create_modern_panel(
        self,
        content: Any,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        border_style: Optional[str] = None,
    ) -> Panel:
        """Create consistently styled 2025 panels"""
        panel_title = None
        if title:
            title_text = Text()
            title_text.append(self._get_icon(Icons.CHEVRON), style=ModernTheme.PRIMARY)
            title_text.append(f" {title}", style=f"bold {ModernTheme.PRIMARY}")
            if subtitle:
                title_text.append(f" • {subtitle}", style=ModernTheme.TEXT_MUTED)
            panel_title = title_text

        return Panel(
            content,
            title=panel_title,
            border_style=border_style or ModernTheme.BORDER,
            box=box.ROUNDED,
            padding=(1, 2),
            expand=False,
        )

    def _print_panel(
        self,
        content: Any,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        border_style: Optional[str] = None,
    ):
        """Print panel with consistent 2025 styling and spacing"""
        self.space()

        if self._rich_console:
            panel = self._create_modern_panel(content, title, subtitle, border_style)
            self._rich_console.print(panel)
        else:
            # Enhanced fallback
            if title:
                display_title = f"{self._get_icon(Icons.CHEVRON)} {title}"
                if subtitle:
                    display_title += f" • {subtitle}"
                typer.secho(f"\n{display_title}", fg=typer.colors.CYAN, bold=True)
                typer.echo("─" * min(len(display_title), 80))

            content_str = str(content)
            for line in content_str.split("\n"):
                typer.echo(f"  {line}")

        self.space()

    # --- Enhanced Code Display ---

    def print_code(
        self,
        code: str,
        language: str = "text",
        title: Optional[str] = None,
        line_numbers: bool = False,
        theme: str = "monokai",
    ):
        """Display code with modern 2025 syntax highlighting"""
        if not code.strip():
            self.warning("No code content to display")
            return

        if not self._rich_console:
            # Enhanced fallback
            if title:
                typer.secho(
                    f"\n{self._get_icon(Icons.CHEVRON)} {title}",
                    fg=typer.colors.CYAN,
                    bold=True,
                )
                typer.echo("─" * min(len(title) + 2, 80))

            for i, line in enumerate(code.strip().split("\n"), 1):
                prefix = f"{i:3d} │ " if line_numbers else "    "
                typer.echo(f"{prefix}{line}")
            self.space()
            return

        # Rich syntax highlighting
        syntax = Syntax(
            code.strip(),
            language,
            theme=theme,
            line_numbers=line_numbers,
            word_wrap=True,
            padding=(1, 2),
            background_color="default",
        )

        subtitle = f"{language.upper()}" if language != "text" else None
        self._print_panel(syntax, title, subtitle, ModernTheme.TEXT_MUTED)

    def print_sql(self, sql: str, title: str = "SQL Query", show_line_numbers: bool = False):
        self.print_code(sql, "sql", title, line_numbers=show_line_numbers)

    def print_json(self, json_data: str, title: str = "JSON Data"):
        self.print_code(json_data, "json", title)

    def print_yaml(self, yaml_data: str, title: str = "YAML Configuration"):
        self.print_code(yaml_data, "yaml", title)

    # --- Enhanced Table System ---

    def print_table(
        self,
        title: Optional[str],
        headers: List[str],
        rows: List[List[Any]],
        caption: Optional[str] = None,
        show_lines: bool = True,
    ):
        """Display data in modern 2025 styled tables"""
        if not headers and not rows:
            self.warning("No data to display in table")
            return

        if not self._rich_console:
            # Enhanced fallback table
            if title:
                typer.secho(
                    f"\n{self._get_icon(Icons.CHEVRON)} {title}",
                    fg=typer.colors.CYAN,
                    bold=True,
                )

            if headers:
                header_line = " │ ".join(f"{h:<15}" for h in headers)
                typer.echo(header_line)
                typer.echo("─" * len(header_line))

            for row in rows:
                row_line = " │ ".join(f"{str(item):<15}" for item in row)
                typer.echo(row_line)

            if caption:
                typer.echo(f"\n{caption}")
            self.space()
            return

        # Rich table with 2025 styling
        table = Table(
            show_header=bool(headers),
            header_style=f"bold {ModernTheme.PRIMARY}",
            border_style=ModernTheme.BORDER,
            box=box.ROUNDED if show_lines else box.SIMPLE,
            caption=caption,
            caption_style=ModernTheme.TEXT_MUTED,
            expand=False,
            show_lines=show_lines,
        )

        for header in headers:
            table.add_column(header, no_wrap=False, style=ModernTheme.TEXT_MUTED, justify="left")

        for row in rows:
            table.add_row(*(str(item) for item in row))

        table_subtitle = f"{len(rows):,} rows" if rows else "No data"
        self._print_panel(table, title, table_subtitle)

    def print_query_results(
        self,
        headers: List[str],
        rows: List[List[Any]],
        title: str = "Query Results",
        summary: Optional[str] = None,
        execution_time: Optional[float] = None,
    ):
        """Specialized table for database query results with 2025 styling"""
        subtitle_parts = [f"{len(rows):,} row{'s' if len(rows) != 1 else ''}"]
        if execution_time is not None:
            subtitle_parts.append(f"{execution_time:.3f}s")

        self.print_table(title, headers, rows, caption=summary)

        if execution_time is not None:
            self.debug(f"Query execution time: {execution_time:.3f} seconds")

    # --- Modern Layout System ---

    def print_header(
        self,
        text: str,
        level: int = 1,
        subtitle: Optional[str] = None,
        divider: bool = True,
    ):
        """Print styled headers with modern 2025 typography"""
        self.space()

        if self._rich_console:
            header_text = Text()

            if level == 1:
                header_text.append(text.upper(), style=f"bold {ModernTheme.PRIMARY}")
                if subtitle:
                    header_text.append(f"\n{subtitle}", style=ModernTheme.TEXT_MUTED)

                self._rich_console.print(header_text)
                if divider:
                    self._rich_console.print(Text("─" * min(len(text) + 4, 80), style=ModernTheme.BORDER))
            else:
                chevron = self._get_icon(Icons.CHEVRON)
                header_text.append(f"{chevron} {text}", style=f"bold {ModernTheme.TEXT_MUTED}")
                if subtitle:
                    header_text.append(f" • {subtitle}", style=ModernTheme.TEXT_MUTED)
                self._rich_console.print(header_text)
        else:
            # Enhanced fallback headers
            prefix = "◆" if level == 1 else self._get_icon(Icons.CHEVRON)
            display_text = text.upper() if level == 1 else text
            color = typer.colors.CYAN if level == 1 else typer.colors.WHITE

            header_line = f"{prefix} {display_text}"
            if subtitle:
                header_line += f" • {subtitle}"

            typer.secho(header_line, fg=color, bold=True)

            if level == 1 and divider:
                typer.secho("─" * min(len(text) + 2, 80), fg=typer.colors.BLUE)

    def print_divider(self, text: Optional[str] = None, style: str = "line"):
        """Print styled divider with 2025 aesthetics"""
        if self._rich_console:
            if style == "line":
                self._rich_console.rule(text, style=ModernTheme.BORDER)
            elif style == "dots":
                dots = "•" * 40
                self._rich_console.print(f"[{ModernTheme.TEXT_MUTED}]{dots}[/]", justify="center")
        else:
            if text:
                typer.echo(f"─── {text} ───")
            else:
                typer.echo("─" * 80)

    def space(self, count: int = 1):
        """Add vertical spacing"""
        for _ in range(count):
            print()

    # --- Enhanced Progress System ---

    @contextmanager
    def status(
        self,
        message: str,
        success_message: Optional[str] = None,
        spinner: str = "dots",
    ) -> Generator[None, None, None]:
        """Modern status indicator with 2025 styling"""
        if not self._rich_console:
            self.info(f"{message}...")
            try:
                yield
                if success_message:
                    self.success(success_message)
            except Exception as e:
                self.error(f"Failed: {str(e)}")
                raise
            return

        # Rich status with modern styling
        with self._rich_console.status(
            f"[{ModernTheme.PRIMARY}]{self._get_icon(Icons.INFO)} {message}[/]",
            spinner=spinner,
        ) as status_obj:
            try:
                yield
                if success_message:
                    icon = self._get_icon(Icons.SUCCESS)
                    status_obj.update(f"[{ModernTheme.SUCCESS}]{icon} {success_message}[/]")
                    time.sleep(0.3)
            except Exception as e:
                icon = self._get_icon(Icons.ERROR)
                status_obj.update(f"[{ModernTheme.ERROR}]{icon} Failed: {str(e)}[/]")
                time.sleep(0.5)
                raise

    @contextmanager
    def progress(self, description: str = "Processing", total: Optional[int] = None):
        """Enhanced progress bar with modern 2025 styling"""
        if not self._rich_console:
            self.info(f"{description}...")
            yield None
            self.success(f"{description} complete")
            return

        columns = [
            SpinnerColumn(style=ModernTheme.PRIMARY),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(
                bar_width=None,
                complete_style=ModernTheme.SUCCESS,
                finished_style=ModernTheme.SUCCESS,
            ),
            TaskProgressColumn(),
        ]

        if total:
            columns.append(MofNCompleteColumn())
        else:
            columns.append(TimeRemainingColumn())

        with Progress(*columns, console=self._rich_console, transient=True) as progress_bar:
            task = progress_bar.add_task(description, total=total)
            yield progress_bar, task

    # --- Enhanced Interactive System ---

    def prompt(
        self,
        text: str,
        default: Any = None,
        password: bool = False,
        validate: Optional[Callable[[Any], bool]] = None,
        expected_type: Optional[type] = None,
        choices: Optional[List[str]] = None,
    ) -> Any:
        """Enhanced prompt with modern 2025 styling and validation"""
        icon = self._get_icon(Icons.PROMPT)

        # Build styled prompt
        prompt_parts = [f"[{ModernTheme.PRIMARY}]{icon}[/]", text]

        if choices:
            choices_str = "/".join(choices)
            prompt_parts.append(f"[{ModernTheme.TEXT_MUTED}]({choices_str})[/]")
        elif default is not None:
            prompt_parts.append(f"[{ModernTheme.TEXT_MUTED}]({default})[/]")

        prompt_text = " ".join(prompt_parts) + f" [{ModernTheme.TEXT_MUTED}]❯[/] "

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if password:
                    result_str = typer.prompt(
                        prompt_text,
                        default=str(default) if default is not None else None,
                        hide_input=True,
                        show_default=False,
                    )
                else:
                    result_str = typer.prompt(
                        prompt_text,
                        default=str(default) if default is not None else None,
                        show_default=False,
                    )

                # Handle choices validation
                if choices and result_str not in choices:
                    self.warning(f"Please choose from: {', '.join(choices)}")
                    continue

                # Type conversion
                result = result_str
                if expected_type and expected_type != str:
                    try:
                        result = expected_type(result_str)
                    except ValueError:
                        self.warning(f"Invalid {expected_type.__name__}. Please try again.")
                        continue

                # Custom validation
                if validate and not validate(result):
                    self.warning("Invalid input. Please try again.")
                    continue

                return result

            except (typer.Abort, KeyboardInterrupt):
                self.info("Operation cancelled by user")
                raise

        self.error("Maximum attempts exceeded")
        raise typer.Abort()

    def confirm(self, text: str, default: bool = False, danger: bool = False) -> bool:
        """Enhanced confirmation with modern 2025 styling and danger mode"""
        icon_type = Icons.WARNING if danger else Icons.PROMPT
        color = ModernTheme.WARNING if danger else ModernTheme.PRIMARY

        icon = self._get_icon(icon_type)
        suffix = " [Y/n]" if default else " [y/N]"

        prompt_text = f"[{color}]{icon}[/] {text}{suffix} [{ModernTheme.TEXT_MUTED}]❯[/] "

        try:
            return typer.confirm(prompt_text, default=default, show_default=False)
        except typer.Abort:
            self.info("Confirmation cancelled")
            return False

    def select_option(
        self,
        prompt_text: str,
        options: List[str],
        default_idx: int = 0,
        show_numbers: bool = True,
    ) -> str:
        """Enhanced option selection with modern 2025 styling"""
        if not options:
            raise ValueError("Options list cannot be empty")

        if default_idx < 0 or default_idx >= len(options):
            default_idx = 0

        self.info(prompt_text)

        # Display options with modern styling
        for i, option in enumerate(options):
            is_default = i == default_idx
            bullet = self._get_icon(Icons.BULLET)

            if self._rich_console:
                style = f"bold {ModernTheme.PRIMARY}" if is_default else ModernTheme.TEXT_MUTED
                prefix = f"{i + 1}. " if show_numbers else f"{bullet} "
                self._rich_console.print(f"  [{style}]{prefix}{option}[/]")
            else:
                marker = "●" if is_default else "○"
                prefix = f"{i + 1}. " if show_numbers else f"{marker} "
                typer.echo(f"  {prefix}{option}")

        while True:
            try:
                choice_str = self.prompt(
                    "Select option number" if show_numbers else "Enter option",
                    default=(str(default_idx + 1) if show_numbers else options[default_idx]),
                    expected_type=str,
                )

                if show_numbers:
                    choice_num = int(choice_str)
                    if 1 <= choice_num <= len(options):
                        return options[choice_num - 1]
                    else:
                        self.warning(f"Please select a number between 1 and {len(options)}")
                else:
                    if choice_str in options:
                        return choice_str
                    else:
                        self.warning(f"Please choose from: {', '.join(options)}")

            except ValueError:
                self.warning("Invalid input. Please enter a valid number.")
            except typer.Abort:
                self.info("Selection cancelled")
                raise

    # --- Enhanced Error Handling ---

    def handle_error(
        self,
        error: Exception,
        context: str = "Operation",
        show_traceback: bool = False,
        suggest_action: Optional[str] = None,
    ):
        """Enhanced error handling with better context and 2025 styling"""
        self.error(f"{context} failed: {type(error).__name__}")

        error_msg = str(error)
        if error_msg:
            self.info(error_msg, dim=True, indent=1)

        if suggest_action:
            self.tip(suggest_action)

        if show_traceback and self._rich_console:
            import traceback

            tb_text = traceback.format_exc()

            if tb_text and tb_text.strip() != "NoneType: None":
                self.space()
                syntax = Syntax(tb_text, "python", theme="monokai", line_numbers=False, word_wrap=True)
                panel = self._create_modern_panel(syntax, title="Traceback", border_style=ModernTheme.ERROR)
                self._rich_console.print(panel)

    # --- Enhanced Configuration Display ---

    def print_config(
        self,
        config: Dict[str, Any],
        title: str = "Configuration",
        mask_keys: Optional[List[str]] = None,
        show_types: bool = False,
    ):
        """Enhanced configuration display with modern 2025 styling"""
        if not config:
            self.warning("No configuration data to display")
            return

        mask_keys_lower = [k.lower() for k in (mask_keys or [])]

        if not self._rich_console:
            # Enhanced fallback
            self.print_header(title, level=2, divider=False)

            for key, value in config.items():
                display_value = "••••••••" if key.lower() in mask_keys_lower and value else str(value)
                type_info = f" ({type(value).__name__})" if show_types else ""
                typer.echo(f"  {key}: {display_value}{type_info}")
            self.space()
            return

        # Rich configuration table with 2025 styling
        table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2, 0, 0),
            show_edge=False,
            expand=False,
        )

        table.add_column(
            "Key",
            style=f"bold {ModernTheme.TEXT_MUTED}",
            justify="right",
            min_width=20,
        )
        table.add_column("Value", style=ModernTheme.PRIMARY, no_wrap=False)

        if show_types:
            table.add_column("Type", style=ModernTheme.TEXT_MUTED, justify="center")

        for key, value in config.items():
            display_value = "••••••••" if key.lower() in mask_keys_lower and value else str(value)
            row_data = [key, display_value]
            if show_types:
                row_data.append(type(value).__name__)
            table.add_row(*row_data)

        config_subtitle = f"{len(config)} settings"
        self._print_panel(table, title, config_subtitle)

    def print_list(
        self,
        items: List[Any],
        title: Optional[str] = None,
        numbered: bool = False,
        columns: int = 1,
    ):
        """Display list with modern 2025 formatting"""
        if not items:
            if title:
                self.warning(f"No items in {title.lower()}")
            return

        if not self._rich_console:
            # Fallback list display
            if title:
                self.print_header(title, level=2, divider=False)

            for i, item in enumerate(items, 1):
                prefix = f"{i}. " if numbered else f"{self._get_icon(Icons.BULLET)} "
                typer.echo(f"  {prefix}{item}")
            self.space()
            return

        # Rich list display with 2025 styling
        content_lines = []
        for i, item in enumerate(items, 1):
            prefix = f"{i}. " if numbered else f"{Icons.BULLET} "
            content_lines.append(f"{prefix}{item}")

        content = "\n".join(content_lines)
        list_subtitle = f"{len(items)} items"
        self._print_panel(content, title, list_subtitle)

    def print_markdown(self, content: str, title: Optional[str] = None):
        """Display markdown content with modern 2025 styling"""
        if not content.strip():
            return

        if not self._rich_console:
            # Fallback - strip markdown and display plain text
            import re

            plain_text = re.sub(r"[*_`#]", "", content)
            if title:
                self.print_header(title, level=2)
            typer.echo(plain_text)
            self.space()
            return

        # Rich markdown display
        markdown_obj = Markdown(content)
        self._print_panel(markdown_obj, title)

    # --- Context Managers ---

    @contextmanager
    def section(self, title: str, collapsed: bool = False):
        """Create section with automatic spacing and modern 2025 styling"""
        self.print_header(title, level=2)
        try:
            yield
        finally:
            if not collapsed:
                self.space()

    @contextmanager
    def indent_context(self, level: int = 1):
        """Context manager for indented output with proper cleanup"""
        original_methods = {
            "info": self.info,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "tip": self.tip,
        }

        def make_indented(method):
            def indented_method(
                message: str,
                dim: bool = False,
                prefix: Optional[str] = None,
                indent: int = 0,
            ):
                return method(message, dim, prefix, indent + level)

            return indented_method

        # Replace methods temporarily
        for name, method in original_methods.items():
            setattr(self, name, make_indented(method))

        try:
            yield
        finally:
            # Restore original methods
            for name, method in original_methods.items():
                setattr(self, name, method)

    # --- Utilities ---

    def clear_screen(self):
        """Clear terminal screen"""
        if self._rich_console:
            self._rich_console.clear()
        else:
            typer.clear()

    def set_quiet_mode(self, quiet: bool):
        """Enable or disable quiet mode"""
        self.quiet_mode = quiet
        self.debug(f"Quiet mode {'enabled' if quiet else 'disabled'}")

    def get_console_info(self) -> Dict[str, Any]:
        """Get information about console capabilities"""
        info = {
            "rich_console": self._rich_console is not None,
            "supports_color": self.supports_color,
            "supports_unicode": self.supports_unicode,
            "quiet_mode": self.quiet_mode,
        }

        if self._rich_console:
            info.update(
                {
                    "console_width": self._rich_console.width,
                    "console_height": self._rich_console.height,
                    "color_system": self._rich_console.color_system,
                    "encoding": self._rich_console.encoding,
                }
            )

        return info


# --- Global Instance and Convenience Functions ---
ui = ModernUIManager()

# Export all methods as functions for backward compatibility and convenience
info = ui.info
success = ui.success
warning = ui.warning
error = ui.error
debug = ui.debug
tip = ui.tip

# Code and data display
print_code = ui.print_code
print_sql = ui.print_sql
print_json = ui.print_json
print_yaml = ui.print_yaml
print_table = ui.print_table
print_query_results = ui.print_query_results

# Configuration and lists
print_config = ui.print_config
print_list = ui.print_list
print_markdown = ui.print_markdown

# Layout and styling
print_header = ui.print_header
print_divider = ui.print_divider
space = ui.space

# Progress and status
status = ui.status
progress = ui.progress

# Interactive elements
prompt = ui.prompt
confirm = ui.confirm
select_option = ui.select_option

# Utilities
clear_screen = ui.clear_screen
handle_error = ui.handle_error
set_quiet_mode = ui.set_quiet_mode
get_console_info = ui.get_console_info

# Context managers
section = ui.section
indent_context = ui.indent_context


# --- Enhanced Demo System ---
if __name__ == "__main__":
    app = typer.Typer(
        rich_markup_mode="rich",
        help="Modern TESH-Query UI Demo System - Simplified 2025 Edition",
    )

    @app.command()
    def demo():
        """Run comprehensive UI demonstration with all enhanced features"""
        clear_screen()

        # Main header with system info
        console_info = get_console_info()
        subtitle = (
            f"Rich: {console_info['rich_console']} • "
            f"Colors: {console_info['supports_color']} • "
            f"Unicode: {console_info['supports_unicode']}"
        )
        print_header("🚀 MODERN TESH-QUERY UI SHOWCASE 2025 🚀", subtitle=subtitle)

        # Enhanced messages demo
        with section("Enhanced Message System"):
            info("Database connection established successfully", prefix="DB")
            success("Query executed in 0.23 seconds", prefix="EXEC")
            warning("Large result set detected (15,000 rows)", prefix="PERF")
            error("Connection timeout after 30 seconds", prefix="NET")
            debug("SQL: SELECT * FROM users WHERE status = 'active'", prefix="DEBUG")
            tip("Use `LIMIT` clause to improve performance for large queries")

            # Demonstrate indented messages
            info("Processing batch operations:")
            with indent_context(1):
                info("Validating input data...")
                success("Input validation completed")
                info("Executing batch insert...")
                success("Batch insert completed (1,234 rows)")

        # Enhanced code display demo
        with section("Enhanced Code Display"):
            # SQL example
            sample_sql = """
SELECT
    u.id,
    u.name,
    u.email,
    COUNT(o.id) as order_count,
    SUM(o.total_amount) as total_spent
FROM customers u
LEFT JOIN orders o ON u.id = o.customer_id
WHERE u.is_active = TRUE
    AND u.created_at >= '2024-01-01'
GROUP BY u.id, u.name, u.email
HAVING COUNT(o.id) > 0
ORDER BY total_spent DESC
LIMIT 100;"""
            print_sql(sample_sql, "Customer Analytics Query", show_line_numbers=True)

            # JSON example
            sample_json = """{
  "api_version": "v2",
  "endpoints": {
    "users": "/api/v2/users",
    "orders": "/api/v2/orders"
  },
  "authentication": {
    "type": "bearer_token",
    "expires_in": 3600
  }
}"""
            print_json(sample_json, "API Configuration")

        # Enhanced tables demo
        with section("Enhanced Table System"):
            headers = ["Product ID", "Name", "Category", "Stock", "Price", "Status"]
            rows = [
                [1001, "Laptop Pro X1", "Electronics", 75, "$1,299.99", "✓ In Stock"],
                [
                    1002,
                    "Wireless Headphones",
                    "Audio",
                    150,
                    "$199.99",
                    "✓ In Stock",
                ],
                [
                    1003,
                    "Smart Watch Series 5",
                    "Wearables",
                    23,
                    "$399.99",
                    "⚠ Low Stock",
                ],
                [1004, "Gaming Mouse", "Peripherals", 0, "$79.99", "✗ Out of Stock"],
                [1005, "4K Monitor", "Displays", 45, "$599.99", "✓ In Stock"],
            ]

            print_query_results(
                headers,
                rows,
                "Product Inventory",
                summary="5 products tracked across 4 categories",
                execution_time=0.045,
            )

            # Configuration display
            config_data = {
                "database_host": "localhost",
                "database_port": 5432,
                "database_name": "tesh_query",
                "connection_pool_size": 10,
                "query_timeout": 30,
                "api_key": "sk-1234567890abcdef",
                "debug_mode": True,
                "log_level": "INFO",
            }

            print_config(
                config_data,
                "Database Configuration",
                mask_keys=["api_key"],
                show_types=True,
            )

        # Enhanced progress demo
        with section("Enhanced Progress System"):
            with status("Connecting to database", "Database connected"):
                time.sleep(1.5)

            with progress("Processing records", total=100) as progress_data:
                if progress_data:
                    prog, task = progress_data
                    for i in range(100):
                        time.sleep(0.02)
                        prog.update(task, advance=1)

        # Enhanced layout demo
        with section("Enhanced Layout System"):
            # Lists and key-value pairs
            features = [
                "Modern color palette with semantic meaning",
                "Enhanced Unicode support with ASCII fallbacks",
                "Thread-safe operations for concurrent usage",
                "Improved error handling with contextual suggestions",
                "Flexible theming system",
            ]

            print_list(features, "New Features", numbered=True)

            # Markdown support
            markdown_content = """
## Performance Improvements

The new UI system includes several **performance enhancements**:

- Reduced memory footprint by 30%
- Faster rendering with optimized Rich components
- Better terminal compatibility detection
- Improved error recovery mechanisms

> **Note**: These improvements are backward compatible with existing code.
"""
            print_markdown(markdown_content, "Release Notes")

        # Error handling demo
        with section("Enhanced Error Handling"):
            try:
                raise ConnectionError("Failed to connect to database server at localhost:5432")
            except Exception as e:
                handle_error(
                    e,
                    "Database Connection",
                    suggest_action="Check if the database server is running",
                )

        space(2)
        success("🎉 All Enhanced Demos Complete! 🎉")

        # Display console capabilities
        info("Console capabilities:")
        print_config(console_info)

    @app.command()
    def interactive():
        """Run interactive demo (commented out for non-interactive environments)"""
        try:
            clear_screen()
            print_header("Interactive Demo", "Test user input features")

            # Basic prompts
            name = prompt("Enter your name", default="Developer", expected_type=str)
            info(f"Hello, {name}!")

            # Choice validation
            environment = prompt(
                "Select environment",
                choices=["development", "staging", "production"],
                default="development",
            )
            info(f"Environment selected: {environment}")

            # Enhanced option selection
            db_options = ["PostgreSQL", "MySQL", "SQLite", "MongoDB"]
            selected_db = select_option("Choose your database:", db_options, default_idx=0)
            success(f"Database selected: {selected_db}")

            # Confirmations
            if confirm("Proceed with setup?", default=True):
                success("Setup will proceed")
            else:
                info("Setup cancelled")

        except (typer.Abort, KeyboardInterrupt):
            warning("Interactive demo interrupted by user")
        except Exception as e:
            handle_error(e, "Interactive Demo", suggest_action="Try running the demo again")

    app()
