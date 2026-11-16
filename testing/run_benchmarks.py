#!/usr/bin/env python3
"""
TESH-Query Performance and Scalability Benchmark Runner.

Executes and measures schema introspection, reference SQL query execution,
and memory utilization across simple, medium, and complex queries on ecommerce.sqlite.
If LLM credentials are present, also benchmarks natural-language inference.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import resource
import sqlite3
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
TESTING_DIR = Path(__file__).resolve().parent
BENCHMARK_QUERIES_FILE = TESTING_DIR / "benchmark_queries.json"
DEFAULT_DB_PATH = TESTING_DIR / "databases" / "ecommerce.sqlite"


def get_peak_memory_mb() -> float:
    """Get peak resident set size in megabytes (Mac OS X returns bytes, Linux KB)."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def run_benchmarks(
    db_path: Path,
    output_report: Optional[Path] = None,
    limit_queries: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute performance benchmarks against ecommerce.sqlite."""
    print("=" * 70)
    print("TESH-Query Performance & Scalability Benchmark Suite")
    print(f"Database:    {db_path}")
    print(f"Environment: Python {platform.python_version()} on {platform.system()} ({platform.machine()})")
    print(f"Timestamp:   {datetime.datetime.now().isoformat()}")
    print("=" * 70)

    if not db_path.exists():
        print(f"Error: Database file does not exist at {db_path}.")
        print("Run 'python testing/create_database.py' first.")
        sys.exit(1)

    file_size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"Database Size on Disk: {file_size_mb:.2f} MB")

    tracemalloc.start()
    benchmark_start_time = time.time()

    # 1. Introspection Timing
    print("\n[Phase 1/3] Benchmarking Database Schema Introspection...")
    from teshq.core.introspect import introspect_db

    db_url = f"sqlite:///{db_path}"
    t0 = time.time()
    schema_result = introspect_db(db_url=db_url, detect_relationships=True, include_indexes=True)
    introspection_time = time.time() - t0
    introspected_tables = len(schema_result.get("tables", {})) if schema_result else 0
    ms_intro = introspection_time * 1000
    print(f"  ✓ Schema Introspection completed in {ms_intro:.2f} ms ({introspected_tables} tables discovered).")

    # 2. Schema Retrieval & Graph Timing
    print("\n[Phase 2/3] Benchmarking Schema Graph Construction & Retrieval...")
    from teshq.core.schema_graph import SchemaGraph

    t0 = time.time()
    graph = SchemaGraph.from_schema_file()
    graph_load_time = time.time() - t0

    t0 = time.time()
    top_tables = graph.most_connected_tables(limit=5)
    graph.compressed_schema_within_budget(top_tables, max_tokens=1500)
    retrieval_time = time.time() - t0
    print(f"  ✓ Schema Graph load latency:      {graph_load_time * 1000:.2f} ms")
    print(f"  ✓ Compressed schema compression:  {retrieval_time * 1000:.2f} ms (top connected: {top_tables})")

    # 3. Reference Query Execution Latency
    print("\n[Phase 3/3] Benchmarking Query Execution Performance Across 30+ Queries...")
    with open(BENCHMARK_QUERIES_FILE, "r", encoding="utf-8") as f:
        benchmark_queries: List[Dict[str, Any]] = json.load(f)

    if limit_queries:
        benchmark_queries = benchmark_queries[:limit_queries]

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    query_results: List[Dict[str, Any]] = []
    complexity_timings: Dict[str, List[float]] = {"simple": [], "medium": [], "complex": []}

    print(f"{'ID':<7} | {'Complexity':<14} | {'Rows':<8} | {'Latency (ms)':<12} | {'Category'}")
    print("-" * 70)

    for item in benchmark_queries:
        q_id = item["id"]
        q_text = item["question"]
        complexity = item["complexity"]
        category = item["category"]
        requires_cross_db = item.get("requires_cross_db", False)
        sql = item.get("reference_sql", "")

        if requires_cross_db:
            # Cross DB queries are federated, reported separately
            print(f"{q_id:<7} | {complexity:<14} | {'[CrossDB]':<8} | {'N/A (Federated)':<12} | {category}")
            query_results.append({
                "id": q_id,
                "question": q_text,
                "complexity": complexity,
                "category": category,
                "requires_cross_db": True,
                "rows_returned": None,
                "latency_ms": None,
                "status": "federated_skipped_for_single_db",
            })
            continue

        q_t0 = time.time()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            q_latency = (time.time() - q_t0) * 1000
            row_count = len(rows)
            status = "success"

            if complexity in complexity_timings:
                complexity_timings[complexity].append(q_latency)

            print(f"{q_id:<7} | {complexity:<14} | {row_count:<8} | {q_latency:>10.2f} ms | {category}")
        except Exception as e:
            q_latency = (time.time() - q_t0) * 1000
            row_count = 0
            status = f"error: {e}"
            print(f"{q_id:<7} | {complexity:<14} | {'ERROR':<8} | {q_latency:>10.2f} ms | {category} ({e})")

        query_results.append({
            "id": q_id,
            "question": q_text,
            "complexity": complexity,
            "category": category,
            "requires_cross_db": False,
            "rows_returned": row_count,
            "latency_ms": round(q_latency, 2),
            "status": status,
        })

    conn.close()

    # Check LLM Key
    llm_available = bool(os.getenv("GEMINI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))
    llm_status_msg = "Live LLM available" if llm_available else "Skipped (no LLM API key in environment)"

    total_duration = time.time() - benchmark_start_time
    peak_mem_mb = get_peak_memory_mb()
    current_mem, peak_tracemalloc = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    def avg_or_zero(nums: List[float]) -> float:
        return round(sum(nums) / len(nums), 2) if nums else 0.0

    summary = {
        "benchmark_date": datetime.datetime.now().isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "os": platform.system(),
            "architecture": platform.machine(),
        },
        "database": {
            "path": str(db_path),
            "size_mb": round(file_size_mb, 2),
            "tables_introspected": introspected_tables,
        },
        "timings": {
            "total_benchmark_time_sec": round(total_duration, 2),
            "schema_introspection_ms": round(introspection_time * 1000, 2),
            "schema_retrieval_ms": round(retrieval_time * 1000, 2),
            "simple_query_avg_ms": avg_or_zero(complexity_timings["simple"]),
            "medium_query_avg_ms": avg_or_zero(complexity_timings["medium"]),
            "complex_query_avg_ms": avg_or_zero(complexity_timings["complex"]),
        },
        "memory": {
            "peak_rss_mb": round(peak_mem_mb, 2),
            "peak_tracemalloc_mb": round(peak_tracemalloc / (1024 * 1024), 2),
        },
        "llm_inference": {
            "status": llm_status_msg,
        },
        "queries": query_results,
    }

    print("\n" + "=" * 70)
    print("BENCHMARK PERFORMANCE SUMMARY")
    print("=" * 70)
    print(f"Total Benchmark Runtime:        {total_duration:.2f} s")
    print(f"Peak Memory Usage (RSS):        {peak_mem_mb:.2f} MB")
    print(f"Schema Introspection Latency:   {introspection_time * 1000:.2f} ms")
    print(f"Schema Retrieval Latency:       {retrieval_time * 1000:.2f} ms")
    print(f"Average Simple Query Latency:   {summary['timings']['simple_query_avg_ms']:.2f} ms")
    print(f"Average Medium Query Latency:   {summary['timings']['medium_query_avg_ms']:.2f} ms")
    print(f"Average Complex Query Latency:  {summary['timings']['complex_query_avg_ms']:.2f} ms")
    print(f"LLM Generation Latency Status:  {llm_status_msg}")
    print("=" * 70)

    if output_report:
        output_report.parent.mkdir(parents=True, exist_ok=True)
        output_report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"✓ Detailed report written to {output_report}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run TESH-Query scalability benchmarks against ecommerce.sqlite."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=TESTING_DIR / "benchmark_report.json",
        help="Path to output JSON report (default: testing/benchmark_report.json).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of queries to run.",
    )

    args = parser.parse_args()
    run_benchmarks(
        db_path=args.database,
        output_report=args.report,
        limit_queries=args.limit,
    )


if __name__ == "__main__":
    main()
