"""
Token analytics CLI commands for TESH-Query.

Provides commands to view local token usage and summaries recorded in usage_metrics.jsonl.
For advanced session tracking and flame graphs, use the Logfire dashboard.
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from teshq.telemetry.analytics import get_summary, reset_metrics
from teshq.utils.ui import error, success, info

app = typer.Typer(name="analytics", help="View local LLM token usage analytics and costs")
console = Console()


@app.command("show")
def show_summary():
    """Show global native usage summary from local metrics."""
    try:
        summary = get_summary()
        
        # Determine Date Range
        if summary.get("first_seen") and summary.get("last_seen"):
            dates = f"[cyan]{summary['first_seen']}[/cyan] to [cyan]{summary['last_seen']}[/cyan]"
        else:
            dates = "[cyan]No data available[/cyan]"

        # Main metrics panel
        info_text = f"""[bold]Activity Period:[/bold] {dates}

[bold]Total Queries:[/bold] {summary['total_queries']:,}
[bold]Successful Queries:[/bold] [green]{summary['successful_queries']:,}[/green]
[bold]Failed Queries:[/bold] [red]{summary['failed_queries']:,}[/red]

[bold]Total Tokens Used:[/bold] [cyan]{summary['total_tokens']:,}[/cyan]
  ├─ [dim]Prompt:[/dim] {summary['prompt_tokens']:,}
  └─ [dim]Completion:[/dim] {summary['completion_tokens']:,}

[bold]Estimated Cost:[/bold] [yellow]${summary['estimated_cost_usd']:.4f}[/yellow]
[bold]Avg Query Latency:[/bold] {summary['avg_latency_ms']} ms
[bold]Total CLI Commands:[/bold] {summary['total_commands']:,}"""

        console.print(Panel(info_text, title="[bold green]Local Usage Summary[/bold green]", expand=False))
        
        # Provider Breakdown
        if summary.get('provider_breakdown'):
            table = Table(show_header=True, header_style="bold magenta", title="Provider Usage")
            table.add_column("Provider")
            table.add_column("Queries", justify="right")
            for prov, count in summary['provider_breakdown'].items():
                table.add_row(prov.title(), str(count))
            console.print(table)
            console.print()

        # Command Breakdown
        if summary.get('command_breakdown'):
            table = Table(show_header=True, header_style="bold blue", title="Command Executions")
            table.add_column("Command")
            table.add_column("Count", justify="right")
            for cmd, count in summary['command_breakdown'].items():
                table.add_row(cmd, str(count))
            console.print(table)
            
        console.print("\n[dim]Note: This shows local data only. For complete cloud observability, view your Logfire dashboard.[/dim]")

    except Exception as e:
        error(f"Failed to load analytics summary: {e}")


@app.command("reset")
def reset_local_metrics():
    """Clear the local usage metrics file."""
    try:
        success_reset = reset_metrics()
        if success_reset:
            success("Local metrics have been reset.")
        else:
            info("Metrics file was already empty or could not be found.")
    except Exception as e:
        error(f"Failed to reset metrics: {e}")


@app.command("pricing")
def show_pricing_info():
    """Show current LLM pricing information for cost estimation."""
    try:
        from teshq.telemetry.pricing import TokenPricingCalculator
        from rich.tree import Tree
        
        console.print(Panel("[bold]LLM Pricing Information[/bold]\n[dim]Prices are per 1,000 tokens and may change[/dim]", 
                          title="[bold yellow]Token Pricing[/bold yellow]"))
        
        pricing = TokenPricingCalculator.PRICING_MAP
        
        for provider, models in pricing.items():
            url = TokenPricingCalculator.get_pricing_url(provider)
            tree = Tree(f"[bold cyan]{provider.title()}[/bold cyan] [dim]({url})[/dim]")
            
            for model, costs in models.items():
                model_node = tree.add(f"[green]{model}[/green]")
                model_node.add(f"Input: [blue]${costs['input']:.4f}[/blue] per 1K tokens")
                model_node.add(f"Output: [red]${costs['output']:.4f}[/red] per 1K tokens")
        
            console.print(tree)
            console.print()
        
        console.print("[dim]Note: Pricing is estimated and may not reflect current rates. Check provider websites for accurate pricing.[/dim]")
        
    except Exception as e:
        error(f"Failed to show pricing info: {e}")


if __name__ == "__main__":
    app()
