import os
import sqlite3

import pandas as pd


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
        df.to_csv(filename, index=index, **kwargs)
        print(f"Data successfully saved to {filename}")
    except Exception as e:
        print(f"Error saving to CSV: {e}")


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
        df.to_excel(filename, sheet_name=sheet_name, index=index, **kwargs)
        print(f"Data successfully saved to {filename}")
    except Exception as e:
        print(f"Error saving to Excel: {e}")


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
        # Ensure the directory for the database file exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=index, **kwargs)
        print(f"Data successfully saved to SQLite database '{db_path}' in table '{table_name}'")
    except Exception as e:
        print(f"Error saving to SQLite: {e}")
