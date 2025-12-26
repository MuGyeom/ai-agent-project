FROM python:3.11-slim
WORKDIR /app
COPY src/search-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/search-worker .
COPY src/common ./common

CMD ["python", "-u", "main.py"] 