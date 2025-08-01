#!/usr/bin/env python3
"""
Test runner for all enhanced file summary functionality tests.

This script runs all test suites for the enhanced file summary feature
to ensure comprehensive coverage of all requirements and edge cases.
"""

import sys
import os
import subprocess

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def run_test_file(test_file):
    """Run a test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            print(result.stdout)
            print(f"PASSED: {test_file}")
            return True
        else:
            print(f"FAILED: {test_file}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"ERROR: {test_file} - {e}")
        return False

def main():
    """Run all enhanced functionality tests."""
    print("Enhanced File Summary Functionality - Comprehensive Test Suite")
    print("=" * 70)
    
    # List of all test files
    test_files = [
        "test_response_formatter.py",
        "test_file_service_enhanced.py", 
        "test_index_prioritization.py",
        "test_enhanced_functionality_comprehensive.py",
        "test_edge_cases_and_errors.py",
        "test_end_to_end_integration.py",
        "test_backward_compatibility.py",
        "test_new_relationship_fields.py"
    ]
    
    # Track results
    passed = 0
    failed = 0
    
    # Run each test file
    for test_file in test_files:
        if run_test_file(test_file):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print('='*70)
    print(f"Total test files: {len(test_files)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\nALL TESTS PASSED! Enhanced file summary functionality is working correctly.")
        return 0
    else:
        print(f"\n{failed} test file(s) failed. Please check the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())