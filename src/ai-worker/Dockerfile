# syntax=docker/dockerfile:1
FROM nvidia/cuda:12.6.3-runtime-ubuntu22.04

# 시스템 업데이트 및 Python 3.11 설치
RUN apt-get update && \
    apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

# python3를 python3.11로 링크
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app

# Requirements 설치 (BuildKit cache mount)
COPY src/ai-worker/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

# 소스 코드 복사
COPY src/ai-worker .
COPY src/common ./common

# 환경변수 기본값 설정 (오버라이드 가능)
# RTX 4070 (12GB) 최적화: AWQ 4-bit 양자화
ENV VLLM_MODEL=hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4
ENV VLLM_QUANTIZATION=awq
ENV VLLM_GPU_MEMORY_UTILIZATION=0.90
ENV VLLM_MAX_MODEL_LEN=8192

# vLLM v0 API 강제 사용 (v1은 아직 불안정)
ENV VLLM_USE_V1=0

CMD ["python3", "-u", "main.py"]