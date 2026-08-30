"""
Model Manager for local GGUF models in TESH-Query.

Handles downloading models from Hugging Face, tracking installed models,
verifying system compatibility, and issuing safety warnings.
"""

import os
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from teshq.core.hardware import detect_hardware
from teshq.utils.logging import logger

MODELS_DIR = Path.home() / ".teshq" / "models"

REGISTRY = {
    "qwen1.5b-coder": {
        "repo": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "file": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        "size_gb": 1.2,
        "required_ram_gb": 6,
        "description": "Ultra-lightweight, runs on low-end systems (1.5B parameter, 4-bit quant)"
    },
    "qwen3b-coder": {
        "repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
        "file": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "size_gb": 2.2,
        "required_ram_gb": 8,
        "description": "Recommended for most systems (3B parameter, 4-bit quant)"
    },
    "qwen7b-coder": {
        "repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "size_gb": 4.7,
        "required_ram_gb": 16,
        "description": "Higher accuracy, recommended for 16GB+ RAM (7B parameter, 4-bit quant)"
    }
}

class ModelManager:
    """Manages local GGUF files in ~/.teshq/models/"""
    
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def get_installed_models(self) -> List[Dict[str, Any]]:
        """List all GGUF files in the models directory."""
        installed = []
        if not self.models_dir.exists():
            return installed
            
        for file in os.listdir(self.models_dir):
            if file.endswith(".gguf"):
                path = self.models_dir / file
                size_gb = path.stat().st_size / (1024 ** 3)
                
                # Check if it matches a registry model
                registry_name = "custom"
                desc = "User-supplied custom GGUF model"
                for name, info in REGISTRY.items():
                    if info["file"] == file:
                        registry_name = name
                        desc = info["description"]
                        break
                        
                installed.append({
                    "name": registry_name,
                    "filename": file,
                    "path": str(path),
                    "size_gb": round(size_gb, 2),
                    "description": desc
                })
        return installed

    def check_compatibility(self, model_name: str) -> Tuple[bool, str]:
        """
        Check if the selected model is compatible with the host system resources.
        Returns (is_compatible, warning_message).
        """
        hw = detect_hardware()
        
        if model_name not in REGISTRY:
            # For custom models, make a general guess based on file size if known
            return True, ""
            
        model_info = REGISTRY[model_name]
        req_ram = model_info["required_ram_gb"]
        
        if hw.ram_total_gb < req_ram:
            msg = (
                f"⚠️ WARNING: This model ('{model_name}') requires at least {req_ram}GB of system RAM.\n"
                f"Your system has {hw.ram_total_gb:.1f}GB total RAM ({hw.ram_available_gb:.1f}GB available).\n"
                f"Running this model may cause severe slowdowns, out-of-memory errors, or system instability.\n"
                f"TESHQ is not liable for system crashes or data loss resulting from resource exhaustion."
            )
            return False, msg
            
        return True, ""

    def download_model(self, name_or_repo: str, filename: Optional[str] = None, progress_callback = None) -> str:
        """
        Download a GGUF model from Hugging Face.
        Returns the absolute local path to the downloaded model.
        """
        # Resolve registry name
        if name_or_repo in REGISTRY:
            model_info = REGISTRY[name_or_repo]
            repo = model_info["repo"]
            file = model_info["file"]
        else:
            # Custom download
            if not filename:
                raise ValueError("Filename must be specified for custom Hugging Face downloads.")
            repo = name_or_repo
            file = filename

        url = f"https://huggingface.co/{repo}/resolve/main/{file}"
        dest_path = self.models_dir / file

        logger.info(f"Downloading from {url} to {dest_path}...")
        
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch model from HF. HTTP Status: {response.status_code}. "
                "Verify the repository and filename are correct."
            )
            
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024 * 1024  # 1MB
        
        downloaded = 0
        with open(dest_path, "wb") as f:
            for data in response.iter_content(block_size):
                f.write(data)
                downloaded += len(data)
                if progress_callback:
                    progress_callback(downloaded, total_size)
                    
        return str(dest_path)

    def delete_model(self, filename: str) -> bool:
        """Delete a local GGUF model file."""
        target_path = self.models_dir / filename
        if target_path.exists() and target_path.suffix == ".gguf":
            target_path.unlink()
            logger.success(f"Deleted local GGUF model: {filename}")
            return True
        return False
