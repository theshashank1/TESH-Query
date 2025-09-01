#!/usr/bin/env python3
"""
TESH-Query Programmatic Usage Examples

This file demonstrates how to use TESH-Query programmatically for various tasks.
"""

import json
import os
from pathlib import Path

# Import TESH-Query
import teshq


def example_1_basic_usage():
    """Example 1: Basic usage with explicit configuration."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)

    # You would typically get these from environment variables or config files
    fmcg_db_url = "sqlite:///fmcg_enterprise_massive.sqlite"  # Using the FMCG database
    default_gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")

    try:
        # Initialize the client
        client = teshq.TeshQuery(db_url=fmcg_db_url, gemini_api_key=default_gemini_api_key)

        print("✅ Client initialized successfully")
        print("   Database: {fmcg_db_url}")
        print("   Model: {client.gemini_model}")

        # Test database connection
        if client.test_connection():
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_2_database_introspection():
    """Example 2: Database schema introspection."""
    print("\n" + "=" * 60)
    print("Example 2: Database Introspection")
    print("=" * 60)

    fmcg_db_url = "sqlite:///fmcg_enterprise_massive.sqlite"
    default_gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")

    try:
        # For introspection, we don't need the Gemini API key
        client = teshq.TeshQuery(db_url=fmcg_db_url, gemini_api_key=default_gemini_api_key)

        # Introspect the database
        print("🔍 Introspecting database schema...")
        schema_info = client.introspect_database(
            detect_relationships=True,
            include_indexes=True,
            include_sample_data=True,
            sample_size=3,
            save_to_files=True,
            output_dir="./examples_output",
        )

        print("✅ Schema introspection complete")
        print("   Tables found: {len(schema_info.get('tables', {}))}")
        print("   Schema saved to: ./examples_output/")

        # Print table names
        if "tables" in schema_info:
            print("\n📋 Tables found:")
            for table_name in schema_info["tables"].keys():
                print(f"   • {table_name}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_3_sql_generation():
    """Example 3: SQL generation from natural language."""
    print("\n" + "=" * 60)
    print("Example 3: SQL Generation")
    print("=" * 60)

    fmcg_db_url = "sqlite:///fmcg_enterprise_massive.sqlite"
    default_gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")

    try:
        client = teshq.TeshQuery(db_url=fmcg_db_url, gemini_api_key=default_gemini_api_key)

        # Introspect the database to get the schema for context
        print("🔍 Introspecting database schema for context...")
        schema_info = client.introspect_database(save_to_files=False)
        schema_for_generation = json.dumps(schema_info, indent=2)

        # Generate SQL from natural language
        queries = [
            "show me all brands",
            "count the total number of products",
            "find the top 5 most expensive products",
            "calculate the average price of products by brand",
        ]

        for nl_query in queries:
            print(f"\n🧠 Natural Language: '{nl_query}'")
            try:
                sql_info = client.generate_sql(nl_query, schema=schema_for_generation)
                print("🔧 Generated SQL:")
                print(f"   {sql_info['query']}")
                if sql_info["parameters"]:
                    print(f"📝 Parameters: {sql_info['parameters']}")
            except Exception as e:
                print(f"❌ Error generating SQL: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_4_complete_workflow():
    """Example 4: Complete workflow - introspect, generate SQL, and execute."""
    print("\n" + "=" * 60)
    print("Example 4: Complete Workflow")
    print("=" * 60)

    fmcg_db_url = "sqlite:///fmcg_enterprise_massive.sqlite"
    default_gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")

    try:
        client = teshq.TeshQuery(db_url=fmcg_db_url, gemini_api_key=default_gemini_api_key)

        # Step 1: Introspect the database (optional, but good for context)
        print("🔍 Introspecting database...")
        client.introspect_database(save_to_files=True, output_dir="./examples_output")

        # Step 2: Execute natural language queries
        print("\n🎯 Executing natural language queries...")

        nl_queries = ["show me top 5 brands by number of products", "what is the average product price"]

        for nl_query in nl_queries:
            print(f"\n📝 Query: '{nl_query}'")
            try:
                # Get complete information including SQL
                result = client.query(nl_query, return_sql=True)

                print(f"🔧 Generated SQL: {result['sql']}")
                print(f"📊 Results ({len(result['results'])} rows):")

                if result["results"]:
                    # Print results as a simple table
                    if len(result["results"]) > 0:
                        headers = list(result["results"][0].keys())
                        print(f"   {' | '.join(headers)}")
                        print(f"   {'-' * (len(headers) * 10)}")
                        for row in result["results"][:5]:  # Show first 5 rows
                            values = [str(row.get(h, "")) for h in headers]
                            print(f"   {' | '.join(values)}")

                        if len(result["results"]) > 5:
                            print(f"   ... and {len(result['results']) - 5} more rows")
                else:
                    print("   No results returned")

            except Exception as e:
                print(f"❌ Error: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_5_convenience_functions():
    """Example 5: Using convenience functions for quick operations."""
    print("\n" + "=" * 60)
    print("Example 5: Convenience Functions")
    print("=" * 60)

    fmcg_db_url = "sqlite:///fmcg_enterprise_massive.sqlite"
    default_gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")

    try:
        # Quick introspection
        print("🔍 Quick database introspection...")
        schema_info = teshq.introspect(fmcg_db_url)
        print(f"✅ Found {len(schema_info.get('tables', {}))} tables")

        # Quick query execution (if API key is available)
        if default_gemini_api_key != "your-api-key-here":
            print("\n🎯 Quick query execution...")
            results = teshq.query("show me all promotions", db_url=fmcg_db_url, gemini_api_key=default_gemini_api_key)
            print(f"✅ Query executed, got {len(results)} results")
        else:
            print("\n⚠️  Skipping query execution (no API key provided)")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all examples."""
    print("🚀 TESH-Query Programmatic Usage Examples")
    print("=" * 60)
    print("These examples demonstrate how to use TESH-Query programmatically.")
    print("Make sure you have your GEMINI_API_KEY environment variable set.")
    print()

    # Create output directory for examples
    Path("examples_output").mkdir(exist_ok=True)

    # Run examples
    example_1_basic_usage()
    example_2_database_introspection()
    example_3_sql_generation()
    example_4_complete_workflow()
    example_5_convenience_functions()

    print("\n" + "=" * 60)
    print("🎉 All examples completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("• Set your GEMINI_API_KEY environment variable")
    print("• The examples now use the 'fmcg_enterprise_massive.sqlite' database.")
    print("• Explore the generated files in ./examples_output/")
    print("• Check out the CLI with: python -m teshq.cli.main --help")


if __name__ == "__main__":
    main()
