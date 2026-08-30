"""
In-Process Local LLM Inference Runtime for TESH-Query.

Loads GGUF models directly into the Python process address space using llama-cpp-python.
No HTTP server, no subprocesses — just direct C/C++ library bindings.
"""

import time
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Iterator, Union
from teshq.utils.logging import logger

@dataclass
class InferenceConfig:
    model_path: str
    n_ctx: int = 4096
    n_gpu_layers: int = -1  # -1 = auto-detect and offload
    n_threads: int = 0      # 0 = auto-detect physical CPU cores
    seed: int = 42
    verbose: bool = False

@dataclass
class GenerationResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float

class InferenceRuntime:
    """
    Manages the lifecycle of a local llama.cpp model in-process.
    
    This acts as a singleton-ish cache per process so that the model
    remains resident in memory for successive queries.
    """
    def __init__(self) -> None:
        self._llm = None
        self._config: Optional[InferenceConfig] = None
        self._loaded: bool = False

    def load(self, config: InferenceConfig) -> None:
        """
        Dynamically imports llama-cpp-python and loads the GGUF model into memory.
        """
        if self._loaded and self._config == config:
            return  # Model already loaded with identical config
            
        self.unload()
        
        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise ImportError(
                "The 'llama-cpp-python' library is not installed.\n"
                "Please install it using: pip install teshq[local]\n"
                "Or set up llama-cpp-python manually for your hardware platform (CUDA/Metal/CPU)."
            ) from e

        if not config.model_path or not os.path.exists(config.model_path):
            raise FileNotFoundError(
                f"Local GGUF model not found at path: '{config.model_path}'. "
                "Please configure a valid path or run 'teshq pull' first."
            )

        logger.info(f"Loading local GGUF model from {config.model_path}...")
        start_time = time.time()
        
        # Determine gpu layers & thread count dynamically if set to auto
        n_gpu = config.n_gpu_layers
        if n_gpu == -1:
            from teshq.core.hardware import detect_hardware
            hw = detect_hardware()
            n_gpu = hw.recommended_n_gpu_layers
            logger.info(f"Auto-detected GPU offload: using {n_gpu} layers ({hw.gpu_backend.upper()})")
            
        n_threads = config.n_threads
        if n_threads == 0:
            from teshq.core.hardware import detect_hardware
            hw = detect_hardware()
            n_threads = max(1, hw.cpu_cores - 1)
            logger.info(f"Auto-detected threads: using {n_threads} CPU cores")

        # Initialize Llama
        try:
            self._llm = Llama(
                model_path=config.model_path,
                n_ctx=config.n_ctx,
                n_gpu_layers=n_gpu,
                n_threads=n_threads,
                seed=config.seed,
                verbose=config.verbose,
            )
            self._config = config
            self._loaded = True
            elapsed = (time.time() - start_time) * 1000
            logger.success(f"GGUF model loaded successfully in {elapsed:.2f} ms")
        except Exception as e:
            logger.error(f"Failed to load GGUF model: {e}")
            self.unload()
            raise

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.0,
        grammar: Optional[Any] = None,
        stop: Optional[List[str]] = None,
    ) -> GenerationResult:
        """
        Runs deterministic token inference on the loaded model.
        """
        if not self._loaded or not self._llm:
            raise RuntimeError("InferenceRuntime is not loaded. Call load() first.")
            
        start_time = time.time()
        
        # Prepare parameters
        stop_words = stop or []
        
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                grammar=grammar,
                stop=stop_words,
            )
            
            choice = response["choices"][0]
            text = choice["message"]["content"]
            usage = response["usage"]
            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage["completion_tokens"]
            total_tokens = usage["total_tokens"]
        else:
            # Use raw completion if no system prompt is provided
            response = self._llm.create_completion(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                grammar=grammar,
                stop=stop_words,
            )
            
            choice = response["choices"][0]
            text = choice["text"]
            usage = response["usage"]
            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage["completion_tokens"]
            total_tokens = usage["total_tokens"]

        latency = (time.time() - start_time) * 1000
        
        return GenerationResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
        )

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.0,
        grammar: Optional[Any] = None,
        stop: Optional[List[str]] = None,
    ) -> Iterator[str]:
        """
        Streams generated tokens one by one (useful for future chat UI).
        """
        if not self._loaded or not self._llm:
            raise RuntimeError("InferenceRuntime is not loaded. Call load() first.")
            
        stop_words = stop or []
        
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            stream = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                grammar=grammar,
                stop=stop_words,
                stream=True
            )
            
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
        else:
            stream = self._llm.create_completion(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                grammar=grammar,
                stop=stop_words,
                stream=True
            )
            
            for chunk in stream:
                yield chunk["choices"][0]["text"]

    def unload(self) -> None:
        """
        Frees memory resources by garbage-collecting the llama.cpp model context.
        """
        if self._llm:
            # Force close and clear
            del self._llm
            self._llm = None
        self._config = None
        self._loaded = False
        logger.info("Local GGUF model unloaded from memory.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def config(self) -> Optional[InferenceConfig]:
        return self._config
