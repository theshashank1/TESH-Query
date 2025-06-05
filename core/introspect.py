import json
import os
from typing import Any, Dict, List, Optional, Tuple, cast  # Added cast

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select
from sqlalchemy.engine import Connection  # Added import for Connection type hint

from utils.keys import get_db_url

# from sqlalchemy.engine.reflection import Inspector


def introspect_db(
    db_url: Optional[str] = None,
    detect_relationships: bool = True,
    include_indexes: bool = True,
    include_sample_data: bool = False,
    sample_size: int = 3,
) -> Dict[str, Any]:
    """
    Perform database schema introspection optimized for LLM query generation.

    Args:
        db_url: Database connection URL.
        detect_relationships: Whether to detect implicit relationships based on naming conventions.
        include_indexes: Whether to include index information.
        include_sample_data: Whether to include sample data from each table.
        sample_size: Number of rows to sample from each table if include_sample_data is True.

    Returns:
        Dict containing the complete schema information.
    """
    if db_url is None:
        db_url = get_db_url()

    if not db_url:
        raise ValueError("Database URL not provided and get_db_url() did not return one.")

    # Connect with minimal logging during introspection
    engine = create_engine(db_url, echo=False)
    metadata = MetaData()

    try:
        # Reflect can fail if DB is not accessible or permissions are wrong
        with engine.connect() as connection:  # Ensure connection is possible before reflecting
            metadata.reflect(bind=connection)
    except Exception as e:
        # It's often better to let specific SQLAlchemy errors propagate
        # or wrap them in a custom exception.
        raise ConnectionError(f"Failed to connect to database or reflect metadata: {e}") from e

    inspector = inspect(engine)

    # Store schema info in structured format
    schema_info: Dict[str, Any] = {
        "tables": {},
        "relationships": {"explicit": [], "implicit": []},
        "data_model_summary": "",
    }

    # Get all tables first so we can detect relationships
    try:
        all_tables = sorted(inspector.get_table_names())
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve table names: {e}") from e

    # Track column names across tables for implicit relationship detection
    primary_keys_registry: Dict[str, List[str]] = {}

    # First pass: collect basic table and column information
    for table_name in all_tables:
        table_info: Dict[str, Any] = {
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
            "indexes": [],
            "sample_data": [],
            "row_count": 0,  # Initialize as 0 instead of "Unknown"
            "description": "",  # Will be generated later
        }

        # Get columns
        try:
            columns = inspector.get_columns(table_name)
        except Exception as e:
            print(f"Warning: Could not get columns for table {table_name}: {e}")
            columns = []

        # Get primary keys
        try:
            pk_constraint = inspector.get_pk_constraint(table_name)
            pk_columns = pk_constraint.get("constrained_columns", [])
            table_info["primary_keys"] = pk_columns
            primary_keys_registry[table_name] = pk_columns
        except Exception as e:
            print(f"Warning: Could not get PK constraint for table {table_name}: {e}")
            pk_columns = []  # Ensure pk_columns is defined
            table_info["primary_keys"] = []
            primary_keys_registry[table_name] = []

        # Store column info
        for col in columns:
            col_info = {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"],
                # Ensure default is stringified if not None, else None
                "default": (str(col.get("default")) if col.get("default") is not None else None),
                "is_primary_key": col["name"] in pk_columns,
                "comment": col.get("comment", ""),
            }
            table_info["columns"].append(col_info)

        # Get foreign keys
        try:
            fks = inspector.get_foreign_keys(table_name)
        except Exception as e:
            print(f"Warning: Could not get foreign keys for table {table_name}: {e}")
            fks = []

        for fk in fks:
            fk_info = {
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"],
                "name": fk.get("name"),
            }
            table_info["foreign_keys"].append(fk_info)

            # Add to explicit relationships
            # Assuming len(constrained_columns) == len(referred_columns) for a given FK
            for i, constrained_col in enumerate(fk["constrained_columns"]):
                # Defensive: Ensure referred_columns has corresponding entry.
                # SQLAlchemy usually guarantees this for valid FKs.
                referred_col = (
                    fk["referred_columns"][i] if i < len(fk["referred_columns"]) else fk["referred_columns"][0]
                )  # type: ignore
                schema_info["relationships"]["explicit"].append(
                    {
                        "from_table": table_name,
                        "from_column": constrained_col,
                        "to_table": fk["referred_table"],
                        "to_column": referred_col,
                        "relationship_type": "many-to-one",  # Default assumption
                    }
                )

        # Get indexes if requested
        if include_indexes:
            try:
                indexes = inspector.get_indexes(table_name)
                for idx in indexes:
                    idx_info = {
                        "name": idx["name"],
                        "columns": idx["column_names"],
                        "unique": idx["unique"],
                    }
                    table_info["indexes"].append(idx_info)
            except Exception as e:
                print(f"Warning: Could not get indexes for table {table_name}: {e}")
                # table_info["indexes"] will remain empty or partially filled

        schema_info["tables"][table_name] = table_info

    # Second pass: detect implicit relationships if requested
    if detect_relationships:
        detect_implicit_relationships(schema_info, all_tables, primary_keys_registry)

    # Third pass: collect statistics and sample data
    with engine.connect() as connection:
        collect_stats_and_samples(
            connection,
            metadata,
            all_tables,
            schema_info,
            include_sample_data,
            sample_size,
        )

    # Generate table descriptions
    generate_table_descriptions(schema_info, include_indexes)

    # Generate overall data model summary
    schema_info["data_model_summary"] = generate_data_model_summary(all_tables, schema_info)

    save_schema_to_files(schema_info, "db_schema", "schema.json", "schema.txt")

    return schema_info


