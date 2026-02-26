"""
Token Estimation for TESH-Query v2.

Estimates prompt token count before sending to the LLM to allow schema
pruning when prompts would be excessively large.
"""


# Approximate characters-per-token ratio for most LLMs (conservative estimate)
_CHARS_PER_TOKEN = 4

# Default token threshold above which schema should be further pruned
DEFAULT_TOKEN_THRESHOLD = 2000


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in *text* using a character-ratio heuristic.

    This is not exact but avoids requiring a tokenizer dependency.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count (integer).
    """
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


def exceeds_threshold(text: str, threshold: int = DEFAULT_TOKEN_THRESHOLD) -> bool:
    """
    Return True if the estimated token count of *text* exceeds *threshold*.

    Args:
        text: The text to check.
        threshold: Token count limit.

    Returns:
        True if estimated tokens > threshold, False otherwise.
    """
    return estimate_tokens(text) > threshold
