#!/usr/bin/env python3
"""
Import validation script for TESH-Query
Tests that all core modules can be imported without external dependencies.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that core modules can be imported"""
    
    print("🔍 Testing core module imports...")
    
    try:
        # Test utils config module (should work without external deps)
        print("  ├── Testing teshq.utils.config...")
        import teshq.utils.config
        print("  │   ✅ Import successful")
        
        # Test basic config functions
        config_keys = teshq.utils.config.CONFIG_KEYS
        print(f"  │   ✅ CONFIG_KEYS available: {config_keys}")
        
    except ImportError as e:
        print(f"  │   ❌ Import failed: {e}")
        return False
    
    try:
        # Test that the package structure is correct
        print("  ├── Testing package structure...")
        import teshq
        import teshq.cli
        import teshq.core
        import teshq.utils
        print("  │   ✅ Package structure valid")
        
    except ImportError as e:
        print(f"  │   ❌ Package structure issue: {e}")
        return False
    
    # Test that external dependency imports are handled gracefully
    print("  ├── Testing external dependency handling...")
    
    try:
        # This should fail gracefully due to missing typer
        import teshq.cli.main
        print("  │   ⚠️  CLI main imported (dependencies may be available)")
    except ImportError as e:
        print(f"  │   ✅ CLI main import failed as expected: {e}")
    
    try:
        # This should fail gracefully due to missing langchain
        import teshq.core.llm
        print("  │   ⚠️  LLM module imported (dependencies may be available)")
    except ImportError as e:
        print(f"  │   ✅ LLM module import failed as expected: {e}")
    
    print("  └── Core imports validation complete")
    return True

def test_file_structure():
    """Test that expected files exist"""
    
    print("\n📁 Testing file structure...")
    
    required_files = [
        "pyproject.toml",
        "README.md",
        "teshq/__init__.py",
        "teshq/cli/__init__.py",
        "teshq/core/__init__.py",
        "teshq/utils/__init__.py",
        "teshq/utils/config.py",
        "tests/",
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - Missing")
            all_exist = False
    
    return all_exist

def test_basic_functionality():
    """Test basic functionality without external dependencies"""
    
    print("\n⚙️  Testing basic functionality...")
    
    try:
        # Test config module functions
        import teshq.utils.config as config
        
        # Test get_config without files (should return empty dict)
        result = config.get_config()
        print(f"  ✅ get_config() returns: {type(result)}")
        
        # Test constants
        print(f"  ✅ DEFAULT_GEMINI_MODEL: {config.DEFAULT_GEMINI_MODEL}")
        print(f"  ✅ CONFIG_KEYS: {len(config.CONFIG_KEYS)} keys")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Basic functionality test failed: {e}")
        return False

def main():
    """Run all validation tests"""
    
    print("🚀 TESH-Query Import Validation")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(test_file_structure())
    results.append(test_imports())
    results.append(test_basic_functionality())
    
    # Summary
    print("\n📊 Validation Summary")
    print("=" * 50)
    
    if all(results):
        print("✅ All validation tests passed!")
        print("✅ Core modules are properly structured")
        print("⚠️  External dependencies are required for full functionality")
        return 0
    else:
        print("❌ Some validation tests failed!")
        print("❌ Core issues need to be resolved")
        return 1

if __name__ == "__main__":
    sys.exit(main())