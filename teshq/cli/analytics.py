import datetime
from collections import Counter

import typer

from teshq.telemetry.events import get_query_metrics
from teshq.utils.analytics import get_usage_metrics
from teshq.utils.ui import info, print_config, print_header, print_table, warning

app = typer.Typer(help="View usage analytics and cost information.")


@app.command(name="show", help="Display aggregated usage and cost analytics.")
def show_analytics():
    """
    Reads usage metrics and displays a summary of LLM calls, token usage,
    estimated costs, feature usage frequency, and AI query performance metrics.
    """
    metrics = get_usage_metrics()

    if not metrics:
        warning("No analytics data found. Start using the tool to generate metrics.")
        raise typer.Exit()

    llm_metrics = [m for m in metrics if m.get("event_type") == "llm_usage"]
    feature_metrics = [m for m in metrics if m.get("event_type") == "feature_usage"]

    print_header("Usage Analytics", subtitle="A summary of your interaction and costs")

    # --- LLM Usage Summary ---
    if llm_metrics:
        total_llm_calls = len(llm_metrics)
        total_input_tokens = sum(m.get("input_tokens", 0) for m in llm_metrics)
        total_output_tokens = sum(m.get("output_tokens", 0) for m in llm_metrics)
        total_tokens = total_input_tokens + total_output_tokens
        total_cost = sum(m.get("cost", 0.0) for m in llm_metrics)

        llm_rows = [
            ["Total LLM Calls", f"{total_llm_calls:,}"],
            ["Total Input Tokens", f"{total_input_tokens:,}"],
            ["Total Output Tokens", f"{total_output_tokens:,}"],
            ["Total Tokens", f"{total_tokens:,}"],
            ["Estimated Total Cost (USD)", f"${total_cost:.6f}"],
        ]
        print_table(title="LLM Usage", headers=["Metric", "Value"], rows=llm_rows, show_lines=False)
    else:
        info("No LLM usage has been recorded yet.")

    # --- Feature Usage Summary ---
    if feature_metrics:
        feature_counts = Counter(m.get("feature_name") for m in feature_metrics)
        feature_rows = [[feature, f"{count:,}"] for feature, count in feature_counts.most_common()]
        print_table(title="Feature Usage Frequency", headers=["Feature", "Count"], rows=feature_rows)
    else:
        info("No feature usage has been recorded yet.")

    # --- AI Query Performance Metrics (v2) ---
    query_events = get_query_metrics()
    if query_events:
        total_queries = len(query_events)
        successful = sum(1 for e in query_events if e.get("success"))
        success_rate = (successful / total_queries * 100) if total_queries else 0.0

        avg_plan = sum(e.get("plan_ms", 0) for e in query_events) / total_queries
        avg_sql = sum(e.get("sql_ms", 0) for e in query_events) / total_queries
        avg_exec = sum(e.get("exec_ms", 0) for e in query_events) / total_queries

        perf_rows = [
            ["Total Queries", f"{total_queries:,}"],
            ["Success Rate", f"{success_rate:.1f}%"],
            ["Avg Plan Latency (ms)", f"{avg_plan:.0f}"],
            ["Avg SQL Latency (ms)", f"{avg_sql:.0f}"],
            ["Avg Execution Latency (ms)", f"{avg_exec:.0f}"],
        ]
        print_table(title="AI Query Performance", headers=["Metric", "Value"], rows=perf_rows, show_lines=False)

    # --- Date Range Display ---
    timestamps = []
    for m in metrics:
        if "timestamp" in m:
            dt = datetime.datetime.fromisoformat(m["timestamp"])
            # Normalize timezone: if naive, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            timestamps.append(dt)

    if timestamps:
        first_event_date = min(timestamps).strftime("%Y-%m-%d %H:%M:%S")
        last_event_date = max(timestamps).strftime("%Y-%m-%d %H:%M:%S")
        date_range_config = {
            "First Event": first_event_date,
            "Last Event": last_event_date,
        }
        print_config(date_range_config, title="Tracking Period")

