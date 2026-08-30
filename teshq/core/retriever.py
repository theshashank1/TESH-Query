"""
Schema Retriever for TESH-Query v2.

Implements a vector-similarity-based schema retrieval pipeline that
selects only the Top-K most relevant tables for a given user query.
This keeps the LLM context window small even for schemas with 100+
tables.

The retriever builds an in-memory index from column descriptors in a
:class:`SchemaGraph` and scores each table against the user query
using TF-IDF cosine similarity (no external embedding service needed).

Usage::

    from teshq.core.retriever import SchemaRetriever

    retriever = SchemaRetriever(schema_graph)
    tables = retriever.retrieve("show monthly revenue by region", top_k=5)
    compressed = schema_graph.compressed_schema(tables)
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from teshq.core.schema_graph import SchemaGraph
from teshq.utils.logging import logger

# Re-use stop-words from schema_pruner to keep the two modules in sync
from teshq.core.schema_pruner import _STOP_WORDS


def _tokenize(text: str) -> List[str]:
    """Split *text* into lowercase alpha tokens, excluding stop-words."""
    return [
        tok
        for tok in re.findall(r"[a-zA-Z_]+", text.lower())
        if tok not in _STOP_WORDS and len(tok) > 1
    ]


class SchemaRetriever:
    """Vector-similarity retriever over a :class:`SchemaGraph`.

    Builds a lightweight TF-IDF index from each table's name and column
    descriptors, then ranks tables by cosine similarity to the user query.
    """

    def __init__(self, schema_graph: SchemaGraph) -> None:
        self._graph = schema_graph
        # table_name → term-frequency vector (dict of token → count)
        self._tf: Dict[str, Counter] = {}
        # token → number of tables containing it
        self._df: Counter = Counter()
        self._num_tables: int = 0
        self._build_index()

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_index(self) -> None:
        """Build inverted index from SchemaGraph tables and columns."""
        self._num_tables = len(self._graph.tables)
        for table_name, col_descriptors in self._graph.tables.items():
            # Combine table name with all column descriptors
            doc_text = f"{table_name} " + " ".join(col_descriptors)
            tokens = _tokenize(doc_text)
            tf = Counter(tokens)
            self._tf[table_name] = tf
            for tok in set(tokens):
                self._df[tok] += 1

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _estimate_table_tokens(self, table_name: str) -> int:
        """Estimate the token count for a table in the compressed representation."""
        if table_name not in self._graph.tables:
            return 0
        cols_str = ", ".join(self._graph.tables[table_name])
        repr_str = f"TABLE {table_name}({cols_str})\n"
        return max(1, len(repr_str) // 4)

    def retrieve(
        self,
        nl_query: str,
        top_k: int = 10,
        expand_neighbors: bool = True,
        budget_tokens: Optional[int] = None,
    ) -> List[str]:
        """Return the *top_k* most relevant table names for *nl_query*.

        Args:
            nl_query: User's natural-language query.
            top_k: Maximum number of directly matched tables.
            expand_neighbors: If ``True``, also include FK-connected
                neighbours of matched tables (does not count towards
                *top_k* cap).
            budget_tokens: Optional maximum estimated token count for the retrieved schema.

        Returns:
            Ordered list of table names (most relevant first).
        """
        query_tokens = _tokenize(nl_query)
        if not query_tokens:
            logger.debug("No meaningful tokens in query — falling back to most connected tables")
            candidates = self._graph.most_connected_tables(limit=top_k)
        else:
            scores: Dict[str, float] = {}
            for table_name, tf in self._tf.items():
                score = self._cosine_score(query_tokens, tf)
                if score > 0:
                    scores[table_name] = score

            if not scores:
                logger.debug("No tables matched query — falling back to most connected tables")
                candidates = self._graph.most_connected_tables(limit=top_k)
            else:
                candidates = sorted(scores, key=lambda t: scores[t], reverse=True)[:top_k]

        if expand_neighbors:
            expanded: List[str] = list(candidates)
            for table in candidates:
                for neighbor in self._graph.neighbors(table):
                    if neighbor not in expanded:
                        expanded.append(neighbor)
            candidates = expanded

        if budget_tokens is None:
            return candidates

        # Prune candidates to fit within budget_tokens
        selected_tables: List[str] = []
        current_tokens = 0
        for table in candidates:
            table_tokens = self._estimate_table_tokens(table)
            # Add some overhead for joins (e.g. 5 tokens per table)
            table_tokens += 5
            
            if current_tokens + table_tokens <= budget_tokens:
                selected_tables.append(table)
                current_tokens += table_tokens
            elif not selected_tables:
                # Force-include at least the first (most relevant) table
                selected_tables.append(table)
                current_tokens += table_tokens
                logger.warning(f"Forcing first table {table} despite exceeding token budget ({current_tokens} > {budget_tokens})")
        
        logger.info(f"Retrieved {len(selected_tables)}/{len(candidates)} tables within budget of {budget_tokens} tokens (est: {current_tokens})")
        return selected_tables

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _idf(self, token: str) -> float:
        """Inverse document frequency with smoothing."""
        df = self._df.get(token, 0)
        if df == 0:
            return 0.0
        return math.log((1 + self._num_tables) / (1 + df)) + 1

    def _cosine_score(self, query_tokens: List[str], doc_tf: Counter) -> float:
        """TF-IDF cosine similarity between *query_tokens* and a doc vector."""
        query_tf = Counter(query_tokens)
        dot = 0.0
        query_norm_sq = 0.0
        doc_norm_sq = 0.0

        all_terms = set(query_tf) | set(doc_tf)
        for term in all_terms:
            idf = self._idf(term)
            q_weight = query_tf.get(term, 0) * idf
            d_weight = doc_tf.get(term, 0) * idf
            dot += q_weight * d_weight
            query_norm_sq += q_weight ** 2
            doc_norm_sq += d_weight ** 2

        if query_norm_sq == 0 or doc_norm_sq == 0:
            return 0.0
        return dot / (math.sqrt(query_norm_sq) * math.sqrt(doc_norm_sq))