def detect_implicit_relationships(
    schema_info: Dict[str, Any],
    all_tables: List[str],
    primary_keys_registry: Dict[str, List[str]],
) -> None:
    """
    Detect implicit relationships based on naming conventions.

    Args:
        schema_info: The schema information dictionary to update
        all_tables: List of all table names
        primary_keys_registry: Dictionary mapping table names to their primary keys
    """
    for table_name in all_tables:
        table_cols = [col["name"] for col in schema_info["tables"][table_name]["columns"]]

        for col_name in table_cols:
            # Common patterns: ends with _id or Id
            potential_table_root = ""
            if col_name.lower().endswith("_id"):
                potential_table_root = col_name[:-3]
            elif (
                col_name.lower().endswith("id") and len(col_name) > 2 and col_name[-2].islower()
            ):  # Avoids treating 'ID' as 'I'
                potential_table_root = col_name[:-2]
            else:
                continue  # Not a typical FK naming convention

            for other_table in all_tables:
                if not primary_keys_registry.get(other_table):  # Skip if target table has no PK
                    continue

                # Basic singular/plural matching (case-insensitive for robustness)
                # (e.g., user_id -> users table, or users_id -> user table)
                singular_other_table = other_table[:-1] if other_table.lower().endswith("s") else other_table
                plural_potential_root = potential_table_root + "s"

                match = False
                if potential_table_root.lower() == other_table.lower():
                    match = True
                elif potential_table_root.lower() == singular_other_table.lower():
                    match = True
                elif plural_potential_root.lower() == other_table.lower():
                    match = True

                if match:
                    # Avoid duplicating an existing explicit relationship
                    is_explicit = any(
                        rel["from_table"] == table_name and rel["from_column"] == col_name and rel["to_table"] == other_table
                        for rel in schema_info["relationships"]["explicit"]
                    )
                    if is_explicit:
                        break  # Already an explicit FK, don't add as implicit

                    if primary_keys_registry[other_table]:  # Ensure PK list is not empty
                        schema_info["relationships"]["implicit"].append(
                            {
                                "from_table": table_name,
                                "from_column": col_name,
                                "to_table": other_table,
                                "to_column": primary_keys_registry[other_table][0],  # Assume first PK column
                                "relationship_type": "potential-many-to-one",  # Or potential one-to-one
                                "confidence": "medium",
                            }
                        )
                        break  # Found a potential match for this col_name, move to next col_name


