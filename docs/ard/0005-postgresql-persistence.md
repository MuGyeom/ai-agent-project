# 5. PostgreSQL for Request Lifecycle Tracking

* Status: Accepted
* Date: 2025-12-30
* Context: Phase 2 (Data Persistence Layer)

## Context and Problem Statement

Phase 1까지는 Kafka를 통한 ephemeral messaging으로 데이터를 전달했지만, 다음과 같은 문제가 있었습니다:

1. **추적 불가**: 요청 ID가 없어 전체 파이프라인 추적 불가
2. **휘발성**: 컨테이너 재시작 시 모든 결과 손실
3. **재현 불가**: 과거 요청 및 결과 재조회 불가
4. **디버깅 어려움**: 실패한 요청 분석 불가
5. **사용자 경험**: 실시간 진행상황 확인 불가

**필요사항**:
- UUID 기반 요청 추적 시스템
- 검색 결과 및 AI 분석 결과 영구 저장
- RESTful API로 상태 조회
- 향후 Redis 캐싱 레이어 통합 대비

## Decision Drivers

* **데이터 일관성**: ACID 트랜잭션 보장 필요
* **관계형 모델**: request → search_results, request → analysis_result (1:N, 1:1)
* **쿼리 복잡도**: JOIN, aggregate 등 복잡한 쿼리 필요
* **확장성**: Redis cache-aside pattern 적용 계획
* **운영 편의성**: 검증된 기술 스택, 풍부한 생태계
* **리소스 효율**: 12GB 이하 메모리 사용

## Considered Options

### Option 1: PostgreSQL
**Pros**:
- ✅ ACID 보장 (강력한 일관성)
- ✅ 관계형 모델 (FK, JOIN 지원)
- ✅ 성숙한 생태계 (SQLAlchemy, pgAdmin)
- ✅ JSON 타입 지원 (유연성)
- ✅ Full-text search 기능
- ✅ Redis 통합 패턴 검증됨

**Cons**:
- ❌ 스키마 변경 시 migration 필요
- ❌ NoSQL 대비 수평 확장 제약

### Option 2: MongoDB
**Pros**:
- ✅ Schema-less (유연성)
- ✅ 수평 확장 용이
- ✅ JSON-native

**Cons**:
- ❌ ACID 보장 약함 (단일 document만)
- ❌ JOIN 성능 낮음
- ❌ 관계형 데이터 모델링 어려움
- ❌ SQLAlchemy ORM 미지원

### Option 3: Redis (단독)
**Pros**:
- ✅ 초고속 읽기/쓰기
- ✅ 간단한 설정

**Cons**:
- ❌ 영속성 보장 약함 (AOF/RDB 설정 필요)
- ❌ 복잡한 쿼리 불가
- ❌ 메모리 제약 (모든 데이터 RAM에)
- ❌ 관계형 모델 표현 어려움

### Option 4: File Storage (JSON/SQLite)
**Pros**:
- ✅ 추가 인프라 불필요
- ✅ 간단한 구조

**Cons**:
- ❌ 동시성 제어 어려움
- ❌ 복잡한 쿼리 불가
- ❌ 확장성 없음
- ❌ 트랜잭션 보장 약함

## Decision Outcome

**PostgreSQL 16-alpine**을 영속성 레이어로 선택했습니다.

### Rationale

1. **ACID 보장**: 데이터 일관성이 최우선
   - 요청과 결과 간 관계 무결성 필수
   - 실패 시 rollback 보장

2. **관계형 모델 적합**:
   ```
   requests (1) ─────→ (N) search_results
            └────→ (1) analysis_result
   ```
   - Foreign Key로 referential integrity 보장
   - CASCADE delete로 정리 자동화

3. **검증된 Cache-Aside 패턴**:
   ```python
   # Future: Redis integration
   def get_request(id):
       cached = redis.get(f"req:{id}")
       if cached: return cached
       
       db_data = postgres.query(...)
       redis.setex(f"req:{id}", 60, db_data)
       return db_data
   ```

