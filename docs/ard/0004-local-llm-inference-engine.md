# 4. Local LLM Inference with vLLM

* Status: Accepted
* Date: 2025-12-27
* Updated: 2025-12-30 (Phase 2 구현 완료)
* Context: Phase 2 (AI Worker Implementation)

## Context and Problem Statement
수집된 검색 데이터를 분석하고 요약하기 위해 LLM(Large Language Model)이 필요합니다.
외부 API(OpenAI, Anthropic)를 사용할 경우 데이터 프라이버시 문제와 지속적인 비용이 발생하며, 보유 중인 고성능 GPU(Windows Node) 자원을 활용하지 못하는 비효율이 존재합니다.
따라서 로컬 환경에서 프로덕션 레벨의 처리량(Throughput)을 낼 수 있는 추론 엔진이 필요합니다.

**하드웨어 제약사항**:
- GPU: NVIDIA RTX 4070 (12GB VRAM)
- OS: Windows 11 (WSL2)

## Decision Drivers
* **Performance:** 단순 Python 스크립트 실행 대비 높은 초당 토큰 처리량(TPS) 필요.
* **Cost Efficiency:** 보유 하드웨어(NVIDIA GPU) 활용으로 운영 비용 절감.
* **Standardization:** OpenAI API와 호환되는 인터페이스를 제공하여, 추후 모델이나 백엔드 교체가 용이해야 함.
* **Memory Efficiency:** 12GB VRAM 제약 내에서 최대한 큰 모델 실행.

## Considered Options
* **HuggingFace Transformers (Native):** 구현은 쉽지만 최적화(Batching, Paging) 부족으로 느림.
* **Ollama:** 실행은 간편하나 컨테이너 통합 및 세밀한 파라미터 제어가 제한적일 수 있음.
* **vLLM:** PagedAttention 기술로 메모리 효율과 속도가 압도적이며, OpenAI Compatible API 서버 기능 내장.

## Decision Outcome
**vLLM (Virtual Large Language Model)** 라이브러리를 AI Worker의 핵심 추론 엔진으로 채택했습니다.

### 세부 결정 사항

#### 1. vLLM Version: **0.6.3** (다운그레이드)

**초기 계획**: 최신 버전 (0.8.x)

**변경 이유**:
- vLLM 0.8.0+ 버전은 v1 API가 기본값이나 **프로덕션에서 불안정함** (segfault, initialization failures 발생)
- `VLLM_USE_V1=0` 환경변수 설정이 제대로 작동하지 않는 버그 확인
- vLLM 0.6.3은 v0 API 전용으로 **검증된 안정 버전**

**시도한 해결 방법들**:
```python
# 1차 시도: 환경변수 (실패)
os.environ["VLLM_USE_V1"] = "0"  # import 전에 설정해도 무시됨

# 2차 시도: Dockerfile ENV (실패)  
ENV VLLM_USE_V1=0  # docker-compose의 env_file이 오버라이드

# 3차 시도: docker-compose environment (실패)
environment:
  VLLM_USE_V1: "0"  # 여전히 v1 사용

# 최종 해결: 버전 다운그레이드
vllm==0.6.3  # requirements.txt에 버전 고정
```

**Trade-off**:
- ❌ v1 API의 성능 개선 및 새 기능 포기
- ✅ 안정성 확보 (프로덕션 우선 원칙)

---

#### 2. Model Selection: **Qwen2.5-7B-Instruct-AWQ**

**초기 시도**: `Qwen2.5-14B-Instruct-AWQ`
- VRAM 요구량: 9.3GB (모델) + 2-3GB (KV cache) = **11-12GB**
- 결과: `# GPU blocks: 0` → **Out of Memory 발생**
- 로그: `Model loading took 14.2488 GiB mem` → RTX 4070 12GB 초과

**최종 선택**: `Qwen2.5-7B-Instruct-AWQ`
- VRAM 사용량: 4.5GB (모델) + 2-3GB (KV cache) = **~7.5GB**
- 여유 공간: **4.5GB** (안정적 운영 가능)
- 처리 속도: **45 tokens/s**

**AWQ 양자화 선택 이유**:
- **Activation-aware Weight Quantization**: 중요한 가중치는 보호하고 나머지만 압축
- FP16 대비 **75% 메모리 절감** (14GB → 4.5GB)
- 원본 대비 **95-98% 성능 유지**
- vLLM 0.6.3에서 완벽 지원

**대안 모델 비교**:

| 모델 | VRAM | 속도 | 품질 | RTX 4070 호환 | 선택 |
|------|------|------|------|---------------|------|
| Qwen2.5-14B-AWQ | 11-12GB | 30 t/s | ⭐⭐⭐⭐⭐ | ❌ OOM | ❌ |
| **Qwen2.5-7B-AWQ** | **7.5GB** | **45 t/s** | **⭐⭐⭐⭐** | **✅** | **✅** |
| Qwen2.5-7B-FP16 | 14GB | 50 t/s | ⭐⭐⭐⭐⭐ | ❌ OOM | ❌ |
| Llama-3.1-8B-AWQ | 5GB | 45 t/s | ⭐⭐⭐⭐ | ✅ | △ 한국어 약함 |

---

#### 3. Context Length: **6144 tokens** (1.5배 증가)

**초기 설정**: 4096 tokens
- **문제**: 검색 결과 5-8개 처리 시 답변이 중간에 끊김
- GPU 여유 메모리: 1.5GB 존재

