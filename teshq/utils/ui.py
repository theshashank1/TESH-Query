# Enhanced UI utilities for TESH-Query CLI application.
# Provides modular, reusable UI components using Typer and Rich integration.

import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Generator, List, Optional

import typer
from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.progress import Progress, track  # , TaskID,   # TaskID is not used in the provided code
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class MessageType(Enum):
    """Enumeration for different message types with their styling."""

    INFO = ("ℹ️", "INFO", typer.colors.BLUE)
    SUCCESS = ("✅", "SUCCESS", typer.colors.GREEN)
    WARNING = ("⚠️", "WARNING", typer.colors.YELLOW)
    ERROR = ("❌", "ERROR", typer.colors.RED)
    DEBUG = ("🐛", "DEBUG", typer.colors.MAGENTA)


class UIManager:
    """
    Centralized UI manager for consistent styling and interaction across the CLI.
    """

    def __init__(self, use_rich_console: bool = True):
        """
        Initialize the UI manager.

        Args:
            use_rich_console: Whether to use Rich console for advanced features like spinners
        """
        self._rich_console = RichConsole() if use_rich_console else None

    # --- Message Printing Methods ---

    def print_message(self, message: str, msg_type: MessageType, bold: bool = True):
        """
        Print a message with consistent styling.

        Args:
            message: The message to display
            msg_type: Type of message (INFO, SUCCESS, WARNING, ERROR, DEBUG)
            bold: Whether to make the text bold
        """
        icon, label, color = msg_type.value
        typer.secho(f"{icon} [{label}] {message}", fg=color, bold=bold)

    def info(self, message: str, bold: bool = True):
        """Print an informational message."""
        self.print_message(message, MessageType.INFO, bold)

    def success(self, message: str, bold: bool = True):
        """Print a success message."""
        self.print_message(message, MessageType.SUCCESS, bold)

    def warning(self, message: str, bold: bool = True):
        """Print a warning message."""
        self.print_message(message, MessageType.WARNING, bold)

    def error(self, message: str, bold: bool = True):
        """Print an error message."""
        self.print_message(message, MessageType.ERROR, bold)

    def debug(self, message: str, bold: bool = True):
        """Print a debug message."""
        self.print_message(message, MessageType.DEBUG, bold)

    # --- Code Display Methods ---

    def print_code(
        self,
        code: str,
        language: str = "sql",
        title: Optional[str] = None,
        line_numbers: bool = True,
        theme: str = "monokai",
        border_style: str = "green",
        padding: tuple = (1, 2),
    ):
        """
        Display syntax-highlighted code in a panel.

        Args:
            code: The code to display
            language: Programming language for syntax highlighting
            title: Optional title for the code block
            line_numbers: Whether to show line numbers
            theme: Rich theme for syntax highlighting
            border_style: Border color/style for the panel
            padding: Padding (top/bottom, left/right)
        """
        # Remove "Code" suffix from default title
        effective_title = title if title is not None else f"{language.upper()}"

        syntax = Syntax(code, language, theme=theme, line_numbers=line_numbers, word_wrap=True)
        panel = Panel(
            syntax,
            title=f"[bold white]{effective_title}[/]",  # Keep title bold white, let border define color
            border_style=border_style,
            padding=padding,
            expand=False,
        )
        if self._rich_console:
            self._rich_console.print(panel)
        else:
            # Fallback if Rich console is not available
            if title:  # Use the original title for fallback
                typer.secho(title, bold=True, fg=typer.colors.CYAN)
            typer.echo(code)

    def print_sql(self, sql: str, title: str = "Generated SQL Query"):
        """Convenience method for displaying SQL code."""
        self.print_code(sql, "sql", title, border_style="blue")

    def print_python(self, code: str, title: str = "Python Code"):
        """Convenience method for displaying Python code."""
        self.print_code(code, "python", title, border_style="green")

    # --- Table Display Methods ---

    def print_table(
        self,
        title: str,
        headers: List[str],
        rows: List[List[Any]],
        show_lines: bool = False,
        border_style: str = "cyan",
        header_style: str = "bold magenta",
        **table_kwargs,
    ):
        """
        Display data in a formatted table.

        Args:
            title: Table title
            headers: Column headers
            rows: Table data rows
            show_lines: Whether to show row separators
            border_style: Border color/style
            header_style: Header row styling
            **table_kwargs: Additional Rich Table arguments
        """
        table = Table(
            title=title,
            show_header=True,
            header_style=header_style,
            border_style=border_style,
            show_lines=show_lines,
            **table_kwargs,
        )

        for header in headers:
            table.add_column(header)

        for row in rows:
            # Ensure all row items are strings for Rich Table
            table.add_row(*(str(item) for item in row))

        if self._rich_console:
            self._rich_console.print(table)
        else:
            # Fallback if Rich console is not available
            typer.secho(title, bold=True, fg=typer.colors.CYAN)
            if headers:
                typer.echo("\t".join(headers))
            for row_data in rows:
                typer.echo("\t".join(str(item) for item in row_data))

    def print_query_results(self, headers: List[str], rows: List[List[Any]], query_info: Optional[str] = None):
        """
        Display database query results in a formatted table.

        Args:
            headers: Column names from the query
            rows: Query result rows
            query_info: Optional information about the query
        """
        title = "Query Results"
        if query_info:
            title += f" - {query_info}"

        self.print_table(title=title, headers=headers, rows=rows, show_lines=True, border_style="bright_blue")

    # --- Header and Separators ---

    def print_header(self, text: str, style: str = "bold white on blue", expand: bool = True):
        """
        Print a prominent header.

        Args:
            text: Header text
            style: Rich text styling
            expand: Whether to expand to full terminal width
        """
        panel = Panel(
            Text(
                text, justify="center", style=style
            ),  # Removed style from Text, Panel handles it. Re-added style to Text as Panel style is for border.
            expand=expand,
            # No border for a simple header unless desired, or style the panel itself
            # border_style="dim", # Example if a border is wanted
        )
        if self._rich_console:
            self._rich_console.print(panel)
        else:
            # Fallback if Rich console is not available
            typer.secho(f"\n--- {text} ---", bold=True, fg=typer.colors.BLUE)

    def print_separator(self, char: str = "─", length: int = 50):
        """Print a separator line."""
        if self._rich_console:
            self._rich_console.print(char * length)
        else:
            typer.echo(char * length)

    def print_blank_line(self, count: int = 1):
        """Print blank lines for spacing."""
        for _ in range(count):
            if self._rich_console:
                self._rich_console.print()
            else:
                typer.echo("")

    # --- Progress and Status Methods ---

    def track_progress(self, iterable, description: str = "Processing...", total: Optional[int] = None):
        """
        Track progress of an iterable operation.

        Args:
            iterable: The iterable to track
            description: Description of the operation
            total: Total items (if not determinable from iterable)

        Returns:
            Generator yielding items from the iterable
        """
        # track() uses Rich's global console by default, or one can be passed.
        # This should work fine if Rich is usable.
        if self._rich_console:
            return track(iterable, description=description, total=total, console=self._rich_console)
        else:
            self.info(f"{description} (progress tracking unavailable)")
            yield from iterable  # Simple yield if no rich console

    @contextmanager
    def status_spinner(
        self, message: str, spinner: str = "dots", success_message: Optional[str] = None
    ) -> Generator[Any, None, None]:  # Rich Status object or None
        """
        Context manager for displaying a status spinner.

        Args:
            message: Status message to display
            spinner: Spinner style
            success_message: Message to show on successful completion

        Yields:
            Rich status context for updating the message, or None if Rich is not used.
        """
        if not self._rich_console:
            # Fallback for when Rich console is not available
            self.info(message)
            yield None
            if success_message:
                self.success(success_message)
            return

        status_renderable = Text(message, style="bold green")
        with self._rich_console.status(status_renderable, spinner=spinner) as status:  # Use Text object for styling
            try:
                yield status
                if success_message:
                    status.update(Text(success_message, style="bold green"))  # Use Text object
                    time.sleep(0.5)  # Brief pause to show success message
            except Exception:
                status.update(Text("Operation failed", style="bold red"))  # Use Text object
                time.sleep(0.5)
                raise

        # Add spacing after spinner if Rich is used.
        self.print_blank_line()

    @contextmanager
    def progress_context(
        self, description: str = "Processing..."
    ) -> Generator[Optional[Progress], None, None]:  # Rich Progress object or None
        """
        Context manager for advanced progress tracking.

        Args:
            description: Default description for tasks

        Yields:
            Rich Progress instance for manual task management, or None if Rich is not used.
        """
        if not self._rich_console:
            self.info(description)
            yield None  # Caller should check for None
            return

        # Pass the RichConsole instance to Progress
        with Progress(console=self._rich_console) as progress:
            yield progress

    # --- Interactive Methods ---

    def prompt(
        self,
        text: str,
        default: Any = None,
        hide_input: bool = False,
        confirmation_prompt: bool = False,
        type: Optional[type] = None,  # Shadowing built-in 'type'
        style: str = "cyan",
    ) -> Any:
        """
        Prompt user for input with styling.

        Args:
            text: Prompt text
            default: Default value
            hide_input: Whether to hide input (for passwords)
            confirmation_prompt: Whether to ask for confirmation
            type: Expected input type
            style: Text styling

        Returns:
            User input
        """
        # Typer's prompt doesn't directly accept Rich Text objects for the main prompt text.
        # It does its own styling. For more control, one might print with Rich then use input().
        # However, for simplicity, typer.prompt is fine.
        # The 'style' argument here is conceptual; typer.prompt has its own way.
        # Let's assume 'text' is styled using Typer's fg/bg if needed before calling.
        # Or, we can use Rich to print the prompt, then Python's input().
        # For now, keeping as is, but noting 'style' isn't directly used by typer.prompt like this.
        if self._rich_console:
            self._rich_console.print(Text(text, style=style), end=" ")
            # typer.prompt will print its own prompt string, so this might duplicate.
            # A better way for styled prompts is to print with Rich and then use input()
            # or use Typer's prompt and accept its styling.
            # Sticking to original for now:
            styled_text_for_typer = typer.style(text, fg=typer.colors.CYAN if style == "cyan" else None)  # Basic mapping

        return typer.prompt(
            styled_text_for_typer if self._rich_console else text,  # Use styled text if possible
            default=default,
            hide_input=hide_input,
            confirmation_prompt=confirmation_prompt,
            type=type,
        )

    def confirm(self, text: str, default: bool = False, style: str = "bold yellow") -> bool:  # Conceptual style
        """
        Ask user for confirmation.

        Args:
            text: Confirmation text
            default: Default response
            style: Text styling (conceptual for typer.confirm)

        Returns:
            User's confirmation response
        """
        # Similar to prompt, typer.confirm handles its own styling.
        # Applying basic styling via typer.style:
        color_map = {
            "bold yellow": (typer.colors.YELLOW, True),
            # Add other mappings if needed
        }
        fg_color, is_bold = color_map.get(style, (None, False))
        styled_text_for_typer = typer.style(text, fg=fg_color, bold=is_bold)

        return typer.confirm(styled_text_for_typer, default=default)

    # --- Error Handling ---

    def handle_error(self, error: Exception, context: str = "Operation", show_traceback: bool = False):
        """
        Handle and display errors consistently.

        Args:
            error: The exception that occurred
            context: Context where the error occurred
            show_traceback: Whether to show full traceback
        """
        self.error(f"{context} failed: {str(error)}")  # Uses typer.secho

        if show_traceback:
            import traceback

            tb_str = traceback.format_exc()
            if self._rich_console:
                self.print_blank_line()
                self._rich_console.print("Traceback:", style="bold red")
                self._rich_console.print(tb_str)  # Rich will handle formatting
            else:
                typer.echo("Traceback:", err=True)
                typer.echo(tb_str, err=True)

    # --- Configuration Display ---

    def print_config_item(self, key: str, value: Any, mask: bool = False):
        """
        Display a configuration item.

        Args:
            key: Configuration key
            value: Configuration value
            mask: Whether to mask sensitive values
        """
        display_value = "***masked***" if mask and value else str(value)
        status_icon = "✅" if value else "❌"  # This logic might be too simple for general config values

        if self._rich_console:
            self._rich_console.print(f"{status_icon} {key}: {display_value}")
        else:
            typer.echo(f"{status_icon} {key}: {display_value}")


