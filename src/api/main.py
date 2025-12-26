from fastapi import FastAPI
from common.utils import KafkaProducerWrapper
from common.config import settings

app = FastAPI()
producer = KafkaProducerWrapper()


@app.post("/analyze")
def analyze(topic: str):
    # topic과 payload를 직접 지정해서 유연하게 사용
    producer.send_data(
        topic=settings.KAFKA_TOPIC_API, value={"topic": topic, "status": "requested"}
    )
    return {"status": "ok"}
