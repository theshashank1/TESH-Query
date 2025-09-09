"""
Token analytics CLI commands for TESH-Query.

Provides commands to view token usage, session summaries, and cost estimates.
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from teshq.utils.token_tracking import get_token_tracker
from teshq.utils.ui import error, success, info

app = typer.Typer(name="analytics", help="View LLM token usage analytics and costs")
console = Console()


@app.command("session")
def show_session_summary(
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Specific session ID to view")
):
    """Show current or specific session token usage summary."""
    try:
        tracker = get_token_tracker()
        
        if session_id and session_id != tracker.session_id:
            error(f"Session {session_id} not found in current tracker")
            return
        
        summary = tracker.get_session_summary()
        
        # Create session summary panel
        session_info = f"""[bold]Session ID:[/bold] {summary['session_id']}
[bold]User ID:[/bold] {summary['user_id']}
[bold]Queries:[/bold] {summary['queries']}
[bold]Total Tokens:[/bold] {summary['total_tokens']:,}
[bold]Total Cost:[/bold] ${summary['total_cost']:.4f}
[bold]Duration:[/bold] {summary['duration_minutes']} minutes
[bold]Avg Tokens/Query:[/bold] {summary.get('average_tokens_per_query', 0):.1f}"""

        console.print(Panel(session_info, title="[bold cyan]Current Session Summary[/bold cyan]", expand=False))
        
        # Show query details if available
        if summary['queries'] > 0 and 'queries_detail' in summary:
            console.print("\n[bold]Query Details:[/bold]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Query ID", style="dim", width=36)
            table.add_column("Tokens", justify="right")
            table.add_column("Cost", justify="right")
            table.add_column("Query Preview", width=50)
            table.add_column("Time")
            
            for query in summary['queries_detail']:
                table.add_row(
                    query['query_id'][:8] + "...",
                    f"{query['tokens']:,}",
                    f"${query['cost']:.4f}",
                    query['query'] or "N/A",
                    query['timestamp'].split('T')[1][:8] if 'T' in query['timestamp'] else query['timestamp']
                )
            
            console.print(table)
        
        success(f"Session summary displayed for {summary['queries']} queries")
        
    except Exception as e:
        error(f"Failed to get session summary: {e}")


@app.command("global")
def show_global_summary(
    days: int = typer.Option(30, "--days", help="Number of days to include in summary")
):
    """Show global token usage summary across all users and sessions."""
    try:
        tracker = get_token_tracker()
        summary = tracker.get_global_summary(days=days)
        
        if 'error' in summary:
            error(f"Failed to get global summary: {summary['error']}")
            return
        
        # Create global summary panel
        global_info = f"""[bold]Period:[/bold] Last {days} days
[bold]Total API Calls:[/bold] {summary['total_calls']:,}
[bold]Total Tokens:[/bold] {summary['total_tokens']:,}
[bold]Average Tokens/Call:[/bold] {summary['average_tokens_per_call']:.1f}
[bold]Max Tokens (Single Call):[/bold] {summary['max_tokens_single_call']:,}
[bold]Estimated Total Cost:[/bold] ${summary['estimated_total_cost']:.4f}"""

        console.print(Panel(global_info, title="[bold green]Global Usage Summary[/bold green]", expand=False))
        
        # Show cost breakdown estimation
        if summary['total_tokens'] > 0:
            console.print("\n[bold]Cost Analysis:[/bold]")
            
            cost_table = Table(show_header=True, header_style="bold blue")
            cost_table.add_column("Metric")
            cost_table.add_column("Value", justify="right")
            
            avg_cost_per_call = summary['estimated_total_cost'] / max(summary['total_calls'], 1)
            cost_per_1k_tokens = (summary['estimated_total_cost'] / max(summary['total_tokens'], 1)) * 1000
            
            cost_table.add_row("Average Cost per Call", f"${avg_cost_per_call:.4f}")
            cost_table.add_row("Cost per 1K Tokens", f"${cost_per_1k_tokens:.4f}")
            cost_table.add_row("Daily Average Cost", f"${summary['estimated_total_cost'] / days:.4f}")
            
            console.print(cost_table)
        
        success(f"Global summary displayed for {days} days")
        
    except Exception as e:
        error(f"Failed to get global summary: {e}")


@app.command("pricing")
def show_pricing_info():
    """Show current LLM pricing information for cost estimation."""
    try:
        from teshq.utils.token_tracking import TokenPricingCalculator
        
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
        from teshq.utils.token_tracking import TokenPricingCalculator
        
        cost = TokenPricingCalculator.calculate_cost(provider, model, prompt_tokens, completion_tokens)
        total_tokens = prompt_tokens + completion_tokens
        
        # Create cost breakdown
        cost_info = f"""[bold]Provider:[/bold] {provider}
[bold]Model:[/bold] {model}
[bold]Prompt Tokens:[/bold] {prompt_tokens:,}
[bold]Completion Tokens:[/bold] {completion_tokens:,}
[bold]Total Tokens:[/bold] {total_tokens:,}
[bold]Estimated Cost:[/bold] ${cost:.6f}"""

        console.print(Panel(cost_info, title="[bold yellow]Cost Estimate[/bold yellow]", expand=False))
        
        # Show cost per token
        if total_tokens > 0:
            cost_per_token = cost / total_tokens
            console.print(f"\n[dim]Cost per token: ${cost_per_token:.8f}[/dim]")
        
        success(f"Cost estimated: ${cost:.6f}")
        
    except Exception as e:
        error(f"Failed to estimate cost: {e}")


@app.command("reset")
def reset_session():
    """Start a new token tracking session."""
    try:
        tracker = get_token_tracker()
        old_session = tracker.session_id
        new_session = tracker.new_session()
        
        info(f"Previous session: {old_session[:8]}...")
        success(f"New session started: {new_session[:8]}...")
        
    except Exception as e:
        error(f"Failed to reset session: {e}")


@app.command("export")
def export_session_data(
    output_file: str = typer.Option("session_export.json", "--output", "-o", help="Output file path"),
    format: str = typer.Option("json", "--format", help="Export format (json, csv)")
):
    """Export current session data to file."""
    try:
        import json
        import csv
        from pathlib import Path
        
        tracker = get_token_tracker()
        summary = tracker.get_session_summary()
        
        output_path = Path(output_file)
        
        if format.lower() == "json":
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            success(f"Session data exported to {output_path}")
            
        elif format.lower() == "csv":
            if 'queries_detail' in summary and summary['queries_detail']:
                with open(output_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['query_id', 'tokens', 'cost', 'query', 'timestamp'])
                    writer.writeheader()
                    writer.writerows(summary['queries_detail'])
                success(f"Session queries exported to {output_path}")
            else:
                error("No query data available to export")
        else:
            error(f"Unsupported format: {format}")
            
    except Exception as e:
        error(f"Failed to export session data: {e}")


if __name__ == "__main__":
    app()