# Modern UI utilities for TESH-Query CLI application.
# Contemporary design with sleek aesthetics and smooth interactions.

import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional  # Added Callable for validate

import typer
from rich import box
from rich.align import Align
from rich.console import Console as RichConsole

# from rich.layout import Layout  # Not directly used in the final UIManager methods
# from rich.live import Live  # Not directly used in the final UIManager methods
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn, track
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class Theme(Enum):
    """Modern color palette inspired by contemporary design systems."""

    # Primary colors
    PRIMARY = "#6366F1"  # Indigo - modern and professional
    SECONDARY = "#8B5CF6"  # Violet - complementary accent

    # Status colors
    SUCCESS = "#10B981"  # Emerald - clean success
    WARNING = "#F59E0B"  # Amber - clear warning
    ERROR = "#EF4444"  # Red - clear error
    INFO = "#06B6D4"  # Cyan - friendly info

    # Neutral colors
    TEXT = "#111827"  # Dark gray - high contrast
    MUTED = "#6B7280"  # Medium gray - subtle text
    SUBTLE = "#9CA3AF"  # Light gray - borders/dividers
    BACKGROUND = "#F9FAFB"  # Very light gray - backgrounds

    # Accent colors
    ACCENT = "#EC4899"  # Pink - highlights
    GLOW = "#34D399"  # Mint - special emphasis


class MessageType(Enum):
    """Modern message types with sleek icons and consistent styling."""

    INFO = ("● [INFO]", "info", Theme.INFO.value, "📘")
    SUCCESS = ("● [SUCCESS]", "success", Theme.SUCCESS.value, "✅")
    WARNING = ("● [WARNING]", "warning", Theme.WARNING.value, "⚠️")
    ERROR = ("● [ERROR]", "error", Theme.ERROR.value, "❌")
    DEBUG = ("○ [DEBUG]", "debug", Theme.MUTED.value, "🔍")
    TIP = ("◆ [TIP]", "tip", Theme.ACCENT.value, "💡")
    LOADING = ("◐ [LOADING]", "loading", Theme.PRIMARY.value, "⏳")