def collect_stats_and_samples(
    connection: Connection,
    metadata: MetaData,
    all_tables: List[str],
    schema_info: Dict[str, Any],
    include_sample_data: bool,
    sample_size: int,
) -> None:
    """
    Collect statistics and sample data from each table.

    Args:
        connection: SQLAlchemy connection
        metadata: SQLAlchemy metadata
        all_tables: List of all table names
        schema_info: The schema information dictionary to update
        include_sample_data: Whether to include sample data
        sample_size: Number of rows to sample
    """
    for table_name in all_tables:
        # Ensure table object is available from reflected metadata
        if table_name not in metadata.tables:
            print(f"Warning: Table '{table_name}' not found in metadata for stats/sampling. Skipping.")
            continue
        table_obj = cast(Table, metadata.tables[table_name])  # Cast to Table type
        current_table_info = schema_info["tables"][table_name]

        # Get row count
        # Row count can return an integer or potentially None if the query fails or the table is empty.
        # We handle the None case by defaulting to 0, but the type hint should allow for None initially.
        try:
            # Using .label("row_count") for clarity if result was a Row object
            row_count_query = select(func.count().label("total_rows")).select_from(table_obj)
            result = connection.execute(row_count_query)
            # scalar_one_or_none is safer if query might return no rows (though count(*) shouldn't)
            row_count_val = result.scalar_one_or_none()
            current_table_info["row_count"] = row_count_val if row_count_val is not None else 0
        except Exception as e:
            print(f"Warning: Error getting row count for {table_name}: {e}")
            current_table_info["row_count"] = "Unknown"  # Keep as string if error

        # Get sample data if requested
        # Check if row_count is an int and greater than 0
        if include_sample_data and isinstance(current_table_info["row_count"], int) and current_table_info["row_count"] > 0:
            try:  # Get sample data if requested
                # Check if row_count is an int and greater than 0
                sample_query = select(table_obj).limit(sample_size)
                result = connection.execute(sample_query)

                sample_rows = []
                for row in result:
                    sample_row = {}
                    # row._asdict() provides a dict view of the row
                    for col_key, value in row._asdict().items():
                        col_name_str = str(col_key)  # Ensure key is string
                        if value is not None:
                            try:
                                json.dumps(value)  # Test JSON serializability
                                sample_row[col_name_str] = value
                            except (TypeError, OverflowError):
                                sample_row[col_name_str] = str(value)  # Fallback to string
                        else:
                            sample_row[col_name_str] = None
                    sample_rows.append(sample_row)
                current_table_info["sample_data"] = sample_rows
            except Exception as e:
                print(f"Warning: Error getting sample data for {table_name}: {e}")
                current_table_info["sample_data"] = []  # Default to empty list on error


def generate_table_descriptions(schema_info: Dict[str, Any], include_indexes: bool) -> None:
    """
    Generate descriptive text for each table in the schema.

    Args:
        schema_info: The schema information dictionary to update
        include_indexes: Whether to include index information
    """
    for table_name, table_data in schema_info["tables"].items():
        columns_desc_parts = []
        for col in table_data["columns"]:
            pk_marker = " (PK)" if col["is_primary_key"] else ""
            nullable_info = "" if col["nullable"] else " NOT NULL"
            default_info = f" (default: {col['default']})" if col["default"] is not None else ""
            comment_info = f" /* {col['comment']} */" if col["comment"] else ""
            columns_desc_parts.append(f"{col['name']}: {col['type']}{nullable_info}{pk_marker}{default_info}{comment_info}")

        fk_descs_parts = []
        for fk in table_data["foreign_keys"]:
            fk_descs_parts.append(
                f"{', '.join(fk['constrained_columns'])} → {fk['referred_table']}({', '.join(fk['referred_columns'])})"
            )

        description = f"Table '{table_name}'"
        if table_data["row_count"] != "Unknown":
            description += f" (approx. {table_data['row_count']} rows)"
        description += f"\n  Columns: {'; '.join(columns_desc_parts)}"

        if fk_descs_parts:
            description += f"\n  Foreign Keys (Explicit): {'; '.join(fk_descs_parts)}"

        if include_indexes and table_data["indexes"]:  # Check include_indexes again
            idx_descs_parts = []
            for idx in table_data["indexes"]:
                unique_marker = " (UNIQUE)" if idx["unique"] else ""
                idx_descs_parts.append(f"{idx['name']} on ({', '.join(idx['columns'])}){unique_marker}")
            if idx_descs_parts:  # Only add if there are indexes to describe
                description += f"\n  Indexes: {'; '.join(idx_descs_parts)}"
        schema_info["tables"][table_name]["description"] = description


