FROM python:3.11-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies with uv
COPY src/search_worker/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY src/search_worker .
COPY src/common ./common

CMD ["python", "-u", "main.py"]