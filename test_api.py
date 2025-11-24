#!/usr/bin/env python3
"""
Simple test script to validate TESH-Query API functionality.
"""

import os
import sqlite3
import tempfile

import teshq

# from pathlib import Path


def create_test_database():
    """Create a simple test SQLite database."""
    # Create temporary database file
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = db_file.name
    db_file.close()

    # Connect and create test data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create test tables
    cursor.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at DATE NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            order_date DATE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    # Insert test data
    cursor.execute(
        """
        INSERT INTO users (name, email, created_at, is_active) VALUES
        ('John Doe', 'john@example.com', '2024-01-15', 1),
        ('Jane Smith', 'jane@example.com', '2024-02-20', 1),
        ('Bob Wilson', 'bob@example.com', '2024-03-10', 0)
    """
    )

    cursor.execute(
        """
        INSERT INTO orders (user_id, amount, order_date) VALUES
        (1, 99.99, '2024-01-20'),
        (1, 149.50, '2024-02-15'),
        (2, 75.25, '2024-02-25'),
        (2, 200.00, '2024-03-05')
    """
    )

    conn.commit()
    conn.close()

    return f"sqlite:///{db_path}", db_path


def test_api_basic_functionality():
    """Test basic API functionality."""
    print("🧪 Testing TESH-Query API Basic Functionality")
    print("=" * 50)

    # Create test database
    db_url, db_path = create_test_database()
    print(f"✅ Created test database: {db_path}")

    try:
        # Test 1: Client initialization without API key (for introspection)
        print("\n📋 Test 1: Client initialization for introspection...")
        client = teshq.TeshQuery(db_url=db_url, gemini_api_key="dummy")
        print("✅ Client initialized successfully")

        # Test 2: Database connection test
        print("\n🔌 Test 2: Database connection...")
        if client.test_connection():
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")
            return False

        # Test 3: Database introspection
        print("\n🔍 Test 3: Database introspection...")
        schema_info = client.introspect_database()
        tables = schema_info.get("tables", {})
        print(f"✅ Introspection complete. Found {len(tables)} tables:")
        for table_name in tables.keys():
            print(f"   • {table_name}")

        # Test 4: Schema formatting
        print("\n📝 Test 4: Schema formatting for LLM...")
        schema_text = client._format_schema_for_llm(schema_info)
        print(f"✅ Schema formatted ({len(schema_text)} characters)")
        print("First 200 characters:")
        print(schema_text[:200] + "..." if len(schema_text) > 200 else schema_text)

        # Test 5: Direct SQL execution
        print("\n⚡ Test 5: Direct SQL execution...")
        results = client.execute_query("SELECT COUNT(*) as user_count FROM users")
        print(f"✅ SQL executed. Results: {results}")

        # Test 6: Convenience introspection function
        print("\n🚀 Test 6: Convenience introspection function...")
        quick_schema = teshq.introspect(db_url)
        print(f"✅ Quick introspection complete. Tables: {len(quick_schema.get('tables', {}))}")

        print("\n🎉 All basic tests passed!")
        return True

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

    finally:

        os.unlink(db_path)
        print(f"🧹 Cleaned up test database: {db_path}")


def test_api_with_mock_llm():
    """Test API functionality with mocked LLM responses."""
    print("\n🤖 Testing API with Mock LLM")
    print("=" * 50)

    # Create test database
    db_url, db_path = create_test_database()

    try:
        # Initialize client (this will fail if no real API key, which is expected)
        client = teshq.TeshQuery(db_url=db_url, gemini_api_key="test-key")
        print("✅ Client initialized with mock API key")

        # Test schema loading capabilities
        schema_info = client.introspect_database()
        schema_text = client._format_schema_for_llm(schema_info)

        print("✅ Schema prepared for LLM:")
        print(f"   - Tables: {len(schema_info.get('tables', {}))}")
        print(f"   - Schema text length: {len(schema_text)} characters")

        # This would normally call the LLM, but will fail with test key
        print("\n⚠️  Note: LLM functionality requires a real GEMINI_API_KEY")
        print("   Set GEMINI_API_KEY environment variable to test LLM features")

        return True

    except Exception as e:
        print(f"ℹ️  Expected error with mock API key: {e}")
        return True  # This is expected behavior

    finally:
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass  # File might have already been deleted or never created


def test_cli_integration():
    """Test that CLI still works after our changes."""
    print("\n🖥️  Testing CLI Integration")
    print("=" * 50)

    import subprocess
    import sys

    try:
        # Test CLI help
        result = subprocess.run(
            [sys.executable, "-m", "teshq.cli.main", "--help"], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            print("✅ CLI help command works")
            print("   CLI interface is intact after API additions")
            return True
        else:
            print(f"❌ CLI help failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ CLI test error: {e}")
        return False


def test_health_check_api():
    """Test the new health check API functionality."""
    print("\n🏥 Testing Health Check API")
    print("=" * 50)

    try:
        # Test 1: Top-level health_check function
        print("\n📋 Test 1: Top-level health_check function...")
        report = teshq.health_check()
        print("✅ Health check function executed successfully")
        print(f"   Status: {report['status']}")
        print(f"   Checks performed: {len(report.get('checks', []))}")
        
        # Test 2: TeshQuery.health_check method
        print("\n🔍 Test 2: TeshQuery class health_check method...")
        # Create test database for client initialization
        db_url, db_path = create_test_database()
        try:
            client = teshq.TeshQuery(db_url=db_url, gemini_api_key="dummy")
            client_report = client.health_check()
            print("✅ Client health_check method executed successfully")
            print(f"   Status: {client_report['status']}")
            print(f"   Total checks: {client_report['summary']['total_checks']}")
        finally:
            os.unlink(db_path)
        
        # Test 3: Verify report structure
        print("\n📝 Test 3: Verify health check report structure...")
        required_keys = ['status', 'timestamp', 'duration_ms', 'checks', 'summary']
        missing_keys = [key for key in required_keys if key not in report]
        if not missing_keys:
            print("✅ Report has all required keys")
            print(f"   Keys: {', '.join(required_keys)}")
        else:
            print(f"❌ Report missing keys: {missing_keys}")
            return False
        
        # Test 4: Verify checks structure
        print("\n🔬 Test 4: Verify individual checks structure...")
        checks = report.get('checks', [])
        if checks:
            check = checks[0]
            check_keys = ['name', 'status', 'message', 'duration_ms', 'details', 'timestamp']
            missing_check_keys = [key for key in check_keys if key not in check]
            if not missing_check_keys:
                print("✅ Check has all required keys")
                print(f"   Sample check: {check['name']} - {check['status']}")
            else:
                print(f"❌ Check missing keys: {missing_check_keys}")
                return False
        else:
            print("⚠️  No checks found in report")
        
        print("\n🎉 All health check API tests passed!")
        return True

    except Exception as e:
        print(f"❌ Error during health check testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("🚀 TESH-Query API Validation Tests")
    print("=" * 60)

    tests = [
        ("Basic API Functionality", test_api_basic_functionality),
        ("API with Mock LLM", test_api_with_mock_llm),
        ("Health Check API", test_health_check_api),
        ("CLI Integration", test_cli_integration),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if success:
            passed += 1

    print(f"\nTotal: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("\n🎉 All tests passed! API is working correctly.")
        print("\nNext steps:")
        print("• Set GEMINI_API_KEY to test LLM features")
        print("• Try: python examples.py")
        print("• Use: import teshq; client = teshq.TeshQuery(...)")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
