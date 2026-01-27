# src/saver/main.py
import os, json, time, uuid
import boto3
from botocore.client import Config as BotoConfig
import src.common.config as config, src.common.utils as utils


def get_s3_client():
    """Connect to MinIO (S3 compatible)"""
    return boto3.client(
        "s3",
        endpoint_url=config.MINIO_ENDPOINT,
        aws_access_key_id=config.MINIO_ACCESS_KEY,
        aws_secret_access_key=config.MINIO_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",  # MinIO doesn't care about region, but required for format
    )


def run_saver():
    # 1. Connect to Kafka Consumer
    print(f"🔌 Connecting to Kafka ({config.KAFKA_BROKER})...")
    consumer = utils.KafkaConsumerWithRetry().consumer

    # 2. Connect to S3 (MinIO)
    s3 = get_s3_client()
    print(f"✅ Connected to MinIO. Listening to {config.KAFKA_TOPIC_RAW}...")

    # 3. Message loop
    for message in consumer:
        data = message.value
        url = data.get("url", "no-url")

        # Generate filename (UUID to prevent duplicates)
        file_name = f"{uuid.uuid4()}.json"

        try:
            # Upload directly to S3 from memory
            s3.put_object(
                Bucket=config.MINIO_BUCKET_NAME,
                Key=file_name,
                Body=json.dumps(data, ensure_ascii=False),
                ContentType="application/json",
            )
            print(f"💾 Saved: {file_name} (Source: {url})")

        except Exception as e:
            print(f"❌ Failed to save to MinIO: {e}")


if __name__ == "__main__":
    # Wait for MinIO to be ready (simple logic to replace K8s initContainer)
    time.sleep(5)
    run_saver()
