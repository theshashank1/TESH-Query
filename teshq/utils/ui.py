"""
Modern UI utilities for TESH-Query CLI application - Final Simplified Edition

Ultra-clean, maintainable design with maximum simplicity and full functionality.
Preserves complete 2025 design aesthetics while being easy to understand and modify.
"""

import sys
import threading
import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

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


# --- 2025 Design System (Ultra-Simplified) ---
class Colors:
    """2025 Contemporary Color Palette"""

    PRIMARY = "#2563EB"  # Modern Blue
    SUCCESS = "#059669"  # Fresh Green
    WARNING = "#D97706"  # Warm Orange
    ERROR = "#DC2626"  # Alert Red
    INFO = "#0891B2"  # Cool Cyan
    ACCENT = "#EC4899"  # Vibrant Pink
    MUTED = "#64748B"  # Sophisticated Gray
    BORDER = "#E2E8F0"  # Subtle Border


class Icons:
    """Modern Icons with Smart Fallbacks"""

    # Primary icons
    INFO, SUCCESS, WARNING, ERROR = "ⓘ", "✓", "⚠", "✗"
    TIP, PROMPT, CHEVRON, BULLET = "💡", "❯", "▸", "•"

    # Smart fallback system
    FALLBACK_MAP = {"ⓘ": "i", "✓": "+", "⚠": "!", "✗": "x", "💡": "*", "❯": ">", "▸": ">", "•": "*"}


class MessageType(Enum):
    """Message Types with 2025 Styling"""

    INFO = (Icons.INFO, Colors.INFO)
    SUCCESS = (Icons.SUCCESS, Colors.SUCCESS)
    WARNING = (Icons.WARNING, Colors.WARNING)
    ERROR = (Icons.ERROR, Colors.ERROR)
    TIP = (Icons.TIP, Colors.ACCENT)


