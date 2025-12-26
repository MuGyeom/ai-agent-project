# src/config.py
import os
from dotenv import load_dotenv

# .env 파일 로드 (같은 경로 혹은 상위 경로의 .env를 찾음)
load_dotenv()


def str_to_bool(value: str) -> bool:
    """문자열 'true', '1', 'yes' 등을 실제 Boolean True로 변환"""
    if not value:
        return False
    return value.lower() in ("true", "1", "t", "yes", "on")


# 환경 변수 가져오기 & 타입 변환
CRAWLER_TIMEOUT = int(os.getenv("CRAWLER_TIMEOUT", 10))
ALTERNATE_USER_AGENT = os.getenv("ALTERNATE_USER_AGENT", "")
CRAWLER_RETRY_ALT_UA = str_to_bool(os.getenv("CRAWLER_RETRY_ALT_UA", "false"))
MAX_CRAWL_RETRIES = int(os.getenv("MAX_CRAWL_RETRIES", 3))
CRAWL_DELAY_SECONDS = int(os.getenv("CRAWL_DELAY_SECONDS", 2))
TARGET_URL = os.getenv("TARGET_URL", "https://news.naver.com")
# 추가 설정 변수들을 여기에 정의
