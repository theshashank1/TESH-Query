import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from teshq.utils.logging import logger


# ── Stop words stripped from NL queries when generating file slugs ─────────
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could",
    "i", "me", "my", "we", "our", "you", "your",
    "show", "give", "get", "find", "list", "display", "tell", "print",
    "fetch", "retrieve", "return", "select", "query",
    "all", "each", "every", "any", "some", "many", "much", "few",
    "from", "in", "on", "at", "to", "for", "of", "with", "by",
    "and", "or", "but", "not", "no", "if", "then", "than", "that",
    "this", "these", "those", "it", "its", "what", "which", "who",
    "how", "where", "when", "why", "please", "just", "also",
})


def get_default_output_dir() -> Path:
    """
    Return the default output directory for query exports.

    Uses ``.teshq/outputs/`` relative to the current working directory.
    Creates the directory (and parent ``.teshq/``) if they don't exist.

    Returns:
        Path: The output directory (guaranteed to exist).
    """
    output_dir = Path.cwd() / ".teshq" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def generate_query_slug(query_text: Optional[str], max_words: int = 4) -> str:
    """
    Convert a natural-language query into a short, filesystem-safe slug.

    Examples::

        "Show all customer table names"  → "customer_table_names"
        "top 10 orders by revenue"       → "top_10_orders_revenue"
        ""                               → "query_results"

    Args:
        query_text: The natural-language query string.
        max_words:  Maximum number of meaningful words to keep.

    Returns:
        A lowercase, underscore-separated slug (3–5 words typically).
    """
    if not query_text or not query_text.strip():
        return "query_results"

    # Lowercase and strip non-alphanumeric (keep spaces and digits)
    text = re.sub(r"[^a-z0-9\s]", "", query_text.lower())
    words = text.split()

    # Remove stop words but keep numbers (e.g. "top 10")
    meaningful = [w for w in words if w not in _STOP_WORDS or w.isdigit()]

    if not meaningful:
        # All words were stop words — fall back to first few raw words
        meaningful = words[:max_words] if words else ["query_results"]

    slug = "_".join(meaningful[:max_words])
    # Clamp slug length to avoid excessively long filenames
    return slug[:60] if slug else "query_results"


def resolve_output_path(
    query_text: Optional[str] = None,
    ext: str = "csv",
    custom_path: Optional[str] = None,
) -> Tuple[Path, str]:
    """
    Resolve the final output file path for an export operation.

    Priority logic:

    1. **custom_path with directories** (e.g. ``reports/q1.csv``)
       → honoured as-is (parent dirs created automatically).
    2. **custom_path bare filename** (e.g. ``my_report.csv``)
       → placed inside ``.teshq/outputs/my_report.csv``.
    3. **No custom_path**
       → auto-generates ``<slug>_<YYYYMMDD_HHMMSS>.<ext>``
       inside ``.teshq/outputs/``.

    Args:
        query_text:  The natural-language query (used for slug generation).
        ext:         File extension without dot (``csv``, ``xlsx``, ``db``).
        custom_path: User-supplied filename or path (from ``/export csv name``
                     or ``--save-csv name``).

    Returns:
        Tuple of (resolved_absolute_path, clean_relative_display_path).
    """
    ext = ext.lstrip(".")

    if custom_path:
        p = Path(custom_path)

        # If user gave a path with directory separators, honour it fully
        if str(p.parent) not in (".", ""):
            p.parent.mkdir(parents=True, exist_ok=True)
            return p.resolve(), str(p)

        # Bare filename → route into .teshq/outputs/
        output_dir = get_default_output_dir()
        resolved = output_dir / p
        return resolved.resolve(), str(resolved.relative_to(Path.cwd()))

    # No custom path → auto-generate slug + timestamp
    slug = generate_query_slug(query_text)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_{timestamp}.{ext}"

    output_dir = get_default_output_dir()
    resolved = output_dir / filename
    return resolved.resolve(), str(resolved.relative_to(Path.cwd()))


