"""
Telemetry management command for TESH-Query.

Allows users to view the current telemetry status and opt in or out of
anonymous usage tracking.
"""

import typer

from teshq.utils.telemetry import (
    _LOCAL_LOG,
    _OPT_OUT_ENV,
    is_telemetry_enabled,
    set_telemetry_enabled,
)
from teshq.utils.ui import info, success, warning

app = typer.Typer(name="telemetry", help="Manage anonymous usage telemetry.", invoke_without_command=True)


@app.callback()
def telemetry(
    ctx: typer.Context,
    disable: bool = typer.Option(False, "--disable", help="Opt out of anonymous usage telemetry."),
    enable: bool = typer.Option(False, "--enable", help="Re-enable anonymous usage telemetry."),
    status: bool = typer.Option(False, "--status", help="Show current telemetry status."),
):
    """
    Manage anonymous usage telemetry.

    Telemetry is enabled by default.  It collects only command names,
    feature flags, and error types — never query text or credentials.

    Examples:

      teshq telemetry --status

      teshq telemetry --disable

      teshq telemetry --enable
    """
    if disable:
        set_telemetry_enabled(False)
        success("Telemetry disabled.  You can re-enable it at any time with: teshq telemetry --enable")
        raise typer.Exit()

    if enable:
        set_telemetry_enabled(True)
        success("Telemetry enabled.  Thank you for helping improve TESH-Query!")
        raise typer.Exit()

    # Default: show status
    _print_status()


def _print_status() -> None:
    enabled = is_telemetry_enabled()
    state = "[green]enabled[/green]" if enabled else "[yellow]disabled[/yellow]"
    info(f"Telemetry status: {state}")
    info("")
    info("What is collected (anonymous):")
    info("  • Command names")
    info("  • Feature flags used")
    info("  • Error types (NOT error messages)")
    info("  • CLI version")
    info("")
    info("What is NEVER collected:")
    info("  • Query text or SQL")
    info("  • Database URLs or credentials")
    info("  • Personal information")
    info("")
    if _LOCAL_LOG.exists():
        info(f"Local telemetry log: {_LOCAL_LOG}")
    else:
        info("Local telemetry log: (no events recorded yet)")
    info("")

    if enabled:
        warning("To opt out: teshq telemetry --disable")
    else:
        info("To opt back in: teshq telemetry --enable")
    info(f"Or set environment variable: {_OPT_OUT_ENV}=1 to disable for this session.")
