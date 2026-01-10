FROM python:3.11-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies with uv
COPY src/api-server/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY src/api-server .
COPY src/common ./common

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]