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
        Print results in a formatted table.
        
        Args:
            results: Query results
            title: Table title
            show_count: Whether to show row count
            tablefmt: Table format for tabulate
        """
        if not results:
            count_msg = " (0 records)" if show_count else ""
            print(f"\n{title}{count_msg}: No data found.")
            return
        
        # Format for display
        display_results = OutputFormatter.format_for_display(results)
        
        # Print with count if requested
        count_msg = f" ({len(results)} record{'s' if len(results) != 1 else ''})" if show_count else ""
        print(f"\n{title}{count_msg}:")
        print(tabulate(display_results, headers="keys", tablefmt=tablefmt))
        print()


class QueryResult:
    """
    Standardized query result container that provides consistent access
    to query results across all interfaces.
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
    def display_results(self) -> List[Dict[str, Any]]:
        """Get results formatted for display."""
        return OutputFormatter.format_for_display(self.raw_results)
    
    def print_table(self, title: str = "Results", show_count: bool = True) -> None:
        """Print results in a formatted table."""
        OutputFormatter.print_results_table(self._normalized_results, title, show_count)
    
    def print_query_table(self) -> None:
        """Print complete query information including SQL and results."""
        print("\n" + "=" * 80)
        if self.natural_language_query:
            print(f"REQUEST: {self.natural_language_query}")
            print("=" * 80)
        
        print(f"\nQUERY: {self.query}")
        
        if self.parameters:
            print(f"PARAMS: {self.parameters}")
        
        print("\nRESULTS:")
        print("-" * 50)
        
        if not self._normalized_results:
            print("No data found.")
            return
        
        display_results = self.display_results
        print(f"Found {len(self._normalized_results)} record(s):\n")
        print(tabulate(display_results, headers="keys", tablefmt="grid"))
        print()
    
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