import os
import sqlite3

import pandas as pd

from teshq.utils.logging import logger


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