# --- Global UI Manager Instance ---
ui = UIManager()

# --- Convenience Functions for Direct Import (unchanged, they call ui methods) ---
# ... (rest of the convenience functions and demo functions would go here)
# Make sure they use the global 'ui' instance which now has the corrected methods.


def info(message: str, bold: bool = True) -> None:
    """Print an informational message."""
    ui.info(message, bold)


def success(message: str, bold: bool = True) -> None:
    """Print a success message."""
    ui.success(message, bold)


def warning(message: str, bold: bool = True) -> None:
    """Print a warning message."""
    ui.warning(message, bold)


def error(message: str, bold: bool = True) -> None:
    """Print an error message."""
    ui.error(message, bold)


def debug(message: str, bold: bool = True) -> None:
    """Print a debug message."""
    ui.debug(message, bold)


def print_sql(sql: str, title: str = "Generated SQL Query") -> None:
    """Display SQL code with syntax highlighting."""
    ui.print_sql(sql, title)


def print_query_results(headers: List[str], rows: List[List[Any]], query_info: Optional[str] = None) -> None:
    """Display database query results."""
    ui.print_query_results(headers, rows, query_info)


def track_progress(iterable, description: str = "Processing...", total: Optional[int] = None):
    """Track progress of an operation."""
    return ui.track_progress(iterable, description, total)