4. **SQLAlchemy ORM**:
   - Type-safe 모델 정의
   - 자동 마이그레이션 (Alembic)
   - 테스트 용이성

5. **Alpine 경량화**:
   - 이미지: 100MB (vs 300MB standard)
   - RAM: ~200MB (vs ~500MB)

---

## Implementation Details

### 1. Database Schema

```sql
-- UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Request lifecycle table
CREATE TABLE requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending/searching/analyzing/completed/failed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Search results (1:N)
CREATE TABLE search_results (
    id SERIAL PRIMARY KEY,
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analysis results (1:1)
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    tokens_used INTEGER,
    inference_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Design Decisions**:
- **UUID**: 분산 환경에서 충돌 방지
- **CASCADE**: 부모 삭제 시 자식 자동 삭제
- **Indexes**: request_id, status, created_at
- **Auto-trigger**: updated_at 자동 업데이트

---

### 2. SQLAlchemy Models

```python
# src/common/database.py
from sqlalchemy import create_engine, Column, UUID, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Request(Base):
    __tablename__ = 'requests'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default='pending')
    
    # Relationships
    search_results = relationship("SearchResult", back_populates="request", 
                                  cascade="all, delete-orphan")
    analysis_result = relationship("AnalysisResult", back_populates="request",
                                   uselist=False, cascade="all, delete-orphan")
```

**Benefits**:
- Type safety (IDE autocomplete)
- Automatic relationship loading
- Query builder (ORM)

---

### 3. Service Integration

#### API Server
```python
@app.post("/analyze")
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    # 1. Create request in DB
    db_request = Request(topic=req.topic, status="pending")
    db.add(db_request)
    db.commit()
    
    # 2. Publish to Kafka (with request_id)
    producer.send({"request_id": str(db_request.id), "topic": req.topic})
    
    # 3. Update status
    db_request.status = "searching"
    db.commit()
    
    return {"request_id": str(db_request.id)}
```

#### Search Worker
```python
# Save search results to DB
for result in search_results:
    db.add(SearchResult(request_id=request_id, url=result['url'], ...))

db_request.status = "analyzing"
db.commit()
```

#### AI Worker
```python
# Load search results from DB
search_results = db.query(SearchResult).filter_by(request_id=request_id).all()

# Save analysis
db.add(AnalysisResult(request_id=request_id, summary=summary, ...))
db_request.status = "completed"
db.commit()
```

---

### 4. Docker Configuration

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: ai_agent
    POSTGRES_USER: agent
    POSTGRES_PASSWORD: agent_password
  volumes:
    - postgres-data:/var/lib/postgresql/data
    - ./src/database/init.sql:/docker-entrypoint-initdb.d/init.sql
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U agent -d ai_agent"]
    interval: 5s
    retries: 5
```

**Key Features**:
- Auto-initialization: `init.sql` runs on first start
- Health check: Services wait for DB ready
- Volume: Data persistence across restarts

---

## Consequences

### Positive

1. ✅ **완전한 추적성**: UUID로 전체 파이프라인 추적
2. ✅ **데이터 영속성**: 컨테이너 재시작해도 결과 보존
3. ✅ **재현성**: 과거 요청 재조회 가능
4. ✅ **디버깅 향상**: 실패 원인 분석 가능
5. ✅ **상태 조회**: RESTful API로 진행상황 확인
6. ✅ **Redis 준비**: Cache-aside 패턴 적용 가능
7. ✅ **확장성**: 적절한 인덱싱으로 성능 유지
8. ✅ **안정성**: ACID 보장으로 데이터 일관성

### Negative

1. ❌ **복잡도 증가**: 
   - SQLAlchemy 학습 곡선
   - Migration 관리 필요
   
2. ❌ **추가 리소스**:
   - RAM: ~200MB
   - Disk: Volume 필요
   
3. ❌ **초기 설정**:
   - Schema 설계 및 마이그레이션
   - 각 Worker DB 연동 코드
   
4. ⚠️ **볼륨 관리**:
   - `docker-compose down -v` 시 데이터 손실 주의
   - 백업 전략 필요

