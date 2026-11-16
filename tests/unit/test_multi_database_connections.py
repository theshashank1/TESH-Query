"""
Unit tests for TESH-Query Multi-Database Connection Management.

Verifies named connection lifecycle, independent SQLAlchemy engine pools,
credential masking, environment variable resolution, and engine disposal.
"""

import pytest

from teshq.core.connection import (
    ConnectionManager,
    DatabaseConnection,
    expand_connection_url,
    mask_database_url,
)


class TestConnectionUrlSecurity:
    """Test URL parsing, masking, and environment variable expansion."""

    def test_mask_password_in_postgresql_url(self):
        url = "postgresql://myuser:SuperSecretPassword123@db.prod.internal:5432/orders_db"
        masked = mask_database_url(url)
        assert "SuperSecretPassword123" not in masked
        assert "myuser" in masked
        assert "db.prod.internal" in masked
        assert "orders_db" in masked

    def test_mask_password_in_mysql_url(self):
        url = "mysql+pymysql://admin:P@ssw0rd!@10.0.0.15:3306/analytics"
        masked = mask_database_url(url)
        assert "P@ssw0rd!" not in masked
        assert "admin" in masked

    def test_sqlite_url_preserves_path(self):
        url = "sqlite:///testing/databases/ecommerce.sqlite"
        masked = mask_database_url(url)
        assert masked == "sqlite:///testing/databases/ecommerce.sqlite"

    def test_expand_connection_url_from_environ(self, monkeypatch):
        monkeypatch.setenv("TEST_DB_HOST", "db.example.org")
        monkeypatch.setenv("TEST_DB_PORT", "5433")
        monkeypatch.setenv("TEST_DB_NAME", "warehouse")

        raw_url = "postgresql://user:pass@${TEST_DB_HOST}:${TEST_DB_PORT}/${TEST_DB_NAME}"
        expanded = expand_connection_url(raw_url)
        assert "db.example.org:5433/warehouse" in expanded

    def test_expand_connection_url_with_default_fallback(self):
        raw_url = "postgresql://user:pass@${UNDEFINED_VAR_XYZ:-localhost}:5432/mydb"
        expanded = expand_connection_url(raw_url)
        assert "localhost:5432/mydb" in expanded


class TestDatabaseConnectionDataclass:
    """Test DatabaseConnection representation and serialization safety."""

    def test_repr_never_leaks_password(self):
        secret_url = "postgresql://app_user:ultra_confidential_pass@host:5432/dbname"
        conn = DatabaseConnection(
            name="prod_pg",
            db_url=secret_url,
            dialect="postgresql",
            description="Production PG"
        )
        repr_str = repr(conn)
        str_str = str(conn)

        assert "ultra_confidential_pass" not in repr_str
        assert "ultra_confidential_pass" not in str_str
        assert "prod_pg" in repr_str

    def test_to_dict_masks_secret_by_default(self):
        secret_url = "postgresql://app_user:ultra_confidential_pass@host:5432/dbname"
        conn = DatabaseConnection(name="prod_pg", db_url=secret_url, dialect="postgresql")
        data = conn.to_dict(mask_secret=True)

        assert "ultra_confidential_pass" not in data["url"]
        assert data["name"] == "prod_pg"


