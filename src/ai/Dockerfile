FROM python:3.11-slim
WORKDIR /app
COPY src/ai/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ai .
COPY src/common ./common

CMD ["python", "-u", "main.py"] 