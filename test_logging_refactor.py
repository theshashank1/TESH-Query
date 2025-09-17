#!/usr/bin/env python3
"""
Test script to validate logging refactor implementation.

This script tests the new logging behavior:
1. Default: logs to file only, no CLI output
2. With --log flag: logs to CLI and file
"""

import os
import subprocess
import tempfile
from pathlib import Path


def run_command(command, capture_output=True):
    """Run a command and return the result."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=capture_output,
        text=True,
        cwd="/home/runner/work/TESH-Query/TESH-Query"
    )
    return result


def test_file_only_logging():
    """Test that default behavior logs to file only."""
    print("🧪 Testing file-only logging (default behavior)...")
    
    # Clear existing logs
    log_file = Path("/home/runner/work/TESH-Query/TESH-Query/logs/teshq.log")
    if log_file.exists():
        log_file.unlink()
    
    # Run command without --log flag
    result = run_command("python -m teshq.cli.main name")
    
    # Check CLI output doesn't contain log messages
    assert "INFO" not in result.stdout, "CLI output should not contain log messages without --log flag"
    assert "App Name: TESH Query" in result.stdout, "CLI should still show normal output"
    
    # Check log file was created and contains logs
    assert log_file.exists(), "Log file should be created"
    log_content = log_file.read_text()
    assert "Executing 'name' command" in log_content, "Log file should contain log messages"
    assert "INFO" in log_content, "Log file should contain INFO level logs"
    
    print("✅ File-only logging test passed!")


def test_cli_and_file_logging():
    """Test that --log flag enables CLI output while keeping file logging."""
    print("🧪 Testing CLI + file logging (with --log flag)...")
    
    # Clear existing logs
    log_file = Path("/home/runner/work/TESH-Query/TESH-Query/logs/teshq.log")
    if log_file.exists():
        log_file.unlink()
    
    # Run command with --log flag
    result = run_command("python -m teshq.cli.main name --log")
    
    # Check CLI output contains log messages
    assert "INFO" in result.stdout, "CLI output should contain log messages with --log flag"
    assert "Executing 'name' command" in result.stdout, "CLI should show log messages"
    assert "App Name: TESH Query" in result.stdout, "CLI should still show normal output"
    
    # Check log file was created and contains logs
    assert log_file.exists(), "Log file should be created"
    log_content = log_file.read_text()
    assert "Executing 'name' command" in log_content, "Log file should contain log messages"
    assert "INFO" in log_content, "Log file should contain INFO level logs"
    
    print("✅ CLI + file logging test passed!")


def test_subcommand_logging():
    """Test that subcommands also support --log flag."""
    print("🧪 Testing subcommand logging behavior...")
    
    # Test config command without --log flag
    result1 = run_command("python -m teshq.cli.main config --no-save", capture_output=True)
    assert "INFO" not in result1.stdout, "Subcommand CLI output should not contain logs without --log"
    
    # Test config command with --log flag
    result2 = run_command("python -m teshq.cli.main config --no-save --log", capture_output=True)
    assert "INFO" in result2.stdout, "Subcommand CLI output should contain logs with --log"
    
    print("✅ Subcommand logging test passed!")


def test_log_file_persistence():
    """Test that log entries accumulate in the file."""
    print("🧪 Testing log file persistence...")
    
    # Clear existing logs
    log_file = Path("/home/runner/work/TESH-Query/TESH-Query/logs/teshq.log")
    if log_file.exists():
        log_file.unlink()
    
    # Run multiple commands
    run_command("python -m teshq.cli.main name")
    run_command("python -m teshq.cli.main name --log")
    
    # Check log file contains entries from both runs
    log_content = log_file.read_text()
    log_lines = [line for line in log_content.split('\n') if 'Executing' in line]
    assert len(log_lines) >= 2, "Log file should contain entries from multiple command runs"
    
    print("✅ Log file persistence test passed!")


def main():
    """Run all tests."""
    print("🚀 Starting logging refactor validation tests...")
    print()
    
    try:
        test_file_only_logging()
        print()
        
        test_cli_and_file_logging() 
        print()
        
        test_subcommand_logging()
        print()
        
        test_log_file_persistence()
        print()
        
        print("🎉 All logging tests passed!")
        print()
        print("✅ Logging refactor implementation is working correctly:")
        print("   • Default behavior: logs to file only")
        print("   • With --log flag: logs to CLI and file")
        print("   • Consistent across all commands")
        print("   • Log file persistence works")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())