def generate_data_model_summary(all_tables: List[str], schema_info: Dict[str, Any]) -> str:
    """
    Generate a text summary of the data model.

    Args:
        all_tables: List of all table names
        schema_info: The schema information dictionary

    Returns:
        A string containing the summary
    """
    tables_summary_list = []
    for table_name_key in all_tables:  # Use sorted list for consistent order
        table_detail = schema_info["tables"][table_name_key]
        pk_cols_str = ", ".join(table_detail["primary_keys"]) if table_detail["primary_keys"] else "None"
        row_count_str = table_detail["row_count"]
        tables_summary_list.append(
            f"- {table_name_key} ({len(table_detail['columns'])} cols, PK: {pk_cols_str}, ~{row_count_str} rows)"
        )

    relationships_summary_list = []
    if schema_info["relationships"]["explicit"]:
        relationships_summary_list.append("\n  Explicit Relationships:")
        for rel in schema_info["relationships"]["explicit"]:
            relationships_summary_list.append(
                f"  - {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
            )
    if schema_info["relationships"]["implicit"]:
        relationships_summary_list.append("\n  Implicit Relationships (Detected by Naming Convention):")
        for rel in schema_info["relationships"]["implicit"]:
            relationships_summary_list.append(
                f"  - {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']} (Type: {rel.get('relationship_type', 'N/A')}, Confidence: {rel.get('confidence', 'N/A')})"  # noqa: E501
            )  # noqa: E501

    if not relationships_summary_list:  # If both explicit and implicit are empty
        relationships_summary_list.append("\n  No relationships defined or detected.")

    return "\n".join(
        [
            "DATABASE STRUCTURE SUMMARY",
            f"Total tables: {len(all_tables)}",
            f"Tables: {', '.join(all_tables) if all_tables else 'No tables found.'}",
            "\nTABLE DETAILS:",
            ("\n".join(tables_summary_list) if tables_summary_list else "  No table details available."),
            *relationships_summary_list,  # Unpack the list of relationship strings
        ]
    )


def format_schema_outputs(schema_info: Dict[str, Any], pretty_json: bool = True) -> Dict[str, str]:
    """
    Formats the schema information into JSON and a human-readable text format.

    Args:
        schema_info: The complete schema information dictionary
        pretty_json: Whether to format the JSON with indentation

    Returns:
        Dictionary with json_output and text_output strings
    """
    if pretty_json:
        json_output = json.dumps(schema_info, indent=2, ensure_ascii=False)
    else:
        json_output = json.dumps(schema_info, ensure_ascii=False)

    text_lines = []
    # Add header
    text_lines.append("DATABASE SCHEMA")
    text_lines.append("=" * 50)
    text_lines.append("")

    # Add data model summary if available
    if schema_info.get("data_model_summary"):
        text_lines.append(schema_info["data_model_summary"])
        text_lines.append("\n" + "=" * 50 + "\n")

    # Add detailed table information
    if schema_info.get("tables"):
        text_lines.append("DETAILED TABLE INFORMATION:")
        text_lines.append("")

        for table_name, table_data in sorted(schema_info["tables"].items()):
            text_lines.append(f"Table: {table_name}")
            text_lines.append("-" * (len(table_name) + 7))

            # Row count
            row_count = table_data.get("row_count", "Unknown")
            text_lines.append(f"Row count: {row_count}")
            text_lines.append("")

            # Columns
            text_lines.append("Columns:")
            if table_data.get("columns"):
                for col_info in table_data["columns"]:
                    line = f"- {col_info['name']} ({col_info['type']})"
                    if not col_info.get("nullable", True):
                        line += ", NOT NULL"
                    if col_info.get("is_primary_key"):
                        line += ", Primary Key"
                    if col_info.get("default") is not None:
                        line += f", Default: {col_info['default']}"
                    if col_info.get("comment"):
                        line += f" /* {col_info['comment']} */"
                    text_lines.append(line)
            else:
                text_lines.append("- (No column information available)")

            # Foreign Keys
            if table_data.get("foreign_keys"):
                text_lines.append("\nForeign Keys:")
                for fk in table_data["foreign_keys"]:
                    text_lines.append(
                        f"- {', '.join(fk['constrained_columns'])} → "
                        f"{fk['referred_table']}({', '.join(fk['referred_columns'])})"
                    )

            # Indexes
            if table_data.get("indexes"):
                text_lines.append("\nIndexes:")
                for idx in table_data["indexes"]:
                    unique_str = "UNIQUE " if idx.get("unique") else ""
                    text_lines.append(f"- {idx['name']}: {unique_str}({', '.join(idx['columns'])})")

            text_lines.append("\n" + "-" * 50 + "\n")

    # Add relationships section
    explicit_rels = schema_info.get("relationships", {}).get("explicit", [])
    if explicit_rels:
        text_lines.append("EXPLICIT RELATIONSHIPS:")
        for rel in explicit_rels:
            text_lines.append(f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}")
        text_lines.append("")

    implicit_rels = schema_info.get("relationships", {}).get("implicit", [])
    if implicit_rels:
        text_lines.append("INFERRED RELATIONSHIPS:")
        for rel in implicit_rels:
            text_lines.append(
                f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']} "
                f"(Type: {rel.get('relationship_type', 'N/A')}, Confidence: {rel.get('confidence', 'N/A')})"
            )
        text_lines.append("")

    text_output = "\n".join(text_lines).strip()
    return {"json_output": json_output, "text_output": text_output}