class UIManager:
    """
    Modern UI manager with contemporary design and smooth interactions.
    Inspired by modern web interfaces and design systems.
    """

    def __init__(self, use_rich_console: bool = True, quiet_mode: bool = False, theme_mode: str = "modern"):
        self._rich_console = RichConsole() if use_rich_console else None
        self.quiet_mode = quiet_mode
        self.theme_mode = theme_mode  # "modern" for text icons, other for emoji

    # --- Modern Message System ---

    def _format_message(self, message: str, msg_type: MessageType, prefix: str = "") -> str:
        """Create beautifully formatted message with modern styling."""
        icon_format, _label, _color, emoji_icon = msg_type.value
        full_message = f"{prefix}{message}" if prefix else message

        if self.theme_mode == "modern":
            return f"{icon_format} {full_message}"
        else:
            return f"{emoji_icon} {full_message}"

    def print_message(self, message: str, msg_type: MessageType, dim: bool = False, prefix: str = ""):
        """Print message with modern styling and smooth visual hierarchy."""
        if self.quiet_mode and msg_type == MessageType.DEBUG:
            return

        formatted_message = self._format_message(message, msg_type, prefix)
        _icon_format, _label, color, _emoji_icon = msg_type.value

        if self._rich_console:
            style = color
            if dim:
                style += " dim"

            text = Text(formatted_message, style=style)
            self._rich_console.print(text)
        else:
            # Clean fallback with better colors
            color_map = {
                Theme.INFO.value: typer.colors.CYAN,
                Theme.SUCCESS.value: typer.colors.GREEN,
                Theme.WARNING.value: typer.colors.YELLOW,
                Theme.ERROR.value: typer.colors.RED,
                Theme.MUTED.value: typer.colors.WHITE,  # Adjusted for Typer's palette
                Theme.ACCENT.value: typer.colors.MAGENTA,
                Theme.PRIMARY.value: typer.colors.BLUE,
            }
            typer.secho(formatted_message, fg=color_map.get(color, typer.colors.WHITE), dim=dim)

    def info(self, message: str, dim: bool = False):
        """Display info with modern styling."""
        self.print_message(message, MessageType.INFO, dim)

    def success(self, message: str, dim: bool = False):
        """Display success with modern styling."""
        self.print_message(message, MessageType.SUCCESS, dim)

    def warning(self, message: str, dim: bool = False):
        """Display warning with modern styling."""
        self.print_message(message, MessageType.WARNING, dim)

    def error(self, message: str, dim: bool = False):
        """Display error with modern styling."""
        self.print_message(message, MessageType.ERROR, dim)

    def debug(self, message: str, dim: bool = True):
        """Display debug info (respects quiet mode)."""
        self.print_message(message, MessageType.DEBUG, dim)

    def tip(self, message: str, dim: bool = False):
        """Display helpful tip with modern styling."""
        self.print_message(message, MessageType.TIP, dim)

    # --- Modern Code Display ---

    def print_code(
        self,
        code: str,
        language: str = "sql",
        title: Optional[str] = None,
        line_numbers: bool = False,
        theme: str = "github-dark",  # Popular and clean theme
        wrap: bool = True,
    ):
        """Display code with modern syntax highlighting and clean presentation."""
        if not self._rich_console:
            if title:
                typer.secho(f"\n▸ {title}", fg=typer.colors.CYAN, bold=True)
            typer.echo(code)
            typer.echo()  # Add a blank line for spacing
            return

        syntax = Syntax(
            code.strip(),
            language,
            theme=theme,
            line_numbers=line_numbers,
            word_wrap=wrap,
            background_color="default",  # Use terminal's default bg
            padding=(1, 2),  # Consistent padding
        )

        if title:
            panel = Panel(
                syntax,
                title=f"[bold {Theme.PRIMARY.value}]▸ {title}[/]",
                border_style=Theme.SUBTLE.value,
                box=box.ROUNDED,  # Modern rounded box
                padding=(0, 1),  # Panel padding
                expand=False,
            )
            self._rich_console.print()  # Space before panel
            self._rich_console.print(panel)
        else:
            self._rich_console.print(syntax)

        self._rich_console.print()  # Space after code block

    def print_sql(self, sql: str, title: str = "SQL Query"):
        """Display SQL with modern styling."""
        self.print_code(sql, "sql", title, theme="monokai")  # Monokai is good for SQL

    def print_python(self, code: str, title: str = "Python Code"):
        """Display Python with modern styling."""
        self.print_code(code, "python", title, theme="monokai")

    # --- Modern Tables ---

    def print_table(
        self,
        title: Optional[str],
        headers: List[str],
        rows: List[List[Any]],
        show_lines: bool = False,
        max_width: Optional[int] = None,
        highlight_first_col: bool = False,
        table_style: str = "modern",  # "modern" or "clean"
    ):
        """Display table with modern, clean design."""
        if not self._rich_console:
            if title:
                typer.secho(f"\n▸ {title}", fg=typer.colors.CYAN, bold=True)
            if headers:
                typer.echo("  " + " │ ".join(headers))
                typer.echo("  " + "─" * (len(" │ ".join(headers)) + len(headers) * 2))  # Basic separator
            for row in rows:
                typer.echo("  " + " │ ".join(str(item) for item in row))
            typer.echo()
            return

        table = Table(
            show_header=bool(headers),
            header_style=f"bold {Theme.PRIMARY.value}",
            border_style=Theme.SUBTLE.value,
            show_lines=show_lines,
            box=box.SIMPLE if table_style == "clean" else box.MINIMAL_DOUBLE_HEAD,
            expand=False,  # Important for controlled width
            width=max_width,
            pad_edge=False,
        )

        for i, header in enumerate(headers):
            style = f"bold {Theme.ACCENT.value}" if i == 0 and highlight_first_col else "default"
            table.add_column(header, style=style, no_wrap=False)  # Allow wrapping for content

        for row in rows:
            table.add_row(*(str(item) for item in row))

        if title:
            panel = Panel(
                table,
                title=f"[bold {Theme.PRIMARY.value}]▸ {title}[/]",
                border_style=Theme.SUBTLE.value,
                box=box.ROUNDED,
                padding=(1, 2),
            )
            self._rich_console.print()
            self._rich_console.print(panel)
        else:
            self._rich_console.print(table)

        self._rich_console.print()

    def print_query_results(
        self, headers: List[str], rows: List[List[Any]], title: Optional[str] = None, summary: Optional[str] = None
    ):
        """Display query results with modern formatting and statistics."""
        display_title = title or "Query Results"
        if rows:
            result_count = len(rows)
            count_text = f"{result_count:,} row{'s' if result_count != 1 else ''}"
            display_title = f"{display_title} • {count_text}"

        self.print_table(
            display_title,
            headers,
            rows,
            show_lines=False,  # Cleaner for query results
            highlight_first_col=True,
            table_style="modern",
        )

        if summary:
            self.info(summary, dim=True)

    # --- Modern Layout ---

    def print_header(self, text: str, level: int = 1):
        """Print header with modern typography and visual hierarchy."""
        if not self._rich_console:
            prefix = "◆" if level == 1 else "▸"
            color = typer.colors.CYAN if level == 1 else typer.colors.WHITE
            typer.secho(f"\n{prefix} {text.upper() if level == 1 else text}", fg=color, bold=True)
            if level == 1:
                typer.secho("─" * (len(text) + 2), fg=typer.colors.BLUE)  # Simple underline
            return

        self._rich_console.print()  # Space before header
        if level == 1:
            self._rich_console.print(Text(text.upper(), style=f"bold {Theme.PRIMARY.value}"))
            self._rich_console.print(Text("─" * (len(text) + 4), style=Theme.SUBTLE.value))  # Subtle underline
        else:
            self._rich_console.print(Text(text, style=f"bold {Theme.MUTED.value}"))

    def print_divider(self, style: str = "subtle", char: str = "─", length: Optional[int] = None):
        """Print modern divider with subtle styling. Spans console width if length is None."""
        if self._rich_console:
            color = Theme.SUBTLE.value if style == "subtle" else Theme.MUTED.value
            if length is None:
                self._rich_console.rule(style=color, characters=char)
            else:
                self._rich_console.print(f"[{color}]{char * length}[/]")
        else:
            console_width = 80  # Fallback width
            typer.echo(char * (length or console_width))

    def space(self, count: int = 1):
        """Add clean spacing."""
        for _ in range(count):
            if self._rich_console:
                self._rich_console.print()
            else:
                typer.echo("")

    def center_text(self, text: str, style: str = ""):
        """Center text with modern styling."""
        if self._rich_console:
            centered = Align.center(Text(text, style=style))
            self._rich_console.print(centered)
        else:
            # Basic centering for fallback
            console_width = 80  # Fallback width
            typer.echo(text.center(console_width))

    # --- Modern Progress & Status ---

    def track_progress(self, iterable, description: str = "Processing", total: Optional[int] = None):
        """Modern progress tracking with sleek design."""
        if self._rich_console:
            return track(
                iterable,
                description=f"[{Theme.PRIMARY.value}]{description}[/]",
                total=total,
                console=self._rich_console,
                transient=True,  # Clears progress on completion
            )
        else:
            self.info(f"{description}...")
            yield from iterable  # Simple yield for fallback

    @contextmanager
    def status(
        self, message: str, success_message: Optional[str] = None, spinner: str = "dots"  # Rich spinner name
    ) -> Generator[Any, None, None]:
        """Modern status indicator with smooth animations."""
        if not self._rich_console:
            self.info(message)  # Print initial message
            yield None
            if success_message:
                self.success(success_message)
            return

        with self._rich_console.status(f"[{Theme.PRIMARY.value}]{message}[/]", spinner=spinner) as status_context:
            try:
                yield status_context
                if success_message:
                    status_context.update(f"[{Theme.SUCCESS.value}]● {success_message}[/]")
                    time.sleep(0.6)  # Brief pause to show success
            except Exception as e:
                status_context.update(f"[{Theme.ERROR.value}]● Operation Failed: {str(e)}[/]")
                time.sleep(0.6)  # Brief pause to show error
                raise  # Re-raise the exception

    @contextmanager
    def progress(self, description: str = "Processing") -> Generator[Optional[Progress], None, None]:
        """Modern progress context with beautiful design."""
        if not self._rich_console:
            self.info(description)
            yield None
            return

        # Comprehensive progress display
        progress_columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),  # Adapts to console width
            TaskProgressColumn(),  # Percentage
            TimeRemainingColumn(),
        ]
        with Progress(*progress_columns, console=self._rich_console, transient=True) as progress_context:
            yield progress_context

    # --- Modern Input ---

    def prompt(
        self,
        text: str,
        default: Any = None,
        password: bool = False,
        validate: Optional[Callable[[Any], bool]] = None,
        expected_type: Optional[type] = None,
    ) -> Any:
        """Modern input prompt with clean design and type handling."""
        prompt_text_display = f"[{Theme.PRIMARY.value}]◆[/] {text}"
        if default is not None:
            prompt_text_display += f" [dim]({default})[/]"
        prompt_text_display += f"[{Theme.MUTED.value}] ›[/] "

        if self._rich_console:
            self._rich_console.print(Text.from_markup(prompt_text_display), end="")
            # Typer will print its own prompt, so we print ours without a newline
            # and let Typer's prompt appear on the same line or next if empty.
            # For a fully custom Rich prompt, one would use Rich's input and then parse.
            # This is a hybrid approach.
            prompt_for_typer = ""  # Typer prompt will handle the actual input
        else:
            # Fallback uses Typer's default prompt styling
            prompt_for_typer = f"{text} ('{default}' if default else '')"

        while True:
            try:
                # Use Typer's prompt for actual input capture and type conversion
                result = typer.prompt(
                    prompt_for_typer,
                    default=default,
                    hide_input=password,
                    type=expected_type,
                    show_default=not self._rich_console,  # Show Typer's default only in fallback
                )
                if validate:
                    if not validate(result):
                        self.warning("Invalid input. Please try again.")
                        if self._rich_console:  # Re-print prompt if rich
                            self._rich_console.print(Text.from_markup(prompt_text_display), end="")
                        continue
                return result
            except typer.Abort:
                self.info("Operation cancelled.")
                raise  # Or return a specific value indicating cancellation

    def confirm(self, text: str, default: bool = False) -> bool:
        """Modern confirmation prompt."""
        suffix = " [Y/n]" if default else " [y/N]"
        prompt_text_display = f"[{Theme.WARNING.value}]◆[/] {text}{suffix}[{Theme.MUTED.value}] ›[/] "

        if self._rich_console:
            self._rich_console.print(Text.from_markup(prompt_text_display), end="")
            prompt_for_typer = ""
        else:
            prompt_for_typer = f"{text}{suffix}"

        try:
            return typer.confirm(prompt_for_typer, default=default, show_default=not self._rich_console)
        except typer.Abort:
            self.info("Confirmation aborted.")
            return False  # Or re-raise based on desired behavior

    def select_option(self, prompt_text: str, options: List[str], default_idx: int = 0) -> str:
        """Modern option selection with clean design."""
        if not options:
            raise ValueError("Options list cannot be empty.")

        self.info(prompt_text)
        for i, option in enumerate(options):
            marker = "●" if i == default_idx else "○"
            style = f"bold {Theme.PRIMARY.value}" if i == default_idx else Theme.MUTED.value
            if self._rich_console:
                self._rich_console.print(f"  [{style}]{marker} {i + 1}. {option}[/]")
            else:
                typer.echo(f"  {marker} {i + 1}. {option}")

        while True:
            try:
                choice_num_str = self.prompt("Select option number", default=str(default_idx + 1), expected_type=str)
                choice_num = int(choice_num_str)
                if 1 <= choice_num <= len(options):
                    return options[choice_num - 1]
                else:
                    self.warning(f"Please select a number between 1 and {len(options)}.")
            except ValueError:
                self.warning("Invalid input. Please enter a number.")
            except typer.Abort:
                self.info("Selection cancelled.")
                raise  # Or return a specific value

    # --- Modern Error Handling ---

    def handle_error(
        self, error: Exception, context: str = "Operation", show_details: bool = False, suggest_fix: Optional[str] = None
    ):
        """Modern error display with helpful suggestions."""
        self.error(f"{context} failed: {type(error).__name__} - {str(error)}")

        if suggest_fix:
            self.tip(f"Suggestion: {suggest_fix}")

        if show_details and self._rich_console:
            import traceback

            self._rich_console.print("\n[dim]Details:[/]")
            tb_text = traceback.format_exc()
            panel = Panel(
                Text(tb_text, style=Theme.MUTED.value),  # Traceback text styled
                title="[dim]Traceback[/]",
                border_style=Theme.ERROR.value,  # Error border for traceback
                box=box.ROUNDED,
                padding=(0, 1),
            )
            self._rich_console.print(panel)
        elif show_details:  # Fallback for no rich console
            import traceback

            typer.echo(f"\nDetails:\n{traceback.format_exc()}", err=True)

    # --- Modern Configuration Display ---

    def print_config(self, config: Dict[str, Any], title: str = "Configuration", mask_keys: Optional[List[str]] = None):
        """Display configuration with modern formatting."""
        mask_keys_lower = [k.lower() for k in (mask_keys or [])]

        if title:
            self.print_header(title, level=2)

        if self._rich_console:
            table = Table(box=None, show_header=False, padding=(0, 1, 0, 1))
            table.add_column(style=Theme.MUTED.value)  # Key column
            table.add_column()  # Value column

            for key, value in config.items():
                display_value = "••••••••" if key.lower() in mask_keys_lower and value else str(value)
                table.add_row(f"{key}:", display_value)
            self._rich_console.print(table)
        else:  # Fallback
            for key, value in config.items():
                display_value = "••••••••" if key.lower() in mask_keys_lower and value else str(value)
                typer.echo(f"  {key}: {display_value}")
        self.space()

    # --- Utility Methods ---

    def clear_screen(self):
        """Clear console with modern transition (if supported)."""
        if self._rich_console:
            self._rich_console.clear()
        else:
            typer.clear()

    def set_quiet_mode(self, quiet: bool):
        """Toggle quiet mode (suppresses debug messages)."""
        self.quiet_mode = quiet
        self.debug(f"Quiet mode {'enabled' if quiet else 'disabled'}.")


