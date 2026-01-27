"""
Utility functions extracted from ai-worker for testability.
This module contains functions that don't require vLLM import.
"""
import os


def get_gpu_memory_gb():
    """
    Detect GPU VRAM in GB using nvidia-smi or pynvml.
    Returns None if no GPU is detected.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Get first GPU's memory (in MB), convert to GB
            memory_mb = int(result.stdout.strip().split('\n')[0])
            memory_gb = memory_mb / 1024
            return memory_gb
    except Exception as e:
        print(f"⚠️  Failed to detect GPU memory via nvidia-smi: {e}")
    
    # Fallback: try pynvml
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        memory_gb = info.total / (1024 ** 3)
        pynvml.nvmlShutdown()
        return memory_gb
    except Exception as e:
        print(f"⚠️  Failed to detect GPU memory via pynvml: {e}")
    
    return None


def select_model_by_vram(vram_gb):
    """
    Select appropriate model based on available GPU VRAM.
    Returns (model_name, quantization, max_model_len)
    """
    # Model configurations by VRAM tier (English-focused Llama models)
    # Format: (min_vram, model_name, quantization, max_model_len)
    model_configs = [
        # 24GB+ (RTX 3090, 4090, A5000, etc.)
        (20, "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4", "awq", 8192),
        # 12-24GB (RTX 4070, 3080 Ti, etc.)
        (10, "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "awq", 8192),
        # 8-12GB (RTX 3070, 4060 Ti, etc.)
        (6, "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "awq", 4096),
        # Below 8GB - use smaller context
        (0, "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "awq", 2048),
    ]
    
    for min_vram, model, quant, max_len in model_configs:
        if vram_gb >= min_vram:
            return model, quant, max_len
    
    # Fallback to smallest config
    return model_configs[-1][1], model_configs[-1][2], model_configs[-1][3]
