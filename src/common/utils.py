import json, time, sys, signal
from kafka import KafkaProducer, KafkaConsumer, errors
from common.config import settings

KAFKA_SERVER = (
    settings.KAFKA_BROKER if settings.KAFKA_BROKER else settings.KAFKA_BOOTSTRAP_SERVERS
)
# 디버깅을 위해 현재 사용 중인 주소 출력
print(f"🔗 [Utils] Connecting to Kafka Brokers: {KAFKA_SERVER}")


class KafkaProducerWrapper:
    def __init__(self, max_retries=10, initial_delay=2):
        print("🔧 Initializing Kafka Producer...")
        self.producer = self._create_producer_with_retry(max_retries, initial_delay)

    def _create_producer_with_retry(self, max_retries, delay):
        attempt = 0
        while attempt < max_retries:
            try:
                producer = KafkaProducer(
                    bootstrap_servers=[KAFKA_SERVER],
                    value_serializer=lambda x: json.dumps(x).encode("utf-8"),
                    compression_type="gzip",
                    api_version_auto_timeout_ms=5000,
                )
                print("✅ Kafka Producer Connected!")
                return producer
            except errors.NoBrokersAvailable:
                attempt += 1
                print(
                    f"⚠️ Producer Connection Failed ({attempt}/{max_retries}). Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                print(f"❌ Producer Error: {e}")
                sys.exit(1)

        print("🚨 Producer failed to connect. Exiting...")
        sys.exit(1)

    def send_data(self, topic, value, callback=None):
        """
        어떤 토픽이든, 어떤 데이터든 보낼 수 있게 일반화함
        """
        future = self.producer.send(topic, value=value)
        if callback:
            future.add_callback(callback)
        future.add_errback(self._on_error)
        # flush는 매번 호출하면 느려지므로 필요할 때만 호출하거나 배치 처리가 좋음

    def _on_error(self, exc):
        print(f"❌ Failed to send: {exc}")

    def get_messages(self):
        """메시지를 하나씩 반환하는 제너레이터 (Graceful Exit 추가)"""
        # 종료 신호가 오면 이 변수를 True로 바꿈
        self._stop_event = False

        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}. Stopping producer loop...")
            self._stop_event = True

        # SIGINT(Ctrl+C)와 SIGTERM(Docker Stop)을 감지
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.close()

        print("👋 Producer loop finished.")

    def close(self):
        self.producer.flush()
        self.producer.close()


class KafkaConsumerWrapper:
    def __init__(self, topic, group_id, max_retries=10, initial_delay=2):
        """
        토픽과 그룹 ID를 인자로 받아서 재사용성 극대화
        """
        print(f"🔧 Initializing Kafka Consumer (Group: {group_id}, Topic: {topic})...")
        self.topic = topic
        self.group_id = group_id
        self.consumer = self._create_consumer_with_retry(max_retries, initial_delay)

    def _create_consumer_with_retry(self, max_retries, delay):
        attempt = 0
        while attempt < max_retries:
            try:
                consumer = KafkaConsumer(
                    self.topic,
                    bootstrap_servers=[KAFKA_SERVER],
                    group_id=self.group_id,
                    auto_offset_reset="earliest",
                    enable_auto_commit=False,  # 수동 커밋으로 변경 (중복 방지)
                    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                )
                print("✅ Kafka Consumer Connected!")
                return consumer
            except errors.NoBrokersAvailable:
                attempt += 1
                print(
                    f"⚠️ Consumer Connection Failed ({attempt}/{max_retries}). Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                print(f"❌ Consumer Error: {e}")
                sys.exit(1)

        print("🚨 Consumer failed to connect. Exiting...")
        sys.exit(1)

    def get_messages(self):
        """메시지를 하나씩 반환하는 제너레이터 (Graceful Exit 추가)"""
        # 종료 신호가 오면 이 변수를 True로 바꿈
        self._stop_event = False

        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}. Stopping consumer loop...")
            self._stop_event = True

        # SIGINT(Ctrl+C)와 SIGTERM(Docker Stop)을 감지
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        for message in self.consumer:
            if self._stop_event:
                break
            yield message

        print("👋 Consumer loop finished.")
