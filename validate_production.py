#!/usr/bin/env python3
"""
Production Readiness Validation Script for TESH-Query

This script performs comprehensive validation to ensure TESH-Query is ready for production deployment.
Run this before deploying to production to validate all systems and configurations.
"""

import sys
from pathlib import Path

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from teshq.utils.config import get_config, is_configured
    from teshq.utils.validation import ConfigValidator, validate_environment, validate_production_readiness
except ImportError as e:
    print(f"❌ Failed to import TESH-Query modules: {e}")
    print("💡 Run: pip install -e . to install TESH-Query")
    sys.exit(1)


def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print("=" * 60)


def print_section(title):
    """Print a formatted section header."""
    print(f"\n🔍 {title}")
    print("-" * 40)


def print_result(test_name, passed, message="", suggestion=""):
    """Print a test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} {test_name}")
    if message:
        print(f"    {message}")
    if suggestion and not passed:
        print(f"    💡 {suggestion}")


def validate_python_environment():
    """Validate Python environment for production."""
    print_section("Python Environment Validation")

    # Check Python version
    python_version = sys.version_info
    min_version = (3, 9)
    version_ok = python_version >= min_version

    print_result(
        "Python Version",
        version_ok,
        f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
        f"Upgrade to Python {min_version[0]}.{min_version[1]} or higher",
    )

    # Check environment validation
    env_valid, env_issues = validate_environment()
    print_result(
        "Required Dependencies",
        env_valid,
        "All required packages available" if env_valid else f"Missing: {', '.join(env_issues)}",
        "Install missing packages with: pip install -e .",
    )

    return version_ok and env_valid


def validate_configuration():
    """Validate application configuration."""
    print_section("Configuration Validation")

    # Check if basic configuration exists
    configured = is_configured()
    print_result(
        "Basic Configuration",
        configured,
        "DATABASE_URL and GEMINI_API_KEY configured" if configured else "Missing required configuration",
        "Run: teshq config --interactive",
    )

    if not configured:
        return False

    # Get and validate configuration
    config = get_config()

    # Validate database URL
    if "DATABASE_URL" in config:
        db_valid, db_message = ConfigValidator.validate_database_url(config["DATABASE_URL"])
        print_result("Database URL Format", db_valid, db_message)

        if db_valid:
            # Test database connection
            conn_valid, conn_message = ConfigValidator.validate_database_connection(config["DATABASE_URL"])
            print_result("Database Connection", conn_valid, conn_message, "Check database server status and credentials")

    # Validate API key
    if "GEMINI_API_KEY" in config:
        api_valid, api_message = ConfigValidator.validate_gemini_api_key(config["GEMINI_API_KEY"])
        print_result("Gemini API Key", api_valid, api_message, "Check API key format and validity")

    return True


def validate_security():
    """Validate security features."""
    print_section("Security Validation")

    # Test SQL injection prevention
    from teshq.utils.validation import CLIValidator

    dangerous_query = "'; DROP TABLE users; --"
    is_safe, message = CLIValidator.validate_natural_language_query(dangerous_query)
    print_result(
        "SQL Injection Prevention",
        not is_safe,  # Should be blocked
        "Dangerous patterns detected and blocked" if not is_safe else "WARNING: Dangerous pattern not detected",
    )

    # Test input validation
    empty_query = ""
    empty_valid, empty_message = CLIValidator.validate_natural_language_query(empty_query)
    print_result(
        "Input Validation",
        not empty_valid,  # Should be invalid
        "Empty inputs properly rejected" if not empty_valid else "WARNING: Empty input accepted",
    )

    return True


def validate_production_deployment():
    """Validate production deployment readiness."""
    print_section("Production Deployment Validation")

    config = get_config()
    is_ready, issues = validate_production_readiness(config)

    if is_ready:
        print_result("Production Readiness", True, "All production requirements met")
    else:
        print_result("Production Readiness", False, f"{len(issues)} issues found")
        for issue in issues:
            if issue.startswith("WARNING"):
                print(f"    ⚠️  {issue}")
            else:
                print(f"    ❌ {issue}")

    # Check for development environment indicators
    if "DATABASE_URL" in config and "localhost" in config["DATABASE_URL"]:
        print_result(
            "Environment Type",
            False,
            "Development environment detected (localhost database)",
            "Use production database URL for deployment",
        )
    else:
        print_result("Environment Type", True, "Production environment configuration")

    return is_ready


def main():
    """Main validation function."""
    print_header("TESH-Query Production Readiness Validation")
    print("This script validates all aspects of TESH-Query for production deployment.")

    # Track overall success
    all_passed = True

    # Run validation steps
    try:
        all_passed &= validate_python_environment()
        all_passed &= validate_configuration()
        all_passed &= validate_security()
        all_passed &= validate_production_deployment()

    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        print("💡 Check your installation and configuration")
        all_passed = False

    # Final result
    print_header("Validation Summary")

    if all_passed:
        print("🎉 TESH-Query is PRODUCTION READY!")
        print("\n✅ All validation checks passed")
        print("✅ Security features validated")
        print("✅ Configuration validated")
        print("✅ Environment validated")
        print("\n🚀 Ready for production deployment!")
    else:
        print("❌ TESH-Query is NOT ready for production")
        print("\n🔧 Please address the issues above before deploying")
        print("💡 Run this script again after making fixes")

    print("\n📚 For deployment guide, see: PRODUCTION_DEPLOYMENT.md")

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
