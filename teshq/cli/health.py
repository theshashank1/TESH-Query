import json
import typer

from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console
from teshq.utils.health import HealthChecker, HealthStatus
from teshq.utils.logging import configure_global_logger
from teshq.utils.ui import error, handle_error, print_header, space, status, success, warning
from rich.table import Table

app = typer.Typer(invoke_without_command=True)

PANEL_DIAGNOSTICS = "⚙️ Diagnostics & Output"


def format_status(check_status: HealthStatus) -> str:
    """Formats the health status with Obsidian Instrument badge styling."""
    if check_status == HealthStatus.HEALTHY:
        return f"[bold {Colors.SUCCESS}]{Icons.check()} Healthy[/bold {Colors.SUCCESS}]"
    elif check_status == HealthStatus.DEGRADED:
        return f"[bold {Colors.WARNING}]{Icons.warn()} Degraded[/bold {Colors.WARNING}]"
    else:
        return f"[bold {Colors.ERROR}]{Icons.cross()} Unhealthy[/bold {Colors.ERROR}]"


@app.callback()
def health(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output health report in machine-readable JSON format (ideal for CI/CD).",
        rich_help_panel=PANEL_DIAGNOSTICS,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show verbose diagnostic latency and enable real-time logs.",
        rich_help_panel=PANEL_DIAGNOSTICS,
    ),
):
    """Check system health and connectivity across database and AI providers."""
    configure_global_logger(enable_cli_output=verbose)

    try:
        if as_json:
            health_checker = HealthChecker()
            health_report = health_checker.run_all_checks()
            print(json.dumps(health_report, indent=2))
            overall_str = health_report.get("status", "unhealthy")
            if overall_str == HealthStatus.UNHEALTHY.value:
                raise typer.Exit(1)
            elif overall_str == HealthStatus.DEGRADED.value:
                raise typer.Exit(2)
            raise typer.Exit(0)

        print_header("System Health Check", "Verifying database and AI provider connectivity...")

        # Use status context manager for the running phase
        with status("Running health checks...", "Health checks completed successfully"):
            health_checker = HealthChecker()
            health_report = health_checker.run_all_checks()

        checks = health_report.get("checks", [])

        if checks:
            table = Table(
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                header_style=f"bold {Colors.TEXT_PRIMARY}",
                title=f"[bold {Colors.PRIMARY}]{Icons.shield()} Diagnostic Checks[/bold {Colors.PRIMARY}]",
                title_justify="left",
                expand=False,
            )
            table.add_column("Component", style=f"bold {Colors.PRIMARY}")
            table.add_column("Status", justify="center")
            table.add_column("Latency", justify="right", style=f"dim {Colors.TEXT_MUTED}")
            table.add_column("Details", style=Colors.TEXT_SECONDARY)

            for check in checks:
                status_str = check.get("status", "unknown")
                try:
                    status_enum = HealthStatus(status_str)
                except ValueError:
                    status_enum = HealthStatus.UNHEALTHY

                duration_ms = check.get("duration_ms", 0)
                dur_str = f"{duration_ms:.1f}ms" if duration_ms > 0 else "<1ms"
                message = check.get("message", "")

                table.add_row(
                    check.get("name", "N/A"),
                    format_status(status_enum),
                    dur_str,
                    message,
                )
            console.print(table)
        else:
            warning("No individual health checks were found or executed.")

        space()

        # Convert overall status string to enum for consistent handling
        overall_status_str = health_report.get("status", "unhealthy")
        try:
            overall_status = HealthStatus(overall_status_str)
        except ValueError:
            overall_status = HealthStatus.UNHEALTHY

        if overall_status == HealthStatus.HEALTHY:
            success("TESH-Query is healthy and ready for queries")
        elif overall_status == HealthStatus.DEGRADED:
            warning("System is operational but has degraded components (check warnings above).")
        else:
            error("System has critical health issues that require attention.")

        if overall_status == HealthStatus.UNHEALTHY:
            raise typer.Exit(1)
        elif overall_status == HealthStatus.DEGRADED:
            raise typer.Exit(2)
        else:
            raise typer.Exit(0)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled.")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(e, "Health Check", suggest_action="Check system configuration and connectivity.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
