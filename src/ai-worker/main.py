import time
from common.config import settings
from common.utils import KafkaConsumerWrapper


def process_ai():
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_AI, group_id=settings.KAFKA_GROUP_AI
    )

    print(f"🤖 [AI Worker] Waiting for research data...")

    for message in consumer.get_messages():
        try:
            task = message.value
            original_topic = task.get("original_topic")
            context = task.get("context")

            print("\n" + "=" * 50)
            print(f"📥 Topic: {original_topic}")
            print(f"📄 Research Data (Combined):")
            # 내용이 기니까 앞부분만 살짝 출력
            print(context[:500] + "\n... (more) ...")
            print("=" * 50)

            # --- Mock LLM ---
            print("🧠 Analyzing & Summarizing...")
            time.sleep(3)
            print("✅ Final Report Generated (Mock).")

        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    process_ai()
