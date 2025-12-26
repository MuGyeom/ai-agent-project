FROM python:3.11-slim
WORKDIR /app

# 공통 모듈과 크롤러 코드 복사
COPY src/common /app/src/common
COPY src/search /app/src/search
COPY requirements.txt .

RUN pip install -r requirements.txt

# 크롤러 실행
CMD ["python", "-m", "src.search.main"]