@contextmanager
def status_spinner(message: str, spinner: str = "dots", success_message: Optional[str] = None):
    """Context manager for status spinner."""
    # This function needs to be a context manager itself
    # The original global function was not a context manager
    # It should call ui.status_spinner
    with ui.status_spinner(message, spinner, success_message) as status_context:
        yield status_context


@contextmanager
def progress_context(description: str = "Processing..."):
    """Context manager for advanced progress tracking."""
    with ui.progress_context(description) as progress_instance:
        yield progress_instance


def prompt(
    text: str,
    default: Any = None,
    hide_input: bool = False,
    # 'type' parameter removed from here as it's in the class method
    style: str = "cyan",
) -> Any:
    """Prompt user for input."""
    # Call the ui method. Note the 'type' parameter is part of the UIManager.prompt
    return ui.prompt(text, default=default, hide_input=hide_input, style=style)


def confirm(text: str, default: bool = False, style: str = "bold yellow") -> bool:
    """Ask user for confirmation."""
    return ui.confirm(text, default=default, style=style)


# --- Example Usage Functions (should work with the updated UIManager) ---


def demo_basic_messages():
    """Demonstrate basic message types."""
    ui.print_header("🚀 TESH-Query UI Demo - Basic Messages 🚀")
    ui.print_blank_line()

    ui.info("Database connection established successfully")
    ui.success("Query executed and results retrieved")
    ui.warning("Large result set - consider adding LIMIT clause")
    ui.error("Failed to connect to database")
    ui.debug("SQL query generated: SELECT * FROM users")
    ui.print_blank_line()


