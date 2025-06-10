from decimal import Decimal

from tabulate import tabulate


def print_query_table(request: str, query: str, params: dict, results: list) -> None:
    """
    Prints query results as neat tables, including the original request, query, and parameters.

    Args:
        request (str): The original request/question
        query (str): The SQL query executed
        params (dict): Query parameters
        results (list): A list of dictionaries containing query results. Each dictionary represents a row.

    """
    print("\n" + "=" * 80)
    print(f"REQUEST: {request}")
    print("=" * 80)

    print(f"\nQUERY: {query}")

    if params:
        print(f"PARAMS: {params}")

    print("\nRESULTS:")
    print("-" * 50)

    if not results:
        print("No data found.")
        return

    # Convert Decimal values to float for clean display
    clean_results = []
    for row in results:
        clean_row = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                # Format decimals nicely - remove unnecessary trailing zeros
                clean_row[key] = f"{float(value):,.2f}".rstrip("0").rstrip(".")
            elif value is None:
                clean_row[key] = "NULL"
            else:
                clean_row[key] = value
        clean_results.append(clean_row)

    # Print the table
    print(f"Found {len(results)} record(s):\n")
    print(tabulate(clean_results, headers="keys", tablefmt="grid"))
    print()


# Even simpler version if you just want the table
def print_simple_table(results: list, title: str = "Results") -> None:
    """
    Prints a simple table of results.

    Args:
        results (list): A list of dictionaries containing the data to be displayed. Each dictionary represents a row.
        title (str): Optional title for the table

    """
    if not results:
        print(f"{title}: No data found.")
        return

    # Clean up Decimal values
    clean_results = []
    for row in results:
        clean_row = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                clean_row[key] = f"{float(value):,.2f}".rstrip("0").rstrip(".")
            else:
                clean_row[key] = value
        clean_results.append(clean_row)

    print(f"\n{title} ({len(results)} records):")
    print(tabulate(clean_results, headers="keys", tablefmt="grid"))
    print()


# Usage examples:
if __name__ == "__main__":
    # Example 1: Full query display
    sample_results = [
        {"job_title": "Human Resources Representative", "min": Decimal("4000.00"), "max": Decimal("9000.00")},
        {"job_title": "Marketing Representative", "min": Decimal("4000.00"), "max": Decimal("9000.00")},
        {"job_title": "President", "min": Decimal("20000.00"), "max": Decimal("40000.00")},
    ]

    print_query_table(
        request="What is the minimum and maximum salary for each job title?",
        query="SELECT job_title, MIN(min_salary), MAX(max_salary) FROM jobs GROUP BY job_title",
        params={},
        results=sample_results,
    )

    # Example 2: Simple table only
    print_simple_table(sample_results, "Salary Ranges")