def save_to_csv(df: pd.DataFrame, filename: str, index: bool = False, **kwargs):
    """
    Saves a Pandas DataFrame to a CSV file.

    Args:
        df: The DataFrame to save.
        filename: The name of the CSV file (e.g., "output.csv").
        index: Whether to write the DataFrame index as a column. Defaults to False.
        **kwargs: Additional arguments to pass to df.to_csv().
    """
    try:
        logger.info("Saving data to CSV", file_path=filename, row_count=len(df))
        # Ensure directory exists if filename has a directory path
        parent_dir = os.path.dirname(filename)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        df.to_csv(filename, index=index, **kwargs)

        logger.success(
            "Data successfully saved to CSV",
            file_path=filename,
            row_count=len(df),
            file_size_bytes=os.path.getsize(filename),
        )
    except Exception as e:
        logger.error("Error saving to CSV", error=e, file_path=filename, row_count=len(df))
        raise


def save_to_excel(df: pd.DataFrame, filename: str, sheet_name: str = "Sheet1", index: bool = False, **kwargs):
    """
    Saves a Pandas DataFrame to an Excel file.

    Args:
        df: The DataFrame to save.
        filename: The name of the Excel file (e.g., "output.xlsx").
        sheet_name: The name of the sheet within the Excel file. Defaults to "Sheet1".
        index: Whether to write the DataFrame index as a column. Defaults to False.
        **kwargs: Additional arguments to pass to df.to_excel().
    """
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise ImportError(
            "Excel export requires 'openpyxl'. Install it with: pip install openpyxl"
        ) from None

    try:
        logger.info("Saving data to Excel", file_path=filename, sheet_name=sheet_name, row_count=len(df))
        # Ensure directory exists if filename has a directory path
        parent_dir = os.path.dirname(filename)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        df.to_excel(filename, sheet_name=sheet_name, index=index, **kwargs)

        logger.success(
            "Data successfully saved to Excel",
            file_path=filename,
            sheet_name=sheet_name,
            row_count=len(df),
            file_size_bytes=os.path.getsize(filename),
        )
    except Exception as e:
        logger.error("Error saving to Excel", error=e, file_path=filename, sheet_name=sheet_name, row_count=len(df))
        raise


def save_to_sqlite(
    df: pd.DataFrame, db_path: str, table_name: str, if_exists: str = "replace", index: bool = False, **kwargs
):
    """
    Saves a Pandas DataFrame to a SQLite database.

    Args:
        df: The DataFrame to save.
        db_path: The path to the SQLite database file (e.g., "my_database.sqlite").
        table_name: The name of the table to save the DataFrame to.
        if_exists: How to behave if the table already exists.
                   'fail': Raise a ValueError.
                   'replace': Drop the table before inserting new values.
                   'append': Insert new values to the existing table.
                   Defaults to "replace".
        index: Whether to write the DataFrame index as a column. Defaults to False.
        **kwargs: Additional arguments to pass to df.to_sql().
    """
    try:
        logger.info("Saving data to SQLite", db_file_path=db_path, table_name=table_name, row_count=len(df))
        # Ensure the directory for the database file exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            # Validate table_name against a safe SQL identifier pattern
            import re as _re
            if not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
                raise ValueError(
                    f"Unsafe table name '{table_name}'. "
                    "Use only letters, digits, and underscores, starting with a letter or underscore."
                )
            df.to_sql(table_name, conn, if_exists=if_exists, index=index, **kwargs)

        logger.success(
            "Data successfully saved to SQLite database",
            db_file_path=db_path,
            table_name=table_name,
            row_count=len(df),
            if_exists=if_exists,
            file_size_bytes=os.path.getsize(db_path),
        )
    except Exception as e:
        logger.error("Error saving to SQLite", error=e, db_file_path=db_path, table_name=table_name, row_count=len(df))
        raise
