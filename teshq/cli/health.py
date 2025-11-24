import typer

from teshq.utils.health import HealthChecker, HealthStatus
from teshq.utils.logging import configure_global_logger
from teshq.utils.ui import error, handle_error, print_header, print_table, space, success, warning

app = typer.Typer(invoke_without_command=True)


def format_status(status: HealthStatus) -> str:
    """Formats the health status with color and icon for table display."""
    if status == HealthStatus.HEALTHY:
        return f"[green]✓ {status.value}[/green]"
    elif status == HealthStatus.DEGRADED:
        return f"[yellow]⚠ {status.value}[/yellow]"
    else:
        return f"[red]✗ {status.value}[/red]"


@app.callback()
def health(
    log: bool = typer.Option(
        False,
        "--log",
        help="Enable real-time logging output to CLI (logs are always saved to file).",
    ),
):
    """Check system health and connectivity."""
    configure_global_logger(enable_cli_output=log)

    try:
        print_header("System Health Check", "Running all system checks...")

        health_checker = HealthChecker()
        health_report = health_checker.run_all_checks()

        headers = ["Component", "Status", "Details"]
        rows = []
        checks = health_report.get("checks", [])

        if checks:
            for check in checks:
                status_enum = check.get("status", HealthStatus.UNHEALTHY)
                rows.append(
                    [
                        check.get("name", "N/A"),
                        format_status(status_enum),
                        check.get("details", "-"),
                    ]
                )
            print_table("Health Check Details", headers, rows)
        else:
            warning("No individual health checks were found or executed.")

        space()

        overall_status = health_report["status"]
        if overall_status == HealthStatus.HEALTHY:
            success("🎉 All systems are healthy and operational!")
        elif overall_status == HealthStatus.DEGRADED:
            warning("⚠️  System is operational but has some issues that should be addressed.")
        else:
            error("❌ System has critical health issues that require immediate attention.")

        if overall_status == HealthStatus.UNHEALTHY:
            raise typer.Exit(1)
        elif overall_status == HealthStatus.DEGRADED:
            raise typer.Exit(2)

    except Exception as e:
        handle_error(e, "Health Check", suggest_action="Check system configuration and connectivity.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