class TestConnectionManagerLifecycle:
    """Test adding, retrieving, listing, testing, and removing connections."""

    @pytest.fixture
    def manager(self):
        """Create an isolated ConnectionManager instance."""
        mgr = ConnectionManager()
        # Clean existing state for clean test run
        mgr.clear_all()
        return mgr

    def test_add_and_retrieve_named_connection(self, manager, tmp_path):
        db_file = tmp_path / "source1.sqlite"
        db_file.touch()
        url = f"sqlite:///{db_file}"

        conn = manager.add_connection(name="source1", db_url=url, description="Test Source 1")
        assert conn.name == "source1"
        assert str(conn.dialect).lower() == "sqlite"

        retrieved = manager.get_named_connection("source1")
        assert retrieved.name == "source1"
        assert retrieved.db_url == url

    def test_add_duplicate_connection_raises_error(self, manager, tmp_path):
        db_file = tmp_path / "dup.sqlite"
        db_file.touch()
        url = f"sqlite:///{db_file}"

        manager.add_connection(name="dup_test", db_url=url)
        with pytest.raises(ValueError, match="already exists"):
            manager.add_connection(name="dup_test", db_url=url)

    def test_invalid_url_raises_value_error(self, manager):
        with pytest.raises(ValueError, match="Invalid database URL"):
            manager.add_connection(name="invalid", db_url="not_a_valid_url")

    def test_get_nonexistent_connection_raises_key_error(self, manager):
        with pytest.raises(KeyError, match="not found"):
            manager.get_named_connection("missing")

    def test_list_connections_returns_all_metadata(self, manager, tmp_path):
        db1 = tmp_path / "db1.sqlite"
        db2 = tmp_path / "db2.sqlite"
        db1.touch()
        db2.touch()

        manager.add_connection(name="db1", db_url=f"sqlite:///{db1}", description="DB 1")
        manager.add_connection(name="db2", db_url=f"sqlite:///{db2}", description="DB 2")

        conns = manager.list_connections()
        names = [c["name"] for c in conns]
        assert "db1" in names
        assert "db2" in names

    def test_set_and_get_default_connection(self, manager, tmp_path):
        db1 = tmp_path / "db1.sqlite"
        db1.touch()
        url = f"sqlite:///{db1}"

        manager.add_connection(name="primary", db_url=url)
        manager.set_default_connection("primary")

        default_conn = manager.get_named_connection("default")
        assert default_conn.name == "primary"

    def test_engine_pool_isolation_and_disposal(self, manager, tmp_path):
        db1 = tmp_path / "pool1.sqlite"
        db2 = tmp_path / "pool2.sqlite"
        db1.touch()
        db2.touch()

        url1 = f"sqlite:///{db1}"
        url2 = f"sqlite:///{db2}"
        manager.add_connection(name="c1", db_url=url1)
        manager.add_connection(name="c2", db_url=url2)

        engine1 = manager.get_engine(url1, engine_name="c1")
        engine2 = manager.get_engine(url2, engine_name="c2")

        # Independent engines
        assert engine1 is not engine2

        # Engine disposal on connection removal
        assert f"c1:{url1}" in manager._engines
        manager.remove_connection("c1")
        assert f"c1:{url1}" not in manager._engines

    def test_test_named_connection_success_and_failure(self, manager, tmp_path):
        valid_db = tmp_path / "valid.sqlite"
        valid_db.touch()
        manager.add_connection(name="valid_conn", db_url=f"sqlite:///{valid_db}")

        success, msg = manager.test_named_connection("valid_conn")
        assert success is True
        assert "successful" in msg.lower()

        # Nonexistent name
        success_missing, msg_missing = manager.test_named_connection("non_existent")
        assert success_missing is False
        assert "not found" in msg_missing.lower()

    def test_dispose_all_alias(self, manager, tmp_path):
        db = tmp_path / "dispose_test.sqlite"
        db.touch()
        url = f"sqlite:///{db}"
        manager.add_connection(name="disp", db_url=url)
        manager.get_engine(url, engine_name="disp")
        assert len(manager._engines) > 0
        manager.dispose_all()
        assert len(manager._engines) == 0

    def test_concurrent_connection_operations(self, manager, tmp_path):
        import concurrent.futures

        def worker(idx):
            db = tmp_path / f"thread_{idx}.sqlite"
            db.touch()
            url = f"sqlite:///{db}"
            conn_name = f"tconn_{idx}"
            manager.add_connection(name=conn_name, db_url=url)
            retrieved = manager.get_named_connection(conn_name)
            assert retrieved.name == conn_name
            engine = manager.get_engine(url, engine_name=conn_name)
            assert engine is not None
            conns = manager.list_connections()
            assert len(conns) > 0
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(16)]
            results = [f.result() for f in futures]
            assert all(results)

    def test_read_only_query_with_comments(self, manager):
        assert manager._is_read_only("SELECT id FROM users") is True
        assert manager._is_read_only("SELECT /* update */ id FROM users") is True
        assert manager._is_read_only("SELECT id FROM users -- update counter") is True
        assert manager._is_read_only("UPDATE users SET name = 'alice'") is False
        assert manager._is_read_only("DELETE FROM users WHERE id = 1") is False

    def test_save_and_reload_connection_with_password(self, manager, tmp_path, monkeypatch):
        test_env = tmp_path / ".teshq.env"
        test_yaml = tmp_path / "connections.yaml"
        monkeypatch.setattr("teshq.config.secrets.SECRETS_FILE", test_env)
        monkeypatch.setattr("teshq.config.paths.CONNECTIONS_FILE", test_yaml)
        monkeypatch.setattr("teshq.core.connection.CONNECTIONS_FILE", test_yaml)

        url_with_pass = "postgresql://dbuser:MySuperPassword999@remotehost:5432/appdb"
        manager.add_connection(name="secure_pg", db_url=url_with_pass, persist=True)

        # Fresh manager loading from yaml
        new_mgr = ConnectionManager(auto_load=False)
        new_mgr._load_saved_connections(file_path=test_yaml)
        loaded_conn = new_mgr.get_named_connection("secure_pg")
        assert loaded_conn.name == "secure_pg"
        assert loaded_conn.db_url == url_with_pass
        assert loaded_conn.masked_url == "postgresql://dbuser:***@remotehost:5432/appdb"

    def test_combine_result_sets_memory_guard(self):
        import pandas as pd

        from teshq.core.federation import CrossDatabaseOrchestrator
        orch = CrossDatabaseOrchestrator()
        orch.MAX_COMBINED_ROWS = 100

        # Create two dataframes that would create 10,000 joined rows (100 x 100)
        df1 = pd.DataFrame({"id": ["A"] * 100, "val1": range(100)})
        df2 = pd.DataFrame({"id": ["A"] * 100, "val2": range(100)})

        combined, _ = orch._combine_result_sets(
            source_dfs={"src1": df1, "src2": df2},
            join_keys=["id"],
            join_type="inner",
        )
        assert len(combined) == 100

    def test_sqlite_pragmas_applied_on_connect(self, manager, tmp_path):
        from sqlalchemy import text
        db_file = tmp_path / "pragmas.sqlite"
        db_file.touch()
        url = f"sqlite:///{db_file}"
        engine = manager.get_engine(url, "sqlite_pragmas")
        with engine.connect() as conn:
            sync = conn.execute(text("PRAGMA synchronous")).scalar()
            cache = conn.execute(text("PRAGMA cache_size")).scalar()
            temp = conn.execute(text("PRAGMA temp_store")).scalar()
            assert sync == 1  # NORMAL
            assert cache == -64000  # 64MB
            assert temp == 2  # MEMORY

    def test_cross_database_parallel_execution(self, tmp_path):
        import sqlite3
        from teshq.core.federation import (
            CrossDatabaseOrchestrator,
            CrossDatabasePlan,
            SubquerySpec,
        )

        db1_path = tmp_path / "db1.sqlite"
        db2_path = tmp_path / "db2.sqlite"

        for path, tbl, col, val in (
            (db1_path, "t1", "v1", 100),
            (db2_path, "t2", "v2", 200),
        ):
            c = sqlite3.connect(str(path))
            c.execute(f"CREATE TABLE {tbl} (id INT PRIMARY KEY, {col} INT);")
            c.execute(f"INSERT INTO {tbl} VALUES (1, {val});")
            c.commit()
            c.close()

        manager = ConnectionManager(auto_load=False)
        manager.add_connection("db1", f"sqlite:///{db1_path}")
        manager.add_connection("db2", f"sqlite:///{db2_path}")

        orch = CrossDatabaseOrchestrator(connection_manager=manager)

        plan = CrossDatabasePlan(
            plan_id="p_parallel",
            query_text="Join t1 and t2 on id",
            subqueries=[
                SubquerySpec(connection_name="db1", sql="SELECT id, v1 FROM t1"),
                SubquerySpec(connection_name="db2", sql="SELECT id, v2 FROM t2"),
            ],
            join_keys=["id"],
            join_type="inner",
        )

        res = orch.execute_plan(plan)
        assert res.success is True
        assert len(res.rows) == 1
        assert res.rows[0]["db1_v1"] == 100
        assert res.rows[0]["db2_v2"] == 200

    def test_tesh_engine_retriever_caching(self, tmp_path, monkeypatch):
        import sqlite3
        from teshq.core.engine import TeshEngine
        from teshq.core.models import QueryPlan, SQLQuery

        db_file = tmp_path / "cached_retriever.sqlite"
        c = sqlite3.connect(str(db_file))
        c.execute("CREATE TABLE products (id INT PRIMARY KEY, name TEXT);")
        c.commit()
        c.close()

        class MockPlanner:
            def plan(self, query, schema, callbacks=None, **kwargs):
                return QueryPlan(tables=["products"], filters=[], aggregations=[], joins_needed=[])

        class MockSQLGen:
            def generate(self, query, schema, plan, callbacks=None, **kwargs):
                return SQLQuery(query="SELECT id, name FROM products;", parameters={}, explanation="Test")

        engine = TeshEngine(db_url=f"sqlite:///{db_file}", api_key="test_key", provider="gemini")
        monkeypatch.setattr(engine, "_get_planner", lambda: MockPlanner())
        monkeypatch.setattr(engine, "_get_sql_gen", lambda: MockSQLGen())

        # First query should populate retriever cache
        res1 = engine.query("List products", dry_run=True)
        assert res1.success is True
        assert len(engine._retrievers) == 1
        first_retriever = next(iter(engine._retrievers.values()))

        # Second query should reuse the exact same retriever instance
        res2 = engine.query("Show all product records", dry_run=True)
        assert res2.success is True
        assert len(engine._retrievers) == 1
        assert next(iter(engine._retrievers.values())) is first_retriever
