import time
import trafilatura
from duckduckgo_search import DDGS
from common.config import settings
from common.utils import KafkaConsumerWrapper, KafkaProducerWrapper
from common.database import SessionLocal, Request, SearchResult


def search_and_crawl(topic, max_results=8):
    """
    1. Search using configured search engine (DuckDuckGo or SearXNG)
    2. Collect top N URLs
    3. Crawl content (with improved trafilatura settings)
    4. Return results as list (for DB storage)
    """
    print(f"🔍 Searching for: {topic}")
    results = []

    # 1. Perform search
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(topic, max_results=max_results))

        for result in search_results:
            url = result["href"]
            title = result["title"]
            print(f"   👉 Found: {title} ({url})")

            # 2. Crawl content (advanced trafilatura settings)
            try:
                downloaded = trafilatura.fetch_url(url)
                content = ""
                
                if downloaded:
                    # Improved extraction settings
                    text = trafilatura.extract(
                        downloaded,
                        include_comments=False,      # Exclude comments
                        include_tables=True,          # Include tables
                        no_fallback=False,            # Allow fallback (more content)
                        favor_precision=False,        # Favor recall (more text)
                        favor_recall=True,
                        deduplicate=True,             # Remove duplicates
                        target_language="ko",         # Prefer Korean
                    )
                    
                    if text and len(text.strip()) > 100:  # Minimum 100 chars
                        # Allow longer content (up to 8000 chars)
                        content = text.strip()[:8000]
                        print(f"      ✅ Extracted {len(content)} characters")
                    else:
                        print(f"      ⚠️ Content too short ({len(text) if text else 0} chars)")
                else:
                    print(f"      ⚠️ Failed to fetch {url}")
                    
            except Exception as e:
                print(f"      ❌ Crawl error for {url}: {e}")
                content = ""

            # Save result (save even if content is empty - title/URL are useful)
            results.append({
                "url": url,
                "title": title,
                "content": content
            })

            time.sleep(1)  # Prevent blocking

    except Exception as e:
        print(f"❌ Search Error: {e}")

    # Return only results with valid content
    valid_results = [r for r in results if r["content"]]
    print(f"📊 Total: {len(results)} results, Valid: {len(valid_results)} with content")
    
    return valid_results if valid_results else results[:3]  # Return at least 3


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

            # Perform search
            search_results_data = search_and_crawl(topic, max_results=8)

            if not search_results_data:
                print(f"⚠️  No search results for {topic}")
                # Update status to failed
                db_request.status = "failed"
                db_request.error_message = "No search results found"
                db.commit()
                consumer.consumer.commit()
                continue

            # Save search results to DB
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

            # Update request status: processing_search → analyzing
            db_request.status = "analyzing"
            db.commit()

            # Send analysis request to AI Worker
            producer.send_data(
                topic=settings.KAFKA_TOPIC_AI,
                value={
                    "request_id": request_id,
                    "topic": topic
                }
            )
            
            # Commit Kafka offset
            consumer.consumer.commit()
            print(f"✅ Request {request_id} handed off to AI worker")

        except Exception as e:
            print(f"❌ Worker Error: {e}")
            # Save error status
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
