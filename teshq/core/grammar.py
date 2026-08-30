"""
SQL GBNF Grammar Loader for TESH-Query.

Loads and compiles the context-free SQL grammar from sql_grammar.gbnf
for use with llama-cpp-python to enforce syntactically correct SQL output.
"""

import os
from pathlib import Path
from teshq.utils.logging import logger

_GRAMMAR_PATH = Path(__file__).parent / "sql_grammar.gbnf"
_cached_grammar = None

def get_sql_grammar():
    """
    Load and compile the SQL GBNF grammar.
    
    Returns:
        LlamaGrammar object if llama_cpp is installed and grammar is valid, else None.
    """
    global _cached_grammar
    if _cached_grammar is not None:
        return _cached_grammar
        
    try:
        from llama_cpp import LlamaGrammar
    except ImportError:
        # Graceful fallback: do not crash on import if only cloud provider is used.
        logger.debug("llama-cpp-python is not installed. Local SQL GBNF grammar will not be loaded.")
        return None
        
    if not _GRAMMAR_PATH.exists():
        logger.error(f"SQL GBNF grammar file not found at {_GRAMMAR_PATH}")
        return None
        
    try:
        logger.info(f"Compiling SQL GBNF grammar from {_GRAMMAR_PATH}...")
        _cached_grammar = LlamaGrammar.from_file(str(_GRAMMAR_PATH))
        return _cached_grammar
    except Exception as e:
        logger.error(f"Failed to compile GBNF SQL grammar: {e}")
        _cached_grammar = None  # Don't cache a broken grammar
        return None
