#!/usr/bin/env python3
"""
Unit tests for max_line_length parameter in search functionality.
Tests both the default behavior (no limit) and the truncation behavior.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from src.code_index_mcp.search.base import parse_search_output
from src.code_index_mcp.search.basic import BasicSearchStrategy


class TestMaxLineLengthParameter:
    """Test class for max_line_length parameter functionality."""

    def test_parse_search_output_no_limit_default(self):
        """Test that parse_search_output has no limit by default (None)."""
        # Create test output with a very long line
        long_line = "x" * 1000  # 1000 character line
        test_output = f"test_file.py:10:{long_line}"
        base_path = "/test/path"
        
        result = parse_search_output(test_output, base_path)
        
        # Should return full line without truncation
        # Check that we have exactly one result
        assert len(result) == 1
        # Get the first (and only) key-value pair
        file_path, matches = next(iter(result.items()))
        assert len(matches) == 1
        line_num, content = matches[0]
        assert line_num == 10
        assert content == long_line
        assert len(content) == 1000

    def test_parse_search_output_no_limit_explicit(self):
        """Test that parse_search_output with explicit None has no limit."""
        # Create test output with a very long line
        long_line = "x" * 500  # 500 character line
        test_output = f"src/module.py:5:{long_line}"
        base_path = "/project"
        
        result = parse_search_output(test_output, base_path, max_line_length=None)
        
        # Should return full line without truncation
        assert len(result) == 1
        file_path, matches = next(iter(result.items()))
        line_num, content = matches[0]
        assert line_num == 5
        assert content == long_line
        assert len(content) == 500

    def test_parse_search_output_with_limit(self):
        """Test that parse_search_output truncates when max_line_length is set."""
        # Create test output with a long line
        long_line = "This is a very long line that should be truncated when max_line_length is applied"
        test_output = f"example.py:1:{long_line}"
        base_path = "/base"
        
        result = parse_search_output(test_output, base_path, max_line_length=30)
        
        # Should return truncated line with suffix
        assert len(result) == 1
        file_path, matches = next(iter(result.items()))
        line_num, content = matches[0]
        assert line_num == 1
        assert content == "This is a very long line that ... (truncated)"
        assert len(content) == 45  # 30 + len("... (truncated)")

    def test_parse_search_output_exactly_at_limit(self):
        """Test that lines exactly at the limit are not truncated."""
        exact_line = "x" * 50  # Exactly 50 characters
        test_output = f"file.py:1:{exact_line}"
        base_path = "/base"
        
        result = parse_search_output(test_output, base_path, max_line_length=50)
        
        # Should return full line without truncation
        assert len(result) == 1
        file_path, matches = next(iter(result.items()))
        line_num, content = matches[0]
        assert line_num == 1
        assert content == exact_line
        assert len(content) == 50
        assert "truncated" not in content

    def test_parse_search_output_under_limit(self):
        """Test that short lines are never truncated."""
        short_line = "Short line"
        test_output = f"file.py:1:{short_line}"
        base_path = "/base"
        
        result = parse_search_output(test_output, base_path, max_line_length=100)
        
        # Should return full line without truncation
        assert len(result) == 1
        file_path, matches = next(iter(result.items()))
        line_num, content = matches[0]
        assert line_num == 1
        assert content == short_line
        assert "truncated" not in content

    def test_basic_search_strategy_max_line_length(self):
        """Test that BasicSearchStrategy respects max_line_length parameter."""
        strategy = BasicSearchStrategy()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file with long line
            test_file = os.path.join(temp_dir, "test.py")
            long_line = "def very_long_function_name_that_should_be_cut_when_max_line_length_is_applied():"
            
            with open(test_file, "w") as f:
                f.write(f"{long_line}\n")
                f.write("    pass\n")
            
            # Search with max_line_length
            results = strategy.search(
                pattern="very_long_function",
                base_path=temp_dir,
                max_line_length=30
            )
            
            # Should find the file and truncate the line
            assert "test.py" in results
            line_num, content = results["test.py"][0]
            assert line_num == 1
            assert content.endswith("... (truncated)")
            # 30 chars + "... (truncated)" (15 chars) = 45 total
            assert len(content) == 45

    def test_basic_search_strategy_no_max_line_length(self):
        """Test that BasicSearchStrategy returns full lines when max_line_length is None."""
        strategy = BasicSearchStrategy()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file with long line
            test_file = os.path.join(temp_dir, "test.py")
            long_line = "def very_long_function_name_that_should_not_be_cut_by_default():"
            
            with open(test_file, "w") as f:
                f.write(f"{long_line}\n")
                f.write("    pass\n")
            
            # Search without max_line_length (default None)
            results = strategy.search(
                pattern="very_long_function",
                base_path=temp_dir,
                max_line_length=None
            )
            
            # Should find the file and return full line
            assert "test.py" in results
            line_num, content = results["test.py"][0]
            assert line_num == 1
            assert content == long_line
            assert "truncated" not in content


def test_integration_search_service_max_line_length():
    """Integration test for SearchService with max_line_length parameter."""
    # This would require mocking the full search service setup
    # For now, we'll test the core functionality through parse_search_output
    pass


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])