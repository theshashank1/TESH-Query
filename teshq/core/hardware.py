"""
Hardware Detection & Recommendation Engine for TESH-Query.

Profiles the system (CPU cores, total RAM, GPU VRAM, OS platform)
to recommend the optimal GGUF quantization model and llama.cpp offload settings.
"""

import os
import sys
import subprocess
import platform
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class HardwareProfile:
    cpu_cores: int                 # Physical/logical cores
    ram_total_gb: float            # Total system RAM in GB
    ram_available_gb: float        # Approximate available RAM in GB
    gpu_name: Optional[str]        # GPU model name if present
    gpu_vram_mb: int               # GPU VRAM in MB (0 if CPU only)
    gpu_backend: str               # "cuda" | "metal" | "cpu" | "vulkan"
    recommended_quant: str         # "Q4_K_M" | "Q5_K_M" | "Q8_0"
    recommended_n_gpu_layers: int  # Offload layers suggestion (e.g. 0 to 99)
    recommended_n_ctx: int         # Recommended context length (e.g. 2048, 4096)

def _get_ram_info() -> Tuple[float, float]:
    """Get total and available RAM in GB with cross-platform fallbacks."""
    total_gb = 8.0  # Safe defaults
    available_gb = 4.0
    
    # Try importing psutil if installed
    try:
        import psutil
        mem = psutil.virtual_memory()
        return mem.total / (1024 ** 3), mem.available / (1024 ** 3)
    except ImportError:
        pass

    try:
        if sys.platform == "win32":
            # Use systeminfo or wmic on Windows
            out = subprocess.check_output(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"], 
                text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if line.strip() and line.strip().isdigit():
                    total_bytes = int(line.strip())
                    total_gb = total_bytes / (1024 ** 3)
                    available_gb = total_gb * 0.5  # Guestimate 50% available
                    break
        elif sys.platform == "darwin":
            # macOS sysctl
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL)
            total_bytes = int(out.strip())
            total_gb = total_bytes / (1024 ** 3)
            # Find free pages via vm_stat if possible
            available_gb = total_gb * 0.5
        else:
            # Linux /proc/meminfo
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                        total_gb = total_kb / (1024 * 1024)
                    elif line.startswith("MemAvailable:"):
                        avail_kb = int(line.split()[1])
                        available_gb = avail_kb / (1024 * 1024)
    except Exception:
        pass
        
    return total_gb, available_gb

def _detect_gpu() -> Tuple[Optional[str], int, str]:
    """
    Detect GPU and return (gpu_name, gpu_vram_mb, gpu_backend).
    Supports CUDA (NVIDIA), Metal (Apple Silicon), and CPU fallback.
    """
    gpu_name = None
    gpu_vram_mb = 0
    gpu_backend = "cpu"
    
    # 1. Check macOS (Metal)
    if sys.platform == "darwin":
        # Check if Apple Silicon (M1/M2/M3/M4)
        machine = platform.machine()
        if machine.startswith("arm") or machine.startswith("aarch"):
            gpu_name = "Apple Silicon GPU"
            # In unified memory, we can use up to ~70% of system memory for VRAM
            total_ram, _ = _get_ram_info()
            gpu_vram_mb = int(total_ram * 1024 * 0.7)
            gpu_backend = "metal"
            return gpu_name, gpu_vram_mb, gpu_backend

    # 2. Check NVIDIA via nvidia-smi
    try:
        # Query GPU name and VRAM in MB
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL
        )
        if out.strip():
            parts = out.strip().split(",")
            gpu_name = parts[0].strip()
            gpu_vram_mb = int(parts[1].strip())
            gpu_backend = "cuda"
            return gpu_name, gpu_vram_mb, gpu_backend
    except Exception:
        pass
        
    # Future fallbacks: ROCm, Vulkan could be queried if needed.
    return gpu_name, gpu_vram_mb, gpu_backend

def recommend_quant(ram_gb: float, vram_mb: int) -> str:
    """Recommend quantization level based on memory constraints."""
    if vram_mb >= 8000 or ram_gb >= 24:
        return "Q8_0"
    elif vram_mb >= 4000 or ram_gb >= 12:
        return "Q5_K_M"
    else:
        return "Q4_K_M"

def recommend_gpu_layers(gpu_backend: str, vram_mb: int, model_size_gb: float = 3.0) -> int:
    """Recommend number of layers to offload to GPU."""
    if gpu_backend == "cpu" or vram_mb == 0:
        return 0
    
    # For sub-4B models (e.g. Qwen 3B/4B), there are usually ~30-40 layers.
    # Total model size in VRAM is ~2.5 - 3.5 GB.
    # If we have Apple Silicon (Metal) or CUDA with at least 4GB VRAM, offload everything.
    if gpu_backend == "metal":
        return 99  # Let Metal driver handle unified memory allocation
        
    # For CUDA, check if we have enough headroom
    required_mb = (model_size_gb * 1024) + 1024  # Model size + context/KV cache overhead
    if vram_mb >= required_mb:
        return 99  # All layers
    elif vram_mb >= 2000:
        # Partial offloading
        return 16
    return 0

def detect_hardware() -> HardwareProfile:
    """Analyze host hardware and recommend parameters for local inference."""
    cpu_cores = os.cpu_count() or 4
    # Attempt to get physical cores if psutil is available
    try:
        import psutil
        cpu_cores = psutil.cpu_count(logical=False) or cpu_cores
    except Exception:
        pass
        
    ram_total, ram_avail = _get_ram_info()
    gpu_name, gpu_vram, gpu_backend = _detect_gpu()
    
    # Determine recommendations
    recommended_quant = recommend_quant(ram_total, gpu_vram)
    recommended_layers = recommend_gpu_layers(gpu_backend, gpu_vram)
    
    # Context window recommendations
    # If low RAM, default to 2048 to save memory. Otherwise 4096.
    recommended_ctx = 2048 if ram_total < 10 else 4096
    
    return HardwareProfile(
        cpu_cores=cpu_cores,
        ram_total_gb=round(ram_total, 2),
        ram_available_gb=round(ram_avail, 2),
        gpu_name=gpu_name,
        gpu_vram_mb=gpu_vram,
        gpu_backend=gpu_backend,
        recommended_quant=recommended_quant,
        recommended_n_gpu_layers=recommended_layers,
        recommended_n_ctx=recommended_ctx,
    )