# --- Global Instance ---
ui = UIManager(theme_mode="")


# --- Modern Convenience Functions ---
def info(message: str, dim: bool = False):
    ui.info(message, dim)


def success(message: str, dim: bool = False):
    ui.success(message, dim)


def warning(message: str, dim: bool = False):
    ui.warning(message, dim)


def error(message: str, dim: bool = False):
    ui.error(message, dim)


def debug(message: str, dim: bool = True):
    ui.debug(message, dim)


def tip(message: str, dim: bool = False):
    ui.tip(message, dim)


def print_sql(sql: str, title: str = "SQL Query"):
    ui.print_sql(sql, title)


def print_python(code: str, title: str = "Python Code"):
    ui.print_python(code, title)


def print_query_results(
    headers: List[str], rows: List[List[Any]], title: Optional[str] = None, summary: Optional[str] = None
):
    ui.print_query_results(headers, rows, title, summary)


def print_table(title: Optional[str], headers: List[str], rows: List[List[Any]], **kwargs):
    ui.print_table(title, headers, rows, **kwargs)


def print_config(config: Dict[str, Any], title: str = "Configuration", mask_keys: Optional[List[str]] = None):
    ui.print_config(config, title, mask_keys)


def print_header(text: str, level: int = 1):
    ui.print_header(text, level)


