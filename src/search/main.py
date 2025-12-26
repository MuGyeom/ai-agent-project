import requests, trafilatura, time
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import src.common.utils as utils

# 기본 요청 헤더 — 일반 브라우저 User-Agent 포함
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def handle_crawled_data(url, raw_html) -> Dict[str, Any] | None:
    clean_text = trafilatura.extract(raw_html)

    if clean_text:
        payload = {"url": url, "content": clean_text}
        # print(payload)
        return payload


def crawl_and_classify(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10,
    retry_alt_ua: bool = True,
) -> Dict[str, Any] | None:
    """
    주어진 URL을 크롤링하여 제목·단락 등으로 분류해 출력합니다.
    403 에러가 날 경우 기본 헤더로 재시도하고, 필요하면 alternate User-Agent로 한 번 더 시도합니다.
    """
    producer = None
    while not producer:
        producer = utils.KafkaProducerWithRetry()
        time.sleep(5)
    session = requests.Session()
    # 설정된 헤더가 있으면 병합, 없으면 기본 헤더 사용
    if headers:
        session.headers.update({**DEFAULT_HEADERS, **headers})
    else:
        session.headers.update(DEFAULT_HEADERS)

    try:
        resp = session.get(url, timeout=timeout)

        # 403일 때 대체 User-Agent로 재시도
        if resp.status_code == 403 and retry_alt_ua:
            alt_headers = dict(session.headers)
            alt_headers["User-Agent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/85.0.4183.121 Safari/537.36"
            )
            resp = session.get(url, headers=alt_headers, timeout=timeout)

        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        title = (
            soup.title.string.strip()
            if soup.title and soup.title.string
            else "제목 없음"
        )
        paragraphs: List[str] = [
            p.get_text().strip() for p in soup.find_all("p") if p.get_text().strip()
        ]

        print(f"URL: {url}")
        print(f"제목: {title}")
        print("\n--- <p> 내용 ---")
        for i, p_text in enumerate(paragraphs):
            print(f"<p> {i+1}: {p_text}")
        return handle_crawled_data(url, resp.text)

    except requests.exceptions.HTTPError as e:
        code = getattr(e.response, "status_code", None)
        if code == 403:
            print("403 Forbidden: 서버가 요청을 차단했습니다.")
            print(
                "- 해결 방법: User-Agent를 변경하거나 브라우저 쿠키/세션을 사용하세요."
            )
            print(
                "- 필요하다면 프록시나 헤드리스 브라우저(Selenium/playwright) 사용을 고려하세요."
            )
        else:
            print(f"HTTP 오류 발생: {e}")
    except requests.exceptions.RequestException as e:
        print(f"요청 중 오류 발생: {e}")
    except Exception as e:
        print(f"데이터 처리 중 오류 발생: {e}")


if __name__ == "__main__":
    target_url = input("크롤링할 URL을 입력하세요: ")
    crawl_and_classify(target_url)
