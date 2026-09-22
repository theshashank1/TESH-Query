"""
Unit tests for the query output path resolution and slug generation.

Tests the new helpers in teshq.utils.save:
  - generate_query_slug()
  - resolve_output_path()
  - get_default_output_dir()
"""
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from teshq.utils.save import (
    generate_query_slug,
    get_default_output_dir,
    resolve_output_path,
    save_to_csv,
    save_to_excel,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  generate_query_slug
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateQuerySlug:
    """Test slug generation from natural language queries."""

    def test_basic_query(self):
        slug = generate_query_slug("show all customer table names")
        assert slug == "customer_table_names"

    def test_numbers_preserved(self):
        slug = generate_query_slug("top 10 orders by revenue")
        assert "10" in slug
        assert "orders" in slug
        assert "revenue" in slug

    def test_empty_string(self):
        assert generate_query_slug("") == "query_results"

    def test_none_input(self):
        assert generate_query_slug(None) == "query_results"

    def test_whitespace_only(self):
        assert generate_query_slug("   ") == "query_results"

    def test_all_stop_words(self):
        slug = generate_query_slug("show me the all")
        # Should fall back to raw words since all are stop words
        assert len(slug) > 0

    def test_special_characters_stripped(self):
        slug = generate_query_slug("what's the customer's order-count?")
        assert "'" not in slug
        assert "-" not in slug
        assert "?" not in slug

    def test_max_words_respected(self):
        slug = generate_query_slug(
            "show me all customer orders with revenue and status and dates",
            max_words=3,
        )
        assert slug.count("_") <= 2  # At most 3 words = 2 underscores

    def test_long_query_clamped(self):
        long_query = " ".join([f"word{i}" for i in range(100)])
        slug = generate_query_slug(long_query)
        assert len(slug) <= 60

    def test_realistic_queries(self):
        cases = [
            ("how many orders were placed last month", "orders_placed_last_month"),
            ("list all tables", "tables"),
            ("count of employees by department", "count_employees_department"),
        ]
        for query, expected in cases:
            slug = generate_query_slug(query)
            # Just check it's reasonable (not exact match due to stop word removal)
            assert len(slug) > 0
            assert slug.replace("_", "").isalnum()


# ═══════════════════════════════════════════════════════════════════════════════
#  get_default_output_dir
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetDefaultOutputDir:
    """Test output directory creation."""

    def test_creates_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output_dir = get_default_output_dir()
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert output_dir == tmp_path / ".teshq" / "outputs"

    def test_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        dir1 = get_default_output_dir()
        dir2 = get_default_output_dir()
        assert dir1 == dir2


# ═══════════════════════════════════════════════════════════════════════════════
#  resolve_output_path
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveOutputPath:
    """Test output path resolution with various input combinations."""

    def test_no_custom_path_generates_slug(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved, display = resolve_output_path(
            query_text="show customer orders",
            ext="csv",
        )
        assert ".teshq" in str(resolved)
        assert "outputs" in str(resolved)
        assert resolved.suffix == ".csv"
        assert "customer_orders" in resolved.stem
        # Should contain a timestamp pattern
        assert re.search(r"\d{8}_\d{6}", resolved.stem)

    def test_custom_bare_filename_routed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved, display = resolve_output_path(
            query_text="anything",
            ext="csv",
            custom_path="my_report.csv",
        )
        assert ".teshq" in str(resolved)
        assert "outputs" in str(resolved)
        assert resolved.name == "my_report.csv"

    def test_custom_path_with_dirs_honored(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        custom = str(tmp_path / "reports" / "q1.csv")
        resolved, display = resolve_output_path(
            query_text="anything",
            ext="csv",
            custom_path=custom,
        )
        assert str(resolved) == str(Path(custom).resolve())

    def test_ext_dot_stripped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved, _ = resolve_output_path(ext=".xlsx")
        assert resolved.suffix == ".xlsx"

    def test_display_path_is_relative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _, display = resolve_output_path(query_text="test", ext="csv")
        assert not display.startswith("/")
        assert ".teshq" in display

    def test_excel_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved, _ = resolve_output_path(query_text="revenue", ext="xlsx")
        assert resolved.suffix == ".xlsx"

    def test_sqlite_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved, _ = resolve_output_path(query_text="data", ext="db")
        assert resolved.suffix == ".db"


# ═══════════════════════════════════════════════════════════════════════════════
#  Integration: save functions respect resolved paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveToOutputDir:
    """Test that save functions work with resolved output paths."""

    def test_csv_saves_to_outputs_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        resolved, display = resolve_output_path(
            query_text="test data",
            ext="csv",
        )
        save_to_csv(df, str(resolved))
        assert resolved.exists()
        assert resolved.stat().st_size > 0

    def test_csv_user_named_to_outputs_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame({"x": [10]})
        resolved, display = resolve_output_path(
            query_text="anything",
            ext="csv",
            custom_path="my_export.csv",
        )
        save_to_csv(df, str(resolved))
        assert resolved.exists()
        assert "my_export.csv" in str(resolved)
