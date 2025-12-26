import os, time
from common.utils import KafkaConsumerWrapper
from common.config import settings

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def start_worker():
    print("Waiting for Kafka...")

    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_AI, group_id=settings.KAFKA_GROUP_AI
    )

    print("[AI Worker] Started. Listening...")

    for message in consumer.get_messages():
        task = message.value
        context = task.get("context")

        print(f"[AI Worker] Processing context: {context[:30]}...")

        # --- 가짜 GPU 추론 (vLLM 나중에 적용) ---
        time.sleep(3)  # 생각하는 척
        final_report = f"Analysis Report: Based on {context}, the conclusion is..."
        # -------------------------------------

        print(f"✅ [DONE] Final Report Created: {final_report}")


if __name__ == "__main__":
    start_worker()
