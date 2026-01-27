from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional
from common.utils import KafkaProducerWrapper
from common.database import get_db, Request, SearchResult, AnalysisResult

app = FastAPI(title="AI Agent API", version="1.0.0")

# CORS settings (for React dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite/CRA default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

producer = KafkaProducerWrapper()


# Request Schema
class AnalyzeRequest(BaseModel):
    topic: str


@app.post("/analyze")
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Create analysis request and start pipeline
    1. Save request to DB (pending status)
    2. Publish search task to Kafka
    3. Update status to searching
    """
    # 1. Create request in DB
    db_request = Request(topic=req.topic, status="pending")
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    
    request_id = str(db_request.id)
    print(f"📝 Created request {request_id} for topic: {req.topic}")
    
    # 2. Publish search task to Kafka (with request_id)
    producer.send_data(
        topic="search-queue",
        value={"request_id": request_id, "topic": req.topic}
    )
    
    # 3. Update status
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
    Get request status
    - Check pipeline progress by request_id
    - Includes search results count and analysis completion status
    """
    db_request = db.query(Request).filter(Request.id == request_id).first()
    
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Basic info
    result = {
        "request_id": str(db_request.id),
        "topic": db_request.topic,
        "status": db_request.status,
        "created_at": db_request.created_at.isoformat(),
        "updated_at": db_request.updated_at.isoformat(),
    }
    
    # Completion time (if exists)
    if db_request.completed_at:
        result["completed_at"] = db_request.completed_at.isoformat()
    
    # Error message (if exists)
    if db_request.error_message:
        result["error"] = db_request.error_message
    
    # Search results count
    result["search_results_count"] = len(db_request.search_results)
    
    # Analysis result (if completed)
    if db_request.analysis_result:
        result["summary"] = db_request.analysis_result.summary
        result["inference_time_ms"] = db_request.analysis_result.inference_time_ms
    
    return result


# ============ Dashboard API ============

@app.get("/api/requests")
def list_requests(
    status: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List requests (with pagination)"""
    query = db.query(Request)
    
    if status and status != 'all':
        query = query.filter(Request.status == status)
    
    total = query.count()
    
    requests = query.order_by(desc(Request.created_at))\
                    .limit(limit)\
                    .offset(offset)\
                    .all()
    
    return {
        "total": total,
        "items": [
            {
                "request_id": str(r.id),
                "topic": r.topic,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
                "search_results_count": len(r.search_results)
            }
            for r in requests
        ]
    }


@app.get("/api/requests/{request_id}")
def get_request_detail(
    request_id: UUID,
    db: Session = Depends(get_db)
):
    """Get request details (including search results + AI analysis)"""
    request = db.query(Request).filter(Request.id == request_id).first()
    if not request:
        raise HTTPException(404, "Request not found")
    
    return {
        "request": {
            "request_id": str(request.id),
            "topic": request.topic,
            "status": request.status,
            "created_at": request.created_at.isoformat(),
            "updated_at": request.updated_at.isoformat(),
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "error_message": request.error_message
        },
        "search_results": [
            {
                "id": sr.id,
                "url": sr.url,
                "title": sr.title,
                "content": sr.content,
                "created_at": sr.created_at.isoformat()
            }
            for sr in request.search_results
        ],
        "analysis_result": {
            "summary": request.analysis_result.summary,
            "inference_time_ms": request.analysis_result.inference_time_ms,
            "created_at": request.analysis_result.created_at.isoformat()
        } if request.analysis_result else None
    }


@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """Get system metrics"""
    # Total requests count
    total = db.query(func.count(Request.id)).scalar()
    
    # Completed requests count
    completed = db.query(func.count(Request.id))\
                  .filter(Request.status == 'completed')\
                  .scalar()
    
    # Average inference time
    avg_time = db.query(func.avg(AnalysisResult.inference_time_ms))\
                 .scalar() or 0
    
    # Status distribution
    status_dist = db.query(
        Request.status,
        func.count(Request.id)
    ).group_by(Request.status).all()
    
    # Requests by hour (last 24 hours)
    since = datetime.utcnow() - timedelta(hours=24)
    hourly = db.query(
        func.date_trunc('hour', Request.created_at).label('hour'),
        func.count(Request.id).label('count')
    ).filter(Request.created_at >= since)\
     .group_by('hour')\
     .order_by('hour')\
     .all()
    
    return {
        "total_requests": total,
        "success_rate": completed / total if total > 0 else 0,
        "avg_inference_time_ms": int(avg_time),
        "requests_by_status": {s: c for s, c in status_dist},
        "requests_by_hour": [
            {"hour": h.isoformat(), "count": c}
            for h, c in hourly
        ]
    }