def print_divider(style: str = "subtle", char: str = "─", length: Optional[int] = None):
    ui.print_divider(style, char, length)


def space(count: int = 1):
    ui.space(count)


def center_text(text: str, style: str = ""):
    ui.center_text(text, style)


def track_progress(iterable, description: str = "Processing", total: Optional[int] = None):
    return ui.track_progress(iterable, description, total)


@contextmanager
def status(message: str, success_message: Optional[str] = None, spinner: str = "dots"):
    with ui.status(message, success_message, spinner) as status_context:
        yield status_context


@contextmanager
def progress(description: str = "Processing"):
    with ui.progress(description) as progress_instance:
        yield progress_instance


def prompt(
    text: str,
    default: Any = None,
    password: bool = False,
    validate: Optional[Callable[[Any], bool]] = None,
    expected_type: Optional[type] = None,
) -> Any:
    return ui.prompt(text, default, password, validate, expected_type)


def confirm(text: str, default: bool = False) -> bool:
    return ui.confirm(text, default)


def select_option(prompt_text: str, options: List[str], default_idx: int = 0) -> str:
    return ui.select_option(prompt_text, options, default_idx)


def clear_screen():
    ui.clear_screen()


def set_quiet_mode(quiet: bool):
    ui.set_quiet_mode(quiet)


