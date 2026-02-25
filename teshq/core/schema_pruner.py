"""
Schema Pruning for TESH-Query v2.

Before sending schema to the LLM, prune it to only the tables relevant to the
natural language query. This reduces token usage and improves LLM focus.
"""

import re
from typing import List

from teshq.core.schema_graph import SchemaGraph

# Common English stop-words to skip when extracting keywords
_STOP_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "by", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "to", "and", "or", "but", "if",
    "me", "my", "we", "our", "you", "your", "it", "its", "this",
    "that", "these", "those", "all", "each", "from", "get", "show",
    "list", "find", "give", "tell", "what", "how", "many", "much",
    "per", "top", "most", "least", "total", "count", "sum", "avg",
    "between", "group", "where", "select", "which",
}


def extract_keywords(nl_query: str) -> List[str]:
    """
    Extract meaningful keywords from a natural language query.

    Args:
        nl_query: The user's natural language query string.

    Returns:
        List of lower-cased keywords.
    """
    tokens = re.findall(r"[a-zA-Z_]+", nl_query.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def prune_schema(schema_graph: SchemaGraph, nl_query: str) -> List[str]:
    """
    Select the subset of tables relevant to *nl_query*.

    Strategy:
    1. Extract keywords from the query.
    2. Match keywords against table names.
    3. Add FK-connected neighbors of matched tables.
    4. If nothing matched, fall back to the top-5 most connected tables.

    Args:
        schema_graph: The full SchemaGraph for the database.
        nl_query: The user's natural language query.

    Returns:
        Ordered list of table names to include in the LLM prompt.
    """
    keywords = extract_keywords(nl_query)
    all_tables = list(schema_graph.tables.keys())

    matched: List[str] = []
    for table in all_tables:
        table_lower = table.lower()
        # Match if any keyword is a substring of the table name or vice versa
        if any(kw in table_lower or table_lower in kw for kw in keywords):
            if table not in matched:
                matched.append(table)

    if not matched:
        # Fallback: use most-connected tables
        return schema_graph.most_connected_tables(limit=5)

    # Expand with direct FK neighbors
    selected: List[str] = list(matched)
    for table in matched:
        for neighbor in schema_graph.neighbors(table):
            if neighbor not in selected:
                selected.append(neighbor)

    return selected
