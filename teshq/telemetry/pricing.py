"""
Token pricing for Google Gemini and Azure OpenAI.

Prices are per 1,000 tokens (input/output).
These are estimates — always check the official pricing pages:
  • Google Gemini: https://ai.google.dev/gemini-api/docs/pricing
  • Azure OpenAI:  https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/
  • Azure AI Foundry MaaS: https://ai.azure.com (model-specific, see Marketplace tab)
"""
from typing import Optional


GOOGLE_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
AZURE_PRICING_URL = "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/"
AZURE_MAAS_PRICING_URL = "https://ai.azure.com"


class TokenPricingCalculator:
    """Estimate costs for Google Gemini and Azure OpenAI models."""

    PRICING_MAP = {
        "google": {
            # Gemini 2.5 (current generation)
            "gemini-2.5-pro":           {"input": 1.25 / 1000, "output": 10.0 / 1000},
            "gemini-2.5-flash":         {"input": 0.15 / 1000, "output": 0.60 / 1000},
            "gemini-2.5-flash-lite":    {"input": 0.075 / 1000, "output": 0.30 / 1000},
            # Gemini 2.0 (stable)
            "gemini-2.0-flash":         {"input": 0.10 / 1000, "output": 0.40 / 1000},
            "gemini-2.0-flash-lite":    {"input": 0.075 / 1000, "output": 0.30 / 1000},
            # Gemini 1.5 (legacy)
            "gemini-1.5-pro":           {"input": 1.25 / 1000, "output": 5.00 / 1000},
            "gemini-1.5-flash":         {"input": 0.075 / 1000, "output": 0.30 / 1000},
        },
        "azure": {
            # Azure OpenAI standard deployments
            "gpt-4o":                   {"input": 2.50 / 1000, "output": 10.00 / 1000},
            "gpt-4o-mini":              {"input": 0.15 / 1000, "output": 0.60 / 1000},
            "gpt-4.1":                  {"input": 2.00 / 1000, "output": 8.00 / 1000},
            "gpt-4.1-mini":             {"input": 0.40 / 1000, "output": 1.60 / 1000},
            "gpt-4.1-nano":             {"input": 0.10 / 1000, "output": 0.40 / 1000},
            # Azure AI Foundry MaaS / Serverless
            "Kimi-K2.6":                {"input": 0.14 / 1000, "output": 0.55 / 1000},
            "Kimi-K2":                  {"input": 0.14 / 1000, "output": 0.55 / 1000},
            "Meta-Llama-3.1-405B-Instruct": {"input": 0.533 / 1000, "output": 1.60 / 1000},
            "Meta-Llama-3.3-70B-Instruct":  {"input": 0.23 / 1000, "output": 0.40 / 1000},
            "Mistral-Large-2411":       {"input": 2.00 / 1000, "output": 6.00 / 1000},
            "Phi-4":                    {"input": 0.125 / 1000, "output": 0.50 / 1000},
            "DeepSeek-R1":              {"input": 0.55 / 1000, "output": 2.19 / 1000},
            "DeepSeek-V3-0324":         {"input": 0.27 / 1000, "output": 1.10 / 1000},
        },
    }

    @classmethod
    def calculate_cost(
        cls,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Optional[float]:
        """
        Calculate estimated cost for token usage.
        Returns None for unknown models.
        """
        provider_pricing = cls.PRICING_MAP.get(provider.lower(), {})
        model_pricing = provider_pricing.get(model)

        if not model_pricing:
            # Try case-insensitive match
            for key, val in provider_pricing.items():
                if key.lower() == model.lower():
                    model_pricing = val
                    break

        if not model_pricing:
            return None  # Unknown model — do not guess

        return (prompt_tokens * model_pricing["input"]) + (completion_tokens * model_pricing["output"])

    @classmethod
    def get_pricing_url(cls, provider: str) -> str:
        """Return the official pricing page URL for the given provider."""
        if provider.lower() == "google":
            return GOOGLE_PRICING_URL
        return AZURE_PRICING_URL
