#!/usr/bin/env python3
"""
Test script to validate TESH-Query API returns a pandas DataFrame,
loading all configuration from environment variables.

This script demonstrates how to initialize and use the TeshQuery client,
relying on a .env file or environment variables for configuration.

Prerequisites:
1. A .env file in the same directory with the following content:
   DATABASE_URL="your_database_connection_string"
   GEMINI_API_KEY="your_gemini_api_key"

   Example for a local SQLite database:
   DATABASE_URL="sqlite:///my_database.db"

2. A database with a 'users' table. You can use the following SQL
   to create the table and insert some data:

   CREATE TABLE users (
       id INTEGER PRIMARY KEY,
       name TEXT NOT NULL,
       email TEXT UNIQUE NOT NULL,
       created_at DATE NOT NULL,
       is_active BOOLEAN DEFAULT 1
   );

   INSERT INTO users (name, email, created_at, is_active) VALUES
   ('John Doe', 'john@example.com', '2024-01-15', 1),
   ('Jane Smith', 'jane@example.com', '2024-02-20', 1),
   ('Bob Wilson', 'bob@example.com', '2024-03-10', 0);
"""

import os

import pandas as pd

import teshq


def test_api_with_env_config():
    """
    Test that the TeshQuery API can be initialized from environment variables
    and used to return a pandas DataFrame.
    """
    print("🧪 Testing TESH-Query API with configuration from environment variables")
    print("=" * 60)

    # Check for required environment variables
    if not os.getenv("DATABASE_URL") or not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: DATABASE_URL and GEMINI_API_KEY must be set as environment variables.")
        print("   Please create a .env file or export them to your shell.")
        return

    try:
        # Initialize the client without arguments.
        # It will automatically load config from environment variables.
        client = teshq.TeshQuery()
        print("✅ Client initialized successfully from environment variables.")

        # Test the database connection
        if not client.test_connection():
            print("❌ Database connection failed. Please check your DATABASE_URL.")
            return
        print("✅ Database connection successful.")

        client.introspect_database()
        print("✅ Database introspection complete")

        natural_language_query = "show me all active users"
        results = client.query(natural_language_query)
        print(f"✅ Executed query: '{natural_language_query}'")

        df = pd.DataFrame(results)
        print("✅ Converted results to pandas DataFrame")

        assert isinstance(df, pd.DataFrame)
        print("✅ Assertion passed: result is a pandas DataFrame")

        print("\n🎉 Test passed!")
        print("   The TESH-Query API can be configured from a .env file and returns a list of dictionaries,")
        print("   which can be easily converted to a pandas DataFrame.")

        if not df.empty:
            print("\nDataFrame head:")
            print(df.head())
        else:
            print("\n⚠️  The query returned an empty result. This might be expected, or your database might be empty.")

    except Exception as e:
        print(f"❌ Error during testing: {e}")


if __name__ == "__main__":
    test_api_with_env_config()
