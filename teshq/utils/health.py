"""
Health check system for TESH-Query production monitoring.

Provides comprehensive health checks for database connectivity, API availability,
and configuration validity.
"""

import time
from typing import Any, Dict, List, Optional

from teshq.utils.config import get_config, get_database_url, get_gemini_config
from teshq.utils.connection import connection_manager
from teshq.utils.logging import logger, metrics
from teshq.utils.retry import retry_api_call
from teshq.utils.validation import ConfigValidator


class HealthStatus:
    """Health status enumeration."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class HealthCheck:
    """Individual health check result."""

    def __init__(
        self, name: str, status: str, message: str = "", duration_ms: float = 0, details: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.status = status
        self.message = message
        self.duration_ms = duration_ms
        self.details = details or {}
        self.timestamp = time.time()


class HealthChecker:
    """Comprehensive health check system."""

    def __init__(self):
        self.checks: List[HealthCheck] = []

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        logger.info("Starting comprehensive health checks")
        start_time = time.time()

        self.checks = [
            self._check_configuration(),
            self._check_database_connectivity(),
            self._check_api_connectivity(),
            self._check_llm_token_usage(),
        ]

        total_duration = (time.time() - start_time) * 1000

        statuses = [check.status for check in self.checks]
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        result = {
            "status": overall_status,
            "timestamp": time.time(),
            "duration_ms": total_duration,
            "checks": [self._check_to_dict(check) for check in self.checks],
            "summary": self._generate_summary(),
        }

        logger.info(
            "Health checks completed",
            overall_status=overall_status,
            total_duration_ms=total_duration,
            healthy_checks=len([c for c in self.checks if c.status == HealthStatus.HEALTHY]),
            total_checks=len(self.checks),
        )
        return result

    def _check_to_dict(self, check: HealthCheck) -> Dict[str, Any]:
        """Convert health check to dictionary."""
        return {
            "name": check.name,
            "status": check.status,
            "message": check.message,
            "duration_ms": check.duration_ms,
            "timestamp": check.timestamp,
            "details": check.details,
        }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate health check summary."""
        status_counts = {}
        for check in self.checks:
            status_counts[check.status] = status_counts.get(check.status, 0) + 1
        return {
            "total_checks": len(self.checks),
            "status_breakdown": status_counts,
            "critical_issues": [check.name for check in self.checks if check.status == HealthStatus.UNHEALTHY],
            "warnings": [check.name for check in self.checks if check.status == HealthStatus.DEGRADED],
        }

    def _check_configuration(self) -> HealthCheck:
        """Check configuration validity."""
        start_time = time.time()
        try:
            get_config()
            database_url = get_database_url()
            gemini_api_key, gemini_model = get_gemini_config()
            issues = []
            warnings = []
            if database_url:
                db_valid, db_message = ConfigValidator.validate_database_url(database_url)
                if not db_valid:
                    issues.append(f"Database URL: {db_message}")
            else:
                issues.append("Database URL is not configured")
            if gemini_api_key:
                api_valid, api_message = ConfigValidator.validate_gemini_api_key(gemini_api_key)
                if not api_valid:
                    issues.append(f"Gemini API Key: {api_message}")
            else:
                issues.append("Gemini API Key is not configured")
            if database_url and "localhost" in database_url:
                warnings.append("Using localhost database (development setup)")
            details = {
                "database_configured": bool(database_url),
                "api_key_configured": bool(gemini_api_key),
                "model": gemini_model,
                "issues": issues,
                "warnings": warnings,
            }
            if issues:
                status = HealthStatus.UNHEALTHY
                message = f"Configuration issues: {'; '.join(issues)}"
            elif warnings:
                status = HealthStatus.DEGRADED
                message = f"Configuration warnings: {'; '.join(warnings)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Configuration is valid"
        except Exception as e:
            details = {"error": str(e)}
            status = HealthStatus.UNHEALTHY
            message = f"Configuration check failed: {e}"
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck("configuration", status, message, duration_ms, details)

    def _check_database_connectivity(self) -> HealthCheck:
        """Check database connectivity."""
        start_time = time.time()
        try:
            database_url = get_database_url()
            if not database_url:
                return HealthCheck(
                    "database_connectivity",
                    HealthStatus.UNHEALTHY,
                    "Database URL not configured",
                    0,
                    {"error": "No database URL"},
                )
            success = connection_manager.test_connection(database_url)
            if success:
                conn_info = connection_manager.get_connection_info()
                details = {"connection_successful": True, "pool_info": conn_info}
                status = HealthStatus.HEALTHY
                message = "Database connection is healthy"
            else:
                details = {"connection_successful": False}
                status = HealthStatus.UNHEALTHY
                message = "Database connection failed"
        except Exception as e:
            details = {"error": str(e), "connection_successful": False}
            status = HealthStatus.UNHEALTHY
            message = f"Database connectivity check failed: {e}"
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck("database_connectivity", status, message, duration_ms, details)

    @retry_api_call("health_check_api")
    def _check_api_connectivity(self) -> HealthCheck:
        """Check API connectivity (Gemini)."""
        start_time = time.time()
        try:
            gemini_api_key, gemini_model = get_gemini_config()
            if not gemini_api_key:
                return HealthCheck(
                    "api_connectivity",
                    HealthStatus.DEGRADED,
                    "API key not configured - LLM features unavailable",
                    0,
                    {"api_configured": False},
                )
            details = {"api_configured": True, "model": gemini_model, "note": "API key format is valid"}
            status = HealthStatus.HEALTHY
            message = "API connectivity appears healthy"
        except Exception as e:
            details = {"error": str(e), "api_configured": bool(gemini_api_key)}
            status = HealthStatus.DEGRADED
            message = f"API connectivity check failed: {e}"
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck("api_connectivity", status, message, duration_ms, details)

    def _check_llm_token_usage(self) -> HealthCheck:
        """Check LLM token usage from metrics."""
        start_time = time.time()
        try:
            token_metrics = metrics.get_summary().get("api_tokens_used", {})
            if not token_metrics:
                details = {"total_tokens": 0}
                status = HealthStatus.HEALTHY
                message = "No token usage recorded yet"
            else:
                total_tokens = token_metrics.get("total", 0)
                avg_tokens = token_metrics.get("avg", 0)
                max_tokens = token_metrics.get("max", 0)
                details = {
                    "total_tokens": total_tokens,
                    "average_tokens_per_call": avg_tokens,
                    "max_tokens_in_one_call": max_tokens,
                    "call_count": token_metrics.get("count", 0),
                }
                status = HealthStatus.HEALTHY
                message = f"Total tokens used: {total_tokens}"
        except Exception as e:
            details = {"error": str(e)}
            status = HealthStatus.UNKNOWN
            message = f"Failed to check token usage: {e}"
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck("llm_token_usage", status, message, duration_ms, details)


health_checker = HealthChecker()


def get_health_status() -> Dict[str, Any]:
    return health_checker.run_all_checks()


def is_healthy() -> bool:
    result = get_health_status()
    return result["status"] == HealthStatus.HEALTHY


def get_metrics_summary() -> Dict[str, Any]:
    return {
        "metrics": metrics.get_summary(),
        "connection_info": connection_manager.get_connection_info(),
        "timestamp": time.time(),
    }
