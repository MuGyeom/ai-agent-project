import time
import trafilatura
from duckduckgo_search import DDGS
from common.config import settings
from common.utils import KafkaConsumerWrapper, KafkaProducerWrapper


def search_and_crawl(topic, max_results=3):
    """
    1. DuckDuckGo 검색
    2. 상위 N개 URL 수집
    3. 본문 크롤링 및 병합
    """
    print(f"🔍 Searching for: {topic}")
    results = []

    # 1. 검색 수행
    try:
        with DDGS() as ddgs:
            # ddgs.text()는 제너레이터이므로 리스트로 변환
            search_results = list(ddgs.text(topic, max_results=max_results))

        for result in search_results:
            url = result["href"]
            title = result["title"]
            print(f"   👉 Found: {title} ({url})")

            # 2. 본문 크롤링 (trafilatura)
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    results.append(
                        f"Source: {title} ({url})\nContent:\n{text[:1000]}...\n"
                    )  # 너무 길지 않게 1000자 제한
                else:
                    print(f"      ⚠️ No content extracted from {url}")
            else:
                print(f"      ⚠️ Failed to fetch {url}")

            time.sleep(1)  # 차단 방지를 위한 예의바른 대기

    except Exception as e:
        print(f"❌ Search Error: {e}")

    return "\n---\n".join(results)


def process_search():
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_SEARCH, group_id=settings.KAFKA_GROUP_SEARCH
    )
    producer = KafkaProducerWrapper()

    print(f"🚀 [Search Worker] Ready using DuckDuckGo...")

    for message in consumer.get_messages():
        try:
            task = message.value
            topic = task.get("topic")

            # 검색 및 크롤링 수행
            combined_context = search_and_crawl(topic)

            if not combined_context:
                combined_context = "No relevant information found."

            # AI Worker로 전송
            payload = {"original_topic": topic, "context": combined_context}
            producer.send_data(topic=settings.KAFKA_TOPIC_AI, value=payload)
            print(f"✅ [Forwarded] Sent {len(combined_context)} chars to AI Worker.")

        except Exception as e:
            print(f"❌ Worker Error: {e}")


if __name__ == "__main__":
    process_search()
