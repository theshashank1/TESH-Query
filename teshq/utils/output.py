"""
Unified output handling for consistent results across CLI, API, and UI.

This module provides standardized output formatting and data processing
to ensure consistency between different interfaces.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from tabulate import tabulate


class OutputFormatter:
    """Handles consistent output formatting across all interfaces."""
    
    @staticmethod
    def normalize_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize query results to ensure consistency across all outputs.
        
        This method:
        - Converts Decimal values to float for JSON serialization
        - Handles None/NULL values consistently
        - Ensures all values are properly serializable
        
        Args:
            results: Raw query results from database
            
        Returns:
            Normalized results suitable for any output format
        """
        if not results:
            return []
            
        normalized = []
        for row in results:
            normalized_row = {}
            for key, value in row.items():
                if isinstance(value, Decimal):
                    # Convert Decimal to float, handling precision properly
                    normalized_row[key] = float(value)
                elif value is None:
                    # Consistent NULL handling
                    normalized_row[key] = None
                else:
                    normalized_row[key] = value
            normalized.append(normalized_row)
        
        return normalized
    
    @staticmethod
    def to_dataframe(results: List[Dict[str, Any]], normalize: bool = True) -> pd.DataFrame:
        """
        Convert query results to pandas DataFrame.
        
        Args:
            results: Query results
            normalize: Whether to normalize the data first
            
        Returns:
            pandas DataFrame
        """
        if normalize:
            results = OutputFormatter.normalize_results(results)
        
        if not results:
            return pd.DataFrame()
            
        return pd.DataFrame(results)
    
    @staticmethod
    def format_for_display(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format results specifically for terminal/UI display.
        
        This handles special display formatting like:
        - Decimal formatting for money/numbers
        - NULL value display
        - String length truncation if needed
        
        Args:
            results: Query results
            
        Returns:
            Display-formatted results
        """
        if not results:
            return []
            
        display_results = []
        for row in results:
            display_row = {}
            for key, value in row.items():
                if isinstance(value, Decimal):
                    # Format decimals nicely for display
                    formatted = f"{float(value):,.2f}".rstrip("0").rstrip(".")
                    display_row[key] = formatted
                elif value is None:
                    display_row[key] = "NULL"
                else:
                    display_row[key] = value
            display_results.append(display_row)
        
        return display_results
    
    @staticmethod
    def print_results_table(
        results: List[Dict[str, Any]], 
        title: str = "Results",
        show_count: bool = True,
        tablefmt: str = "grid"
    ) -> None:
        """
        Print results in a formatted table using Modern UI.
        
        Args:
            results: Query results
            title: Table title
            show_count: Whether to show row count
            tablefmt: Table format (ignored, kept for compatibility)
        """
        from teshq.cli.ui import warning, print_results_table
        
        if not results:
            count_msg = " (0 records)" if show_count else ""
            warning(f"{title}{count_msg}: No data found.")
            return
        
        # Format for display
        display_results = OutputFormatter.format_for_display(results)
        
        headers = list(display_results[0].keys())
        rows = [[row[h] for h in headers] for row in display_results]
        
        summary = f"{len(results)} record{'s' if len(results) != 1 else ''}" if show_count else ""
        print_results_table(headers=headers, rows=rows, title=title, summary=summary)




import json
import math
from pathlib import Path


class QueryResult:
    """
    Standardized query result container that provides consistent access
    to query results across all interfaces (CLI, API, Data Engineering, ML).
    """
    
    def __init__(
        self, 
        results: List[Dict[str, Any]], 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None,
        natural_language_query: Optional[str] = None
    ):
        """
        Initialize query result container.
        
        Args:
            results: Raw query results from database
            query: SQL query that was executed
            parameters: Query parameters used
            natural_language_query: Original natural language request
        """
        self.raw_results = results
        self.query = query
        self.parameters = parameters or {}
        self.natural_language_query = natural_language_query
        
        # Normalize results once for consistency
        self._normalized_results = OutputFormatter.normalize_results(results)
        self._dataframe = None
        self._arrow_table = None
        self._polars_df = None
    
    @property
    def results(self) -> List[Dict[str, Any]]:
        """Get normalized results suitable for API/JSON output."""
        return self._normalized_results
    
    @property
    def dataframe(self) -> pd.DataFrame:
        """Get results as pandas DataFrame (cached)."""
        if self._dataframe is None:
            self._dataframe = OutputFormatter.to_dataframe(self._normalized_results, normalize=False)
        return self._dataframe

    @property
    def arrow(self) -> Any:
        """
        Get results as a PyArrow Table (zero-copy data exchange for ML and analytics).

        Raises:
            ImportError: If pyarrow is not installed.
        """
        if self._arrow_table is None:
            try:
                import pyarrow as pa  # type: ignore
            except ImportError:
                raise ImportError(
                    "PyArrow is required for .arrow. Install with: pip install 'teshq[data]'"
                )
            if not self._normalized_results:
                self._arrow_table = pa.Table.from_batches([])
            else:
                self._arrow_table = pa.Table.from_pandas(self.dataframe)
        return self._arrow_table

    @property
    def polars(self) -> Any:
        """
        Get results as a Polars DataFrame (blazing-fast multi-threaded analytics).

        Raises:
            ImportError: If polars is not installed.
        """
        if self._polars_df is None:
            try:
                import polars as pl  # type: ignore
            except ImportError:
                raise ImportError(
                    "Polars is required for .polars. Install with: pip install 'teshq[data]'"
                )
            if not self._normalized_results:
                self._polars_df = pl.DataFrame()
            else:
                try:
                    # Prefer zero-copy arrow conversion if pyarrow is present
                    self._polars_df = pl.from_arrow(self.arrow)
                except Exception:
                    self._polars_df = pl.from_dicts(self._normalized_results)
        return self._polars_df
    
    @property
    def display_results(self) -> List[Dict[str, Any]]:
        """Get results formatted for display."""
        return OutputFormatter.format_for_display(self.raw_results)
    
    def print_table(self, title: str = "Results", show_count: bool = True) -> None:
        """Print results in a formatted table."""
        OutputFormatter.print_results_table(self._normalized_results, title, show_count)
    
    def print_query_table(self) -> None:
        """Print query results nicely using modern UI."""
        from teshq.cli.ui import warning, print_results_table, print_header
        
        if self.natural_language_query:
            print_header(f"Query: \"{self.natural_language_query}\"", level=2)
            
        if not self._normalized_results:
            warning("No data found for this query.")
            return
        
        display_results = self.display_results
        headers = list(display_results[0].keys())
        rows = [[row[h] for h in headers] for row in display_results]
        
        print_results_table(
            headers=headers, 
            rows=rows, 
            title="Results",
            summary=f"Found {len(self._normalized_results):,} record(s)"
        )

    def paginate(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """
        Paginate query results for streaming, batched retrieval, and chunked display.

        Args:
            page: 1-indexed page number.
            page_size: Maximum rows per page.

        Returns:
            Dictionary with pagination metadata and current page slice.
        """
        total_rows = len(self._normalized_results)
        page = max(1, page)
        page_size = max(1, page_size)
        total_pages = max(1, math.ceil(total_rows / page_size))

        start = (page - 1) * page_size
        end = start + page_size
        page_rows = self._normalized_results[start:end]

        return {
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "data": page_rows,
        }

    def to_payload(self, max_rows: int = 500) -> Dict[str, Any]:
        """
        Generate a structured payload containing typed column definitions,
        sample rows, and automated visualization recommendation hints.
        """
        if not self._normalized_results:
            return {
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "chart_hints": {"type": "table"},
                "sql": self.query,
                "parameters": self.parameters,
            }

        first_row = self._normalized_results[0]
        columns = []
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []

        for col_name, val in first_row.items():
            col_type = "string"
            if isinstance(val, (int, float)):
                col_type = "numeric"
                numeric_cols.append(col_name)
            elif isinstance(val, bool):
                col_type = "boolean"
                categorical_cols.append(col_name)
            elif val is not None and any(kw in col_name.lower() for kw in ("date", "time", "created_at", "updated_at")):
                col_type = "datetime"
                datetime_cols.append(col_name)
            else:
                categorical_cols.append(col_name)

            columns.append({"name": col_name, "type": col_type})

        # Infer chart recommendation
        if datetime_cols and numeric_cols:
            chart_hint = {
                "type": "line",
                "x_axis": datetime_cols[0],
                "y_axis": numeric_cols[0],
                "title": f"{numeric_cols[0]} over {datetime_cols[0]}",
            }
        elif categorical_cols and numeric_cols:
            chart_hint = {
                "type": "bar",
                "x_axis": categorical_cols[0],
                "y_axis": numeric_cols[0],
                "title": f"{numeric_cols[0]} by {categorical_cols[0]}",
            }
        elif len(numeric_cols) >= 2:
            chart_hint = {
                "type": "scatter",
                "x_axis": numeric_cols[0],
                "y_axis": numeric_cols[1],
                "title": f"{numeric_cols[1]} vs {numeric_cols[0]}",
            }
        else:
            chart_hint = {"type": "table"}

        return {
            "columns": columns,
            "rows": self._normalized_results[:max_rows],
            "total_rows": len(self._normalized_results),
            "chart_hints": chart_hint,
            "sql": self.query,
            "parameters": self.parameters,
        }

    def to_parquet(self, path: Union[str, Path], **kwargs: Any) -> str:
        """Export results to an Apache Parquet file."""
        target = str(path)
        self.dataframe.to_parquet(target, index=False, **kwargs)
        return target

    def to_jsonl(self, path: Union[str, Path]) -> str:
        """Export results to a line-delimited JSON (JSONL) file."""
        target = str(path)
        with open(target, "w", encoding="utf-8") as f:
            for row in self._normalized_results:
                f.write(json.dumps(row, default=str) + "\n")
        return target

    def to_dict(self, include_sql: bool = False) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Convert to dictionary format for API responses.
        
        Args:
            include_sql: Whether to include SQL query information
            
        Returns:
            Results as list of dicts, or complete info dict if include_sql=True
        """
        if include_sql:
            return {
                "sql": self.query,
                "parameters": self.parameters,
                "results": self.results,
                "natural_language_query": self.natural_language_query,
            }
        else:
            return self.results
    
    def __len__(self) -> int:
        """Return number of result rows."""
        return len(self._normalized_results)
    
    def __bool__(self) -> bool:
        """Return True if there are results."""
        return bool(self._normalized_results)