"""
Token analytics CLI commands for TESH-Query.

Provides commands to view local token usage and summaries recorded in usage_metrics.jsonl.
For advanced session tracking and flame graphs, use the Logfire dashboard.
"""

import json

import typer
from rich.console import Group
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from teshq.cli.ui.theme import ROUNDED_BOX, Colors, Icons, console
from teshq.telemetry.analytics import get_summary, reset_metrics
from teshq.utils.ui import error, info, success

app = typer.Typer(
    name="analytics",
    help="View local LLM token usage analytics, estimated costs, and pricing.",
    invoke_without_command=True,
)

PANEL_OUTPUT = "📊 Metrics & Output"
PANEL_ACTIONS = "⚙️ Actions"


@app.callback(invoke_without_command=True)
def analytics_default(ctx: typer.Context):
    """Default handler: Display usage summary if no subcommand was specified."""
    if ctx.invoked_subcommand is None:
        show_summary(as_json=False)


@app.command("show")
def show_summary(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output metrics summary in machine-readable JSON format.",
        rich_help_panel=PANEL_OUTPUT,
    ),
):
    """Show global native usage summary from local metrics."""
    try:
        summary = get_summary()

        if as_json:
            print(json.dumps(summary, indent=2))
            raise typer.Exit(0)

        # Determine Date Range
        if summary.get("first_seen") and summary.get("last_seen"):
            dates = (
                f"[bold {Colors.PRIMARY}]{summary['first_seen']}[/bold {Colors.PRIMARY}] to "
                f"[bold {Colors.PRIMARY}]{summary['last_seen']}[/bold {Colors.PRIMARY}]"
            )
        else:
            dates = f"[{Colors.TEXT_MUTED}]No recorded activity yet[/{Colors.TEXT_MUTED}]"

        total_queries = summary.get("total_queries", 0)
        successful_queries = summary.get("successful_queries", 0)
        failed_queries = summary.get("failed_queries", 0)
        total_tokens = summary.get("total_tokens", 0)
        prompt_tokens = summary.get("prompt_tokens", 0)
        completion_tokens = summary.get("completion_tokens", 0)
        cost_usd = summary.get("estimated_cost_usd", 0.0)
        avg_latency = summary.get("avg_latency_ms", 0.0)
        total_commands = summary.get("total_commands", 0)

        success_pct = (successful_queries / total_queries * 100) if total_queries > 0 else 0.0

        # KPI Tiles Grid
        kpi_table = Table.grid(padding=(0, 3))
        kpi_table.add_column()
        kpi_table.add_column()
        kpi_table.add_column()
        kpi_table.add_column()

        # Row 1: Headers / Category labels
        kpi_table.add_row(
            Text("Total Queries:", style=f"bold {Colors.TEXT_MUTED}"),
            Text("Tokens Consumed:", style=f"bold {Colors.TEXT_MUTED}"),
            Text("Estimated Cost:", style=f"bold {Colors.TEXT_MUTED}"),
            Text("Avg Latency:", style=f"bold {Colors.TEXT_MUTED}"),
        )

        # Row 2: Hero KPI Numbers
        kpi_table.add_row(
            Text(f"{total_queries:,}", style=f"bold {Colors.TEXT_PRIMARY}"),
            Text(f"{total_tokens:,}", style=f"bold {Colors.AI_ACCENT}"),
            Text(f"${cost_usd:.4f}", style=f"bold {Colors.WARNING}"),
            Text(f"{avg_latency:.1f} ms", style=f"bold {Colors.PRIMARY}"),
        )

        # Row 3: Sub-metrics
        success_style = Colors.SUCCESS if success_pct >= 90 else Colors.WARNING
        ok_err_str = (
            f"[{success_style}]{successful_queries:,} ok[/{success_style}] [dim]·[/dim] "
            f"[{Colors.ERROR}]{failed_queries:,} err[/{Colors.ERROR}]"
        )
        kpi_table.add_row(
            Text.from_markup(ok_err_str),
            Text.from_markup(f"[dim]{prompt_tokens:,} in · {completion_tokens:,} out[/dim]"),
            Text.from_markup(f"[dim]{total_commands:,} CLI runs[/dim]"),
            Text.from_markup(f"[{success_style}]{success_pct:.1f}% success[/{success_style}]"),
        )

        period_line = Text()
        period_line.append(f"  {Icons.time()} Activity: ", style=f"{Colors.TEXT_MUTED}")
        period_line.append_text(Text.from_markup(dates))

        content = Group(
            period_line,
            Text(""),
            kpi_table,
        )

        console.print(
            Panel(
                content,
                title=f"[bold {Colors.PRIMARY}]⟡ Local Usage & Token Analytics[/bold {Colors.PRIMARY}]",
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                padding=(1, 2),
                expand=False,
            )
        )
        console.print()

        # Provider Breakdown
        if summary.get("provider_breakdown"):
            table = Table(
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_SUBTLE,
                header_style=f"bold {Colors.PRIMARY}",
                title=f"[{Colors.TEXT_TERTIARY}]AI Provider Distribution[/{Colors.TEXT_TERTIARY}]",
                title_justify="left",
                expand=False,
            )
            table.add_column("Provider", style=f"bold {Colors.TEXT_PRIMARY}")
            table.add_column("Queries", justify="right", style=Colors.AI_ACCENT)
            table.add_column("Share", justify="right", style=Colors.TEXT_SECONDARY)
            table.add_column("Distribution", width=14)

            total_prov_queries = sum(summary["provider_breakdown"].values()) or 1
            for prov, count in summary["provider_breakdown"].items():
                share = count / total_prov_queries
                bar_len = int(share * 10)
                bar = f"[{Colors.PRIMARY}]{'█' * bar_len}[/{Colors.PRIMARY}][dim]{'░' * (10 - bar_len)}[/dim]"
                table.add_row(prov.title(), f"{count:,}", f"{share:.1%}", bar)
            console.print(table)
            console.print()

        # Command Breakdown
        if summary.get("command_breakdown"):
            table = Table(
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_SUBTLE,
                header_style=f"bold {Colors.PRIMARY}",
                title=f"[{Colors.TEXT_TERTIARY}]CLI Command Invocations[/{Colors.TEXT_TERTIARY}]",
                title_justify="left",
                expand=False,
            )
            table.add_column("Command", style=f"bold {Colors.TEXT_PRIMARY}")
            table.add_column("Count", justify="right", style=Colors.TEXT_SECONDARY)
            table.add_column("Share", justify="right", style=Colors.TEXT_MUTED)

            total_cmds = sum(summary["command_breakdown"].values()) or 1
            for cmd, count in summary["command_breakdown"].items():
                share = count / total_cmds
                table.add_row(cmd, f"{count:,}", f"{share:.1%}")
            console.print(table)

        console.print(
            f"\n[dim {Colors.TEXT_MUTED}]Note: Local metrics reflect this machine only. "
            f"For cloud tracing, check your configured Logfire dashboard.[/dim {Colors.TEXT_MUTED}]"
        )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        error(f"Failed to load analytics summary: {e}")
        raise typer.Exit(1)