class ModernUI:
    """
    Ultra-Simplified Modern UI Manager

    Single, focused class that handles all UI operations with minimal complexity
    while preserving complete 2025 design aesthetics and full functionality.
    """

    def __init__(self, use_rich: bool = True, quiet: bool = False):
        """Initialize with minimal setup"""
        self.quiet = quiet
        self._lock = threading.Lock()

        # Simple, reliable initialization
        self.console = self._setup_rich_console() if use_rich else None
        self.has_rich = self.console is not None
        self.has_unicode = self._detect_unicode()
        self.has_color = self._detect_color()

    def _setup_rich_console(self) -> Optional[RichConsole]:
        """Setup Rich console with error handling"""
        try:
            console = RichConsole(
                force_terminal=True, color_system="auto", highlight=False, legacy_windows=False, safe_box=True
            )
            console.print("", end="")  # Test console
            return console
        except Exception:
            return None

    def _detect_unicode(self) -> bool:
        """Detect Unicode support"""
        try:
            sys.stdout.write("•")
            sys.stdout.flush()
            return True
        except (UnicodeEncodeError, UnicodeError):
            return False

    def _detect_color(self) -> bool:
        """Detect color support"""
        if self.console:
            return self.console.color_system is not None
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _get_icon(self, icon: str) -> str:
        """Get icon with smart fallback"""
        return icon if self.has_unicode else Icons.FALLBACK_MAP.get(icon, icon)

    # --- Core Messaging System ---
    def _print_message(self, message: str, msg_type: MessageType, dim: bool = False, prefix: str = "", indent: int = 0):
        """Unified message printing with 2025 styling"""
        if self.quiet and msg_type == MessageType.INFO:
            return

        with self._lock:  # Thread safety
            icon, color = msg_type.value
            display_icon = self._get_icon(icon)

            # Format message with indentation and prefix
            indent_str = "  " * indent
            prefix_str = f"{prefix} " if prefix else ""
            formatted_message = f"{indent_str}{prefix_str}{message}"

            if self.has_rich:
                # Rich console output with 2025 styling
                style = f"{color}" + (" dim" if dim else "")
                self.console.print(f"[{style}]{display_icon}[/] {formatted_message}")
            else:
                # Typer fallback with color mapping
                color_mapping = {
                    Colors.INFO: typer.colors.CYAN,
                    Colors.SUCCESS: typer.colors.GREEN,
                    Colors.WARNING: typer.colors.YELLOW,
                    Colors.ERROR: typer.colors.RED,
                    Colors.ACCENT: typer.colors.MAGENTA,
                }
                typer.secho(f"{display_icon} {formatted_message}", fg=color_mapping.get(color, typer.colors.WHITE), dim=dim)

    # Message methods - clean and simple
    def info(self, message: str, **kwargs):
        """Display info message"""
        self._print_message(message, MessageType.INFO, **kwargs)

    def success(self, message: str, **kwargs):
        """Display success message"""
        self._print_message(message, MessageType.SUCCESS, **kwargs)

    def warning(self, message: str, **kwargs):
        """Display warning message"""
        self._print_message(message, MessageType.WARNING, **kwargs)

    def error(self, message: str, **kwargs):
        """Display error message"""
        self._print_message(message, MessageType.ERROR, **kwargs)

    def tip(self, message: str, **kwargs):
        """Display tip message"""
        self._print_message(message, MessageType.TIP, **kwargs)

    def debug(self, message: str, **kwargs):
        """Display debug message (respects quiet mode)"""
        if not self.quiet:
            self._print_message(message, MessageType.INFO, dim=True, **kwargs)

    # --- Layout and Structure ---
    def space(self, count: int = 1):
        """Add vertical spacing"""
        for _ in range(count):
            print()

    def print_header(self, text: str, subtitle: str = "", level: int = 1, divider: bool = True):
        """Print styled header with 2025 typography"""
        self.space()

        if self.has_rich:
            if level == 1:
                # Main header with bold styling
                header_text = Text(text.upper(), style=f"bold {Colors.PRIMARY}")
                if subtitle:
                    header_text.append(f"\n{subtitle}", style=Colors.MUTED)

                self.console.print(header_text)
                if divider:
                    self.console.print("─" * min(len(text) + 4, 80), style=Colors.BORDER)
            else:
                # Sub-header with chevron
                chevron = self._get_icon(Icons.CHEVRON)
                header_text = Text(f"{chevron} {text}", style=f"bold {Colors.MUTED}")
                if subtitle:
                    header_text.append(f" • {subtitle}", style=Colors.MUTED)
                self.console.print(header_text)
        else:
            # Fallback headers
            prefix = "◆" if level == 1 else self._get_icon(Icons.CHEVRON)
            display_text = text.upper() if level == 1 else text
            color = typer.colors.CYAN if level == 1 else typer.colors.WHITE

            full_header = f"{prefix} {display_text}"
            if subtitle:
                full_header += f" • {subtitle}"

            typer.secho(full_header, fg=color, bold=True)

            if level == 1 and divider:
                typer.echo("─" * min(len(text) + 2, 80))

    def print_divider(self, text: str = "", style: str = "line"):
        """Print styled divider"""
        if self.has_rich:
            if style == "line":
                self.console.rule(text or None, style=Colors.BORDER)
            elif style == "dots":
                self.console.print("•" * 40, style=Colors.MUTED, justify="center")
        else:
            typer.echo(f"─── {text} ───" if text else "─" * 80)

    # --- Panel System ---
    def _create_panel(self, content: Any, title: str = "", subtitle: str = "") -> Panel:
        """Create modern 2025 styled panel"""
        panel_title = None
        if title:
            title_text = Text()
            title_text.append(self._get_icon(Icons.CHEVRON), style=Colors.PRIMARY)
            title_text.append(f" {title}", style=f"bold {Colors.PRIMARY}")
            if subtitle:
                title_text.append(f" • {subtitle}", style=Colors.MUTED)
            panel_title = title_text

        return Panel(content, title=panel_title, border_style=Colors.BORDER, box=box.ROUNDED, padding=(1, 2), expand=False)

    def _print_panel(self, content: Any, title: str = "", subtitle: str = ""):
        """Print panel with consistent spacing"""
        self.space()

        if self.has_rich:
            panel = self._create_panel(content, title, subtitle)
            self.console.print(panel)
        else:
            # Fallback panel
            if title:
                display_title = f"{self._get_icon(Icons.CHEVRON)} {title}"
                if subtitle:
                    display_title += f" • {subtitle}"
                typer.secho(f"\n{display_title}", fg=typer.colors.CYAN, bold=True)
                typer.echo("─" * min(len(display_title), 80))

            for line in str(content).split("\n"):
                typer.echo(f"  {line}")

        self.space()

    # --- Code Display ---
    def print_code(
        self, code: str, language: str = "text", title: str = "", line_numbers: bool = False, theme: str = "monokai"
    ):
        """Display code with syntax highlighting"""
        if not code.strip():
            self.warning("No code content to display")
            return

        if self.has_rich:
            syntax = Syntax(
                code.strip(),
                language,
                theme=theme,
                line_numbers=line_numbers,
                word_wrap=True,
                padding=(1, 2),
                background_color="default",
            )
            subtitle = language.upper() if language != "text" else ""
            self._print_panel(syntax, title, subtitle)
        else:
            # Fallback code display
            if title:
                self.print_header(title, level=2, divider=False)

            for i, line in enumerate(code.strip().split("\n"), 1):
                prefix = f"{i:3d} │ " if line_numbers else "    "
                typer.echo(f"{prefix}{line}")
            self.space()

    def print_sql(self, sql: str, title: str = "SQL Query", show_line_numbers: bool = False):
        """Display SQL with syntax highlighting"""
        self.print_code(sql, "sql", title, line_numbers=show_line_numbers)

    def print_json(self, json_data: str, title: str = "JSON Data"):
        """Display JSON with syntax highlighting"""
        self.print_code(json_data, "json", title)

    def print_yaml(self, yaml_data: str, title: str = "YAML Configuration"):
        """Display YAML with syntax highlighting"""
        self.print_code(yaml_data, "yaml", title)

    # --- Table System ---
    def print_table(self, title: str, headers: List[str], rows: List[List[Any]], caption: str = "", show_lines: bool = True):
        """Display table with modern 2025 styling"""
        if not rows:
            self.warning("No data to display in table")
            return

        if self.has_rich:
            table = Table(
                show_header=bool(headers),
                header_style=f"bold {Colors.PRIMARY}",
                border_style=Colors.BORDER,
                box=box.ROUNDED if show_lines else box.SIMPLE,
                caption=caption or None,
                caption_style=Colors.MUTED,
                expand=False,
                show_lines=show_lines,
            )

            for header in headers:
                table.add_column(header, style=Colors.MUTED, justify="left")

            for row in rows:
                table.add_row(*[str(item) for item in row])

            subtitle = f"{len(rows):,} rows" if rows else "No data"
            self._print_panel(table, title, subtitle)
        else:
            # Fallback table
            if title:
                self.print_header(title, level=2, divider=False)

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

    def print_query_results(
        self,
        headers: List[str],
        rows: List[List[Any]],
        title: str = "Query Results",
        summary: str = "",
        execution_time: float = None,
    ):
        """Display query results with execution metrics"""
        display_title = title
        if execution_time:
            display_title += f" ({execution_time:.3f}s)"

        self.print_table(display_title, headers, rows, summary)

        if execution_time:
            self.debug(f"Query execution time: {execution_time:.3f} seconds")

    # --- Configuration Display ---
    def print_config(
        self, config: Dict[str, Any], title: str = "Configuration", mask_keys: List[str] = None, show_types: bool = False
    ):
        """Display configuration with modern styling"""
        if not config:
            self.warning("No configuration data to display")
            return

        mask_keys = mask_keys or []

        if self.has_rich:
            table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2, 0, 0), show_edge=False, expand=False)

            table.add_column("Key", style=f"bold {Colors.MUTED}", justify="right", min_width=20)
            table.add_column("Value", style=Colors.PRIMARY, no_wrap=False)

            if show_types:
                table.add_column("Type", style=Colors.MUTED, justify="center")

            for key, value in config.items():
                display_value = "••••••••" if key in mask_keys else str(value)
                row_data = [key, display_value]
                if show_types:
                    row_data.append(type(value).__name__)
                table.add_row(*row_data)

            subtitle = f"{len(config)} settings"
            self._print_panel(table, title, subtitle)
        else:
            # Fallback configuration display
            self.print_header(title, level=2, divider=False)

            for key, value in config.items():
                display_value = "••••••••" if key in mask_keys else str(value)
                type_info = f" ({type(value).__name__})" if show_types else ""
                typer.echo(f"  {key}: {display_value}{type_info}")
            self.space()

    def print_list(self, items: List[Any], title: str = "", numbered: bool = False, columns: int = 1):
        """Display list with modern formatting"""
        if not items:
            if title:
                self.warning(f"No items in {title.lower()}")
            return

        if self.has_rich:
            content_lines = []
            for i, item in enumerate(items, 1):
                prefix = f"{i}. " if numbered else f"{Icons.BULLET} "
                content_lines.append(f"{prefix}{item}")

            content = "\n".join(content_lines)
            subtitle = f"{len(items)} items"
            self._print_panel(content, title, subtitle)
        else:
            # Fallback list display
            if title:
                self.print_header(title, level=2, divider=False)

            for i, item in enumerate(items, 1):
                prefix = f"{i}. " if numbered else f"{self._get_icon(Icons.BULLET)} "
                typer.echo(f"  {prefix}{item}")
            self.space()

    def print_markdown(self, content: str, title: str = ""):
        """Display markdown content"""
        if not content.strip():
            return

        if self.has_rich:
            markdown = Markdown(content)
            self._print_panel(markdown, title)
        else:
            # Strip markdown for fallback
            import re

            plain_text = re.sub(r"[*_`#]", "", content)
            if title:
                self.print_header(title, level=2)
            typer.echo(plain_text)
            self.space()

    # --- Progress System ---
    @contextmanager
    def status(self, message: str, success_message: str = "", spinner: str = "dots"):
        """Status indicator with modern styling"""
        if self.has_rich:
            with self.console.status(
                f"[{Colors.PRIMARY}]{self._get_icon(Icons.INFO)} {message}[/]", spinner=spinner
            ) as status_obj:
                try:
                    yield
                    if success_message:
                        icon = self._get_icon(Icons.SUCCESS)
                        status_obj.update(f"[{Colors.SUCCESS}]{icon} {success_message}[/]")
                        time.sleep(0.3)
                except Exception as e:
                    icon = self._get_icon(Icons.ERROR)
                    status_obj.update(f"[{Colors.ERROR}]{icon} Failed: {str(e)}[/]")
                    time.sleep(0.5)
                    raise
        else:
            # Fallback status
            self.info(f"{message}...")
            try:
                yield
                if success_message:
                    self.success(success_message)
            except Exception as e:
                self.error(f"Failed: {str(e)}")
                raise

    @contextmanager
    def progress(self, description: str = "Processing", total: int = None):
        """Progress bar with modern styling"""
        if self.has_rich:
            columns = [
                SpinnerColumn(style=Colors.PRIMARY),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=None, complete_style=Colors.SUCCESS, finished_style=Colors.SUCCESS),
                TaskProgressColumn(),
            ]

            if total:
                columns.append(MofNCompleteColumn())
            else:
                columns.append(TimeRemainingColumn())

            with Progress(*columns, console=self.console, transient=True) as progress_bar:
                task = progress_bar.add_task(description, total=total)
                yield progress_bar, task
        else:
            # Fallback progress
            self.info(f"{description}...")
            yield None
            self.success(f"{description} complete")

    # --- Interactive System ---
    def prompt(
        self,
        text: str,
        default: Any = None,
        password: bool = False,
        validate: Callable = None,
        expected_type: type = None,
        choices: List[str] = None,
    ) -> Any:
        """Enhanced prompt with validation"""
        icon = self._get_icon(Icons.PROMPT)

        # Build prompt text
        prompt_parts = [f"[{Colors.PRIMARY}]{icon}[/]", text]

        if choices:
            prompt_parts.append(f"[{Colors.MUTED}]({'/'.join(choices)})[/]")
        elif default is not None:
            prompt_parts.append(f"[{Colors.MUTED}]({default})[/]")

        prompt_text = " ".join(prompt_parts) + f" [{Colors.MUTED}]❯[/] "

        for attempt in range(3):
            try:
                if password:
                    result = typer.prompt(
                        prompt_text, default=str(default) if default else None, hide_input=True, show_default=False
                    )
                else:
                    result = typer.prompt(prompt_text, default=str(default) if default else None, show_default=False)

                # Validate choices
                if choices and result not in choices:
                    self.warning(f"Please choose from: {', '.join(choices)}")
                    continue

                # Type conversion
                if expected_type and expected_type != str:
                    try:
                        result = expected_type(result)
                    except ValueError:
                        self.warning(f"Invalid {expected_type.__name__}. Please try again.")
                        continue

                # Custom validation
                if validate and not validate(result):
                    self.warning("Invalid input. Please try again.")
                    continue

                return result

            except (typer.Abort, KeyboardInterrupt):
                self.info("Operation cancelled")
                raise

        self.error("Maximum attempts exceeded")
        raise typer.Abort()

    def confirm(self, text: str, default: bool = False, danger: bool = False) -> bool:
        """Confirmation with optional danger styling"""
        icon_type = Icons.WARNING if danger else Icons.PROMPT
        color = Colors.WARNING if danger else Colors.PRIMARY

        icon = self._get_icon(icon_type)
        suffix = " [Y/n]" if default else " [y/N]"

        prompt_text = f"[{color}]{icon}[/] {text}{suffix} [{Colors.MUTED}]❯[/] "

        try:
            return typer.confirm(prompt_text, default=default, show_default=False)
        except typer.Abort:
            self.info("Confirmation cancelled")
            return False

    def select_option(self, prompt_text: str, options: List[str], default_idx: int = 0, show_numbers: bool = True) -> str:
        """Option selection with modern styling"""
        if not options:
            raise ValueError("Options list cannot be empty")

        default_idx = max(0, min(default_idx, len(options) - 1))
        self.info(prompt_text)

        # Display options
        for i, option in enumerate(options):
            is_default = i == default_idx

            if self.has_rich:
                style = f"bold {Colors.PRIMARY}" if is_default else Colors.MUTED
                prefix = f"{i + 1}. " if show_numbers else f"{self._get_icon(Icons.BULLET)} "
                self.console.print(f"  [{style}]{prefix}{option}[/]")
            else:
                marker = "●" if is_default else "○"
                prefix = f"{i + 1}. " if show_numbers else f"{marker} "
                typer.echo(f"  {prefix}{option}")

        while True:
            try:
                choice = self.prompt(
                    "Select option number" if show_numbers else "Enter option",
                    default=str(default_idx + 1) if show_numbers else options[default_idx],
                    expected_type=str,
                )

                if show_numbers:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(options):
                        return options[choice_num - 1]
                    else:
                        self.warning(f"Please select a number between 1 and {len(options)}")
                else:
                    if choice in options:
                        return choice
                    else:
                        self.warning(f"Please choose from: {', '.join(options)}")

            except ValueError:
                self.warning("Invalid input. Please enter a valid number.")
            except typer.Abort:
                self.info("Selection cancelled")
                raise

    # --- Error Handling ---
    def handle_error(
        self, error: Exception, context: str = "Operation", show_traceback: bool = False, suggest_action: str = ""
    ):
        """Enhanced error handling"""
        self.error(f"{context} failed: {type(error).__name__}")

        if str(error):
            self.info(str(error), dim=True, indent=1)

        if suggest_action:
            self.tip(suggest_action)

        if show_traceback and self.has_rich:
            import traceback

            tb_text = traceback.format_exc()

            if tb_text and "NoneType: None" not in tb_text:
                self.space()
                syntax = Syntax(tb_text, "python", theme="monokai", word_wrap=True)
                panel = Panel(syntax, title="Traceback", border_style=Colors.ERROR, box=box.ROUNDED)
                self.console.print(panel)

    # --- Context Managers ---
    @contextmanager
    def section(self, title: str, collapsed: bool = False):
        """Section context with automatic spacing"""
        self.print_header(title, level=2)
        try:
            yield
        finally:
            if not collapsed:
                self.space()

    @contextmanager
    def indent_context(self, level: int = 1):
        """Context manager for indented output"""
        original_methods = {name: getattr(self, name) for name in ["info", "success", "warning", "error", "tip"]}

        # Create indented versions
        def make_indented(method):
            def wrapper(message: str, **kwargs):
                current_indent = kwargs.get("indent", 0)
                kwargs["indent"] = current_indent + level
                return method(message, **kwargs)

            return wrapper

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
        if self.has_rich:
            self.console.clear()
        else:
            typer.clear()

    def set_quiet_mode(self, quiet: bool):
        """Set quiet mode"""
        self.quiet = quiet

    def get_console_info(self) -> Dict[str, Any]:
        """Get console capabilities information"""
        info = {
            "rich_console": self.has_rich,
            "supports_color": self.has_color,
            "supports_unicode": self.has_unicode,
            "quiet_mode": self.quiet,
            "timestamp": "2025-06-18 13:57:42",
            "user": "theshashank1",
        }

        if self.console:
            info.update(
                {
                    "console_width": self.console.width,
                    "console_height": self.console.height,
                    "color_system": self.console.color_system,
                    "encoding": self.console.encoding,
                }
            )

        return info


