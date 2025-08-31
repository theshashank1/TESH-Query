#!/usr/bin/env python3
"""
TESH-Query Programmatic Usage Examples

This file demonstrates how to use TESH-Query programmatically for various tasks.
"""

import os
import json
from pathlib import Path

# Import TESH-Query
import teshq


def example_1_basic_usage():
    """Example 1: Basic usage with explicit configuration."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)
    
    # You would typically get these from environment variables or config files
    db_url = "sqlite:///example.db"  # Replace with your database URL
    gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
    
    try:
        # Initialize the client
        client = teshq.TeshQuery(
            db_url=db_url,
            gemini_api_key=gemini_api_key
        )
        
        print(f"✅ Client initialized successfully")
        print(f"   Database: {db_url}")
        print(f"   Model: {client.gemini_model}")
        
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
    
    db_url = "sqlite:///example.db"
    
    try:
        # For introspection, we don't need the Gemini API key
        client = teshq.TeshQuery(db_url=db_url, gemini_api_key="dummy")
        
        # Introspect the database
        print("🔍 Introspecting database schema...")
        schema_info = client.introspect_database(
            detect_relationships=True,
            include_indexes=True,
            include_sample_data=True,
            sample_size=3,
            save_to_files=True,
            output_dir="./examples_output"
        )
        
        print(f"✅ Schema introspection complete")
        print(f"   Tables found: {len(schema_info.get('tables', {}))}")
        print(f"   Schema saved to: ./examples_output/")
        
        # Print table names
        if 'tables' in schema_info:
            print("\n📋 Tables found:")
            for table_name in schema_info['tables'].keys():
                print(f"   • {table_name}")
                
    except Exception as e:
        print(f"❌ Error: {e}")


def example_3_sql_generation():
    """Example 3: SQL generation from natural language."""
    print("\n" + "=" * 60)
    print("Example 3: SQL Generation")
    print("=" * 60)
    
    db_url = "sqlite:///example.db"
    gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
    
    # Sample schema for demonstration
    sample_schema = """
    Database Schema:
    
    Table: users
      - id: INTEGER NOT NULL (Primary Key)
      - name: VARCHAR(255) NOT NULL
      - email: VARCHAR(255) NOT NULL
      - created_at: DATETIME NOT NULL
      - is_active: BOOLEAN DEFAULT TRUE
    
    Table: orders
      - id: INTEGER NOT NULL (Primary Key)
      - user_id: INTEGER NOT NULL (Foreign Key to users.id)
      - total_amount: DECIMAL(10,2) NOT NULL
      - order_date: DATETIME NOT NULL
      - status: VARCHAR(50) DEFAULT 'pending'
    """
    
    try:
        client = teshq.TeshQuery(
            db_url=db_url,
            gemini_api_key=gemini_api_key
        )
        
        # Generate SQL from natural language
        queries = [
            "show me all active users",
            "count the total number of orders",
            "find users who have placed orders in the last 30 days",
            "calculate the average order amount by user"
        ]
        
        for nl_query in queries:
            print(f"\n🧠 Natural Language: '{nl_query}'")
            try:
                sql_info = client.generate_sql(nl_query, schema=sample_schema)
                print(f"🔧 Generated SQL:")
                print(f"   {sql_info['query']}")
                if sql_info['parameters']:
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
    
    db_url = "sqlite:///example.db"
    gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
    
    try:
        client = teshq.TeshQuery(
            db_url=db_url,
            gemini_api_key=gemini_api_key
        )
        
        # Step 1: Create a simple test database (for demonstration)
        print("📋 Setting up test database...")
        setup_queries = [
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, created_at DATETIME)",
            "INSERT OR IGNORE INTO users (id, name, email, created_at) VALUES (1, 'John Doe', 'john@example.com', '2024-01-15')",
            "INSERT OR IGNORE INTO users (id, name, email, created_at) VALUES (2, 'Jane Smith', 'jane@example.com', '2024-02-20')",
        ]
        
        for query in setup_queries:
            try:
                client.execute_query(query)
            except Exception:
                pass  # Ignore errors for demo purposes
        
        # Step 2: Introspect the database
        print("\n🔍 Introspecting database...")
        schema_info = client.introspect_database()
        
        # Step 3: Execute natural language queries
        print("\n🎯 Executing natural language queries...")
        
        nl_queries = [
            "show me all users",
            "count the total number of users"
        ]
        
        for nl_query in nl_queries:
            print(f"\n📝 Query: '{nl_query}'")
            try:
                # Get complete information including SQL
                result = client.query(nl_query, return_sql=True)
                
                print(f"🔧 Generated SQL: {result['sql']}")
                print(f"📊 Results ({len(result['results'])} rows):")
                
                if result['results']:
                    # Print results as a simple table
                    if len(result['results']) > 0:
                        headers = list(result['results'][0].keys())
                        print(f"   {' | '.join(headers)}")
                        print(f"   {'-' * (len(headers) * 10)}")
                        for row in result['results'][:5]:  # Show first 5 rows
                            values = [str(row.get(h, '')) for h in headers]
                            print(f"   {' | '.join(values)}")
                        
                        if len(result['results']) > 5:
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
    
    db_url = "sqlite:///example.db"
    gemini_api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
    
    try:
        # Quick introspection
        print("🔍 Quick database introspection...")
        schema_info = teshq.introspect(db_url)
        print(f"✅ Found {len(schema_info.get('tables', {}))} tables")
        
        # Quick query execution (if API key is available)
        if gemini_api_key != "your-api-key-here":
            print("\n🎯 Quick query execution...")
            results = teshq.query(
                "show me all users",
                db_url=db_url,
                gemini_api_key=gemini_api_key
            )
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
    print("• Replace 'sqlite:///example.db' with your actual database URL")
    print("• Explore the generated files in ./examples_output/")
    print("• Check out the CLI with: python -m teshq.cli.main --help")


if __name__ == "__main__":
    main()