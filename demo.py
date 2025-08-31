#!/usr/bin/env python3
"""
Demo: TESH-Query CLI and Programmatic API working together

This script demonstrates how CLI and programmatic access can work together seamlessly.
"""

import tempfile
import sqlite3
import os
import subprocess
import sys
from pathlib import Path

import teshq


def setup_demo_database():
    """Create a demo database with sample data."""
    print("🗄️  Setting up demo database...")
    
    # Create a temporary database file
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = db_file.name
    db_file.close()
    
    # Connect and create schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            registration_date DATE NOT NULL,
            status TEXT DEFAULT 'active'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            stock_quantity INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            order_date DATE NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Insert sample data
    customers_data = [
        (1, 'Alice Johnson', 'alice@example.com', '2024-01-15', 'active'),
        (2, 'Bob Smith', 'bob@example.com', '2024-02-20', 'active'),
        (3, 'Carol Davis', 'carol@example.com', '2024-03-10', 'inactive'),
        (4, 'David Wilson', 'david@example.com', '2024-03-25', 'active'),
    ]
    
    products_data = [
        (1, 'Laptop Pro', 'Electronics', 1299.99, 15),
        (2, 'Wireless Mouse', 'Electronics', 49.99, 100),
        (3, 'Coffee Mug', 'Kitchen', 12.99, 50),
        (4, 'Notebook', 'Office', 8.99, 200),
    ]
    
    orders_data = [
        (1, 1, 1, 1, '2024-01-20', 1299.99),
        (2, 1, 2, 2, '2024-01-21', 99.98),
        (3, 2, 3, 3, '2024-02-25', 38.97),
        (4, 4, 1, 1, '2024-03-30', 1299.99),
        (5, 4, 4, 5, '2024-03-30', 44.95),
    ]
    
    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers_data)
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products_data)
    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders_data)
    
    conn.commit()
    conn.close()
    
    db_url = f"sqlite:///{db_path}"
    print(f"✅ Demo database created: {db_path}")
    print(f"   Database URL: {db_url}")
    
    return db_url, db_path


def demo_programmatic_api(db_url):
    """Demonstrate programmatic API usage."""
    print("\n🐍 Programmatic API Demo")
    print("=" * 40)
    
    # Initialize client
    client = teshq.TeshQuery(db_url=db_url, gemini_api_key="demo-key")
    print("✅ TESH-Query client initialized")
    
    # Test connection
    if client.test_connection():
        print("✅ Database connection successful")
    else:
        print("❌ Database connection failed")
        return False
    
    # Introspect database
    print("\n🔍 Introspecting database schema...")
    schema_info = client.introspect_database()
    
    tables = schema_info.get('tables', {})
    print(f"✅ Found {len(tables)} tables:")
    for table_name, table_info in tables.items():
        column_count = len(table_info.get('columns', {}))
        print(f"   • {table_name} ({column_count} columns)")
    
    # Execute some queries
    print("\n⚡ Executing direct SQL queries...")
    
    queries = [
        ("Customer count", "SELECT COUNT(*) as total_customers FROM customers"),
        ("Active customers", "SELECT COUNT(*) as active_customers FROM customers WHERE status = 'active'"),
        ("Total revenue", "SELECT SUM(total_amount) as total_revenue FROM orders"),
        ("Products by category", "SELECT category, COUNT(*) as product_count FROM products GROUP BY category"),
    ]
    
    for description, sql in queries:
        try:
            results = client.execute_query(sql)
            print(f"   {description}: {results[0] if results else 'No results'}")
        except Exception as e:
            print(f"   {description}: Error - {e}")
    
    return True


def demo_cli_integration(db_url, db_path):
    """Demonstrate CLI integration after programmatic setup."""
    print("\n🖥️  CLI Integration Demo")
    print("=" * 40)
    
    # Set up environment for CLI
    env = os.environ.copy()
    env['DATABASE_URL'] = db_url
    
    # Test CLI introspection
    print("🔍 Running CLI introspection...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "teshq.cli.main", "introspect", 
             "--output-dir", "demo_output"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ CLI introspection successful")
            print("   Schema files saved to demo_output/")
            
            # Check if files were created
            output_dir = Path("demo_output")
            if output_dir.exists():
                files = list(output_dir.glob("*"))
                print(f"   Created files: {[f.name for f in files]}")
        else:
            print(f"❌ CLI introspection failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ CLI test error: {e}")
    
    # Test CLI database connection
    print("\n🔌 Testing CLI database connection...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "teshq.cli.main", "database", "--connect"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ CLI database connection successful")
        else:
            print(f"❌ CLI database connection failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ CLI database test error: {e}")


def demo_unified_workflow():
    """Demonstrate a unified workflow using both CLI and API."""
    print("\n🔄 Unified Workflow Demo")
    print("=" * 40)
    
    print("This demonstrates how you can:")
    print("1. ✅ Set up database programmatically")
    print("2. ✅ Use programmatic API for analysis")
    print("3. ✅ Use CLI for additional operations")
    print("4. ✅ Share configuration between both")
    
    print("\n📋 Workflow Summary:")
    print("   • Database: Set up with sample e-commerce data")
    print("   • API: Used for introspection and direct queries") 
    print("   • CLI: Used for schema export and connection testing")
    print("   • Config: Shared environment variables")
    
    print("\n💡 Benefits:")
    print("   • Single configuration works for both interfaces")
    print("   • Programmatic analysis + CLI convenience")
    print("   • Seamless integration in any workflow")


def main():
    """Run the complete demo."""
    print("🚀 TESH-Query: CLI + Programmatic API Integration Demo")
    print("=" * 60)
    
    try:
        # Setup
        db_url, db_path = setup_demo_database()
        
        # Programmatic demo
        demo_programmatic_api(db_url)
        
        # CLI demo
        demo_cli_integration(db_url, db_path)
        
        # Unified workflow explanation
        demo_unified_workflow()
        
        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("=" * 60)
        
        print("\n📚 What you've seen:")
        print("✅ Programmatic API for integration into applications")
        print("✅ CLI interface for interactive and scripted use")
        print("✅ Shared configuration between both interfaces")
        print("✅ Database introspection and query execution")
        print("✅ Seamless workflow combining both approaches")
        
        print("\n🔗 Try it yourself:")
        print("# Programmatic usage")
        print("import teshq")
        print(f"client = teshq.TeshQuery(db_url='{db_url}', gemini_api_key='your-key')")
        print("results = client.query('show me all customers')")
        print("")
        print("# CLI usage") 
        print(f"export DATABASE_URL='{db_url}'")
        print("teshq introspect")
        print("teshq query 'show me all customers'")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return False
        
    finally:
        # Cleanup
        try:
            if 'db_path' in locals():
                os.unlink(db_path)
                print(f"\n🧹 Cleaned up demo database: {db_path}")
        except:
            pass
        
        # Clean up demo output directory
        try:
            import shutil
            if Path("demo_output").exists():
                shutil.rmtree("demo_output")
                print("🧹 Cleaned up demo output directory")
        except:
            pass


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)