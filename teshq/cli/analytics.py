"""
Token analytics CLI commands for TESH-Query.

Provides commands to view local token usage and summaries recorded in usage_metrics.jsonl.
For advanced session tracking and flame graphs, use the Logfire dashboard.
"""

import json
from typing import Optional
import typer
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console
from teshq.telemetry.analytics import get_summary, reset_metrics
from teshq.utils.ui import error, info, success, warning

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
            dates = f"[bold {Colors.PRIMARY}]{summary['first_seen']}[/bold {Colors.PRIMARY}] to [bold {Colors.PRIMARY}]{summary['last_seen']}[/bold {Colors.PRIMARY}]"
        else:
            dates = f"[{Colors.TEXT_MUTED}]No recorded activity yet[/{Colors.TEXT_MUTED}]"

        # Main metrics panel
        info_text = f"""[{Colors.TEXT_TERTIARY}]Activity Period:[/{Colors.TEXT_TERTIARY}] {dates}

[{Colors.TEXT_TERTIARY}]Total Queries:[/{Colors.TEXT_TERTIARY}]    [bold {Colors.TEXT_PRIMARY}]{summary['total_queries']:,}[/bold {Colors.TEXT_PRIMARY}]
  ├─ [{Colors.SUCCESS}]Successful:[/{Colors.SUCCESS}]   [bold {Colors.SUCCESS}]{summary['successful_queries']:,}[/bold {Colors.SUCCESS}]
  └─ [{Colors.ERROR}]Failed:[/{Colors.ERROR}]       [bold {Colors.ERROR}]{summary['failed_queries']:,}[/bold {Colors.ERROR}]

[{Colors.TEXT_TERTIARY}]Tokens Used:[/{Colors.TEXT_TERTIARY}]      [bold {Colors.AI_ACCENT}]{summary['total_tokens']:,}[/bold {Colors.AI_ACCENT}]
  ├─ [dim]Prompt:[/dim]       {summary['prompt_tokens']:,}
  └─ [dim]Completion:[/dim]   {summary['completion_tokens']:,}

[{Colors.TEXT_TERTIARY}]Estimated Cost:[/{Colors.TEXT_TERTIARY}]   [bold {Colors.WARNING}]${summary['estimated_cost_usd']:.4f}[/bold {Colors.WARNING}]
[{Colors.TEXT_TERTIARY}]Avg Latency:[/{Colors.TEXT_TERTIARY}]      [bold {Colors.TEXT_PRIMARY}]{summary['avg_latency_ms']} ms[/bold {Colors.TEXT_PRIMARY}]
[{Colors.TEXT_TERTIARY}]CLI Invocations:[/{Colors.TEXT_TERTIARY}]  [bold {Colors.TEXT_PRIMARY}]{summary['total_commands']:,}[/bold {Colors.TEXT_PRIMARY}]"""

        console.print(
            Panel(
                info_text,
                title=f"[bold {Colors.PRIMARY}]{Icons.token()} Local Usage & Token Analytics[/bold {Colors.PRIMARY}]",
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                expand=False,
            )
        )

        # Provider Breakdown
        if summary.get("provider_breakdown"):
            table = Table(
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                header_style=f"bold {Colors.PRIMARY}",
                title="[bold]AI Provider Distribution[/bold]",
                expand=False,
            )
            table.add_column("Provider", style=f"bold {Colors.TEXT_PRIMARY}")
            table.add_column("Queries", justify="right", style=Colors.AI_ACCENT)
            for prov, count in summary["provider_breakdown"].items():
                table.add_row(prov.title(), f"{count:,}")
            console.print(table)
            console.print()

        # Command Breakdown
        if summary.get("command_breakdown"):
            table = Table(
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                header_style=f"bold {Colors.PRIMARY}",
                title="[bold]CLI Command Invocations[/bold]",
                expand=False,
            )
            table.add_column("Command", style=f"bold {Colors.TEXT_PRIMARY}")
            table.add_column("Count", justify="right", style=Colors.TEXT_SECONDARY)
            for cmd, count in summary["command_breakdown"].items():
                table.add_row(cmd, f"{count:,}")
            console.print(table)

        console.print(
            f"\n[dim {Colors.TEXT_MUTED}]Note: Local metrics reflect this machine only. For cloud tracing, check your configured Logfire dashboard.[/dim {Colors.TEXT_MUTED}]"
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
        from rich.tree import Tree
        from teshq.telemetry.pricing import TokenPricingCalculator

        console.print(
            Panel(
                f"[bold {Colors.TEXT_PRIMARY}]LLM Pricing Directory[/bold {Colors.TEXT_PRIMARY}]\n"
                f"[dim {Colors.TEXT_MUTED}]Standard rates per 1,000 tokens for inference cost estimations[/dim {Colors.TEXT_MUTED}]",
                title=f"[bold {Colors.WARNING}]{Icons.cost()} Token Pricing[/bold {Colors.WARNING}]",
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                expand=False,
            )
        )

        pricing = TokenPricingCalculator.PRICING_MAP

        for provider, models in pricing.items():
            url = TokenPricingCalculator.get_pricing_url(provider)
            tree = Tree(f"[bold {Colors.PRIMARY}]{provider.title()}[/bold {Colors.PRIMARY}] [dim]({url})[/dim]")

            for model, costs in models.items():
                model_node = tree.add(f"[bold {Colors.AI_ACCENT}]{model}[/bold {Colors.AI_ACCENT}]")
                model_node.add(f"Prompt:     [dim]$[/dim][bold]{costs['input']:.4f}[/bold] per 1K tokens")
                model_node.add(f"Completion: [dim]$[/dim][bold]{costs['output']:.4f}[/bold] per 1K tokens")

            console.print(tree)
            console.print()

        console.print(
            f"[dim {Colors.TEXT_MUTED}]Note: Rates are benchmark estimates. Consult provider websites for live enterprise tier rates.[/dim {Colors.TEXT_MUTED}]"
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

