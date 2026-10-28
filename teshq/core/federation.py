"""
Cross-Database Query Federation Layer for TESH-Query.

Provides structured multi-database query planning, isolated subquery execution,
bounded result joining, schema disambiguation, source attribution, and deterministic
security policy enforcement across N named database connections.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from teshq.core.connection import DatabaseConnection, connection_manager as default_connection_manager
from teshq.core.query import execute_sql_query
from teshq.core.sql_normalizer import normalize_sql
from teshq.core.sql_validator import validate_sql
from teshq.core.validation import ValidationError
from teshq.utils.logging import logger


@dataclass
class SubquerySpec:
    """Specification for a bounded subquery targeted at a single named database."""

    database: str = ""
    sql: str = ""
    purpose: str = ""
    join_keys: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    row_limit: int = 5000
    connection_name: Optional[str] = None
    alias: str = ""

    def __post_init__(self):
        if not self.database and self.connection_name:
            self.database = self.connection_name
        elif not self.connection_name and self.database:
            self.connection_name = self.database

    def to_dict(self) -> Dict[str, Any]:
        return {
            "database": self.database,
            "sql": self.sql,
            "purpose": self.purpose,
            "join_keys": self.join_keys,
            "parameters": self.parameters,
            "row_limit": self.row_limit,
            "alias": self.alias,
        }


@dataclass
class CrossDatabasePlan:
    """Structured query plan orchestrating queries across multiple databases."""

    nl_query: str = ""
    subqueries: List[SubquerySpec] = field(default_factory=list)
    join_keys: List[str] = field(default_factory=list)
    join_type: str = "outer"  # "inner", "left", "outer", "concat"
    explanation: str = ""
    post_operations: Optional[Dict[str, Any]] = None
    plan_id: str = ""
    query_text: Optional[str] = None
    join_key: Optional[str] = None

    def __post_init__(self):
        if not self.nl_query and self.query_text:
            self.nl_query = self.query_text
        if self.join_key and not self.join_keys:
            self.join_keys = [self.join_key]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nl_query": self.nl_query,
            "subqueries": [sq.to_dict() for sq in self.subqueries],
            "join_keys": self.join_keys,
            "join_type": self.join_type,
            "explanation": self.explanation,
            "plan_id": self.plan_id,
            "post_operations": self.post_operations or {},
        }


@dataclass
class SubqueryExecutionResult:
    """Execution telemetry and data for a single database subquery."""

    database: str = ""
    sql: str = ""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    latency_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    alias: str = ""
    connection_name: Optional[str] = None
    rows_returned: Optional[int] = None
    execution_time_ms: Optional[float] = None
    status: Optional[str] = None

    def __post_init__(self):
        if not self.database and self.connection_name:
            self.database = self.connection_name
        elif not self.connection_name and self.database:
            self.connection_name = self.database

        if self.rows_returned is not None and self.row_count == 0:
            self.row_count = self.rows_returned
        elif self.rows_returned is None:
            self.rows_returned = self.row_count

        if self.execution_time_ms is not None and self.latency_ms == 0:
            self.latency_ms = int(self.execution_time_ms)
        elif self.execution_time_ms is None:
            self.execution_time_ms = float(self.latency_ms)

        if not self.status:
            if self.error and "dry_run" in self.error:
                self.status = "dry_run"
            else:
                self.status = "success" if self.success else f"error: {self.error}"


class SubqueryResultsList(list):
    """List of SubqueryExecutionResult supporting connection name indexing."""

    def get(self, key: str, default=None):
        for item in self:
            if getattr(item, "database", None) == key or getattr(item, "connection_name", None) == key:
                return item
        return default

    def __getitem__(self, item):
        if isinstance(item, str):
            for obj in self:
                if getattr(obj, "database", None) == item or getattr(obj, "connection_name", None) == item:
                    return obj
            raise KeyError(f"No subquery result found for connection '{item}'")
        return super().__getitem__(item)


@dataclass
class CrossDatabaseResult:
    """Unified result of a cross-database query execution with source attribution."""

    nl_query: str
    plan: CrossDatabasePlan
    subquery_results: Any
    rows: List[Dict[str, Any]]
    dataframe: pd.DataFrame
    total_latency_ms: int
    source_attribution: Dict[str, List[str]]  # database -> list of column names
    success: bool
    partial_failure: bool = False
    error: Optional[str] = None
    dry_run: bool = False

    @property
    def plan_id(self) -> str:
        return getattr(self.plan, "plan_id", "") or "cross_db_plan"

    @property
    def status(self) -> str:
        if self.dry_run:
            return "dry_run"
        if self.partial_failure:
            return "partial_failure"
        return "success" if self.success else "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nl_query": self.nl_query,
            "status": self.status,
            "success": self.success,
            "partial_failure": self.partial_failure,
            "error": self.error,
            "total_latency_ms": self.total_latency_ms,
            "row_count": len(self.rows),
            "source_attribution": self.source_attribution,
            "rows": self.rows,
        }


class CrossDatabaseOrchestrator:
    """
    Orchestrates cross-database querying across N named connections.
    """

    DEFAULT_ROW_LIMIT = 5000
    MAX_ROW_LIMIT = 20000
    MAX_COMBINED_ROWS = 50000

    def __init__(
        self,
        manager: Optional[Any] = None,
        max_rows_per_subquery: int = DEFAULT_ROW_LIMIT,
        connection_manager: Optional[Any] = None,
    ):
        self.connection_manager = manager or connection_manager or default_connection_manager
        self.default_row_limit = max_rows_per_subquery

    def plan_query(
        self,
        nl_query: str,
        target_connections: Optional[List[str]] = None,
        predefined_subqueries: Optional[List[SubquerySpec]] = None,
        join_keys: Optional[List[str]] = None,
        join_type: str = "outer",
        explanation: str = "",
    ) -> CrossDatabasePlan:
        """
        Build a validated CrossDatabasePlan.

        Accepts explicit subqueries or infers them from candidate connection schemas.
        """
        available_names = (
            list(self.connection_manager._connections.keys())
            if hasattr(self.connection_manager, "_connections")
            else []
        )
        if not available_names and hasattr(self.connection_manager, "list_connections"):
            conns = self.connection_manager.list_connections()
            if isinstance(conns, dict):
                available_names = list(conns.keys())
            else:
                available_names = [
                    c.get("name") if isinstance(c, dict) else getattr(c, "name", str(c))
                    for c in conns
                ]

        if not available_names:
            raise KeyError("No database connections are registered in ConnectionManager.")

        conns_to_use = target_connections or available_names
        for c in conns_to_use:
            if c not in available_names:
                raise KeyError(f"Target connection '{c}' not found. Available: {available_names}")

        if predefined_subqueries:
            subqueries = predefined_subqueries
        else:
            subqueries = []
            for c in conns_to_use:
                subqueries.append(
                    SubquerySpec(
                        database=c,
                        sql="",
                        purpose=f"Query {c}",
                        join_keys=join_keys or [],
                        row_limit=self.DEFAULT_ROW_LIMIT,
                    )
                )

        return CrossDatabasePlan(
            nl_query=nl_query,
            subqueries=subqueries,
            join_keys=join_keys or [],
            join_type=join_type,
            explanation=explanation or f"Cross-database plan across: {', '.join(conns_to_use)}",
        )

    def validate_plan(self, plan: CrossDatabasePlan) -> Tuple[bool, List[str]]:
        """
        Validate all subqueries in the plan independently against target dialects.

        Ensures AST safety, read-only guarantees, parameter binding, and bounded limits.
        """
        errors: List[str] = []
        if not plan.subqueries:
            errors.append("Cross-database plan must contain at least one subquery.")
            return False, errors

        for sq in plan.subqueries:
            if not sq.sql or not sq.sql.strip():
                errors.append(f"Subquery for database '{sq.database}' has empty SQL.")
                continue

            dialect = "sqlite"
            try:
                conn = self.connection_manager.get_named_connection(sq.database)
                dialect = conn.dialect
            except Exception:
                pass

            try:
                validate_sql(sq.sql, dialect=dialect)
            except Exception as e:
                errors.append(f"Subquery validation failed on '{sq.database}': {e}")

            if sq.row_limit is not None and sq.row_limit > self.MAX_ROW_LIMIT:
                errors.append(
                    f"Subquery for '{sq.database}' requested {sq.row_limit} rows, "
                    f"exceeding max allowed limit of {self.MAX_ROW_LIMIT}."
                )

        return (len(errors) == 0), errors

    def execute_plan(
        self,
        plan: CrossDatabasePlan,
        dry_run: bool = False,
        allow_partial_failures: bool = True,
    ) -> CrossDatabaseResult:
        """
        Execute subqueries and combine their intermediate results in memory.
        """
        t0 = time.time()
        is_valid, validation_errors = self.validate_plan(plan)
        if not is_valid and not dry_run:
            raise ValidationError(f"Plan validation failed: {'; '.join(validation_errors)}")

        subquery_results = SubqueryResultsList()
        source_dfs: Dict[str, pd.DataFrame] = {}

        if dry_run:
            total_ms = int((time.time() - t0) * 1000)
            for sq in plan.subqueries:
                subquery_results.append(
                    SubqueryExecutionResult(
                        database=sq.database,
                        sql=normalize_sql(sq.sql),
                        rows=[],
                        row_count=0,
                        latency_ms=0,
                        success=True,
                        error="dry_run",
                        alias=sq.alias,
                    )
                )
            return CrossDatabaseResult(
                nl_query=plan.nl_query,
                plan=plan,
                subquery_results=subquery_results,
                rows=[],
                dataframe=pd.DataFrame(),
                total_latency_ms=total_ms,
                source_attribution={},
                success=True,
                dry_run=True,
            )

        failed_sources: List[str] = []

        def _execute_single_subquery(
            sq: SubquerySpec,
        ) -> Tuple[SubqueryExecutionResult, Optional[pd.DataFrame], Optional[str]]:
            sq_t0 = time.time()
            normalized_sql = normalize_sql(sq.sql).rstrip(";").strip()

            effective_limit = sq.row_limit if sq.row_limit is not None else self.DEFAULT_ROW_LIMIT
            if "LIMIT" not in normalized_sql.upper():
                normalized_sql += f" LIMIT {effective_limit}"

            try:
                conn: DatabaseConnection = self.connection_manager.get_named_connection(sq.database)
                rows = execute_sql_query(
                    db_url=conn.db_url,
                    query=normalized_sql,
                    parameters=sq.parameters,
                )
                if effective_limit and len(rows) > effective_limit:
                    rows = rows[: effective_limit]

                sq_latency = int((time.time() - sq_t0) * 1000)
                sub_res = SubqueryExecutionResult(
                    database=sq.database,
                    sql=normalized_sql,
                    rows=rows,
                    row_count=len(rows),
                    latency_ms=sq_latency,
                    success=True,
                    alias=sq.alias,
                )
                return sub_res, pd.DataFrame(rows), None

            except Exception as e:
                sq_latency = int((time.time() - sq_t0) * 1000)
                logger.error(
                    "Cross-database subquery failed",
                    database=sq.database,
                    error=str(e),
                )
                sub_res = SubqueryExecutionResult(
                    database=sq.database,
                    sql=normalized_sql,
                    rows=[],
                    row_count=0,
                    latency_ms=sq_latency,
                    success=False,
                    error=str(e),
                    alias=sq.alias,
                )
                return sub_res, None, str(e)

        if len(plan.subqueries) <= 1:
            raw_results = [_execute_single_subquery(sq) for sq in plan.subqueries]
        else:
            max_workers = min(len(plan.subqueries), 8)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_execute_single_subquery, sq) for sq in plan.subqueries]
                raw_results = [f.result() for f in futures]

        for sq, (sub_res, df, err) in zip(plan.subqueries, raw_results):
            subquery_results.append(sub_res)
            if err is not None:
                failed_sources.append(sq.database)
                if not allow_partial_failures:
                    total_ms = int((time.time() - t0) * 1000)
                    return CrossDatabaseResult(
                        nl_query=plan.nl_query,
                        plan=plan,
                        subquery_results=subquery_results,
                        rows=[],
                        dataframe=pd.DataFrame(),
                        total_latency_ms=total_ms,
                        source_attribution={},
                        success=False,
                        error=f"Subquery for database '{sq.database}' failed: {err}",
                    )
            else:
                if df is not None:
                    source_dfs[sq.database] = df

        if len(failed_sources) == len(plan.subqueries):
            total_ms = int((time.time() - t0) * 1000)
            err_msg = "; ".join(f"{s.database}: {s.error}" for s in subquery_results if s.error)
            return CrossDatabaseResult(
                nl_query=plan.nl_query,
                plan=plan,
                subquery_results=subquery_results,
                rows=[],
                dataframe=pd.DataFrame(),
                total_latency_ms=total_ms,
                source_attribution={},
                success=False,
                partial_failure=False,
                error=f"All cross-database subqueries failed: {err_msg}",
            )

        combined_df, source_attribution = self._combine_result_sets(
            source_dfs=source_dfs,
            join_keys=plan.join_keys,
            join_type=plan.join_type,
        )

        combined_rows = combined_df.replace({pd.NA: None, float("nan"): None}).to_dict(orient="records")

        total_ms = int((time.time() - t0) * 1000)
        has_partial_failure = len(failed_sources) > 0

        return CrossDatabaseResult(
            nl_query=plan.nl_query,
            plan=plan,
            subquery_results=subquery_results,
            rows=combined_rows,
            dataframe=combined_df,
            total_latency_ms=total_ms,
            source_attribution=source_attribution,
            success=True,
            partial_failure=has_partial_failure,
            error=f"Partial failure on sources: {', '.join(failed_sources)}" if has_partial_failure else None,
        )

    def _combine_result_sets(
        self,
        source_dfs: Any,
        join_keys: Optional[List[str]] = None,
        join_key: Optional[str] = None,
        join_type: str = "outer",
    ) -> Tuple[Any, Dict[str, List[str]]]:
        """
        Merge/join multiple intermediate DataFrames on common join keys.

        Disambiguates non-join columns with source prefixes, coerces key types,
        and builds column-level source attribution metadata.
        """
        attribution: Dict[str, List[str]] = {}
        if join_key and not join_keys:
            join_keys = [join_key]
        elif not join_keys:
            join_keys = []

        is_subquery_results = isinstance(source_dfs, (list, tuple))
        if is_subquery_results:
            dfs: Dict[str, pd.DataFrame] = {}
            for item in source_dfs:
                db_name = getattr(item, "connection_name", None) or getattr(item, "database", "source")
                rows = getattr(item, "rows", [])
                dfs[db_name] = pd.DataFrame(rows)
            source_dfs = dfs

        if not source_dfs:
            empty_df = pd.DataFrame()
            return ([] if is_subquery_results else empty_df), attribution

        if len(source_dfs) == 1:
            db_name, df = next(iter(source_dfs.items()))
            attribution[db_name] = list(df.columns)
            return (df.to_dict(orient="records") if is_subquery_results else df), attribution

        cleaned_dfs: Dict[str, pd.DataFrame] = {}
        for db_name, df in source_dfs.items():
            if df.empty:
                cleaned_dfs[db_name] = df.copy()
                attribution[db_name] = []
                continue

            clean = df.copy()

            new_columns = {}
            for col in clean.columns:
                matched_key = next((k for k in join_keys if k.lower() == str(col).lower()), None)
                if matched_key:
                    new_columns[col] = matched_key
                    clean[col] = (
                        clean[col]
                        .astype(str)
                        .str.strip()
                        .where(clean[col].notna(), None)
                    )
                else:
                    new_columns[col] = f"{db_name}_{col}"

            clean = clean.rename(columns=new_columns)
            cleaned_dfs[db_name] = clean
            attribution[db_name] = [new_columns[c] for c in df.columns]

        merged_df: Optional[pd.DataFrame] = None
        pd_how = "outer" if join_type in ("outer", "full") else ("inner" if join_type == "inner" else "left")

        for db_name, df in cleaned_dfs.items():
            if merged_df is None:
                merged_df = df
            else:
                common_keys = [k for k in join_keys if k in merged_df.columns and k in df.columns]
                if common_keys:
                    merged_df = pd.merge(merged_df, df, on=common_keys, how=pd_how)
                else:
                    merged_df = pd.concat([merged_df.reset_index(drop=True), df.reset_index(drop=True)], axis=1)

                # Memory protection: prevent explosive cartesian joins from exhausting RAM
                max_combined = getattr(self, "MAX_COMBINED_ROWS", 50000)
                if len(merged_df) > max_combined:
                    logger.warning(
                        "Cross-database join result exceeded memory threshold; capped to prevent OOM",
                        row_count=len(merged_df),
                        max_allowed=max_combined,
                    )
                    merged_df = merged_df.iloc[:max_combined]

        final_df = merged_df if merged_df is not None else pd.DataFrame()
        final_df = final_df.replace({pd.NA: None, float("nan"): None})
        if is_subquery_results:
            return final_df.to_dict(orient="records"), attribution
        return final_df, attribution
