# src/saver/main.py
import os, json, time, uuid
import boto3
from botocore.client import Config as BotoConfig
import src.common.config as config, src.common.utils as utils


def get_s3_client():
    """MinIO 연결 (S3 호환)"""
    return boto3.client(
        "s3",
        endpoint_url=config.MINIO_ENDPOINT,
        aws_access_key_id=config.MINIO_ACCESS_KEY,
        aws_secret_access_key=config.MINIO_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",  # MinIO는 리전 무관하지만 형식상 필요
    )


def run_saver():
    # 1. Kafka Consumer 연결
    print(f"🔌 Connecting to Kafka ({config.KAFKA_BROKER})...")
    consumer = utils.KafkaConsumerWithRetry().consumer

    # 2. S3(MinIO) 연결
    s3 = get_s3_client()
    print(f"✅ Connected to MinIO. Listening to {config.KAFKA_TOPIC_RAW}...")

    # 3. 메시지 루프
    for message in consumer:
        data = message.value
        url = data.get("url", "no-url")

        # 파일명 생성 (UUID로 중복 방지)
        file_name = f"{uuid.uuid4()}.json"

        try:
            # S3 업로드 (메모리에서 바로 업로드)
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
    # MinIO가 뜰 때까지 잠시 대기 (K8s initContainer 대체용 간이 로직)
    time.sleep(5)
    run_saver()