@app.command("reset")
def reset_local_metrics(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Confirm reset without prompting.",
        rich_help_panel=PANEL_ACTIONS,
    ),
):
    """Clear the local usage metrics log file."""
    try:
        if not yes:
            try:
                confirmed = Confirm.ask(
                    f"[{Colors.WARNING}]Reset all local token and execution metrics?[/{Colors.WARNING}]",
                    default=False,
                )
            except KeyboardInterrupt:
                console.print(f"\n[{Colors.TEXT_MUTED}]Reset cancelled.[/{Colors.TEXT_MUTED}]")
                raise typer.Exit(0)

            if not confirmed:
                info("Metrics reset cancelled.")
                raise typer.Exit(0)

        success_reset = reset_metrics()
        if success_reset:
            success("Local metrics have been reset.")
        else:
            info("Metrics file was already empty or could not be found.")
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        error(f"Failed to reset metrics: {e}")
        raise typer.Exit(1)


@app.command("pricing")
def show_pricing_info():
    """Show current LLM pricing information for cost estimation."""
    try:
        from teshq.telemetry.pricing import TokenPricingCalculator

        pricing = TokenPricingCalculator.PRICING_MAP

        table = Table(
            box=ROUNDED_BOX,
            border_style=Colors.BORDER_SUBTLE,
            header_style=f"bold {Colors.PRIMARY}",
            title=f"[bold {Colors.PRIMARY}]⟡ LLM Pricing Reference[/bold {Colors.PRIMARY}] [dim](per 1K tokens)[/dim]",
            title_justify="left",
            expand=False,
        )
        table.add_column("Provider", style=f"bold {Colors.TEXT_PRIMARY}")
        table.add_column("Model", style=Colors.AI_ACCENT)
        table.add_column("Input Rate", justify="right", style=Colors.TEXT_SECONDARY)
        table.add_column("Output Rate", justify="right", style=Colors.TEXT_SECONDARY)

        for provider, models in pricing.items():
            for model, costs in models.items():
                table.add_row(
                    provider.title(),
                    model,
                    f"${costs['input']:.4f}",
                    f"${costs['output']:.4f}",
                )

        console.print(table)
        console.print(
            f"\n[dim {Colors.TEXT_MUTED}]Note: Rates are benchmark estimates per 1,000 tokens "
            f"for inference cost calculations.[/dim {Colors.TEXT_MUTED}]\n"
        )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        error(f"Failed to show pricing info: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
