"""
CLI Commands for running text-to-SQL benchmarks in TESH-Query.
"""

import os
import typer
from typing import Optional
from teshq.cli.ui import print_header, print_footer, status, error, warning, tip, success
from teshq.config.loader import get_settings
from teshq.core.benchmark import BenchmarkRunner, BenchmarkResult

app = typer.Typer(help="Evaluate text-to-SQL accuracy, speed, and token cost.")

@app.command(name="run")
def run_benchmark(
    questions: Optional[str] = typer.Option(
        None, "--questions", "-q", 
        help="Path to questions YAML file. Defaults to benchmarks/questions.yaml"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="Force provider override ('google', 'azure', or 'local')."
    ),
    export_path: Optional[str] = typer.Option(
        None, "--export", "-e",
        help="Export the markdown report to a file path."
    ),
):
    """
    Run the SQL compilation benchmark suite.
    """
    print_header("TESHQ BENCHMARK HARNESS", level=1)
    
    # 1. Resolve questions path
    if not questions:
        questions = os.path.join("benchmarks", "questions.yaml")
        
    abs_questions_path = os.path.abspath(questions)
    
    # 2. Resolve database URL
    s = get_settings()
    db_url = s.database_url
    if not db_url:
        error("DATABASE_URL is not configured in settings. Cannot run execution-match benchmarks.")
        tip("Run: teshq config --db")
        raise typer.Exit(1)
        
    # 3. Create runner
    try:
        runner = BenchmarkRunner(abs_questions_path, db_url=db_url, provider=provider)
    except Exception as e:
        error(f"Failed to initialize benchmark runner: {e}")
        raise typer.Exit(1)

    # 4. Run benchmarks
    results = []
    with status("Executing benchmark suite...", success_message="Benchmark run completed."):
        try:
            results = runner.run()
        except Exception as e:
            error(f"Benchmark run failed: {e}")
            raise typer.Exit(1)
            
    # 5. Print Summary
    total = len(results)
    if total == 0:
        warning("No benchmark questions loaded.")
        print_footer()
        return
        
    exact_matches = sum(1 for r in results if r.exact_match)
    exec_matches = sum(1 for r in results if r.execution_match)
    errors = sum(1 for r in results if r.execution_error is not None)
    avg_latency = sum(r.latency_ms for r in results) / total
    
    typer.echo("")
    typer.secho("📊 Summary Results:", bold=True)
    
    exec_match_pct = (exec_matches / total) * 100
    color = "green" if exec_match_pct >= 80 else "yellow" if exec_match_pct >= 50 else "red"
    
    typer.secho(f"  • Execution Match:  {exec_matches}/{total} ({exec_match_pct:.1f}%)", fg=color, bold=True)
    typer.echo(f"  • Exact SQL Match:  {exact_matches}/{total} ({(exact_matches/total)*100:.1f}%)")
    typer.echo(f"  • Database Errors:  {errors}/{total} ({(errors/total)*100:.1f}%)")
    typer.echo(f"  • Avg Latency:      {avg_latency:.2f} ms")
    
    # 6. Generate report markdown
    report = BenchmarkRunner.generate_report(results)
    
    # Export report if requested
    if export_path:
        try:
            abs_export_path = os.path.abspath(export_path)
            os.makedirs(os.path.dirname(abs_export_path), exist_ok=True)
            with open(abs_export_path, "w", encoding="utf-8") as f:
                f.write(report)
            success(f"Report exported to: {abs_export_path}")
        except Exception as e:
            warning(f"Failed to export report: {e}")
            
    # Print the markdown report to console for rich visual inspection
    typer.echo("")
    typer.secho("📝 Detailed Results Report:", bold=True)
    typer.echo("--------------------------------------------------------------------------------")
    typer.echo(report)
    typer.echo("--------------------------------------------------------------------------------")
    
    print_footer()

@app.command(name="compare")
def compare_benchmarks(
    questions: Optional[str] = typer.Option(
        None, "--questions", "-q", 
        help="Path to questions YAML file."
    ),
):
    """
    Compare local vs cloud backend accuracy and speed side-by-side.
    """
    print_header("TESHQ BENCHMARK COMPARISON", level=1)
    
    if not questions:
        questions = os.path.join("benchmarks", "questions.yaml")
    abs_questions_path = os.path.abspath(questions)
    
    s = get_settings()
    db_url = s.database_url
    if not db_url:
        error("DATABASE_URL is not configured.")
        raise typer.Exit(1)
        
    # Check if local is set up
    local_ready = False
    if s.local_model_path and os.path.exists(s.local_model_path):
        try:
            import llama_cpp
            local_ready = True
        except ImportError:
            pass
            
    # Check if cloud (google/azure) is set up
    cloud_provider = "google"
    if s.azure_openai_api_key:
        cloud_provider = "azure"
    elif not s.gemini_api_key:
        warning("Cloud API key not configured. Cloud run might fail.")

    # 1. Run local
    local_results = []
    if local_ready:
        with status("Running local benchmarks...", success_message="Local benchmarks complete."):
            runner = BenchmarkRunner(abs_questions_path, db_url=db_url, provider="local")
            local_results = runner.run()
    else:
        warning("Local GGUF backend is not fully configured or installed. Skipping local run.")
        
    # 2. Run cloud
    cloud_results = []
    with status(f"Running cloud benchmarks ({cloud_provider.upper()})...", success_message="Cloud benchmarks complete."):
        runner = BenchmarkRunner(abs_questions_path, db_url=db_url, provider=cloud_provider)
        cloud_results = runner.run()
        
    # 3. Compare and output side-by-side
    total = len(cloud_results)
    if total == 0:
        error("No benchmark items loaded.")
        raise typer.Exit(1)
        
    typer.echo("")
    typer.secho("📊 Comparison Metrics:", bold=True)
    typer.echo("| Metric | Local Backend | Cloud Backend |")
    typer.echo("| :--- | :---: | :---: |")
    
    if local_results:
        local_exec = sum(1 for r in local_results if r.execution_match)
        local_exact = sum(1 for r in local_results if r.exact_match)
        local_lat = sum(r.latency_ms for r in local_results) / total
        
        cloud_exec = sum(1 for r in cloud_results if r.execution_match)
        cloud_exact = sum(1 for r in cloud_results if r.exact_match)
        cloud_lat = sum(r.latency_ms for r in cloud_results) / total
        
        typer.echo(f"| **Execution Match %** | {local_exec/total*100:.1f}% ({local_exec}/{total}) | {cloud_exec/total*100:.1f}% ({cloud_exec}/{total}) |")
        typer.echo(f"| **Exact SQL Match %** | {local_exact/total*100:.1f}% ({local_exact}/{total}) | {cloud_exact/total*100:.1f}% ({cloud_exact}/{total}) |")
        typer.echo(f"| **Avg Latency (ms)**  | {local_lat:.2f} ms | {cloud_lat:.2f} ms |")
    else:
        cloud_exec = sum(1 for r in cloud_results if r.execution_match)
        cloud_exact = sum(1 for r in cloud_results if r.exact_match)
        cloud_lat = sum(r.latency_ms for r in cloud_results) / total
        typer.echo(f"| **Execution Match %** | N/A | {cloud_exec/total*100:.1f}% ({cloud_exec}/{total}) |")
        typer.echo(f"| **Exact SQL Match %** | N/A | {cloud_exact/total*100:.1f}% ({cloud_exact}/{total}) |")
        typer.echo(f"| **Avg Latency (ms)**  | N/A | {cloud_lat:.2f} ms |")
        
    print_footer()
