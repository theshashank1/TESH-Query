"""
Benchmark Runner for TESH-Query.

Runs a defined set of natural language questions against the active LLM client,
compares generated SQL queries to reference SQL queries, validates database execution,
and generates performance/accuracy metrics.
"""

import time
import os
import yaml
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from teshq.core.engine import TeshEngine
from teshq.core.query import execute_sql_query
from teshq.utils.logging import logger

@dataclass
class BenchmarkItem:
    id: int
    question: str
    reference_sql: str
    order_matters: bool = False

@dataclass
class BenchmarkResult:
    item: BenchmarkItem
    generated_sql: str
    exact_match: bool
    execution_match: bool
    execution_error: Optional[str]
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int

def normalize_sql_string(sql: str) -> str:
    """Normalize SQL by lowercasing and collapsing whitespace to compare strings."""
    import re
    sql = sql.lower().strip()
    sql = re.sub(r'\s+', ' ', sql)
    # Remove semi-colon
    if sql.endswith(';'):
        sql = sql[:-1].strip()
    return sql

def compare_execution_results(
    ref_rows: List[Dict[str, Any]], 
    gen_rows: List[Dict[str, Any]], 
    order_matters: bool = False
) -> bool:
    """
    Compare database outputs using industry-standard values-only comparison.
    
    This follows the Spider/BIRD benchmark methodology:
    - Column names are IGNORED (handles aliases like COUNT(*) vs COUNT(*) AS total)
    - Numeric tolerance is applied for float comparisons
    - If generated has MORE columns than reference, checks if reference values are a subset
    """
    if len(ref_rows) != len(gen_rows):
        return False
    if not ref_rows and not gen_rows:
        return True

    def normalize_value(v: Any) -> Any:
        """Normalize a value for comparison with numeric tolerance."""
        if v is None:
            return None
        if isinstance(v, float):
            # Round to avoid floating-point precision issues
            return round(v, 6)
        if isinstance(v, (dict, list, set)):
            return str(v)
        # Try to normalize string-encoded numbers
        if isinstance(v, str):
            try:
                f = float(v)
                if f == int(f):
                    return int(f)
                return round(f, 6)
            except (ValueError, OverflowError):
                return v
        return v

    def row_to_value_tuple(row: Dict[str, Any]) -> tuple:
        """Extract just the values from a row dict, ignoring column names."""
        return tuple(normalize_value(v) for v in row.values())

    def values_match(ref_vals: tuple, gen_vals: tuple) -> bool:
        """Check if reference values are present in generated values (handles superset columns)."""
        if len(ref_vals) == len(gen_vals):
            return ref_vals == gen_vals
        # If generated has more columns, check if ref values are a contiguous subset
        if len(gen_vals) > len(ref_vals):
            for start in range(len(gen_vals) - len(ref_vals) + 1):
                if gen_vals[start:start + len(ref_vals)] == ref_vals:
                    return True
            # Also check if the ref values exist scattered in gen values
            # (model may have reordered or inserted extra columns)
            ref_set = Counter(ref_vals)
            gen_set = Counter(gen_vals)
            return all(gen_set[v] >= ref_set[v] for v in ref_set)
        return False

    ref_tuples = [row_to_value_tuple(r) for r in ref_rows]
    gen_tuples = [row_to_value_tuple(g) for g in gen_rows]

    if order_matters:
        return all(values_match(r, g) for r, g in zip(ref_tuples, gen_tuples))
    else:
        # For unordered comparison, try to find a matching for each ref row
        if len(ref_tuples[0]) == len(gen_tuples[0]):
            # Same column count — use efficient bag comparison
            ref_bag = Counter(ref_tuples)
            gen_bag = Counter(gen_tuples)
            return ref_bag == gen_bag
        else:
            # Different column counts — use matching approach
            used = [False] * len(gen_tuples)
            for ref_t in ref_tuples:
                found = False
                for i, gen_t in enumerate(gen_tuples):
                    if not used[i] and values_match(ref_t, gen_t):
                        used[i] = True
                        found = True
                        break
                if not found:
                    return False
            return True