---

## Migration Strategy

### Phase 1 → Phase 2 전환

**Breaking Changes**: 없음

**Kafka Message 형식 변경**:
```python
# Before
{"topic": "search query", "status": "requested"}

# After
{"request_id": "uuid-string", "topic": "search query"}
```

**점진적 적용**:
1. ✅ PostgreSQL 서비스 추가
2. ✅ Schema 생성 (auto-init)
3. ✅ API Server 수정 (request creation)
4. ✅ Search Worker 수정 (result saving)
5. ✅ AI Worker 수정 (analysis saving)
6. ✅ Status API 추가

**Rollback Plan**:
- PostgreSQL 컨테이너만 제거
- Kafka 메시지는 topic 필드만 사용
- 기존 Worker 코드로 복원 가능

---

## Performance Considerations

### Expected Load
- Requests/day: ~1,000
- Search results/request: 3-8
- DB size growth: ~10MB/day

### Optimization
1. **Indexes**:
   ```sql
   CREATE INDEX idx_requests_status ON requests(status);
   CREATE INDEX idx_requests_created ON requests(created_at DESC);
   CREATE INDEX idx_search_request_id ON search_results(request_id);
   ```

2. **Connection Pooling**:
   ```python
   engine = create_engine(url, pool_size=5, max_overflow=10)
   ```

3. **Partial Indexes** (future):
   ```sql
   CREATE INDEX idx_active_requests ON requests(status) 
   WHERE status IN ('pending', 'searching', 'analyzing');
   ```

---

## Future Enhancements

### 1. Redis Caching Layer
```yaml
redis:
  image: redis:7-alpine
  # Status 조회 캐싱
```

**Cache Strategy**:
- `request:{id}:status` (TTL: 60s)
- `request:{id}:summary` (TTL: 5m)
- Write-through on status update

### 2. Read Replica
```yaml
postgres-replica:
  # Analytics queries offloading
```

### 3. Partitioning
```sql
-- Time-based partitioning for old data
CREATE TABLE requests_2025_01 PARTITION OF requests
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

### 4. Full-Text Search
```sql
CREATE INDEX idx_search_content_fts ON search_results 
USING GIN (to_tsvector('english', content));
```

---

## Security Considerations

1. **Credentials Management**:
   - Password in `.env` file (not committed)
   - Production: Secret management (Vault, K8s Secrets)

2. **SQL Injection**:
   - ✅ SQLAlchemy ORM (parameterized queries)
   - ❌ No raw SQL strings

3. **Access Control**:
   - Single user (`agent`) for simplicity
   - Future: Row-level security (RLS)

---

## Monitoring & Maintenance

### Health Checks
```bash
# PostgreSQL health
docker exec postgres pg_isready -U agent

# Connection test
docker exec postgres psql -U agent -d ai_agent -c "SELECT 1"
```

### Useful Queries
```sql
-- Active requests
SELECT status, COUNT(*) FROM requests GROUP BY status;

-- Today's requests
SELECT COUNT(*) FROM requests WHERE created_at > CURRENT_DATE;

-- Average processing time
SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) 
FROM requests WHERE status = 'completed';
```

### Backup Strategy
```bash
# Manual backup
docker exec postgres pg_dump -U agent ai_agent > backup.sql

# Automated (future)
# - Daily snapshots to S3
# - Point-in-time recovery (WAL archiving)
```

---

## Alternatives Not Chosen

### Why not MongoDB?
- 관계형 모델이 명확함 (request → results)
- JOIN 성능 중요 (status 조회 시)
- ACID 보장 필수

### Why not Redis only?
- 영속성 보장 약함
- 메모리 제약 (모든 데이터 RAM)
- Redis는 캐싱 레이어로 활용 예정

### Why not MySQL?
- PostgreSQL vs MySQL은 선호도 차이
- PostgreSQL의 JSON 지원이 더 강력
- 이미 PostgreSQL 경험 있음

---

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/16/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [Cache-Aside Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside)
