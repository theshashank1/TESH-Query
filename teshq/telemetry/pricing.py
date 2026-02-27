"""
Token pricing and cost calculation for different LLM providers and models.
"""

class TokenPricingCalculator:
    """Calculate estimated costs for different LLM providers and models."""
    
    # Pricing per 1K tokens (updated for 2024-2025 rates).
    # Input/output costs sourced from official provider pricing pages.
    PRICING_MAP = {
        "google": {
            # Gemini 2.x (current generation)
            "gemini-2.0-flash-lite": {"input": 0.075 / 1000, "output": 0.30 / 1000},
            "gemini-2.0-flash": {"input": 0.10 / 1000, "output": 0.40 / 1000},
            "gemini-2.5-pro": {"input": 1.25 / 1000, "output": 10.0 / 1000},
            # Gemini 1.x (legacy, still supported)
            "gemini-1.5-flash": {"input": 0.075 / 1000, "output": 0.30 / 1000},
            "gemini-1.5-pro": {"input": 1.25 / 1000, "output": 5.00 / 1000},
        },
        "openai": {
            # GPT-4o family (current generation)
            "gpt-4o": {"input": 2.50 / 1000, "output": 10.00 / 1000},
            "gpt-4o-mini": {"input": 0.15 / 1000, "output": 0.60 / 1000},
            # Legacy models
            "gpt-4-turbo": {"input": 10.00 / 1000, "output": 30.00 / 1000},
            "gpt-3.5-turbo": {"input": 0.50 / 1000, "output": 1.50 / 1000},
        },
        "anthropic": {
            # Claude 3.5 family (current generation)
            "claude-3-5-sonnet": {"input": 3.00 / 1000, "output": 15.00 / 1000},
            "claude-3-5-haiku": {"input": 0.80 / 1000, "output": 4.00 / 1000},
            # Claude 3 family (legacy)
            "claude-3-haiku": {"input": 0.25 / 1000, "output": 1.25 / 1000},
        },
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
