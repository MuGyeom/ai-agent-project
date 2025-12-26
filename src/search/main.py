import trafilatura  # 크롤링 라이브러리는 워커에서만 임포트
from common.utils import KafkaConsumerWrapper, KafkaProducerWrapper
from common.config import settings


def process_search():
    # 1. Consumer: search-queue에서 할 일 가져옴
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_SEARCH, group_id=settings.KAFKA_GROUP_SEARCH
    )

    # 2. Producer: 결과물을 ai-queue로 보냄
    producer = KafkaProducerWrapper()

    for message in consumer.get_messages():
        task = message.value
        keyword = task["topic"]
        print(f"🔍 Crawling: {keyword}")

        # --- 크롤링 로직 (비즈니스 로직) ---
        # 실제로는 여기서 구글 검색 후 URL을 따와야 하지만 예시로 직관적인 URL 사용
        downloaded = trafilatura.fetch_url("https://example.com")
        content = trafilatura.extract(downloaded) if downloaded else ""
        # ------------------------------

        # 다음 단계로 전송
        producer.send_data(
            topic=settings.KAFKA_TOPIC_SEARCH,
            value={"context": content, "original_topic": keyword},
        )


if __name__ == "__main__":
    process_search()
