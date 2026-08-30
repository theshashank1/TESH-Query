"""
Unit tests for the local GGUF LLM backend in TESH-Query.

Mocks the llama-cpp-python C-bindings dependency to run safely in any environment.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock llama_cpp module in sys.modules to prevent ModuleNotFoundError during patching
mock_llama_cpp = MagicMock()
sys.modules['llama_cpp'] = mock_llama_cpp

from teshq.core.hardware import detect_hardware, recommend_quant, recommend_gpu_layers
from teshq.core.inference import InferenceRuntime, InferenceConfig
from teshq.core.grammar import get_sql_grammar
from teshq.core.model_manager import ModelManager, REGISTRY


class TestHardwareDetection(unittest.TestCase):
    """Test CPU, RAM, and GPU detection heuristics."""
    
    def test_recommend_quant(self):
        # High-end systems get Q8
        self.assertEqual(recommend_quant(ram_gb=32, vram_mb=8000), "Q8_0")
        # Mid-range systems get Q5
        self.assertEqual(recommend_quant(ram_gb=16, vram_mb=4000), "Q5_K_M")
        # Low-end systems get Q4
        self.assertEqual(recommend_quant(ram_gb=8, vram_mb=0), "Q4_K_M")

    def test_recommend_gpu_layers(self):
        # CPU only offloads 0 layers
        self.assertEqual(recommend_gpu_layers("cpu", vram_mb=0), 0)
        # Metal offloads all layers (using 99 as flag)
        self.assertEqual(recommend_gpu_layers("metal", vram_mb=8000), 99)
        # CUDA with enough VRAM offloads all layers
        self.assertEqual(recommend_gpu_layers("cuda", vram_mb=6000, model_size_gb=3.0), 99)
        # CUDA with low VRAM offloads partial layers
        self.assertEqual(recommend_gpu_layers("cuda", vram_mb=2048, model_size_gb=3.0), 16)

    def test_detect_hardware(self):
        profile = detect_hardware()
        self.assertIsNotNone(profile.cpu_cores)
        self.assertGreater(profile.ram_total_gb, 0)
        self.assertIn(profile.gpu_backend, ["cpu", "cuda", "metal"])


class TestInferenceRuntime(unittest.TestCase):
    """Test direct in-process llama.cpp runner (mocked Llama C-bindings)."""
    
    @patch('llama_cpp.Llama')
    def test_runtime_lifecycle(self, mock_llama_cls):
        # Setup mock instance
        mock_llama = MagicMock()
        mock_llama_cls.return_value = mock_llama
        
        # Mock completion response
        mock_llama.create_completion.return_value = {
            "choices": [{"text": "SELECT * FROM users;"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        
        runtime = InferenceRuntime()
        config = InferenceConfig(model_path="dummy_path.gguf")
        
        # Test load
        with patch('os.path.exists', return_value=True):
            runtime.load(config)
            self.assertTrue(runtime.is_loaded)
            self.assertEqual(runtime.config, config)
            
            # Test generate (without system prompt -> raw completion)
            res = runtime.generate("Show all users")
            self.assertEqual(res.text, "SELECT * FROM users;")
            self.assertEqual(res.prompt_tokens, 10)
            self.assertEqual(res.completion_tokens, 5)
            
            # Test unload
            runtime.unload()
            self.assertFalse(runtime.is_loaded)


class TestGrammarLoader(unittest.TestCase):
    """Test SQL GBNF grammar parser caching."""
    
    @patch('llama_cpp.LlamaGrammar')
    def test_grammar_compilation(self, mock_grammar_cls):
        mock_grammar = MagicMock()
        mock_grammar_cls.from_file.return_value = mock_grammar
        
        # Compiles and returns object
        grammar = get_sql_grammar()
        self.assertIsNotNone(grammar)


class TestModelManager(unittest.TestCase):
    """Test local GGUF registry and safety warnings."""
    
    def test_registry_metadata(self):
        # We should have qwen3b in registry
        self.assertIn("qwen3b-coder", REGISTRY)
        info = REGISTRY["qwen3b-coder"]
        self.assertEqual(info["required_ram_gb"], 8)

    @patch('teshq.core.model_manager.detect_hardware')
    def test_compatibility_warning(self, mock_detect):
        # Mock low RAM (4GB)
        mock_profile = MagicMock()
        mock_profile.ram_total_gb = 4.0
        mock_profile.ram_available_gb = 1.5
        mock_detect.return_value = mock_profile
        
        manager = ModelManager()
        # Qwen 3B Coder needs 8GB RAM, so it should trigger warning (is_compat = False)
        is_compat, warn_msg = manager.check_compatibility("qwen3b-coder")
        self.assertFalse(is_compat)
        self.assertIn("WARNING: This model ('qwen3b-coder') requires at least 8GB", warn_msg)
        
        # Mock high RAM (16GB)
        mock_profile.ram_total_gb = 16.0
        is_compat, warn_msg = manager.check_compatibility("qwen3b-coder")
        self.assertTrue(is_compat)
        self.assertEqual(warn_msg, "")
