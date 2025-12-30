from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID
from common.utils import KafkaProducerWrapper
from common.database import get_db, Request

app = FastAPI()
producer = KafkaProducerWrapper()


# Request Schema
class AnalyzeRequest(BaseModel):
    topic: str


@app.post("/analyze")
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    분석 요청 생성 및 파이프라인 시작
    1. DB에 요청 저장 (pending 상태)
    2. Kafka에 검색 작업 발행
    3. 상태를 searching으로 업데이트
    """
    # 1. DB에 요청 생성
    db_request = Request(topic=req.topic, status="pending")
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    
    request_id = str(db_request.id)
    print(f"📝 Created request {request_id} for topic: {req.topic}")
    
    # 2. Kafka에 검색 작업 발행 (request_id 포함)
    producer.send_data(
        topic="search-queue",
        value={"request_id": request_id, "topic": req.topic}
    )
    
    # 3. 상태 업데이트
    db_request.status = "searching"
    db.commit()
    print(f"🔍 Status updated to 'searching' for request {request_id}")
    
    return {
        "request_id": request_id,
        "status": "searching",
        "message": f"Analysis started for {req.topic}"
    }


@app.get("/status/{request_id}")
def get_status(request_id: UUID, db: Session = Depends(get_db)):
    """
    요청 상태 조회
    - request_id로 전체 파이프라인 진행상황 확인
    - 검색 결과 개수, 분석 완료 여부 포함
    """
    db_request = db.query(Request).filter(Request.id == request_id).first()
    
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # 기본 정보
    result = {
        "request_id": str(db_request.id),
        "topic": db_request.topic,
        "status": db_request.status,
        "created_at": db_request.created_at.isoformat(),
        "updated_at": db_request.updated_at.isoformat(),
    }
    
    # 완료 시간 (있으면)
    if db_request.completed_at:
        result["completed_at"] = db_request.completed_at.isoformat()
    
    # 에러 메시지 (있으면)
    if db_request.error_message:
        result["error"] = db_request.error_message
    
    # 검색 결과 개수
    result["search_results_count"] = len(db_request.search_results)
    
    # 분석 결과 (완료 시)
    if db_request.analysis_result:
        result["summary"] = db_request.analysis_result.summary
        result["inference_time_ms"] = db_request.analysis_result.inference_time_ms
    
    return result