def save_schema_to_files(
    schema_info: Dict[str, Any],
    output_dir: str = ".",
    json_filename: str = "schema.json",
    text_filename: str = "schema.txt",
) -> Tuple[str, str]:
    """
    Saves the schema information to JSON and text files.

    Args:
        schema_info: The schema information dictionary
        output_dir: Directory to save the files in
        json_filename: Name for the JSON file
        text_filename: Name for the text file

    Returns:
        Tuple of (json_file_path, text_file_path)
    """
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get formatted outputs
    outputs = format_schema_outputs(schema_info, pretty_json=True)

    # Full paths for the files
    json_path = os.path.join(output_dir, json_filename)
    text_path = os.path.join(output_dir, text_filename)

    # Write JSON file
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(outputs["json_output"])
    except IOError as e:
        print(f"Error writing JSON file: {e}")
        json_path = None  # type: ignore

    # Write text file
    try:
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(outputs["text_output"])
    except IOError as e:
        print(f"Error writing text file: {e}")
        text_path = None  # type: ignore

    return json_path, text_path  # type: ignore


def main(
    db_url: Optional[str] = None,
    output_dir: str = ".",
    detect_relationships: bool = True,
    include_indexes: bool = True,
    include_sample_data: bool = False,
    sample_size: int = 3,
) -> Dict[str, Any]:
    """
    Main function to introspect a database and save schema information to files.

    Args:
        db_url: Database connection URL
        output_dir: Directory to save output files
        detect_relationships: Whether to detect implicit relationships
        include_indexes: Whether to include index information
        include_sample_data: Whether to include sample data
        sample_size: Number of rows to sample if include_sample_data is True

    Returns:
        The schema information dictionary
    """
    print("Starting database introspection...")

    try:
        # Introspect the database
        schema_info = introspect_db(
            db_url=db_url,
            detect_relationships=detect_relationships,
            include_indexes=include_indexes,
            include_sample_data=include_sample_data,
            sample_size=sample_size,
        )

        # Save to files
        json_path, text_path = save_schema_to_files(schema_info, output_dir=output_dir)

        if json_path and text_path:
            print("Schema information saved to:")
            print(f"  - JSON: {json_path}")
            print(f"  - Text: {text_path}")

        return schema_info

    except Exception as e:
        print(f"Error during database introspection: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database Schema Introspection Tool")
    parser.add_argument("--db-url", help="Database connection URL")
    parser.add_argument("--output-dir", default=".", help="Directory to save output files")
    parser.add_argument(
        "--no-detect-relationships",
        action="store_false",
        dest="detect_relationships",
        help="Disable implicit relationship detection",
    )
    parser.add_argument(
        "--no-indexes",
        action="store_false",
        dest="include_indexes",
        help="Exclude index information",
    )
    parser.add_argument(
        "--include-sample-data",
        action="store_true",
        help="Include sample data from each table",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=3,
        help="Number of rows to sample from each table",
    )

    args = parser.parse_args()

    main(
        db_url=args.db_url,
        output_dir=args.output_dir,
        detect_relationships=args.detect_relationships,
        include_indexes=args.include_indexes,
        include_sample_data=args.include_sample_data,
        sample_size=args.sample_size,
    )
