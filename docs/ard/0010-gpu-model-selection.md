# 10. Automatic GPU Model Selection

* Status: Accepted
* Date: 2026-01-14
* Context: Phase 3 (AI Worker Enhancement)

## Context and Problem Statement

AI Worker에서 vLLM 모델 사용 시 다음과 같은 문제가 있었습니다:

1. **하드코딩된 모델**: 환경변수로 모델 지정 필수
2. **GPU 호환성 문제**: 12GB GPU에 70B 모델 로드 시도 → OOM
3. **배포 복잡성**: GPU 사양별 다른 설정 필요
4. **개발 환경 다양성**: RTX 4070 (12GB), RTX 3090 (24GB) 등 혼재

**필요사항**:
- GPU VRAM 자동 감지
- VRAM에 맞는 최적 모델 자동 선택
- 환경변수로 오버라이드 가능

## Decision Drivers

* **사용 편의성**: 설정 없이 최적 모델 사용
* **안정성**: OOM 에러 방지
* **확장성**: 다양한 GPU 지원
* **유연성**: 수동 오버라이드 가능

## Decision Outcome

**GPU VRAM 자동 감지 및 모델 자동 선택** 로직을 구현했습니다.

---

## Implementation Details

### 1. GPU Memory Detection

```python
# src/common/ai_worker_utils.py
def get_gpu_memory_gb():
    """Detect GPU VRAM in GB using nvidia-smi or pynvml."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            memory_mb = int(result.stdout.strip().split('\n')[0])
            return memory_mb / 1024  # Convert to GB
    except Exception:
        pass
    
    # Fallback: try pynvml
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.total / (1024 ** 3)
    except Exception:
        pass
    
    return None
```

### 2. Model Selection by VRAM

```python
def select_model_by_vram(vram_gb):
    """Select appropriate model based on available GPU VRAM."""
    model_configs = [
        # (min_vram_gb, model_name, quantization, max_model_len)
        (20, "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4", "awq", 8192),
        (10, "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "awq", 8192),
        (6,  "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "awq", 4096),
        (0,  "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "awq", 2048),
    ]
    
    for min_vram, model, quant, max_len in model_configs:
        if vram_gb >= min_vram:
            return model, quant, max_len
    
    return model_configs[-1][1], model_configs[-1][2], model_configs[-1][3]
```

### 3. AI Worker Integration

```python
# src/ai_worker/main.py
env_model = os.getenv("VLLM_MODEL")

if env_model:
    # Use explicitly specified model
    MODEL_NAME = env_model
    QUANTIZATION = os.getenv("VLLM_QUANTIZATION", "awq")
    MAX_MODEL_LEN = int(os.getenv("VLLM_MAX_MODEL_LEN", "4096"))
else:
    # Auto-select model based on GPU VRAM
    gpu_memory = get_gpu_memory_gb()
    if gpu_memory:
        print(f"🎮 Detected GPU VRAM: {gpu_memory:.1f} GB")
        MODEL_NAME, QUANTIZATION, MAX_MODEL_LEN = select_model_by_vram(gpu_memory)
    else:
        # Fallback to safe default
        MODEL_NAME = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
        QUANTIZATION = "awq"
        MAX_MODEL_LEN = 4096
```

---

## Model Tiers

| GPU VRAM | 선택 모델 | Context Length |
|----------|----------|----------------|
| 20GB+ | Llama 3.1 70B AWQ | 8192 |
| 10-20GB | Llama 3.1 8B AWQ | 8192 |
| 6-10GB | Llama 3.1 8B AWQ | 4096 |
| <6GB | Llama 3.1 8B AWQ | 2048 |

---

## Consequences

### Positive

1. ✅ **Zero-Config 배포**: GPU에 맞는 모델 자동 선택
2. ✅ **OOM 방지**: VRAM에 맞는 context length 자동 조정
3. ✅ **유연성**: `VLLM_MODEL` 환경변수로 오버라이드 가능
4. ✅ **테스트 용이**: 함수 분리로 단위 테스트 가능

### Negative

1. ❌ **nvidia-smi 의존**: GPU 없는 환경에서 폴백 필요
2. ❌ **멀티 GPU 미지원**: 첫 번째 GPU만 감지

---

## Testing

```python
# tests/test_ai_worker.py
def test_12gb_selects_8b_long_context():
    model, quant, max_len = select_model_by_vram(12.0)
    assert "8B" in model
    assert max_len == 8192

def test_24gb_plus_selects_70b():
    model, quant, max_len = select_model_by_vram(24.0)
    assert "70B" in model
```

---

## References

- [nvidia-smi Documentation](https://developer.nvidia.com/nvidia-system-management-interface)
- [pynvml](https://pypi.org/project/pynvml/)
- [vLLM Memory Management](https://docs.vllm.ai/en/latest/)
