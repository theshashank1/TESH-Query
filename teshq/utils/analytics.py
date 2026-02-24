import datetime
import json
import sys  # Added for writing warnings to stderr
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

# Define the path for the metrics file. Using .jsonl for line-separated JSON objects is efficient for append-only logs.
METRICS_FILE = Path("usage_metrics.jsonl")

# Fallback dictionary for common models
# Prices are per 1 Million Tokens (Input Cost, Output Cost)
# These values can get out of date, but serve as a good fallback.
_STATIC_MODEL_COSTS = {
    # Prices per 1 Million Tokens (Input, Output)
    "google": {
        "gemini-1.5-flash": (0.35, 1.05),
        "gemini-1.5-pro": (3.50, 10.50),
        "gemini-2.5-flash": (0.30, 2.50),
    },
    "openai": {
        "gpt-4o": (5.00, 15.00),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-3.5-turbo": (0.50, 1.50),
    },
}


def _get_model_cost(provider: str, model: str) -> Tuple[float, float]:
    """
    Fetches the latest cost for a given model from the Helicone API
    with a local fallback for common models.

    This function sends a request to the Helicone cost management API to get
    up-to-date pricing. If the API call fails, it will attempt to
    find the model in a static, hard-coded list.

    Args:
        provider: The provider of the LLM (e.g., 'google', 'openai').
        model: The specific model name (e.g., 'gemini-1.5-flash', 'gpt-4').

    Returns:
        A tuple containing the input cost per 1 million tokens and the output
        cost per 1 million tokens. Returns (0.0, 0.0) if the model
        is not found in the API or the static fallback.
    """
    url = f"https://www.helicone.ai/api/llm-costs?provider={provider}&model={model}"
    try:
        response = requests.get(url, timeout=2)  # Added a 2-second timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (e.g., 404, 500)
        data = response.json()

        # Ensure the response is a list with at least one element
        if data and isinstance(data, list) and data[0]:
            input_cost = float(data[0].get("input_cost_per_1m", 0.0))
            output_cost = float(data[0].get("output_cost_per_1m", 0.0))
            return input_cost, output_cost

    except (requests.RequestException, ValueError, KeyError, IndexError):
        # If the API call fails or the model is not found, try the static list
        sys.stderr.write(f"Warning: Helicone API request failed for {provider}/{model}. " f"Attempting static fallback.\n")

        fallback_prices = _STATIC_MODEL_COSTS.get(provider, {}).get(model)
        if fallback_prices:
            return fallback_prices  # Return (input_cost, output_cost) from static dict

        # If the API call fails AND it's not in the static list, default to zero cost.
        return 0.0, 0.0

    return 0.0, 0.0


def track_llm_usage(model: str, input_tokens: int, output_tokens: int, provider: str = "google"):
    """
    Records an LLM usage event, including a dynamically calculated cost.

    This function captures key details about each LLM interaction, calculates the
    associated cost by fetching real-time data, and then stores the complete
    event as a JSON object in the metrics log file.

    Args:
        model: The identifier of the language model used.
        input_tokens: The number of tokens in the input prompt.
        output_tokens: The number of tokens in the model's generated output.
        provider: The provider of the LLM (defaults to 'google').
    """
    # Fetch real-time cost data and calculate the cost for the current call
    input_cost_per_1m, output_cost_per_1m = _get_model_cost(provider, model)
    input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
    output_cost = (output_tokens / 1_000_000) * output_cost_per_1m
    total_cost = input_cost + output_cost

    metric = {
        # Use datetime.timezone.utc to create a timezone-aware datetime
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": "llm_usage",
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost": total_cost,
    }

    # Append the metric as a new line to the file, ensuring thread-safe appends
    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(metric) + "\n")


def track_feature_usage(feature_name: str, properties: Dict[str, Any] = None):
    """
    Records a feature usage event to the metrics log file.

    This is used to track when specific features or commands in the application
    are used. It helps in understanding user engagement and feature popularity.

    Args:
        feature_name: The name of the feature that was used.
        properties: An optional dictionary for additional context-specific
                    information about the event.
    """
    if properties is None:
        properties = {}

    metric = {
        # Use datetime.timezone.utc to create a timezone-aware datetime
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": "feature_usage",
        "feature_name": feature_name,
        "properties": properties,
    }

    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(metric) + "\n")


def get_usage_metrics() -> List[Dict[str, Any]]:
    """
    Reads and returns all usage metrics from the log file.

    This function safely reads the metrics file, parsing each line as a
    separate JSON object. It is designed to be resilient, handling cases where
    the file might not exist or contains corrupted/empty lines.

    Returns:
        A list of dictionaries, where each dictionary represents a recorded
        metric event. Returns an empty list if the file doesn't exist.
    """
    if not METRICS_FILE.exists():
        return []

    metrics = []
    with open(METRICS_FILE, "r") as f:
        for line in f:
            # Skip empty or whitespace-only lines
            if not line.strip():
                continue
            try:
                metrics.append(json.loads(line))
            except json.JSONDecodeError:
                # For robustness, skip any line that is not valid JSON.
                # In a production system, you might want to log this error.
                pass
    return metrics
