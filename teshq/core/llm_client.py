"""
Unified LLM Client Abstraction for TESH-Query.

Provides a common interface (LLMClient) for both cloud backends (Gemini, Azure)
and the local in-process GGUF inference backend.
"""

import re
import json
from typing import Protocol, Optional, Iterator, Dict, Any, List, Tuple
from teshq.core.models import QueryPlan, SQLQuery
from teshq.core.planner import QueryPlanner, build_planner
from teshq.core.sql_gen import SQLGenerator, build_sql_generator
from teshq.core.inference import InferenceRuntime, InferenceConfig
from teshq.core.grammar import get_sql_grammar
from teshq.core.dialect import SQLDialect, detect_dialect, get_dialect_hints, get_dialect_rules
from teshq.utils.logging import logger

class LLMClient(Protocol):
    """Unified protocol defining operations for generating query plans and SQL."""
    
    def generate_plan(self, nl_query: str, schema: str, callbacks: Optional[List[Any]] = None) -> QueryPlan:
        """Produce a structured QueryPlan (Stage 1)."""
        ...
        
    def generate_sql(
        self, 
        nl_query: str, 
        schema: str, 
        plan: QueryPlan, 
        error_hint: Optional[str] = None, 
        callbacks: Optional[List[Any]] = None
    ) -> SQLQuery:
        """Produce a structured SQLQuery statement (Stage 2)."""
        ...

    def get_token_tracker(self) -> Dict[str, int]:
        """Return the accumulated token usage counters."""
        ...


class CloudLLMClient(LLMClient):
    """
    Wraps cloud providers (Gemini, Azure OpenAI) using LangChain.
    Runs the canonical two-stage (Plan -> Generate) workflow.
    """
    def __init__(self, planner: QueryPlanner, sql_gen: SQLGenerator):
        self._planner = planner
        self._sql_gen = sql_gen
        self._prompt_tokens = 0
        self._completion_tokens = 0

    def generate_plan(self, nl_query: str, schema: str, callbacks: Optional[List[Any]] = None) -> QueryPlan:
        return self._planner.plan(nl_query, schema, callbacks=callbacks)

    def generate_sql(
        self, 
        nl_query: str, 
        schema: str, 
        plan: QueryPlan, 
        error_hint: Optional[str] = None, 
        callbacks: Optional[List[Any]] = None
    ) -> SQLQuery:
        return self._sql_gen.generate(nl_query, schema, plan, error_hint=error_hint, callbacks=callbacks)

    def get_token_tracker(self) -> Dict[str, int]:
        # Tokens are tracked via LangChain callbacks in the query engine
        return {}


# _detect_dialect and _dialect_hints are now centralized in teshq.core.dialect

def format_date_difference(dialect: SQLDialect, expr1: str, expr2: str) -> str:
    """Format dialect-appropriate expression for difference in days between two date/time expressions (expr2 - expr1)."""
    if dialect == SQLDialect.SQLITE:
        return f"CAST(julianday({expr2}) - julianday({expr1}) AS INTEGER)"
    elif dialect == SQLDialect.POSTGRESQL:
        return f"DATE_PART('day', {expr2} - {expr1})"
    elif dialect == SQLDialect.MYSQL:
        return f"DATEDIFF({expr2}, {expr1})"
    elif dialect == SQLDialect.MSSQL:
        return f"DATEDIFF(day, {expr1}, {expr2})"
    elif dialect == SQLDialect.ORACLE:
        return f"({expr2} - {expr1})"
    return f"DATEDIFF({expr2}, {expr1})"


def split_schema_cols(cols_str: str) -> List[str]:
    """Parse column definitions from schema string, respecting nested parentheses for types like DECIMAL(10, 2)."""
    cols = []
    current = []
    depth = 0
    for char in cols_str:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            cols.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        cols.append(''.join(current).strip())
    return [c for c in cols if c]


