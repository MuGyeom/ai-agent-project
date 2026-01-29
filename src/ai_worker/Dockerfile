# syntax=docker/dockerfile:1
FROM nvidia/cuda:12.6.3-runtime-ubuntu22.04

# System update and Python 3.11 installation
RUN apt-get update && \
    apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Link python3 to python3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install requirements (BuildKit cache mount)
COPY src/ai_worker/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# Copy source code
COPY src/ai_worker .
COPY src/common ./common

# Environment variable defaults (can be overridden)
# RTX 4070 (12GB) optimized: AWQ 4-bit quantization
ENV VLLM_MODEL=hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4
ENV VLLM_QUANTIZATION=awq
ENV VLLM_GPU_MEMORY_UTILIZATION=0.90
ENV VLLM_MAX_MODEL_LEN=8192

# Force vLLM v0 API (v1 is still unstable)
ENV VLLM_USE_V1=0

CMD ["python3", "-u", "main.py"]