# --- These are drivers for testing ---


# --- Modern Demo Functions ---
def demo_messages():
    ui.print_header("Message System", level=1)
    info("Database connection established.")
    success("Query executed successfully (0.23s).")
    warning("Large result set detected (15,000 rows).")
    error("Connection timeout after 30 seconds.")
    debug("SQL: SELECT * FROM users WHERE status = 'active'")
    tip("Use `LIMIT` clause to improve performance for large queries.")
    ui.print_message("Custom emoji message (theme_mode != 'modern')", MessageType.LOADING, prefix="Job XYZ: ")
    space()


def demo_code_display():
    ui.print_header("Code Display", level=1)
    sample_sql = """
    SELECT
        u.id,
        u.name,
        u.email,
        COUNT(o.id) as order_count,
        SUM(o.total_amount) as total_spent
    FROM customers u
    LEFT JOIN orders o ON u.id = o.customer_id
    WHERE u.registration_date >= DATE('now', '-1 year')
      AND u.is_active = TRUE
    GROUP BY 1, 2, 3
    HAVING COUNT(o.id) > 0
    ORDER BY total_spent DESC
    LIMIT 10;
    """
    print_sql(sample_sql, "Customer Analytics Query")
    print_python("class MyClass:\n    def __init__(self):\n        pass", "Sample Python Class")


