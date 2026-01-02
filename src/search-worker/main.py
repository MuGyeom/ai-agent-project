import time
import trafilatura
from duckduckgo_search import DDGS
from common.config import settings
from common.utils import KafkaConsumerWrapper, KafkaProducerWrapper
from common.database import SessionLocal, Request, SearchResult


def search_and_crawl(topic, max_results=5):
    """
    1. DuckDuckGo 검색
    2. 상위 N개 URL 수집
    3. 본문 크롤링
    4. 결과를 리스트로 반환 (DB 저장용)
    """
    print(f"🔍 Searching for: {topic}")
    results = []

    # 1. 검색 수행
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(topic, max_results=max_results))

        for result in search_results:
            url = result["href"]
            title = result["title"]
            print(f"   👉 Found: {title} ({url})")

            # 2. 본문 크롤링 (trafilatura)
            downloaded = trafilatura.fetch_url(url)
            content = ""
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    content = text[:2000]  # 2000자 제한
                else:
                    print(f"      ⚠️ No content extracted from {url}")
            else:
                print(f"      ⚠️ Failed to fetch {url}")

            # 결과 저장 (DB 저장용)
            results.append({
                "url": url,
                "title": title,
                "content": content
            })

            time.sleep(1)  # 차단 방지를 위한 예의바른 대기

    except Exception as e:
        print(f"❌ Search Error: {e}")

    return results


def process_search():
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_SEARCH, group_id=settings.KAFKA_GROUP_SEARCH
    )
    producer = KafkaProducerWrapper()

    print(f"🚀 [Search Worker] Ready using DuckDuckGo...")

    for message in consumer.get_messages():
        db = SessionLocal()
        try:
            task = message.value
            request_id = task.get("request_id")
            topic = task.get("topic")

            print(f"📥 Received request {request_id}: {topic}")

            # 검색 및 크롤링 수행
            search_results_data = search_and_crawl(topic)

            if not search_results_data:
                print(f"⚠️ No search results found for {topic}")
                # 상태를 failed로 업데이트
                db_request = db.query(Request).filter(Request.id == request_id).first()
                if db_request:
                    db_request.status = "failed"
                    db_request.error_message = "No search results found"
                    db.commit()
                continue

            # DB에 검색 결과 저장
            for result_data in search_results_data:
                search_result = SearchResult(
                    request_id=request_id,
                    url=result_data['url'],
                    title=result_data['title'],
                    content=result_data['content']
                )
                db.add(search_result)
            
            db.commit()
            print(f"💾 Saved {len(search_results_data)} search results to DB")

            # 요청 상태 업데이트: searching → analyzing
            db_request = db.query(Request).filter(Request.id == request_id).first()
            if db_request:
                db_request.status = "analyzing"
                db.commit()
                print(f"🔄 Status updated to 'analyzing' for request {request_id}")

            # AI Worker로 전송 (request_id만 전송 - AI Worker가 DB에서 읽을 것)
            producer.send_data(
                topic=settings.KAFKA_TOPIC_AI,
                value={"request_id": request_id, "topic": topic}
            )
            print(f"✅ [Forwarded] Sent to AI Worker for analysis")

        except Exception as e:
            print(f"❌ Worker Error: {e}")
            # 에러 상태 저장
            if 'request_id' in locals() and request_id:
                db_request = db.query(Request).filter(Request.id == request_id).first()
                if db_request:
                    db_request.status = "failed"
                    db_request.error_message = str(e)
                    db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    process_search()
