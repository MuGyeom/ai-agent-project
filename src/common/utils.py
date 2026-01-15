import json, time, sys, signal
from kafka import KafkaProducer, KafkaConsumer, errors
from common.config import settings

KAFKA_SERVER = (
    settings.KAFKA_BROKER if settings.KAFKA_BROKER else settings.KAFKA_BOOTSTRAP_SERVERS
)
# Print current Kafka broker address for debugging
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
        Generic method to send any data to any topic
        """
        future = self.producer.send(topic, value=value)
        if callback:
            future.add_callback(callback)
        future.add_errback(self._on_error)
        # Avoid calling flush on every send for performance; use batch processing instead

    def _on_error(self, exc):
        print(f"❌ Failed to send: {exc}")

    def get_messages(self):
        """Generator that yields messages one by one (with graceful exit)"""
        # Set to True when shutdown signal is received
        self._stop_event = False

        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}. Stopping producer loop...")
            self._stop_event = True

        # Catch SIGINT (Ctrl+C) and SIGTERM (Docker stop)
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
        Initialize consumer with topic and group_id for maximum reusability
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
                    enable_auto_commit=False,  # Manual commit to prevent duplicate analysis
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
        """Generator that yields messages one by one (with graceful exit)"""
        # Set to True when shutdown signal is received
        self._stop_event = False

        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}. Stopping consumer loop...")
            self._stop_event = True

        # Catch SIGINT (Ctrl+C) and SIGTERM (Docker stop)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        for message in self.consumer:
            if self._stop_event:
                break
            yield message

        print("👋 Consumer loop finished.")
