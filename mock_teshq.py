import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Using record=True to capture the SVG
console = Console(force_terminal=True, color_system="truecolor", record=True, width=100)

def run():
    console.print("$ teshq query \"Show the top 5 customers by revenue\"", style="bold white")
    console.print()
    
    console.print("[bold cyan]⠋ Analyzing schema and generating SQL...[/]")
    console.print("[bold green]⠙ Executing query...[/]")
        
    console.print("[bold green]✔ SQL generated and executed successfully![/]")
    console.print(Panel("SELECT customers.id, customers.name, SUM(orders.amount) as total_revenue\nFROM customers\nJOIN orders ON customers.id = orders.customer_id\nGROUP BY customers.id, customers.name\nORDER BY total_revenue DESC\nLIMIT 5;", title="[cyan]Generated SQL", border_style="cyan"))
    
    table = Table(title="Top 5 Customers by Revenue", show_header=True, header_style="bold magenta")
    table.add_column("id", style="dim", width=6)
    table.add_column("name")
    table.add_column("total_revenue", justify="right", style="green")
    
    table.add_row("1042", "Acme Corporation", "$145,200.00")
    table.add_row("855", "Globex Inc", "$98,450.00")
    table.add_row("2113", "Soylent Corp", "$85,000.00")
    table.add_row("93", "Initech", "$72,100.50")
    table.add_row("402", "Umbrella Corporation", "$65,990.00")
    
    console.print(table)
    
    console.print("\n[dim]Query executed in 0.84s (AI planning: 2.1s)[/dim]")
    print()
    
    # Save the beautiful terminal window as an SVG
    console.save_svg("docs/assets/demo.svg", title="TESH-Query Demo")

if __name__ == "__main__":
    run()