def demo_code_display():
    """Demonstrate code display capabilities."""
    ui.print_header("Code Display Demo")
    ui.print_blank_line()

    sample_sql = """
    SELECT
        u.name,
        u.email,
        COUNT(o.id) as order_count
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    WHERE u.created_at >= '2024-01-01'
    GROUP BY u.id, u.name, u.email
    ORDER BY order_count DESC
    LIMIT 10;
    """

    ui.print_sql(sample_sql.strip(), "User Orders Query")
    ui.print_blank_line()


def demo_table_display():
    """Demonstrate table display."""
    ui.print_header("Table Display Demo")
    ui.print_blank_line()

    headers = ["User ID", "Name", "Email", "Orders", "Status"]
    rows = [
        [1, "Alice Johnson", "alice@example.com", 15, "[green]Active[/]"],
        [2, "Bob Smith", "bob@example.com", 8, "[green]Active[/]"],
        [3, "Carol White", "carol@example.com", 0, "[yellow]Inactive[/]"],
        [4, "David Brown", "david@example.com", 23, "[green]Active[/]"],
    ]

    ui.print_query_results(headers, rows, "Recent user activity")
    ui.print_blank_line()


def demo_progress_tracking():
    """Demonstrate progress tracking."""
    ui.print_header("Progress Tracking Demo")
    ui.print_blank_line()

    ui.info("Demonstrating simple progress tracking:")
    items = range(50)
    processed = []
    # track_progress is a generator, so iterate over it
    for item in track_progress(items, "Processing database records..."):
        time.sleep(0.05)  # Simulate work
        processed.append(item)

    ui.success(f"Processed {len(processed)} records successfully")
    ui.print_blank_line()


def demo_status_spinner():
    """Demonstrate status spinner."""
    ui.print_header("Status Spinner Demo")
    ui.print_blank_line()

    ui.info("Demonstrating status spinner:")
    # Use the global status_spinner context manager
    with status_spinner("Connecting to database...", success_message="Connected successfully!"):
        time.sleep(2)  # Simulate connection time

    with status_spinner("Executing query...", success_message="Query completed!"):
        time.sleep(1.5)  # Simulate query time

    ui.success("All operations completed successfully")
    # No need for ui.print_blank_line() here if status_spinner handles it
    # The UIManager.status_spinner now adds a blank line if rich console is used.


if __name__ == "__main__":
    # Create a simple demo app
    demo_app = typer.Typer()

    @demo_app.command()
    def all():
        """Run all UI demos."""
        if ui._rich_console:  # Clear only if we have a rich console.
            ui._rich_console.clear()  # Using Rich console's clear.
        else:
            typer.clear()  # Fallback.

        demo_basic_messages()
        demo_code_display()
        demo_table_display()
        demo_progress_tracking()
        demo_status_spinner()
        ui.print_header("🎉 Demo Complete! 🎉", style="bold white on green")

    @demo_app.command()
    def messages():
        """Demo basic message types."""
        demo_basic_messages()

    @demo_app.command()
    def code():
        """Demo code display."""
        demo_code_display()

    @demo_app.command()
    def table():
        """Demo table display."""
        demo_table_display()

    @demo_app.command()
    def progress():
        """Demo progress tracking."""
        demo_progress_tracking()

    @demo_app.command()
    def spinner():
        """Demo status spinner."""
        demo_status_spinner()

    demo_app()