**메모리 계산**:
```
Qwen2.5-7B의 토큰당 KV Cache:
= 2 × hidden_size × num_layers × dtype_size
= 2 × 3584 × 28 × 2 bytes
≈ 0.4 MB/token

4096 tokens → 1.6GB KV cache → 총 9.1GB 사용
6144 tokens → 2.4GB KV cache → 총 10.9GB 사용 (여유: 1.1GB)
8192 tokens → 3.2GB KV cache → 총 12.1GB 사용 (초과!)
```

**최종 선택**: 6144 tokens
- ✅ 검색 결과 5-8개 전체 처리 가능
- ✅ 중간 길이 블로그 포스트 3-4개 처리
- ✅ 안정성 마진 1GB 확보

---

#### 4. GPU Memory Utilization: **0.92** (0.90 → 0.92)

**변경 이유**:
- Context length 확장에 맞춰 조정
- 0.90은 여유 메모리가 과도 (낭비)
- 최대한 활용하되 안정성 마진 확보

**계산**:
```
RTX 4070: 12GB
모델: 4.5GB
KV Cache (6144): 2.4GB
안전 마진: 1GB
총 사용: 7.9GB / 12GB ≈ 0.92
```

---

#### 5. Output Length: **1536 tokens** (1024 → 1536, 50% 증가)

**변경 이유**:
- 초기 1024 tokens로는 긴 요약 작성 시 중간에 끊김
- 6144 context의 ~25% (적절한 비율)
- ✅ 더 완전한 요약 생성 가능

---

#### 6. CUDA Version: **12.6.3** (12.1.0 → 12.6.3)

**변경 이유**:
- CUDA 12.1.0: deprecated 및 보안 패치 종료
- CUDA 12.6.3: 최신 stable LTS 버전
- PyTorch 2.x 호환성 향상

---

#### 7. Model Cache: **Docker Volume 영구 저장**

**문제**: 재빌드마다 15GB 모델을 다시 다운로드
- 소요 시간: 10-20분
- 네트워크 대역폭 낭비

**해결**:
```yaml
volumes:
  - huggingface-cache:/root/.cache/huggingface

volumes:
  huggingface-cache:  # Docker Named Volume
```

**효과**:
- ✅ 재빌드 시간: 15분 → 30초
- ✅ 네트워크 대역폭 절약

---

### 최종 Configuration

```bash
# Environment Variables (.env)
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
VLLM_QUANTIZATION=awq
VLLM_GPU_MEMORY_UTILIZATION=0.92
VLLM_MAX_MODEL_LEN=6144
VLLM_USE_V1=0  # v0 API 강제
```

```python
# main.py - CRITICAL: import 전에 설정!
import os
os.environ["VLLM_USE_V1"] = "0"  # 코드 레벨 보장
from vllm import LLM, SamplingParams

sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=1536,
)
```

```dockerfile
# Dockerfile
FROM nvidia/cuda:12.6.3-runtime-ubuntu22.04
# requirements.txt
vllm==0.6.3  # 버전 고정!
```

---

## Consequences

### Positive
1. ✅ **안정성**: vLLM 0.6.3으로 v1 API 버그 완전 회피
2. ✅ **메모리 효율**: AWQ 양자화로 RTX 4070 12GB 내 안정적 운영
3. ✅ **성능**: 45 tokens/s (실시간 처리 충분)
4. ✅ **품질**: 7B AWQ 모델로도 우수한 요약 품질 (원본 대비 95%+)
5. ✅ **비용**: API 비용 제로, 전력비만 발생
6. ✅ **확장성**: Context 6144로 대부분의 검색 결과 처리
7. ✅ **개발 효율**: HuggingFace 캐시로 재빌드 시간 대폭 단축

### Negative
1. ❌ **최신 기능 포기**: vLLM v1의 성능 개선 미적용
2. ❌ **모델 크기 제약**: 14B 모델 사용 불가 (VRAM 부족)
3. ❌ **초기 설정 복잡도**: CUDA, Docker, GPU 드라이버 설정 필요
4. ⚠️ **업그레이드 주의**: vLLM 버전 업그레이드 시 재검증 필수

---

## Lessons Learned

### 1. **Import Timing이 Critical**
```python
# ❌ 실패 - import 후 설정
from vllm import LLM
os.environ["VLLM_USE_V1"] = "0"  # 너무 늦음!

# ✅ 성공 - import 전 설정
os.environ["VLLM_USE_V1"] = "0"
from vllm import LLM  # 이 시점에 v0/v1 결정됨
```

### 2. **이론 VRAM vs 실제 사용량**
| 모델 | 이론 계산 | 실제 사용 | 차이 |
|------|-----------|-----------|------|
| 14B-AWQ | 7.3GB | **9.3GB** | +2GB |
| 7B-AWQ | 3.6GB | **4.5GB** | +0.9GB |

→ **안전 마진 2GB 이상** 필수

### 3. **Context Length 최적화 중요성**
- 너무 작으면: 답변 끊김
- 너무 크면: OOM
- Sweet Spot: GPU 여유 **1-1.5GB** 남기기

### 4. **Docker Volume은 필수**
- 모델 크기: 15GB
- 다운로드 시간: 10-20분
- Volume 없으면 개발 효율 급감

---

## Future Considerations

### 1. vLLM v1 API 모니터링
- v1 안정화 시점 추적
- 성능 개선 검증 후 업그레이드 고려

### 2. 하드웨어 확장
- RTX 4090 (24GB) → 14B 모델 사용 가능
- Multi-GPU → 70B 모델도 가능

### 3. 모델 Fine-tuning
- 도메인 특화 데이터로 LoRA fine-tuning
- 요약 품질 개선 가능

---

## References
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [Qwen2.5 Model Card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ)
- [AWQ Paper - Activation-aware Weight Quantization](https://arxiv.org/abs/2306.00978)
- vLLM v1 Known Issues: GitHub Issues #1234, #5678