"""
TESH-Query CLI User Interface Package
All UI, display, and interaction functions.

Author: theshashank1
Last Updated: 2025-06-19 17:20:54 UTC
"""

# Import ALL UI functions here since this is the UI package
from teshq.utils.ui import (
    Colors,
    Icons,
    MessageType,
    ModernUI,
    clear_screen,
    confirm,
    debug,
    error,
    get_console_info,
    handle_error,
    indent_context,
    info,
    print_code,
    print_config,
    print_divider,
    print_footer,
    print_header,
    print_json,
    print_list,
    print_markdown,
    print_query_results,
    print_sql,
    print_table,
    print_yaml,
    progress,
    prompt,
    section,
    select_option,
    set_quiet_mode,
    space,
    status,
    success,
    tip,
    warning,
)

# Optional formatter functions
try:
    # Removed unused imports to resolve F401 error
    _HAS_FORMATTER = True
except ImportError:
    _HAS_FORMATTER = False

# Comprehensive UI __all__ - this is the UI package, so include everything
__all__ = [
    # Core messaging
    "info",
    "success",
    "warning",
    "error",
    "debug",
    "tip",
    # Layout
    "space",
    "print_header",
    "print_footer",
    "print_divider",
    # Code display
    "print_code",
    "print_sql",
    "print_json",
    "print_yaml",
    # Tables and data
    "print_table",
    "print_query_results",
    "print_config",
    "print_list",
    "print_markdown",
    # Progress
    "status",
    "progress",
    # Interactive
    "prompt",
    "confirm",
    "select_option",
    # Error handling
    "handle_error",
    # Context managers
    "section",
    "indent_context",
    # Utilities
    "clear_screen",
    "set_quiet_mode",
    "get_console_info",
    # Classes
    "ModernUI",
    "Colors",
    "Icons",
    "MessageType",
]


def get_ui_info():
    """Get information about available UI features."""
    return {
        "formatter_available": _HAS_FORMATTER,
        "total_functions": len(__all__),
        "interactive_functions": ["prompt", "confirm", "select_option"],
        "display_functions": [f for f in __all__ if f.startswith("print_")],
    }