class BenchmarkRunner:
    """
    Orchestrates running a set of SQL benchmarks.
    """
    def __init__(self, questions_path: str, db_url: Optional[str] = None, provider: Optional[str] = None):
        self.questions_path = questions_path
        self.db_url = db_url
        self.provider = provider
        self.items: List[BenchmarkItem] = []
        self._load_questions()

    def _load_questions(self) -> None:
        """Load benchmark items from YAML file."""
        if not os.path.exists(self.questions_path):
            # Create default benchmark file if missing
            self._create_default_questions()
            
        with open(self.questions_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
            
        for i, doc in enumerate(data):
            self.items.append(BenchmarkItem(
                id=doc.get("id", i + 1),
                question=doc["question"],
                reference_sql=doc["reference_sql"],
                order_matters=doc.get("order_matters", False)
            ))

    def _create_default_questions(self) -> None:
        """Create a default benchmark suite matching the FMCG SQLite database structure."""
        os.makedirs(os.path.dirname(self.questions_path), exist_ok=True)
        default_data = [
            {
                "id": 1,
                "question": "Show all regions.",
                "reference_sql": "SELECT region_id, region_name FROM regions;",
                "order_matters": False
            },
            {
                "id": 2,
                "question": "Show the top 5 products by price (mrp).",
                "reference_sql": "SELECT product_name, mrp FROM products ORDER BY mrp DESC LIMIT 5;",
                "order_matters": True
            },
            {
                "id": 3,
                "question": "How many total customers do we have?",
                "reference_sql": "SELECT COUNT(*) FROM customers;",
                "order_matters": False
            },
            {
                "id": 4,
                "question": "List the customer names in region 1 (East).",
                "reference_sql": "SELECT customer_name FROM customers WHERE region_id = 1;",
                "order_matters": False
            },
            {
                "id": 5,
                "question": "Show the number of products in each brand. List brand and count.",
                "reference_sql": "SELECT brand, COUNT(product_id) FROM products GROUP BY brand;",
                "order_matters": False
            },
            {
                "id": 6,
                "question": "List the category names and their corresponding product names.",
                "reference_sql": "SELECT c.category_name, p.product_name FROM categories c JOIN products p ON c.category_id = p.category_id;",
                "order_matters": False
            },
            {
                "id": 7,
                "question": "Find the total quantity sold for each product. Show product name and total quantity.",
                "reference_sql": "SELECT p.product_name, SUM(o.quantity) FROM products p JOIN order_items o ON p.product_id = o.product_id GROUP BY p.product_name;",
                "order_matters": False
            }
        ]
        with open(self.questions_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(default_data, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Created default benchmark suite at {self.questions_path}")

    def run(self) -> List[BenchmarkResult]:
        """Run all loaded benchmark items against the target engine."""
        results: List[BenchmarkResult] = []
        
        # Initialize engine
        engine = TeshEngine(db_url=self.db_url, provider=self.provider)
        
        logger.info(f"Starting benchmark run with {len(self.items)} items against provider: {engine._provider}")
        
        for item in self.items:
            logger.info(f"Running Item {item.id}/{len(self.items)}: '{item.question}'")
            
            generated_sql = ""
            exact_match = False
            execution_match = False
            execution_error = None
            latency = 0.0
            p_tokens = 0
            c_tokens = 0
            
            try:
                # 1. Generate SQL
                t0 = time.time()
                query_res = engine.query(item.question, dry_run=True)
                latency = (time.time() - t0) * 1000
                
                generated_sql = query_res.sql
                # QueryResult only exposes total_tokens; split is unavailable
                p_tokens = query_res.total_tokens
                c_tokens = 0
                
                # 2. Check exact string match
                exact_match = (normalize_sql_string(generated_sql) == normalize_sql_string(item.reference_sql))
                
                # 3. Check execution match
                ref_rows = execute_sql_query(db_url=self.db_url, query=item.reference_sql)
                try:
                    gen_rows = execute_sql_query(db_url=self.db_url, query=generated_sql, parameters=query_res.parameters)
                    execution_match = compare_execution_results(ref_rows, gen_rows, item.order_matters)
                except Exception as db_err:
                    execution_error = str(db_err)
                    logger.warning(f"Database error executing generated SQL: {db_err}")
                    
            except Exception as e:
                execution_error = f"Inference / compiler error: {e}"
                logger.error(f"Failed to run benchmark item {item.id}: {e}")
                
            results.append(BenchmarkResult(
                item=item,
                generated_sql=generated_sql,
                exact_match=exact_match,
                execution_match=execution_match,
                execution_error=execution_error,
                latency_ms=latency,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens
            ))
            
        return results

    @staticmethod
    def generate_report(results: List[BenchmarkResult]) -> str:
        """Generate a formatted markdown report of the benchmark run."""
        total = len(results)
        exact_matches = sum(1 for r in results if r.exact_match)
        exec_matches = sum(1 for r in results if r.execution_match)
        errors = sum(1 for r in results if r.execution_error is not None)
        
        avg_latency = sum(r.latency_ms for r in results) / total if total else 0
        total_prompt_tokens = sum(r.prompt_tokens for r in results)
        total_comp_tokens = sum(r.completion_tokens for r in results)
        
        lines = [
            "# TESH-Query Benchmark Report",
            "",
            "## Summary Metrics",
            "",
            f"| Metric | Value |",
            f"| :--- | :--- |",
            f"| **Total Queries Tested** | {total} |",
            f"| **Exact SQL Matches** | {exact_matches} ({exact_matches/total*100:.1f}%) |",
            f"| **Execution Matches** | {exec_matches} ({exec_matches/total*100:.1f}%) |",
            f"| **Database Errors** | {errors} ({errors/total*100:.1f}%) |",
            f"| **Average Latency** | {avg_latency:.2f} ms |",
            f"| **Total Prompt Tokens** | {total_prompt_tokens} |",
            f"| **Total Completion Tokens** | {total_comp_tokens} |",
            "",
            "## Detailed Results",
            "",
            "| ID | Question | Exact Match | Exec Match | Latency (ms) | Notes |",
            "| :--- | :--- | :---: | :---: | :---: | :--- |"
        ]
        
        for r in results:
            exact_str = "✅" if r.exact_match else "❌"
            exec_str = "✅" if r.execution_match else "❌"
            
            note = ""
            if r.execution_error:
                note = f"Error: {r.execution_error[:60]}"
                if len(r.execution_error) > 60:
                    note += "..."
            elif not r.exact_match and r.execution_match:
                note = "Equivalent SQL structure"
                
            lines.append(f"| {r.item.id} | {r.item.question} | {exact_str} | {exec_str} | {r.latency_ms:.1f} | {note} |")

        # Add SQL comparison section for failed items
        failed = [r for r in results if not r.execution_match]
        if failed:
            lines.append("")
            lines.append("## Failed Query Analysis")
            lines.append("")
            for r in failed:
                lines.append(f"### ID {r.item.id}: {r.item.question}")
                lines.append("")
                lines.append(f"**Reference SQL:**")
                lines.append(f"```sql")
                lines.append(r.item.reference_sql)
                lines.append(f"```")
                lines.append(f"**Generated SQL:**")
                lines.append(f"```sql")
                lines.append(r.generated_sql if r.generated_sql else "(no SQL generated)")
                lines.append(f"```")
                if r.execution_error:
                    lines.append(f"**Error:** `{r.execution_error}`")
                lines.append("")
            
        return "\n".join(lines)