def demo_table_display():
    ui.print_header("Data Visualization", level=1)
    headers = ["ID", "Product Name", "Category", "Stock", "Price"]
    rows = [
        [1, "Laptop Pro X", "Electronics", 75, "$1299.99"],
        [2, "Organic Coffee Beans", "Groceries", 250, "$18.50"],
        [3, "Running Shoes V2", "Apparel", 120, "$89.95"],
        [4, "Smart Home Hub", "Electronics", 40, "$149.00"],
    ]
    print_query_results(headers, rows, "Inventory Overview", summary="Stock levels are healthy across major categories.")
    print_table("Simple Table (Clean Style)", headers[:3], rows[:2], table_style="clean", show_lines=True)


def demo_interactive_elements():
    ui.print_header("Interactive Elements", level=1)
    try:
        name = prompt("Enter your name", default="Guest", expected_type=str)
        info(f"Hello, {name}!")

        age = prompt("Enter your age", expected_type=int, validate=lambda x: x > 0)
        success(f"Age confirmed: {age}")

        db_options = ["PostgreSQL", "MySQL", "SQLite", "MongoDB"]
        selected_db = select_option("Choose your database:", db_options, default_idx=1)
        success(f"Database selected: {selected_db}")

        if confirm("Proceed with data migration?", default=False):
            success("Data migration initiated.")
        else:
            warning("Data migration cancelled by user.")
    except typer.Abort:
        error("Interactive demo aborted by user.")
    except Exception as e:
        ui.handle_error(e, "Interactive Demo", show_details=True)
    space()


def demo_progress_indicators():
    ui.print_header("Progress Visualization", level=1)
    info("Simulating file downloads:")
    with progress("Downloading files") as p:
        task1 = p.add_task("image.jpg", total=100)
        task2 = p.add_task("archive.zip", total=150)
        while not p.finished:
            p.update(task1, advance=0.9)
            p.update(task2, advance=0.6)
            time.sleep(0.02)
    success("Downloads complete.")

    items = range(50)
    for _item in track_progress(items, "Processing records", total=len(items)):
        time.sleep(0.03)
    success("Record processing complete.")

    with status(
        "Connecting to external API...", success_message="API Connection successful!", spinner="aesthetic"
    ):  # Changed spinner
        time.sleep(1.5)
    space()


def demo_layout_and_config():
    ui.print_header("Layout & Configuration", level=1)
    center_text("✨ TESH-Query Enhanced UI ✨", style=f"bold {Theme.ACCENT.value}")
    space()
    print_divider(length=40)
    print_header("System Configuration", level=2)
    config_data = {
        "username": "testuser",
        "api_key": "dkf93kdf93kdfkd",
        "timeout": 30,
        "debug_mode": True,
        "connection_string": "postgres://user:pass@host:port/db",
    }
    print_config(config_data, title=None, mask_keys=["api_key", "connection_string"])  # Title already printed by header
    space()


if __name__ == "__main__":
    # Create a simple Typer app to run demos
    app = typer.Typer(
        name="TESH-Query UI Demo",
        help="Showcase of modern UI components.",
        rich_markup_mode="rich",  # Enable Rich markup in Typer help
    )

    @app.command()
    def all(quiet: bool = typer.Option(False, "--quiet", "-q", help="Enable quiet mode.")):
        """Run all UI demos."""
        set_quiet_mode(quiet)
        clear_screen()
        center_text("🚀 TESH-Query UI Showcase 🚀", style=f"bold {Theme.PRIMARY.value}")
        space(1)

        demo_messages()
        demo_code_display()
        demo_table_display()
        demo_interactive_elements()
        demo_progress_indicators()
        demo_layout_and_config()

        print_divider(style="bold", char="═")
        center_text("🎉 All Demos Complete! 🎉", style=f"bold {Theme.SUCCESS.value}")
        space()

    @app.command()
    def messages():
        demo_messages()

    @app.command()
    def code():
        demo_code_display()

    @app.command()
    def table():
        demo_table_display()

    @app.command()
    def interactive():
        demo_interactive_elements()

    @app.command()
    def progress_demo():
        demo_progress_indicators()  # Renamed to avoid conflict

    @app.command()
    def layout():
        demo_layout_and_config()

    app()
