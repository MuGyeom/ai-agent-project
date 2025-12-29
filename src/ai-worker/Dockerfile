FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

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

# Requirements 설치
COPY src/ai-worker/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY src/ai-worker .
COPY src/common ./common

# 환경변수 기본값 설정 (오버라이드 가능)
ENV VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
ENV VLLM_GPU_MEMORY_UTILIZATION=0.85
ENV VLLM_MAX_MODEL_LEN=4096

CMD ["python3", "-u", "main.py"]