class LocalLLMClient(LLMClient):
    """
    Runs in-process LLM inference using llama-cpp-python.
    Uses a grammar-constrained, single-shot generation to save local compute/tokens.
    """
    def __init__(self, runtime: InferenceRuntime, config: InferenceConfig, db_url: str = ""):
        self._runtime = runtime
        self._config = config
        self._grammar = get_sql_grammar()
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._dialect = detect_dialect(db_url)

    def generate_plan(self, nl_query: str, schema: str, callbacks: Optional[List[Any]] = None) -> QueryPlan:
        """
        Lightweight, schema-aware query planning for local backend.
        Extracts candidate tables, joins, filters, and aggregations directly from the schema and query.
        """
        tables: List[str] = []
        filters: List[str] = []
        aggregations: List[str] = []
        joins: List[str] = []

        schema_tables: Dict[str, List[str]] = {}
        schema_joins: List[str] = []
        
        for line in schema.splitlines():
            line = line.strip()
            if line.startswith("TABLE "):
                match = re.match(r"TABLE\s+([a-zA-Z0-9_.]+)\s*\((.*?)\)", line)
                if match:
                    t_name = match.group(1)
                    cols = split_schema_cols(match.group(2))
                    schema_tables[t_name] = cols
            elif "→" in line:
                schema_joins.append(line)

        query_lower = nl_query.lower()
        clean_query = re.sub(r"[^\w\s]", " ", query_lower)
        words = clean_query.split()
        query_words = set(words)
        for w in list(query_words):
            if w.endswith("ies") and len(w) > 3:
                query_words.add(w[:-3] + "y")
            elif w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
                query_words.add(w[:-1])

        GENERIC_COLUMN_WORDS = {
            "name", "date", "id", "type", "status", "code", "desc", "description",
            "value", "time", "created", "updated", "at", "by", "num", "number", "first", "second",
            "day", "days", "month", "months", "year", "years", "hour", "hours", "week", "weeks",
            "total", "sum", "avg", "average", "count", "min", "max", "all"
        }

        # Identify leading subject entity (e.g. "Identify customers..." -> customers)
        subject_match = re.match(r"(?:identify|find|list|show|get|display|select)\s+(?:all\s+)?([a-zA-Z_]+)", clean_query)
        subject_word = subject_match.group(1) if subject_match else ""
        subject_sing = subject_word[:-3] + "y" if subject_word.endswith("ies") and len(subject_word) > 3 else (subject_word[:-1] if subject_word.endswith("s") and len(subject_word) > 3 and not subject_word.endswith("ss") else subject_word)

        table_scores: Dict[str, int] = {}
        for t_name, cols in schema_tables.items():
            score = 0
            # For schema-qualified names like 'hr.employees', also match on the base name
            t_base = t_name.split(".")[-1] if "." in t_name else t_name
            if t_base.endswith("ies") and len(t_base) > 3:
                t_singular = t_base[:-3] + "y"
            elif t_base.endswith("s") and len(t_base) > 3 and not t_base.endswith("ss"):
                t_singular = t_base[:-1]
            else:
                t_singular = t_base
            if t_name in query_words or t_base in query_words or t_singular in query_words:
                score += 20
            if subject_word and (t_base == subject_word or t_singular == subject_sing or t_singular == subject_word):
                score += 15
            for col_item in cols:
                col_name = col_item.split()[0]
                col_phrase = col_name.replace("_", " ")
                if col_name not in GENERIC_COLUMN_WORDS and (col_name in query_lower or col_phrase in query_lower):
                    score += 15
                else:
                    col_words = col_name.split("_")
                    for cw in col_words:
                        if len(cw) > 2 and cw in query_words and cw not in GENERIC_COLUMN_WORDS:
                            score += 5
            if score > 0:
                table_scores[t_name] = score

        # Handle numeric entity IDs like 'region 1', 'customer 5', 'account 101'
        TIME_AND_METRIC_WORDS = {"than", "more", "less", "gap", "difference", "day", "days", "month", "months", "year", "years", "top", "first", "second", "last", "limit", "within", "over", "under", "between"}
        id_filter_entities = set()
        id_matches = re.findall(r"\b([a-zA-Z_]+)\s+(\d+)\b", query_lower)
        for entity, num_val in id_matches:
            if entity in TIME_AND_METRIC_WORDS:
                continue
            candidate_cols = [f"{entity}_id", f"{entity}_no", f"{entity}_code", f"{entity}_num", f"{entity}_key"]
            found = False
            for t_name, cols in schema_tables.items():
                t_sing = t_name[:-3] + "y" if t_name.endswith("ies") and len(t_name) > 3 else (t_name[:-1] if t_name.endswith("s") and len(t_name) > 3 else t_name)
                cand_set = list(candidate_cols)
                if entity == t_name.lower() or entity == t_sing.lower():
                    cand_set.append("id")
                for col_item in cols:
                    c_name = col_item.split()[0]
                    if any(c_name == cand or c_name.startswith(f"{cand} ") for cand in cand_set):
                        filter_expr = f"{c_name} = {num_val}"
                        if filter_expr not in filters:
                            filters.append(filter_expr)
                        table_scores[t_name] = table_scores.get(t_name, 0) + 20
                        found = True
                        id_filter_entities.add(entity)
                        break
                if found:
                    break

        # Table selection
        sorted_tables = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_tables:
            primary_table = sorted_tables[0][0]
            tables.append(primary_table)
            primary_col_names = [c.split()[0] for c in schema_tables[primary_table]]
            primary_col_words = set(w for c in primary_col_names for w in c.split("_"))
            
            for t, sc in sorted_tables[1:]:
                # For schema-qualified names, use the base name for matching
                t_base = t.split(".")[-1] if "." in t else t
                # If secondary table was only matched as an ID entity (e.g. 'region 1') and primary table already has the FK
                t_sing = t_base[:-3] + "y" if t_base.endswith("ies") and len(t_base) > 3 else (t_base[:-1] if t_base.endswith("s") and len(t_base) > 3 else t_base)
                if t_sing in id_filter_entities and any(f"{t_sing}_id" in c or f"{t_sing}_no" in c for c in schema_tables[primary_table]):
                    has_explicit_col = False
                    for c in schema_tables[t]:
                        c_name = c.split()[0]
                        if not c_name.endswith("_id") and c_name != "id":
                            if c_name in query_lower or c_name.replace("_", " ") in query_lower:
                                has_explicit_col = True
                    if not has_explicit_col:
                        continue

                needs_secondary = False
                if t_base in query_words or t_sing in query_words:
                    needs_secondary = True
                else:
                    for c in schema_tables[t]:
                        c_name = c.split()[0]
                        if c_name.endswith("_id") or c_name == "id":
                            continue
                        col_phrase = c_name.replace("_", " ")
                        if c_name not in GENERIC_COLUMN_WORDS and (c_name in query_lower or col_phrase in query_lower):
                            needs_secondary = True
                            break
                        c_words = c_name.split("_")
                        new_words = [w for w in c_words if len(w) > 2 and w in query_words and w not in GENERIC_COLUMN_WORDS and w not in primary_col_words]
                        if new_words and sc >= 15:
                            needs_secondary = True
                            break
                if needs_secondary and t not in tables:
                    tables.append(t)

        # Date column discovery - ranked by query keyword relevance
        def find_date_col(t_list: List[str]) -> Optional[Tuple[str, str]]:
            date_keywords = ["date", "time", "created", "timestamp", "datetime", "updated", "day", "dt"]
            candidates = []
            for t in t_list:
                for col_def in schema_tables.get(t, []):
                    cn = col_def.split()[0]
                    cl = cn.lower()
                    cu = col_def.upper()
                    if any(dk in cl for dk in date_keywords) or any(dt in cu for dt in ["DATE", "TIME", "TIMESTAMP"]):
                        match_score = sum(1 for token in cn.split("_") if token.lower() in query_words)
                        candidates.append((match_score, t, cn))
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                return candidates[0][1], candidates[0][2]
            return None

        # Check for date gap / difference conditions, e.g. "gap of more than 90 days", "difference of > 90 days"
        gap_match = re.search(
            r"(?:(?:gap|difference|interval)\s+(?:of\s+)?(?:more\s+than|>|greater\s+than|at\s+least)\s*(\d+)\s*days?)|(?:(?:more\s+than|>|greater\s+than)\s*(\d+)\s*days?\s+(?:apart|between|gap|difference))",
            query_lower,
        )
        if gap_match:
            days_threshold = gap_match.group(1) or gap_match.group(2)
            dt_target = find_date_col(tables) or find_date_col(list(schema_tables.keys()))
            if dt_target:
                dt_table, d_col = dt_target
                diff_expr = format_date_difference(self._dialect, f"{dt_table}1.{d_col}", f"{dt_table}2.{d_col}")
                filters.append(f"{diff_expr} > {days_threshold}")
                if "consecutive" in query_words or "two consecutive" in query_lower:
                    filters.append(f"{dt_table}1.{d_col} < {dt_table}2.{d_col}")
            else:
                filters.append(f"difference between consecutive dates > {days_threshold} days")

        # Aggregations: use word boundary check so 'count' does not match 'account' or 'discount'
        duration_phrases = ["number of days", "number of months", "number of years", "number of hours", "number of weeks"]
        has_count_phrase = bool(re.search(r"\b(?:how\s+many|count|number\s+of)\b", query_lower)) and not any(p in query_lower for p in duration_phrases)
        if has_count_phrase:
            aggregations.append("COUNT(*)")

        # Determine aggregate operation
        agg_op = "SUM"
        if any(w in query_words for w in ["average", "avg", "mean"]):
            agg_op = "AVG"
        elif any(w in query_words for w in ["max", "maximum", "highest", "most", "peak"]):
            agg_op = "MAX"
        elif any(w in query_words for w in ["min", "minimum", "lowest", "least", "cheapest"]):
            agg_op = "MIN"

        def is_col_ambiguous(col: str, target_tables: List[str]) -> bool:
            return sum(1 for t in target_tables if any(c.split()[0] == col for c in schema_tables.get(t, []))) > 1

        def format_agg(func: str, t_name: str, c_name: str) -> str:
            if not is_col_ambiguous(c_name, tables):
                return f"{func}({c_name})"
            return f"{func}({t_name}.{c_name})"

        metric_match = re.search(r"(?:total|sum\s+of|average\s+of|avg\s+of|mean\s+of|max\s+of|highest\s+of|min\s+of|lowest\s+of)\s+([a-zA-Z_]+)", clean_query)
        found_agg = False
        if metric_match:
            m_word = metric_match.group(1)
            m_sing = m_word[:-1] if m_word.endswith("s") and len(m_word) > 3 else m_word
            if m_word not in GENERIC_COLUMN_WORDS and m_word not in [t.lower() for t in tables]:
                for t_name in tables + [t for t in schema_tables if t not in tables]:
                    for c in schema_tables[t_name]:
                        c_name = c.split()[0]
                        if c_name.endswith("_id") or c_name == "id":
                            continue
                        c_tokens = c_name.split("_")
                        if m_word in c_tokens or m_sing in c_tokens or c_name == m_word or c_name == m_sing:
                            aggregations.append(format_agg(agg_op, t_name, c_name))
                            found_agg = True
                            break
                    if found_agg:
                        break

        if not found_agg and not has_count_phrase and ("total" in query_words or "sum" in query_words or agg_op != "SUM"):
            # Dynamic numeric column discovery: scan schema for numeric-typed columns
            # instead of relying on hardcoded column name patterns
            _NUMERIC_TYPE_PATTERNS = {
                "INT", "INTEGER", "DECIMAL", "NUMERIC", "REAL", "FLOAT", "DOUBLE",
                "MONEY", "BIGINT", "SMALLINT", "TINYINT", "NUMBER",
            }
            for t_name in tables:
                for c in schema_tables[t_name]:
                    c_name = c.split()[0]
                    if c_name.endswith("_id") or c_name == "id":
                        continue
                    # Check if this is a PK or FK column (skip those)
                    if " PK" in c or " FK" in c:
                        continue
                    # Extract the type portion from the descriptor (e.g. "amount DECIMAL(10,2)" → "DECIMAL(10,2)")
                    c_parts = c.split(None, 1)
                    c_type_str = c_parts[1].upper() if len(c_parts) > 1 else ""
                    is_numeric = any(nt in c_type_str for nt in _NUMERIC_TYPE_PATTERNS)
                    if is_numeric:
                        # Prefer columns whose name tokens overlap with query words
                        if c_name in query_words or any(w in c_name.split("_") for w in query_words if len(w) > 2 and w not in GENERIC_COLUMN_WORDS):
                            aggregations.append(format_agg(agg_op, t_name, c_name))
                            break
                if aggregations:
                    break
            # Fallback: if no type-based match, try name-based heuristic for schemas
            # that don't include type info in descriptors (e.g. compressed schema with stripped types)
            if not aggregations:
                numeric_name_hints = ["amount", "total", "price", "cost", "quantity", "qty", "sales", "revenue", "balance", "fee", "val", "value", "rate", "weight", "volume", "hours", "salary"]
                for t_name in tables:
                    for c in schema_tables[t_name]:
                        c_name = c.split()[0]
                        if c_name.endswith("_id") or c_name == "id":
                            continue
                        c_lower = c_name.lower()
                        if any(h in c_lower for h in numeric_name_hints):
                            if c_name in query_words or any(w in c_name.split("_") for w in query_words if len(w) > 2 and w not in GENERIC_COLUMN_WORDS):
                                aggregations.append(format_agg(agg_op, t_name, c_name))
                                break
                    if aggregations:
                        break

        # Bridge disconnected tables using BFS on schema foreign keys
        if len(tables) > 1:
            from collections import defaultdict, deque
            adj = defaultdict(dict)
            for j_line in schema_joins:
                parts = j_line.split("→")
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    t_left = left.rsplit(".", 1)[0]
                    t_right = right.rsplit(".", 1)[0]
                    adj[t_left][t_right] = f"{left} = {right}"
                    adj[t_right][t_left] = f"{left} = {right}"

            def find_path(start: str, target: str) -> Optional[List[str]]:
                queue = deque([[start]])
                visited = {start}
                while queue:
                    p = queue.popleft()
                    node = p[-1]
                    if node == target:
                        return p
                    for nbr in adj.get(node, {}):
                        if nbr not in visited:
                            visited.add(nbr)
                            queue.append(p + [nbr])
                return None

            for i in range(len(tables)):
                for j in range(i + 1, len(tables)):
                    path = find_path(tables[i], tables[j])
                    if path:
                        for node in path:
                            if node not in tables:
                                tables.append(node)

            for j_line in schema_joins:
                parts = j_line.split("→")
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    t_left = left.rsplit(".", 1)[0]
                    t_right = right.rsplit(".", 1)[0]
                    if t_left in tables and t_right in tables:
                        cond = f"{left} = {right}"
                        if cond not in joins:
                            joins.append(cond)

        plan = QueryPlan(tables=tables, filters=filters, aggregations=aggregations, joins_needed=joins)
        logger.info(f"Local query plan generated: tables={plan.tables}, joins={plan.joins_needed}, filters={plan.filters}")
        return plan

    def generate_sql(
        self, 
        nl_query: str, 
        schema: str, 
        plan: QueryPlan, 
        error_hint: Optional[str] = None, 
        callbacks: Optional[List[Any]] = None
    ) -> SQLQuery:
        """Generates SQL using grammar constraints and custom local prompt."""
        self._runtime.load(self._config)
        
        dialect_str = str(self._dialect)
        hints = get_dialect_hints(self._dialect)
        rules = get_dialect_rules(self._dialect)

        dialect_date_rule = ""
        if self._dialect == SQLDialect.SQLITE:
            dialect_date_rule = "When calculating difference between dates in SQLite, always use CAST(julianday(date2) - julianday(date1) AS INTEGER). NEVER subtract date strings directly."
        elif self._dialect == SQLDialect.POSTGRESQL:
            dialect_date_rule = "When calculating difference between dates in PostgreSQL, use DATE_PART('day', date2 - date1) or (date2::date - date1::date)."
        elif self._dialect == SQLDialect.MYSQL:
            dialect_date_rule = "When calculating difference between dates in MySQL, use DATEDIFF(date2, date1)."
        elif self._dialect == SQLDialect.MSSQL:
            dialect_date_rule = "When calculating difference between dates in SQL Server, use DATEDIFF(day, date1, date2)."
        elif self._dialect == SQLDialect.ORACLE:
            dialect_date_rule = "When calculating difference between dates in Oracle, use (date2 - date1)."

        system_prompt = (
            f"You are a strict text-to-SQL assistant targeting a {dialect_str} database. "
            "CRITICAL RULES:\n"
            f"1. Generate ONLY a valid {dialect_str} SQL statement.\n"
            "2. Use ONLY the exact table and column names provided in the schema below. Do NOT invent or guess column names.\n"
            f"3. Do not use syntax or functions from other database engines. Use only {dialect_str}-compatible syntax.\n"
            "4. Do not include markdown formatting or explanations.\n"
            "5. Select ONLY the columns the user explicitly asked for. Do not add unrequested ID columns.\n"
            "   EXCEPTION: When the user asks to 'show all', 'list all', or 'display all' from a table without specifying particular columns, include ALL columns from the primary table. NEVER emit SELECT * — always list explicit column names (e.g. SELECT region_id, region_name FROM regions).\n"
            "6. When using aggregate functions (SUM, COUNT, AVG, MIN, MAX), ALWAYS enclose the argument in parentheses, for example: SUM(column_name) or COUNT(column_name). NEVER write a function name without parentheses (e.g. NEVER write SUM column).\n"
            "7. When the user asks to show or rank items by a metric (e.g. 'by price (mrp)'), include BOTH the item name and the metric column in the SELECT clause.\n"
            "8. Only JOIN tables that are strictly necessary to answer the query. If all requested columns and filter conditions exist in a single table, do NOT join other tables.\n"
            "9. When an entity is specified with a number/digit (e.g. 'region 1', 'customer 5'), filter on that entity's integer ID column (e.g. region_id = 1). NEVER apply an entity ID filter to numbers representing durations, days, limits, or thresholds (e.g. '90 days' is a duration, NOT an entity ID).\n"
            "10. Do NOT add LIMIT unless the user explicitly requested a limit, top N, or first N rows.\n"
            "11. Embed literal values directly in the SQL. Do NOT use :param_name bind parameters.\n"
            "12. When JOINing tables, use ONLY the FK→ relationships shown in the schema.\n"
            "13. If you give a table an alias in FROM or JOIN (e.g., order_items oi), use that alias for all its columns (e.g., oi.quantity). NEVER use the full table name once an alias is defined.\n"
            "14. If you JOIN the same table more than once, give each instance a unique alias (e.g., orders o1, orders o2 or orders1, orders2). If the query plan references orders1 and orders2, alias them accordingly (e.g., FROM orders orders1 JOIN orders orders2 ON ...).\n"
            "15. If you select a column from a table (e.g. alias.column or table.column), that table MUST be included in the FROM or JOIN clause. NEVER select a column from a table that is not joined in FROM."
        )
        if dialect_date_rule:
            system_prompt += f"\n16. {dialect_date_rule}"
        if rules:
            system_prompt += f"\n{rules}"
        if hints:
            system_prompt += f"\n{hints}"

        # Focus schema string to tables identified in plan
        if plan and plan.tables:
            focused_lines = []
            for line in schema.splitlines():
                if line.startswith("TABLE "):
                    match = re.match(r"TABLE\s+([a-zA-Z0-9_.]+)", line)
                    if match and match.group(1) in plan.tables:
                        focused_lines.append(line)
                elif "→" in line:
                    parts = line.split("→")
                    if len(parts) == 2:
                        t1 = parts[0].strip().rsplit(".", 1)[0]
                        t2 = parts[1].strip().rsplit(".", 1)[0]
                        if t1 in plan.tables and t2 in plan.tables:
                            if "JOINS:" not in focused_lines:
                                focused_lines.append("")
                                focused_lines.append("JOINS:")
                            focused_lines.append(line)
            if focused_lines:
                schema = "\n".join(focused_lines)

        plan_context = ""
        if plan and (plan.tables or plan.joins_needed or plan.filters or plan.aggregations):
            parts = []
            if plan.tables:
                parts.append(f"  Tables: {', '.join(plan.tables)}")
            if plan.filters:
                parts.append(f"  Filters: {', '.join(plan.filters)}")
            if plan.aggregations:
                parts.append(f"  Aggregations: {', '.join(plan.aggregations)}")
            if plan.joins_needed:
                parts.append(f"  Joins: {', '.join(plan.joins_needed)}")
            if parts:
                plan_context = "Query plan:\n" + "\n".join(parts) + "\n\n"
        
        prompt = f"Database Schema:\n{schema}\n\n{plan_context}Natural Language Request: {nl_query}\n\n"
        if error_hint:
            prompt += (
                f"IMPORTANT: The previous SQL attempt failed with this error:\n{error_hint}\n"
                "You MUST fix the error. Re-read the schema above carefully and use only the exact column names listed.\n\n"
            )
        prompt += "SQL Query:"

        res = self._runtime.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=512,
            temperature=0.0,
            grammar=self._grammar,
        )
        
        # Accumulate tokens
        self._prompt_tokens += res.prompt_tokens
        self._completion_tokens += res.completion_tokens
        
        # Clean up any potential markdown wraps
        cleaned_query = res.text.strip()
        if cleaned_query.startswith("```"):
            lines = cleaned_query.splitlines()
            if lines[0].startswith("```sql") or lines[0].startswith("```"):
                cleaned_query = "\n".join(lines[1:-1]).strip()

        # Clean up any missing parentheses around aggregate functions (e.g. SUM col -> SUM(col))
        cleaned_query = re.sub(
            r"\b(SUM|COUNT|AVG|MIN|MAX)\s+([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?|\*)",
            r"\1(\2)",
            cleaned_query,
            flags=re.IGNORECASE,
        )

        # Fix table-name vs alias conflicts if a table is aliased in FROM/JOIN
        alias_counts: Dict[str, List[str]] = {}
        for m in re.finditer(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)(?:\s+AS)?\s+([a-zA-Z0-9_]+)\b", cleaned_query, re.IGNORECASE):
            tbl = m.group(1)
            alias = m.group(2)
            if alias.upper() not in {"ON", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL", "GROUP", "ORDER", "LIMIT", "SET", "USING", "AND"}:
                if tbl.lower() != alias.lower():
                    alias_counts.setdefault(tbl, []).append(alias)
        for tbl, aliases in alias_counts.items():
            if len(aliases) == 1:
                # Unique alias: replace tbl.col with alias.col
                cleaned_query = re.sub(rf"\b{re.escape(tbl)}\.([a-zA-Z0-9_]+)\b", rf"{aliases[0]}.\1", cleaned_query)

        # Ensure any column selected from an unjoined planned table gets its table joined
        from_join_tables = set()
        for m in re.finditer(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.]+)\b", cleaned_query, re.IGNORECASE):
            from_join_tables.add(m.group(1).lower())

        cur_schema_tables: Dict[str, List[str]] = {}
        cur_schema_joins: List[str] = []
        for line in schema.splitlines():
            line = line.strip()
            if line.startswith("TABLE "):
                m = re.match(r"TABLE\s+([a-zA-Z0-9_.]+)\s*\((.*?)\)", line)
                if m:
                    cur_schema_tables[m.group(1)] = split_schema_cols(m.group(2))
            elif "→" in line:
                cur_schema_joins.append(line)

        cols_referenced = re.findall(r"\b(?:([a-zA-Z0-9_]+)\.)?([a-zA-Z0-9_]+)\b", cleaned_query)
        SQL_KEYWORDS = {"SELECT", "FROM", "JOIN", "AS", "ON", "WHERE", "AND", "OR", "CAST", "INTEGER", "DATE", "GROUP", "BY", "ORDER", "LIMIT", "DESC", "ASC", "HAVING", "CASE", "WHEN", "THEN", "ELSE", "END", "NULL", "NOT", "IS", "IN", "BETWEEN", "LIKE", "ILIKE", "EXISTS", "UNION", "ALL", "DISTINCT", "SUM", "COUNT", "AVG", "MIN", "MAX"}
        
        missing_col_tables: Dict[Tuple[str, str], str] = {}
        for prefix, col in cols_referenced:
            if col.upper() in SQL_KEYWORDS:
                continue
            in_joined = any(any(c.split()[0].lower() == col.lower() for c in cur_schema_tables.get(t, [])) for t in from_join_tables)
            if not in_joined:
                for t_name, t_cols in cur_schema_tables.items():
                    if any(c.split()[0].lower() == col.lower() for c in t_cols):
                        missing_col_tables[(prefix, col)] = t_name

        for (prefix, col), missing_table in missing_col_tables.items():
            if missing_table.lower() not in from_join_tables:
                for j in cur_schema_joins:
                    p = j.split("→")
                    if len(p) != 2:
                        continue
                    left = p[0].strip()
                    right = p[1].strip()
                    t_left = left.rsplit(".", 1)[0].lower()
                    t_right = right.rsplit(".", 1)[0].lower()
                    c_left = left.rsplit(".", 1)[1]
                    c_right = right.rsplit(".", 1)[1]
                    
                    if t_left == missing_table.lower() and t_right in from_join_tables:
                        target_alias = t_right
                        m_alias = re.search(rf"\b(?:FROM|JOIN)\s+{re.escape(t_right)}(?:\s+AS)?\s+([a-zA-Z0-9_]+)\b", cleaned_query, re.I)
                        if m_alias and m_alias.group(1).upper() not in SQL_KEYWORDS:
                            target_alias = m_alias.group(1)
                        join_clause = f"JOIN {missing_table} ON {missing_table}.{c_left} = {target_alias}.{c_right}"
                        where_pos = cleaned_query.upper().find("WHERE")
                        if where_pos != -1:
                            cleaned_query = cleaned_query[:where_pos] + join_clause + "\n" + cleaned_query[where_pos:]
                        else:
                            cleaned_query += "\n" + join_clause
                        from_join_tables.add(missing_table.lower())
                        if prefix:
                            cleaned_query = re.sub(rf"\b{re.escape(prefix)}\.{re.escape(col)}\b", f"{missing_table}.{col}", cleaned_query)
                        break
                    elif t_right == missing_table.lower() and t_left in from_join_tables:
                        target_alias = t_left
                        m_alias = re.search(rf"\b(?:FROM|JOIN)\s+{re.escape(t_left)}(?:\s+AS)?\s+([a-zA-Z0-9_]+)\b", cleaned_query, re.I)
                        if m_alias and m_alias.group(1).upper() not in SQL_KEYWORDS:
                            target_alias = m_alias.group(1)
                        join_clause = f"JOIN {missing_table} ON {missing_table}.{c_right} = {target_alias}.{c_left}"
                        where_pos = cleaned_query.upper().find("WHERE")
                        if where_pos != -1:
                            cleaned_query = cleaned_query[:where_pos] + join_clause + "\n" + cleaned_query[where_pos:]
                        else:
                            cleaned_query += "\n" + join_clause
                        from_join_tables.add(missing_table.lower())
                        if prefix:
                            cleaned_query = re.sub(rf"\b{re.escape(prefix)}\.{re.escape(col)}\b", f"{missing_table}.{col}", cleaned_query)
                        break

        # Check for alias.col where col does NOT belong to the table bound to that alias
        alias_to_table: Dict[str, str] = {}
        for m in re.finditer(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.]+)(?:\s+AS)?\s+([a-zA-Z0-9_]+)\b", cleaned_query, re.IGNORECASE):
            tbl = m.group(1)
            al = m.group(2)
            if al.upper() not in SQL_KEYWORDS:
                alias_to_table[al] = tbl

        added_self_joins: List[str] = []
        unique_mismatches: List[Tuple[str, str]] = []
        for m in re.finditer(r"\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\b", cleaned_query):
            pair = (m.group(1), m.group(2))
            if pair not in unique_mismatches:
                unique_mismatches.append(pair)

        for al, col in unique_mismatches:
            if al in alias_to_table:
                bound_table = alias_to_table[al]
                table_cols = [c.split()[0].lower() for c in cur_schema_tables.get(bound_table, [])]
                if col.lower() not in table_cols:
                    for actual_table, cols in cur_schema_tables.items():
                        if any(c.split()[0].lower() == col.lower() for c in cols):
                            prefix_base = re.sub(r"[^a-zA-Z0-9]", "", actual_table)[:3].lower()
                            new_alias = f"{prefix_base}1" if f"{prefix_base}1" not in alias_to_table else f"{prefix_base}2"
                            if new_alias not in alias_to_table:
                                for j in cur_schema_joins:
                                    p = j.split("→")
                                    if len(p) == 2:
                                        l_tbl = p[0].strip().rsplit(".", 1)[0]
                                        r_tbl = p[1].strip().rsplit(".", 1)[0]
                                        l_col = p[0].strip().rsplit(".", 1)[1]
                                        r_col = p[1].strip().rsplit(".", 1)[1]
                                        if l_tbl.lower() == actual_table.lower() and r_tbl.lower() == bound_table.lower():
                                            join_clause = f"JOIN {actual_table} AS {new_alias} ON {new_alias}.{l_col} = {al}.{r_col}"
                                            added_self_joins.append(join_clause)
                                            alias_to_table[new_alias] = actual_table
                                            break
                                        elif r_tbl.lower() == actual_table.lower() and l_tbl.lower() == bound_table.lower():
                                            join_clause = f"JOIN {actual_table} AS {new_alias} ON {new_alias}.{r_col} = {al}.{l_col}"
                                            added_self_joins.append(join_clause)
                                            alias_to_table[new_alias] = actual_table
                                            break
                            cleaned_query = re.sub(rf"\b{re.escape(al)}\.{re.escape(col)}\b", f"{new_alias}.{col}", cleaned_query)
                            break

        if added_self_joins:
            where_pos = cleaned_query.upper().find("WHERE")
            join_str = "\n" + "\n".join(added_self_joins) + "\n"
            if where_pos != -1:
                cleaned_query = cleaned_query[:where_pos] + join_str + cleaned_query[where_pos:]
            else:
                cleaned_query += join_str

        # Expand SELECT * if emitted, to comply with validation rules
        if re.search(r"\bSELECT\s+\*\s+FROM\s+([a-zA-Z0-9_.]+)", cleaned_query, re.IGNORECASE):
            match = re.search(r"\bSELECT\s+\*\s+FROM\s+([a-zA-Z0-9_.]+)(.*)", cleaned_query, re.IGNORECASE | re.DOTALL)
            if match:
                table_name = match.group(1)
                rest = match.group(2)
                table_match = re.search(rf"TABLE\s+{re.escape(table_name)}\s*\((.*?)\)", schema)
                if table_match:
                    raw_cols = [c.strip().split()[0] for c in split_schema_cols(table_match.group(1)) if c.strip()]
                    if raw_cols:
                        cleaned_query = f"SELECT {', '.join(raw_cols)} FROM {table_name}{rest}"
        
        # Fake callback updates if custom tracker callback provided
        if callbacks:
            for cb in callbacks:
                # Update TokenTracker if present
                if hasattr(cb, "prompt_tokens") and hasattr(cb, "completion_tokens"):
                    cb.prompt_tokens += res.prompt_tokens
                    cb.completion_tokens += res.completion_tokens

        return SQLQuery(query=cleaned_query, parameters={})

    def get_token_tracker(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._prompt_tokens + self._completion_tokens,
        }