# --- Global Instance ---
ui = ModernUI()

# --- Direct Method Exports (Primary API) ---
info = ui.info
success = ui.success
warning = ui.warning
error = ui.error
debug = ui.debug
tip = ui.tip

space = ui.space
print_header = ui.print_header
print_divider = ui.print_divider

print_code = ui.print_code
print_sql = ui.print_sql
print_json = ui.print_json
print_yaml = ui.print_yaml

print_table = ui.print_table
print_query_results = ui.print_query_results
print_config = ui.print_config
print_list = ui.print_list
print_markdown = ui.print_markdown

status = ui.status
progress = ui.progress

prompt = ui.prompt
confirm = ui.confirm
select_option = ui.select_option

handle_error = ui.handle_error

section = ui.section
indent_context = ui.indent_context

clear_screen = ui.clear_screen
set_quiet_mode = ui.set_quiet_mode
get_console_info = ui.get_console_info


# --- Demo System ---
if __name__ == "__main__":
    app = typer.Typer(help="Modern TESH-Query UI Demo - Final Simplified Edition")

    @app.command()
    def demo():
        """Run comprehensive demonstration of all features"""
        clear_screen()

        # System information
        console_info = get_console_info()
        subtitle = (
            f"Rich: {console_info['rich_console']} • "
            f"Colors: {console_info['supports_color']} • "
            f"Unicode: {console_info['supports_unicode']}"
        )

        print_header("🚀 MODERN TESH-QUERY UI SHOWCASE 2025 🚀", subtitle)

        # Enhanced message system demo
        with section("Enhanced Message System"):
            info("Database connection established successfully", prefix="DB")
            success("Query executed in 0.23 seconds", prefix="EXEC")
            warning("Large result set detected (15,000 rows)", prefix="PERF")
            error("Connection timeout after 30 seconds", prefix="NET")
            debug("SQL: SELECT * FROM users WHERE status = 'active'", prefix="DEBUG")
            tip("Use `LIMIT` clause to improve performance for large queries")

            # Indented messages demonstration
            info("Processing batch operations:")
            with indent_context(1):
                info("Validating input data...")
                success("Input validation completed")
                info("Executing batch insert...")
                success("Batch insert completed (1,234 rows)")

        # Code display demonstration
        with section("Enhanced Code Display"):
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

        # Table system demonstration
        with section("Enhanced Table System"):
            headers = ["Product ID", "Name", "Category", "Stock", "Price", "Status"]
            rows = [
                [1001, "Laptop Pro X1", "Electronics", 75, "$1,299.99", "✓ In Stock"],
                [1002, "Wireless Headphones", "Audio", 150, "$199.99", "✓ In Stock"],
                [1003, "Smart Watch Series 5", "Wearables", 23, "$399.99", "⚠ Low Stock"],
                [1004, "Gaming Mouse", "Peripherals", 0, "$79.99", "✗ Out of Stock"],
                [1005, "4K Monitor", "Displays", 45, "$599.99", "✓ In Stock"],
            ]

            print_query_results(
                headers, rows, "Product Inventory", summary="5 products tracked across 4 categories", execution_time=0.045
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

            print_config(config_data, "Database Configuration", mask_keys=["api_key"], show_types=True)

        # Progress system demonstration
        with section("Enhanced Progress System"):
            with status("Connecting to database", "Database connected successfully"):
                time.sleep(1.5)

            with progress("Processing records", total=100) as progress_data:
                if progress_data:
                    prog, task = progress_data
                    for i in range(100):
                        time.sleep(0.02)
                        prog.update(task, advance=1)

        # Layout demonstration
        with section("Enhanced Layout System"):
            features = [
                "Ultra-simplified codebase for better maintainability",
                "Complete 2025 design system preservation",
                "Enhanced Unicode support with smart ASCII fallbacks",
                "Thread-safe operations for concurrent usage",
                "Improved error handling with contextual suggestions",
                "Flexible theming and styling system",
            ]

            print_list(features, "Key Features", numbered=True)

            # Markdown demonstration
            markdown_content = """
## Performance Improvements

The simplified UI system includes several **performance enhancements**:

- **Reduced memory footprint** by 40%
- **Faster rendering** with optimized Rich components
- **Better terminal compatibility** detection
- **Improved error recovery** mechanisms
- **Simplified codebase** for easier maintenance

> **Note**: All improvements maintain complete backward compatibility.
"""
            print_markdown(markdown_content, "Release Notes")

        # Error handling demonstration
        with section("Enhanced Error Handling"):
            try:
                raise ConnectionError("Failed to connect to database server at localhost:5432")
            except Exception as e:
                handle_error(
                    e, "Database Connection", suggest_action="Check if the database server is running and accessible"
                )

        print_divider("Demo Complete")
        success("🎉 All Enhanced Demos Complete! 🎉")

        # Display console capabilities
        info("Console capabilities:")
        print_config(console_info, "System Information")

    @app.command()
    def interactive():
        """Enhanced interactive demo showcasing all user input capabilities"""
        try:
            clear_screen()
            print_header("🎯 INTERACTIVE UI DEMO", "Test all user input features")

            # Welcome message with current timestamp
            welcome_message = """
                                ## Welcome to the Interactive Demo

                                **User:** theshashank1
                                **Timestamp:** 2025-06-18 13:57:42 UTC
                                **Version:** Final Simplified Edition

                                This comprehensive demo showcases all interactive UI capabilities including
                                prompts, validations, confirmations, and selections with modern 2025 styling.
                                """
            print_markdown(welcome_message)

            # Basic input demonstrations
            with section("Basic Input & Validation"):
                name = prompt("What's your preferred display name?", default="theshashank1", expected_type=str)
                success(f"Welcome, {name}!")

                experience_level = prompt(
                    "Rate your experience level (1-10)", default=8, expected_type=int, validate=lambda x: 1 <= x <= 10
                )

                if experience_level >= 8:
                    tip(f"Expert level ({experience_level}/10) - You're highly skilled!")
                elif experience_level >= 5:
                    info(f"Intermediate level ({experience_level}/10) - Solid foundation!")
                else:
                    info(f"Beginner level ({experience_level}/10) - Great starting point!")

                if confirm("Would you like to test password input?", default=False):
                    test_password = prompt(
                        "Enter a test password (hidden input)", password=True, validate=lambda x: len(x) >= 6
                    )
                    success(f"Password set successfully (length: {len(test_password)} characters)")

            # Choice and selection demonstrations
            with section("Choice Selection & Menu Options"):
                environment = prompt(
                    "Select your preferred development environment",
                    choices=["development", "staging", "production", "local"],
                    default="development",
                )
                info(f"Environment configured: {environment}")

                database_options = [
                    "PostgreSQL - Robust relational database",
                    "MySQL - Popular open-source database",
                    "SQLite - Lightweight file-based database",
                    "MongoDB - Document-oriented NoSQL database",
                    "Redis - In-memory data structure store",
                ]

                selected_database = select_option("Choose your preferred database system:", database_options, default_idx=0)
                success(f"Database selected: {selected_database}")

                frameworks = ["Django", "FastAPI", "Flask", "Streamlit", "Gradio"]
                framework = select_option("Select your Python web framework:", frameworks, default_idx=1)
                tip(f"Excellent choice! {framework} is perfect for modern development")

            # Advanced validation demonstrations
            with section("Advanced Validation & Configuration"):
                email = prompt(
                    "Enter your email for notifications",
                    default="theshashank1@example.com",
                    validate=lambda x: "@" in x and "." in x.split("@")[-1],
                )
                info(f"Email configured: {email}")

                port = prompt(
                    "Enter API server port", default=8000, expected_type=int, validate=lambda x: 1024 <= x <= 65535
                )
                success(f"API server will run on port {port}")

                log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                log_level = prompt("Select logging level", choices=log_levels, default="INFO")

                themes = ["default", "dark", "light", "high-contrast", "accessibility"]
                theme = select_option("Choose your preferred UI theme:", themes, default_idx=0)
                info(f"Theme applied: {theme}")

            # Confirmation demonstrations
            with section("Confirmations & Decision Points"):
                setup_database = confirm("Initialize database connection with current settings?", default=True)

                if setup_database:
                    success("Database initialization confirmed")

                    # Simulate setup process
                    with progress("Initializing database connection", total=50) as prog_data:
                        if prog_data:
                            prog, task = prog_data
                            for i in range(50):
                                time.sleep(0.05)
                                prog.update(task, advance=1)

                    success("Database connection established successfully!")
                else:
                    info("Database setup skipped")

                if confirm("Would you like to test the danger confirmation style?", default=False, danger=True):
                    warning("This demonstrated the danger confirmation styling")

            # Configuration summary
            with section("Configuration Summary & Results"):
                user_configuration = {
                    "user_name": name,
                    "experience_level": f"{experience_level}/10",
                    "environment": environment,
                    "database": selected_database.split(" - ")[0],
                    "framework": framework,
                    "email": email,
                    "api_port": port,
                    "log_level": log_level,
                    "theme": theme,
                    "database_setup": setup_database,
                    "session_timestamp": "2025-06-18 13:57:42",
                }

                print_config(user_configuration, "Interactive Demo Configuration", mask_keys=["email"], show_types=True)

                # Generate performance metrics
                performance_metrics = [
                    ["Response Time", f"{0.12 + (experience_level * 0.02):.2f}s", "Excellent"],
                    ["Memory Usage", f"{42 + (len(name) * 2)}MB", "Normal"],
                    ["CPU Usage", f"{8 + (port // 200)}%", "Low"],
                    ["Active Connections", f"{port // 10}", "Stable"],
                    ["Success Rate", "99.98%", "Optimal"],
                ]

                print_query_results(
                    ["Metric", "Value", "Status"],
                    performance_metrics,
                    f"System Performance - {framework} on {environment}",
                    summary=f"Optimized for {name} at experience level {experience_level}",
                    execution_time=0.018,
                )

            # Demo completion
            print_divider("Interactive Demo Complete")

            completion_message = f"""
## 🎉 Interactive Demo Complete!

**Congratulations {name}!** You've successfully tested all interactive UI features.

### Features Demonstrated:
- **Text prompts** with default values and type validation
- **Password input** with hidden character display
- **Choice validation** with predefined option sets
- **Menu selection** with numbered options and highlighting
- **Advanced validation** with custom validation functions
- **Confirmation dialogs** with regular and danger styling
- **Progress indicators** with real-time updates
- **Configuration display** with data masking
- **Performance metrics** with execution timing

### Your Final Configuration:
- **Environment:** {environment}
- **Database:** {selected_database.split(' - ')[0]}
- **Framework:** {framework}
- **Theme:** {theme}
- **Performance Level:** Expert

The TESH-Query UI system is production-ready! 🚀
"""
            print_markdown(completion_message)

            if confirm("Would you like to run the interactive demo again?", default=False):
                space()
                info("Restarting interactive demo...")
                time.sleep(1)
                interactive.callback()  # Recursive call to restart
            else:
                success("Thank you for testing the interactive demo!")
                tip("Use these UI patterns in your TESH-Query CLI applications")

        except (typer.Abort, KeyboardInterrupt):
            warning("Interactive demo interrupted by user")
            info("Demo session ended gracefully")
        except Exception as e:
            handle_error(
                e,
                "Interactive Demo",
                show_traceback=True,
                suggest_action="Check your input values and try running the demo again",
            )

    app()
