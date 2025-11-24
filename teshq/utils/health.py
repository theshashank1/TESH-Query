"""
Health check system for TESH-Query production monitoring.

Provides comprehensive health checks for database connectivity, API availability,
and configuration validity using a modular, decorator-based approach.
"""

import functools
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from teshq.utils.config import get_database_url, get_gemini_config
from teshq.utils.logging import logger
from teshq.utils.retry import retry_api_call
from teshq.utils.validation import ConfigValidator

_health_checks: Dict[str, Callable[[], Tuple["HealthStatus", str, Dict[str, Any]]]] = {}


def health_check(name: str) -> Callable:
    """Decorator to register a function as a health check."""

    def decorator(
        func: Callable[[], Tuple["HealthStatus", str, Dict[str, Any]]]
    ) -> Callable[[], Tuple["HealthStatus", str, Dict[str, Any]]]:
        _health_checks[name] = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Tuple["HealthStatus", str, Dict[str, Any]]:
            return func(*args, **kwargs)

        return wrapper

    return decorator


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheckResult(BaseModel):
    """Pydantic model for an individual health check result."""

    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class HealthChecker:
    """Comprehensive and modular health check system."""

    def __init__(self, checks_to_run: Dict[str, Callable] = None):
        self.check_functions = checks_to_run if checks_to_run is not None else _health_checks

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered health checks and return a comprehensive status report."""
        logger.info(f"Starting {len(self.check_functions)} health checks...")
        start_time = time.time()

        check_results: List[HealthCheckResult] = []
        for name, check_func in self.check_functions.items():
            check_start_time = time.time()
            try:
                status, message, details = check_func()
            except Exception as e:
                logger.error(f"Health check '{name}' raised an unhandled exception.", error=e)
                status = HealthStatus.UNHEALTHY
                message = f"Check failed with an unhandled exception: {e}"
                details = {"error_type": type(e).__name__, "error_message": str(e)}

            duration_ms = (time.time() - check_start_time) * 1000
            check_results.append(
                HealthCheckResult(name=name, status=status, message=message, duration_ms=duration_ms, details=details)
            )

        total_duration = (time.time() - start_time) * 1000
        overall_status = self._calculate_overall_status(check_results)
        summary = self._generate_summary(check_results)

        report = {
            "status": overall_status.value,
            "timestamp": time.time(),
            "duration_ms": total_duration,
            "checks": [result.model_dump() for result in check_results],
            "summary": summary,
        }

        logger.info(
            "Health checks completed",
            overall_status=report["status"],
            total_duration_ms=report["duration_ms"],
            healthy_checks=summary["status_breakdown"].get(HealthStatus.HEALTHY.value, 0),
            total_checks=summary["total_checks"],
        )
        return report

    def is_healthy(self) -> bool:
        report = self.run_all_checks()
        return report["status"] == HealthStatus.HEALTHY.value

    def _calculate_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        statuses = {result.status for result in results}
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def _generate_summary(self, results: List[HealthCheckResult]) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        for result in results:
            status_value = result.status.value
            status_counts[status_value] = status_counts.get(status_value, 0) + 1

        return {
            "total_checks": len(results),
            "status_breakdown": status_counts,
            "critical_issues": [r.name for r in results if r.status == HealthStatus.UNHEALTHY],
            "warnings": [r.name for r in results if r.status == HealthStatus.DEGRADED],
        }


@health_check("configuration")
def check_configuration() -> Tuple[HealthStatus, str, Dict[str, Any]]:
    """Validates that all necessary configurations are present and correctly formatted."""
    database_url = get_database_url()
    gemini_api_key, gemini_model = get_gemini_config()
    issues: List[str] = []

    if not database_url:
        issues.append("Database URL is not configured")
    else:
        is_valid, msg = ConfigValidator.validate_database_url(database_url)
        if not is_valid:
            issues.append(f"Database URL: {msg}")

    if not gemini_api_key:
        issues.append("Gemini API Key is not configured")
    else:
        is_valid, msg = ConfigValidator.validate_gemini_api_key(gemini_api_key)
        if not is_valid:
            issues.append(f"Gemini API Key: {msg}")

    details = {
        "database_configured": bool(database_url),
        "api_key_configured": bool(gemini_api_key),
        "model": gemini_model,
        "issues": issues,
    }

    if issues:
        return HealthStatus.UNHEALTHY, f"Configuration has critical issues: {'; '.join(issues)}", details
    return HealthStatus.HEALTHY, "Configuration is valid and complete", details


@health_check("database_connectivity")
def check_database_connectivity() -> Tuple[HealthStatus, str, Dict[str, Any]]:
    """Checks the ability to connect to the database and execute a simple query."""
    database_url = get_database_url()
    if not database_url:
        return HealthStatus.UNHEALTHY, "Database URL not configured", {"error": "No database URL"}

    try:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.scalar() != 1:
                return (
                    HealthStatus.UNHEALTHY,
                    "Database query returned unexpected result.",
                    {"query": "SELECT 1"},
                )
    except SQLAlchemyError as e:
        return (
            HealthStatus.UNHEALTHY,
            f"Database connection failed: {e}",
            {"error_type": type(e).__name__, "error_message": str(e)},
        )
    except Exception as e:
        return (
            HealthStatus.UNHEALTHY,
            f"An unexpected error occurred during database check: {e}",
            {"error_type": type(e).__name__, "error_message": str(e)},
        )

    return HealthStatus.HEALTHY, "Database connection is healthy and responsive", {}


@health_check("api_connectivity")
@retry_api_call("health_check_api")
def check_api_connectivity() -> Tuple[HealthStatus, str, Dict[str, Any]]:
    """Checks Gemini API key validity by attempting to initialize the query generator."""
    api_key, model = get_gemini_config()
    if not api_key:
        return HealthStatus.DEGRADED, "API key not configured; LLM features unavailable", {"api_configured": False}

    try:
        from teshq.core.llm import SQLQueryGenerator

        generator = SQLQueryGenerator(api_key=api_key, model_name=model)
        _ = generator.llm.client
        details = {"api_configured": True, "model": model, "initialization_successful": True}
        return HealthStatus.HEALTHY, "API connectivity is healthy", details
    except Exception as e:
        error_msg = f"API key is configured but initialization failed: {e}"
        details = {"api_configured": True, "model": model, "error": str(e)}
        return HealthStatus.DEGRADED, error_msg, details


if __name__ == "__main__":
    import json

    print("Running TESH-Query Health Checks...")
    health_checker = HealthChecker()
    full_report = health_checker.run_all_checks()

    print("\n--- Health Check Report ---")
    print(json.dumps(full_report, indent=2))
    print("--- End of Report ---\n")

    if health_checker.is_healthy():
        print("✅ System is healthy.")
    else:
        print(f"❌ System status is: {full_report['status'].upper()}")
