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
        
        info_text = f"""[bold]Total Queries:[/bold] {summary['total_queries']:,}
[bold]Successful Queries:[/bold] {summary['successful_queries']:,}
[bold]Failed Queries:[/bold] {summary['failed_queries']:,}
[bold]Total Tokens:[/bold] {summary['total_tokens']:,}
[bold]Estimated Cost:[/bold] ${summary['estimated_cost_usd']:.4f}
[bold]Avg Query Latency:[/bold] {summary['avg_latency_ms']} ms
[bold]Total Commands Executed:[/bold] {summary['total_commands']:,}"""

        console.print(Panel(info_text, title="[bold green]Local Usage Summary[/bold green]", expand=False))
        
        if summary['command_breakdown']:
            console.print("\n[bold]Command Breakdown:[/bold]")
            table = Table(show_header=True, header_style="bold blue")
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
            tree = Tree(f"[bold cyan]{provider.title()}[/bold cyan]")
            
            for model, costs in models.items():
                model_node = tree.add(f"[green]{model}[/green]")
                model_node.add(f"Input: [blue]${costs['input']:.4f}[/blue] per 1K tokens")
                model_node.add(f"Output: [red]${costs['output']:.4f}[/red] per 1K tokens")
        
            console.print(tree)
            console.print()
        
        console.print("[dim]Note: Pricing is estimated and may not reflect current rates. Check provider websites for accurate pricing.[/dim]")
        
    except Exception as e:
        error(f"Failed to show pricing info: {e}")


@app.command("cost")
def estimate_cost(
    provider: str = typer.Argument(..., help="LLM provider (google, openai, anthropic)"),
    model: str = typer.Argument(..., help="Model name"),
    prompt_tokens: int = typer.Argument(..., help="Number of prompt tokens"),
    completion_tokens: int = typer.Argument(..., help="Number of completion tokens"),
):
    """Calculate estimated cost for specific token usage."""
    try:
        from teshq.telemetry.pricing import TokenPricingCalculator
        
        cost = TokenPricingCalculator.calculate_cost(provider, model, prompt_tokens, completion_tokens)
        total_tokens = prompt_tokens + completion_tokens
        
        cost_info = f"""[bold]Provider:[/bold] {provider}
[bold]Model:[/bold] {model}
[bold]Prompt Tokens:[/bold] {prompt_tokens:,}
[bold]Completion Tokens:[/bold] {completion_tokens:,}
[bold]Total Tokens:[/bold] {total_tokens:,}
[bold]Estimated Cost:[/bold] ${cost:.6f}"""

        console.print(Panel(cost_info, title="[bold yellow]Cost Estimate[/bold yellow]", expand=False))
        
        if total_tokens > 0:
            console.print(f"\n[dim]Cost per token: ${cost / total_tokens:.8f}[/dim]")
        
        success(f"Cost estimated: ${cost:.6f}")
        
    except Exception as e:
        error(f"Failed to estimate cost: {e}")


if __name__ == "__main__":
    app()
