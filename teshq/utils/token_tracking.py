"""
LLM Token tracking and analytics system with optional LangSmith integration.

This module provides comprehensive token usage tracking, analytics, and reporting
for LLM API calls, with support for per-query, per-session, and global tracking.
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager
from collections import defaultdict
import uuid

from teshq.utils.logging import logger, metrics


@dataclass
class TokenUsage:
    """Token usage information for a single API call."""
    query_id: str
    session_id: str
    user_id: Optional[str]
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: Optional[float]
    timestamp: datetime
    natural_language_query: Optional[str] = None
    generated_sql: Optional[str] = None
    execution_time_ms: Optional[float] = None


@dataclass
class SessionSummary:
    """Summary of token usage for a session."""
    session_id: str
    user_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    total_queries: int
    total_tokens: int
    total_cost_estimate: float
    queries: List[str]  # List of query IDs


@dataclass
class UserSummary:
    """Summary of token usage for a user."""
    user_id: str
    total_sessions: int
    total_queries: int
    total_tokens: int
    total_cost_estimate: float
    first_query: datetime
    last_query: datetime


class TokenPricingCalculator:
    """Calculate estimated costs for different LLM providers and models."""
    
    # Pricing per 1K tokens (as of 2024) - these should be updated regularly
    PRICING_MAP = {
        "google": {
            "gemini-2.0-flash-lite": {"input": 0.075/1000, "output": 0.3/1000},
            "gemini-1.5-flash": {"input": 0.075/1000, "output": 0.3/1000},
            "gemini-1.5-pro": {"input": 1.25/1000, "output": 5.0/1000},
        },
        "openai": {
            "gpt-4": {"input": 30.0/1000, "output": 60.0/1000},
            "gpt-4-turbo": {"input": 10.0/1000, "output": 30.0/1000},
            "gpt-3.5-turbo": {"input": 0.5/1000, "output": 1.5/1000},
        },
        "anthropic": {
            "claude-3.5-sonnet": {"input": 3.0/1000, "output": 15.0/1000},
            "claude-3-haiku": {"input": 0.25/1000, "output": 1.25/1000},
        }
    }
    
    @classmethod
    def calculate_cost(cls, provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate estimated cost for token usage."""
        provider_pricing = cls.PRICING_MAP.get(provider.lower(), {})
        model_pricing = provider_pricing.get(model.lower(), {})
        
        if not model_pricing:
            # Fallback to default pricing if model not found
            input_cost = 1.0/1000  # $1 per 1K tokens
            output_cost = 3.0/1000  # $3 per 1K tokens
        else:
            input_cost = model_pricing.get("input", 1.0/1000)
            output_cost = model_pricing.get("output", 3.0/1000)
        
        return (prompt_tokens * input_cost) + (completion_tokens * output_cost)


