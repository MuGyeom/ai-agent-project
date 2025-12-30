from sqlalchemy import create_engine, Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from common.config import settings

Base = declarative_base()

# Request 모델: 전체 요청 lifecycle 관리
class Request(Base):
    __tablename__ = 'requests'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='pending')  # pending, searching, analyzing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Relationships
    search_results = relationship("SearchResult", back_populates="request", cascade="all, delete-orphan")
    analysis_result = relationship("AnalysisResult", back_populates="request", uselist=False, cascade="all, delete-orphan")

# SearchResult 모델: 검색 결과 저장
class SearchResult(Base):
    __tablename__ = 'search_results'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey('requests.id'), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    request = relationship("Request", back_populates="search_results")

# AnalysisResult 모델: AI 분석 결과 저장
class AnalysisResult(Base):
    __tablename__ = 'analysis_results'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey('requests.id'), nullable=False)
    summary = Column(Text, nullable=False)
    tokens_used = Column(Integer)
    inference_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    request = relationship("Request", back_populates="analysis_result")

# Database 연결 설정
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 연결 유효성 검사
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI
def get_db():
    """Database session dependency"""
    db = SessionLocal()
    print("postgreSQL connected!")
    try:
        yield db
    finally:
        db.close()
