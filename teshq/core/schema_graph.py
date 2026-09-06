"""
Schema Intelligence Layer for TESH-Query v2.

Converts introspected schema into a relational graph with FK relationships
and generates compressed, token-efficient schema summaries for LLM prompts.
"""

from typing import Dict, List, Optional, Set

from pydantic import BaseModel


class JoinEdge(BaseModel):
    """Represents a foreign-key join relationship between two tables."""

    left_table: str
    right_table: str
    left_column: str
    right_column: str


class SchemaGraph(BaseModel):
    """Relational graph representation of a database schema."""

    tables: Dict[str, List[str]]  # table -> list of column descriptors
    joins: List[JoinEdge]
    summary: str
    dialect: str = "generic"  # e.g. "SQLite", "PostgreSQL", "MySQL", ...

    @classmethod
    def from_introspected(cls, schema_info: dict) -> "SchemaGraph":
        """
        Build a SchemaGraph from the output of introspect_db().

        Args:
            schema_info: Dict returned by teshq.core.introspect.introspect_db()

        Returns:
            A populated SchemaGraph instance.
        """
        tables: Dict[str, List[str]] = {}
        joins: List[JoinEdge] = []
        dialect = schema_info.get("dialect", "generic")

        for table_name, table_data in schema_info.get("tables", {}).items():
            pk_cols = set(table_data.get("primary_keys", []))
            fk_cols: Dict[str, str] = {}
            for fk in table_data.get("foreign_keys", []):
                referred = fk["referred_table"]
                for i, constrained_col in enumerate(fk["constrained_columns"]):
                    referred_cols = fk.get("referred_columns", [])
                    referred_col = referred_cols[i] if i < len(referred_cols) else "id"
                    fk_cols[constrained_col] = f"{referred}.{referred_col}"

            col_descriptors: List[str] = []
            for col in table_data.get("columns", []):
                name = col["name"]
                col_type = str(col["type"])
                if name in pk_cols:
                    col_descriptors.append(f"{name} PK")
                elif name in fk_cols:
                    col_descriptors.append(f"{name} FK→{fk_cols[name]}")
                else:
                    col_descriptors.append(f"{name} {col_type}")

            tables[table_name] = col_descriptors

            # Build JoinEdge entries from explicit foreign keys
            for fk in table_data.get("foreign_keys", []):
                referred_table = fk["referred_table"]
                for i, constrained_col in enumerate(fk["constrained_columns"]):
                    referred_cols = fk.get("referred_columns", [])
                    referred_col = referred_cols[i] if i < len(referred_cols) else "id"
                    joins.append(
                        JoinEdge(
                            left_table=table_name,
                            right_table=referred_table,
                            left_column=constrained_col,
                            right_column=referred_col,
                        )
                    )

        summary = cls._build_summary(tables, joins)
        return cls(tables=tables, joins=joins, summary=summary, dialect=dialect)

    @staticmethod
    def _build_summary(tables: Dict[str, List[str]], joins: List[JoinEdge]) -> str:
        """Generate a one-line-per-table compressed schema summary."""
        lines: List[str] = []
        for table_name, cols in tables.items():
            cols_str = ", ".join(cols)
            lines.append(f"TABLE {table_name}({cols_str})")
        if joins:
            lines.append("")
            lines.append("JOINS:")
            for edge in joins:
                lines.append(f"{edge.left_table}.{edge.left_column} → {edge.right_table}.{edge.right_column}")
        return "\n".join(lines)

    def get_table_columns(self, table_name: str) -> List[str]:
        """Return just column names (no type descriptors) for a table.

        Args:
            table_name: Table name (supports schema-qualified like 'schema.table').

        Returns:
            List of column name strings (e.g. ["id", "name", "created_at"]).
        """
        col_descriptors = self.tables.get(table_name, [])
        return [desc.split()[0] for desc in col_descriptors]

    def compressed_schema(self, table_names: List[str]) -> str:
        """
        Return a compressed schema string for the given subset of tables.

        Args:
            table_names: Tables to include in the output.

        Returns:
            Compressed schema string suitable for LLM prompts.
        """
        lines: List[str] = []
        for table_name in table_names:
            if table_name in self.tables:
                cols_str = ", ".join(self.tables[table_name])
                lines.append(f"TABLE {table_name}({cols_str})")

        relevant_joins = [
            j for j in self.joins if j.left_table in table_names and j.right_table in table_names
        ]
        if relevant_joins:
            lines.append("")
            lines.append("JOINS:")
            for edge in relevant_joins:
                lines.append(f"{edge.left_table}.{edge.left_column} → {edge.right_table}.{edge.right_column}")

        return "\n".join(lines)

    def compressed_schema_within_budget(
        self,
        table_names: List[str],
        max_tokens: int,
        query_words: Optional[Set[str]] = None,
    ) -> str:
        """
        Generate compressed schema, shortening descriptors or dropping less critical columns if it exceeds token budget.

        Args:
            table_names: Tables to include.
            max_tokens: Approximate token budget.
            query_words: Optional set of lowercased words from the user query.
                Used in Level 2 compression to keep columns relevant to the query
                instead of relying on hardcoded column name patterns.
        """
        schema_str = self.compressed_schema(table_names)
        if len(schema_str) // 4 <= max_tokens:
            return schema_str

        # Level 1 compression: keep ALL column names but strip data types (retain PK and FK markers)
        lines: List[str] = []
        for table_name in table_names:
            if table_name in self.tables:
                compact_cols = []
                for col_desc in self.tables[table_name]:
                    if " PK" in col_desc or " FK→" in col_desc:
                        compact_cols.append(col_desc)
                    else:
                        col_name = col_desc.split()[0]
                        compact_cols.append(col_name)
                cols_str = ", ".join(compact_cols)
                lines.append(f"TABLE {table_name}({cols_str})")

        relevant_joins = [
            j for j in self.joins if j.left_table in table_names and j.right_table in table_names
        ]
        if relevant_joins:
            lines.append("")
            lines.append("JOINS:")
            for edge in relevant_joins:
                lines.append(f"{edge.left_table}.{edge.left_column} → {edge.right_table}.{edge.right_column}")

        level1_str = "\n".join(lines)
        if len(level1_str) // 4 <= max_tokens:
            return level1_str

        # Level 2 compression (severe over-budget): keep PK, FK, and columns relevant to the query
        # Dynamic: instead of hardcoded business column names, keep columns whose name
        # tokens overlap with the user's query words (schema-agnostic)
        _query_words = query_words or set()
        lines = []
        for table_name in table_names:
            if table_name in self.tables:
                filtered_cols = []
                for col_desc in self.tables[table_name]:
                    col_name = col_desc.split()[0]
                    if " PK" in col_desc or " FK→" in col_desc:
                        filtered_cols.append(col_desc)
                    elif _query_words:
                        # Keep if any token in the column name matches a query word
                        col_tokens = set(col_name.lower().split("_"))
                        if col_tokens & _query_words:
                            filtered_cols.append(col_name)
                    else:
                        # Fallback when no query words: keep columns with common
                        # analytical patterns (names, dates, statuses, amounts)
                        cl = col_name.lower()
                        if any(x in cl for x in [
                            "name", "status", "date", "created", "type", "amount",
                            "total", "price", "quantity", "cost", "count",
                        ]):
                            filtered_cols.append(col_name)
                if not filtered_cols:
                    filtered_cols = [self.tables[table_name][0]]
                cols_str = ", ".join(filtered_cols)
                lines.append(f"TABLE {table_name}({cols_str})")

        if relevant_joins:
            lines.append("")
            lines.append("JOINS:")
            for edge in relevant_joins:
                lines.append(f"{edge.left_table}.{edge.left_column} → {edge.right_table}.{edge.right_column}")

        return "\n".join(lines)

    def neighbors(self, table_name: str) -> List[str]:
        """Return all tables directly FK-connected to the given table."""
        result: List[str] = []
        for edge in self.joins:
            if edge.left_table == table_name and edge.right_table not in result:
                result.append(edge.right_table)
            elif edge.right_table == table_name and edge.left_table not in result:
                result.append(edge.left_table)
        return result

    def most_connected_tables(self, limit: int = 5) -> List[str]:
        """Return the tables with the most FK connections, up to *limit*."""
        counts: Dict[str, int] = {t: 0 for t in self.tables}
        for edge in self.joins:
            counts[edge.left_table] = counts.get(edge.left_table, 0) + 1
            counts[edge.right_table] = counts.get(edge.right_table, 0) + 1
        sorted_tables = sorted(counts, key=lambda t: counts[t], reverse=True)
        return sorted_tables[:limit]