class LangSmithIntegration:
    """Optional LangSmith integration for enhanced analytics."""
    
    def __init__(self, api_key: Optional[str] = None, project_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("LANGSMITH_API_KEY")
        self.project_name = project_name or os.getenv("LANGSMITH_PROJECT", "tesh-query")
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            try:
                from langsmith import Client
                self.client = Client(api_key=self.api_key)
                logger.info("LangSmith integration enabled", project=self.project_name)
            except ImportError:
                logger.warning("LangSmith requested but langsmith package not installed. Run: pip install langsmith")
                self.enabled = False
            except Exception as e:
                logger.warning("Failed to initialize LangSmith client", error=e)
                self.enabled = False
        else:
            self.client = None
    
    def log_run(self, token_usage: TokenUsage, trace_id: Optional[str] = None) -> Optional[str]:
        """Log a run to LangSmith."""
        if not self.enabled:
            return None
        
        try:
            run_data = {
                "name": "tesh-query-llm-call",
                "run_type": "llm",
                "inputs": {
                    "natural_language_query": token_usage.natural_language_query,
                    "model": token_usage.model,
                    "provider": token_usage.provider,
                },
                "outputs": {
                    "generated_sql": token_usage.generated_sql,
                },
                "extra": {
                    "metadata": {
                        "query_id": token_usage.query_id,
                        "session_id": token_usage.session_id,
                        "user_id": token_usage.user_id,
                        "prompt_tokens": token_usage.prompt_tokens,
                        "completion_tokens": token_usage.completion_tokens,
                        "total_tokens": token_usage.total_tokens,
                        "cost_estimate": token_usage.cost_estimate,
                        "execution_time_ms": token_usage.execution_time_ms,
                    }
                },
                "start_time": token_usage.timestamp,
                "end_time": token_usage.timestamp,
            }
            
            if trace_id:
                run_data["trace_id"] = trace_id
            
            run = self.client.create_run(**run_data)
            return str(run.id)
            
        except Exception as e:
            logger.warning("Failed to log run to LangSmith", error=e)
            return None


class TokenTracker:
    """Comprehensive token usage tracking and analytics."""
    
    def __init__(self, 
                 langsmith_api_key: Optional[str] = None,
                 langsmith_project: Optional[str] = None,
                 user_id: Optional[str] = None):
        self.session_id = str(uuid.uuid4())
        self.user_id = user_id or os.getenv("TESH_USER_ID", "anonymous")
        
        # In-memory tracking for current session
        self.current_session_usage: List[TokenUsage] = []
        self.session_start_time = datetime.now()
        
        # LangSmith integration
        self.langsmith = LangSmithIntegration(langsmith_api_key, langsmith_project)
        
        logger.info("Token tracker initialized", session_id=self.session_id, user_id=self.user_id)
    
    def new_session(self, user_id: Optional[str] = None) -> str:
        """Start a new tracking session."""
        # Save current session if it has data
        if self.current_session_usage:
            self._save_session_summary()
        
        # Start new session
        self.session_id = str(uuid.uuid4())
        if user_id:
            self.user_id = user_id
        self.current_session_usage = []
        self.session_start_time = datetime.now()
        
        logger.info("New token tracking session started", session_id=self.session_id, user_id=self.user_id)
        return self.session_id
    
    def track_usage(self,
                   model: str,
                   provider: str,
                   prompt_tokens: int,
                   completion_tokens: int,
                   natural_language_query: Optional[str] = None,
                   generated_sql: Optional[str] = None,
                   execution_time_ms: Optional[float] = None) -> TokenUsage:
        """Track token usage for a query."""
        
        query_id = str(uuid.uuid4())
        total_tokens = prompt_tokens + completion_tokens
        cost_estimate = TokenPricingCalculator.calculate_cost(provider, model, prompt_tokens, completion_tokens)
        
        usage = TokenUsage(
            query_id=query_id,
            session_id=self.session_id,
            user_id=self.user_id,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_estimate=cost_estimate,
            timestamp=datetime.now(),
            natural_language_query=natural_language_query,
            generated_sql=generated_sql,
            execution_time_ms=execution_time_ms,
        )
        
        # Store in current session
        self.current_session_usage.append(usage)
        
        # Log to metrics system
        self._log_to_metrics(usage)
        
        # Log to LangSmith if enabled
        if self.langsmith.enabled:
            self.langsmith.log_run(usage)
        
        # Persistent storage
        self._save_usage_record(usage)
        
        logger.info("Token usage tracked", 
                   query_id=query_id,
                   total_tokens=total_tokens,
                   cost_estimate=f"${cost_estimate:.6f}")
        
        return usage
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session token usage."""
        if not self.current_session_usage:
            return {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "queries": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "start_time": self.session_start_time.isoformat(),
                "duration_minutes": 0,
            }
        
        total_tokens = sum(usage.total_tokens for usage in self.current_session_usage)
        total_cost = sum(usage.cost_estimate or 0 for usage in self.current_session_usage)
        duration = (datetime.now() - self.session_start_time).total_seconds() / 60
        
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "queries": len(self.current_session_usage),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "start_time": self.session_start_time.isoformat(),
            "duration_minutes": round(duration, 2),
            "average_tokens_per_query": round(total_tokens / len(self.current_session_usage), 2),
            "queries_detail": [
                {
                    "query_id": usage.query_id,
                    "tokens": usage.total_tokens,
                    "cost": usage.cost_estimate,
                    "query": usage.natural_language_query[:100] + "..." if usage.natural_language_query and len(usage.natural_language_query) > 100 else usage.natural_language_query,
                    "timestamp": usage.timestamp.isoformat(),
                }
                for usage in self.current_session_usage
            ]
        }
    
    def get_global_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get global token usage summary from metrics."""
        try:
            token_metrics = metrics.get_summary().get("api_tokens_used", {})
            
            if not token_metrics:
                return {
                    "total_tokens": 0,
                    "total_calls": 0,
                    "average_tokens_per_call": 0,
                    "period_days": days,
                    "estimated_total_cost": 0.0,
                }
            
            total_tokens = token_metrics.get("total", 0)
            call_count = token_metrics.get("count", 0)
            avg_tokens = token_metrics.get("avg", 0)
            max_tokens = token_metrics.get("max", 0)
            
            # Rough cost estimate (assuming average pricing)
            estimated_cost = total_tokens * 0.002  # $2 per 1K tokens average
            
            return {
                "total_tokens": total_tokens,
                "total_calls": call_count,
                "average_tokens_per_call": round(avg_tokens, 2),
                "max_tokens_single_call": max_tokens,
                "period_days": days,
                "estimated_total_cost": round(estimated_cost, 4),
            }
            
        except Exception as e:
            logger.error("Failed to get global summary", error=e)
            return {"error": str(e)}
    
    def _log_to_metrics(self, usage: TokenUsage):
        """Log usage to the metrics system."""
        tags = {
            "provider": usage.provider,
            "model": usage.model,
            "user_id": usage.user_id,
            "session_id": usage.session_id,
        }
        
        metrics.increment_counter("api_calls_total", tags=tags)
        metrics.add_point("api_tokens_used", usage.total_tokens, tags=tags)
        metrics.add_point("api_cost_estimate", usage.cost_estimate or 0, tags=tags)
        
        if usage.execution_time_ms:
            metrics.add_point("llm_execution_time_ms", usage.execution_time_ms, tags=tags)
    
    def _save_usage_record(self, usage: TokenUsage):
        """Save usage record to persistent storage."""
        try:
            # Create logs directory if it doesn't exist
            logs_dir = "logs"
            os.makedirs(logs_dir, exist_ok=True)
            
            # Save to daily log file
            date_str = usage.timestamp.strftime("%Y-%m-%d")
            log_file = f"{logs_dir}/token_usage_{date_str}.jsonl"
            
            with open(log_file, "a") as f:
                f.write(json.dumps(asdict(usage), default=str) + "\n")
                
        except Exception as e:
            logger.warning("Failed to save token usage record", error=e)
    
    def _save_session_summary(self):
        """Save session summary to persistent storage."""
        try:
            if not self.current_session_usage:
                return
                
            summary = SessionSummary(
                session_id=self.session_id,
                user_id=self.user_id,
                start_time=self.session_start_time,
                end_time=datetime.now(),
                total_queries=len(self.current_session_usage),
                total_tokens=sum(usage.total_tokens for usage in self.current_session_usage),
                total_cost_estimate=sum(usage.cost_estimate or 0 for usage in self.current_session_usage),
                queries=[usage.query_id for usage in self.current_session_usage],
            )
            
            # Create logs directory if it doesn't exist
            logs_dir = "logs"
            os.makedirs(logs_dir, exist_ok=True)
            
            # Save session summary
            log_file = f"{logs_dir}/session_summaries.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(asdict(summary), default=str) + "\n")
                
        except Exception as e:
            logger.warning("Failed to save session summary", error=e)


# Global token tracker instance
_global_tracker: Optional[TokenTracker] = None


def get_token_tracker(
    langsmith_api_key: Optional[str] = None,
    langsmith_project: Optional[str] = None,
    user_id: Optional[str] = None,
    force_new: bool = False
) -> TokenTracker:
    """Get or create the global token tracker instance."""
    global _global_tracker
    
    if _global_tracker is None or force_new:
        _global_tracker = TokenTracker(langsmith_api_key, langsmith_project, user_id)
    
    return _global_tracker


@contextmanager
def track_llm_call(
    model: str,
    provider: str,
    natural_language_query: Optional[str] = None,
    user_id: Optional[str] = None,
    langsmith_api_key: Optional[str] = None,
):
    """
    Context manager to track LLM API calls with automatic token extraction.
    
    Usage:
        with track_llm_call("gemini-2.0-flash-lite", "google", "show me users") as tracker:
            response = llm.invoke(messages)
            # Token usage will be automatically tracked
            tracker.set_response(response, generated_sql="SELECT * FROM users")
    """
    tracker = get_token_tracker(langsmith_api_key=langsmith_api_key, user_id=user_id)
    start_time = time.time()
    
    class CallTracker:
        def __init__(self):
            self.response = None
            self.generated_sql = None
            
        def set_response(self, response, generated_sql: Optional[str] = None):
            self.response = response
            self.generated_sql = generated_sql
            
        def track_usage(self, prompt_tokens: int, completion_tokens: int):
            execution_time_ms = (time.time() - start_time) * 1000
            return tracker.track_usage(
                model=model,
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                natural_language_query=natural_language_query,
                generated_sql=self.generated_sql,
                execution_time_ms=execution_time_ms,
            )
    
    call_tracker = CallTracker()
    
    try:
        yield call_tracker
        
        # Auto-track if response is set and has usage info
        if hasattr(call_tracker.response, 'usage_metadata'):
            usage = call_tracker.response.usage_metadata
            call_tracker.track_usage(
                prompt_tokens=usage.get('input_tokens', 0),
                completion_tokens=usage.get('output_tokens', 0)
            )
        
    except Exception as e:
        logger.error("Error in LLM call tracking", error=e)
        raise