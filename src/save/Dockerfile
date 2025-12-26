FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# 코드 복사
COPY src/common /app/src/common
COPY src/save /app/src/save

# 실행
CMD ["python", "-m", "src.save.main"]