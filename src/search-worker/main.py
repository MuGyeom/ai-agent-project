import time
import trafilatura
from duckduckgo_search import DDGS
from common.config import settings
from common.utils import KafkaConsumerWrapper, KafkaProducerWrapper
from common.database import SessionLocal, Request, SearchResult


def search_and_crawl(topic, max_results=8):
    """
    1. DuckDuckGo 검색
    2. 상위 N개 URL 수집
    3. 본문 크롤링 (개선된 trafilatura 설정)
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

            # 2. 본문 크롤링 (trafilatura 고급 설정)
            try:
                downloaded = trafilatura.fetch_url(url)
                content = ""
                
                if downloaded:
                    # 개선된 추출 설정
                    text = trafilatura.extract(
                        downloaded,
                        include_comments=False,      # 댓글 제외
                        include_tables=True,          # 표 포함
                        no_fallback=False,            # fallback 허용 (더 많은 콘텐츠)
                        favor_precision=False,        # recall 우선 (더 많은 텍스트)
                        favor_recall=True,
                        deduplicate=True,             # 중복 제거
                        target_language="ko",         # 한국어 우선
                    )
                    
                    if text and len(text.strip()) > 100:  # 최소 100자 이상
                        # 더 긴 본문 허용 (8000자까지)
                        content = text.strip()[:8000]
                        print(f"      ✅ Extracted {len(content)} characters")
                    else:
                        print(f"      ⚠️ Content too short ({len(text) if text else 0} chars)")
                else:
                    print(f"      ⚠️ Failed to fetch {url}")
                    
            except Exception as e:
                print(f"      ❌ Crawl error for {url}: {e}")
                content = ""

            # 결과 저장 (빈 내용이라도 저장 - 제목/URL은 유용)
            results.append({
                "url": url,
                "title": title,
                "content": content
            })

            time.sleep(1)  # 차단 방지

    except Exception as e:
        print(f"❌ Search Error: {e}")

    # 유효한 콘텐츠가 있는 결과만 반환
    valid_results = [r for r in results if r["content"]]
    print(f"📊 Total: {len(results)} results, Valid: {len(valid_results)} with content")
    
    return valid_results if valid_results else results[:3]  # 최소 3개는 반환


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

            print(f"\n{'='*60}")
            print(f"Received request: {request_id} : {topic}")

            # 🔒 Pessimistic Lock: Row-level locking
            # SELECT FOR UPDATE SKIP LOCKED prevents race conditions
            from sqlalchemy import text
            
            # Try to acquire exclusive lock on this request
            lock_query = text("""
                SELECT id, status 
                FROM requests 
                WHERE id = :request_id 
                AND status = 'searching'
                FOR UPDATE SKIP LOCKED
            """)
            
            result = db.execute(lock_query, {"request_id": request_id}).fetchone()
            
            if not result:
                # Either already locked by another worker, or status != 'searching'
                existing = db.query(Request).filter(Request.id == request_id).first()
                if existing:
                    if existing.status == 'searching':
                        print(f"🔒 Request {request_id} locked by another worker, skipping")
                    else:
                        print(f"⏭️  Request {request_id} already processed (status: {existing.status})")
                else:
                    print(f"❌ Request {request_id} not found")
                consumer.consumer.commit()
                continue

            # We successfully acquired the lock! Update status immediately
            db_request = db.query(Request).filter(Request.id == request_id).first()
            db_request.status = 'processing_search'
            db.commit()
            print(f"✅ Locked and claimed request {request_id}")

            # 검색 수행
            search_results_data = search_and_crawl(topic, max_results=8)

            if not search_results_data:
                print(f"⚠️  No search results for {topic}")
                # 상태를 failed로 업데이트
                db_request.status = "failed"
                db_request.error_message = "No search results found"
                db.commit()
                consumer.consumer.commit()
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

            # 요청 상태 업데이트: processing_search → analyzing
            db_request.status = "analyzing"
            db.commit()

            # AI Worker에 분석 요청 전달
            producer.send_data(
                topic=settings.KAFKA_TOPIC_AI,
                value={
                    "request_id": request_id,
                    "topic": topic
                }
            )
            
            # Kafka offset 커밋
            consumer.consumer.commit()
            print(f"✅ Request {request_id} handed off to AI worker")

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
