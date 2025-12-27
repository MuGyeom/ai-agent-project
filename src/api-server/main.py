from fastapi import FastAPI
from pydantic import BaseModel  # <-- 필수 import
from common.utils import KafkaProducerWrapper

app = FastAPI()
producer = KafkaProducerWrapper()


# [수정] 요청 데이터 구조 정의 (Schema)
class AnalyzeRequest(BaseModel):
    topic: str


@app.post("/analyze")
def analyze(req: AnalyzeRequest):  # <-- 여기를 AnalyzeRequest 타입으로 변경
    # req.topic 으로 데이터 접근
    producer.send_data(
        topic="search-queue", value={"topic": req.topic, "status": "requested"}
    )
    return {"status": "ok", "message": f"Analysis started for {req.topic}"}
