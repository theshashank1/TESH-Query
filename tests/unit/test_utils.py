"""
Unit tests for teshq.utils (output formatting, query result models, and file exports).
"""

from decimal import Decimal
import tempfile
from pathlib import Path

import pandas as pd

from teshq.utils.output import OutputFormatter, QueryResult
from teshq.utils.save import generate_query_slug, save_to_csv, save_to_sqlite


class TestOutputFormatter:
    """Tests for OutputFormatter normalization and conversions."""

    def test_normalize_results_empty(self):
        assert OutputFormatter.normalize_results([]) == []

    def test_normalize_converts_decimal_and_handles_none(self):
        raw = [
            {"id": 1, "price": Decimal("19.99"), "note": None},
            {"id": 2, "price": Decimal("0.00"), "note": "ok"},
        ]
        normalized = OutputFormatter.normalize_results(raw)
        assert normalized[0]["price"] == 19.99
        assert isinstance(normalized[0]["price"], float)
        assert normalized[0]["note"] is None
        assert normalized[1]["price"] == 0.0

    def test_to_dataframe(self):
        raw = [{"col_a": "val1", "col_b": Decimal("10.5")}]
        df = OutputFormatter.to_dataframe(raw)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df["col_b"].iloc[0] == 10.5


class TestQueryResultWrapper:
    """Tests for the user-facing QueryResult wrapper in teshq.utils.output."""

    def test_query_result_properties(self):
        rows = [{"name": "alice"}, {"name": "bob"}]
        qr = QueryResult(
            results=rows,
            query="SELECT name FROM users",
            parameters={"status": "active"},
            natural_language_query="active users",
        )
        assert len(qr) == 2
        assert bool(qr) is True
        assert qr.query == "SELECT name FROM users"
        assert qr.parameters == {"status": "active"}
        assert qr.natural_language_query == "active users"

        # DataFrame caching
        df = qr.dataframe
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

        # Dict export
        d = qr.to_dict(include_sql=True)
        assert d["sql"] == "SELECT name FROM users"
        assert len(d["results"]) == 2

    def test_empty_query_result(self):
        qr = QueryResult(results=[], query="SELECT 1 WHERE 1=0")
        assert len(qr) == 0
        assert bool(qr) is False


class TestSaveUtils:
    """Tests for export helper utilities."""

    def test_generate_query_slug(self):
        slug = generate_query_slug("Show all customer table names")
        assert "customer_table_names" in slug

    def test_generate_query_slug_empty(self):
        slug = generate_query_slug("")
        assert slug == "query_results"

    def test_save_to_csv(self):
        df = pd.DataFrame([{"id": 1, "name": "test"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = str(Path(tmp_dir) / "output.csv")
            save_to_csv(df, filename=path)
            assert Path(path).exists()
            content = Path(path).read_text()
            assert "name" in content
            assert "test" in content

    def test_save_to_sqlite(self):
        df = pd.DataFrame([{"id": 10, "val": "abc"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = str(Path(tmp_dir) / "test.db")
            save_to_sqlite(df, db_path=path, table_name="results")
            assert Path(path).exists()


