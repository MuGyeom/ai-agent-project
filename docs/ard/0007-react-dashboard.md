# 6. React Dashboard for Request Monitoring

* Status: Accepted
* Date: 2026-01-10
* Context: Phase 3 (User Interface Layer)

## Context and Problem Statement

PostgreSQL 영속성 레이어(ARD-0005)를 통해 데이터를 저장하게 되었지만, 다음과 같은 문제가 있었습니다:

1. **가시성 부족**: API 호출로만 데이터 확인 가능
2. **수동 확인**: curl/Postman으로 직접 API 호출 필요
3. **실시간 모니터링 불가**: 진행상황 자동 갱신 없음
4. **분석 결과 확인 어려움**: JSON 응답 직접 파싱 필요
5. **시스템 상태 파악 어려움**: 메트릭 없음

**필요사항**:
- 웹 기반 실시간 대시보드
- 요청 목록 조회 및 상세 보기
- 분석 요청 생성 기능
- 시스템 메트릭 시각화

## Decision Drivers

* **개발 속도**: 빠른 프로토타이핑 필요
* **반응형 UI**: 데스크톱/모바일 지원
* **실시간 업데이트**: Auto-refresh 기능
* **차트 시각화**: 메트릭 데이터 시각화
* **컨테이너화**: Docker 통합 필수
* **타입 안정성**: 컴포넌트 재사용성

## Considered Options

### Option 1: Vite + React + TailwindCSS
**Pros**:
- ✅ 빠른 개발 서버 (HMR)
- ✅ 경량 번들 사이즈
- ✅ TailwindCSS 유틸리티 클래스
- ✅ React Router 통합
- ✅ Recharts 차트 라이브러리 연동

**Cons**:
- ❌ SSR 미지원 (SEO 불필요하므로 무관)
- ❌ TailwindCSS 학습 곡선

### Option 2: Next.js
**Pros**:
- ✅ SSR/SSG 지원
- ✅ 파일 기반 라우팅
- ✅ API Routes 내장

**Cons**:
- ❌ 오버엔지니어링 (SSR 불필요)
- ❌ 복잡한 설정
- ❌ 무거운 번들

### Option 3: Vue.js
**Pros**:
- ✅ 쉬운 학습 곡선
- ✅ 통합 생태계

**Cons**:
- ❌ React 대비 생태계 작음
- ❌ 기존 경험 부족

### Option 4: Plain HTML + JavaScript
**Pros**:
- ✅ 의존성 없음
- ✅ 간단한 구조

**Cons**:
- ❌ 컴포넌트 재사용 어려움
- ❌ 상태 관리 복잡
- ❌ 차트 라이브러리 통합 어려움

## Decision Outcome

**Vite + React + TailwindCSS + Recharts**를 선택했습니다.

### Rationale

1. **빠른 개발 사이클**: 
   - Vite HMR: <100ms 갱신
   - TailwindCSS: 스타일 파일 분리 불필요

2. **컴포넌트 기반 구조**:
   ```
   src/
   ├── components/
   │   ├── RequestList.jsx    # 요청 목록
   │   ├── RequestDetail.jsx  # 요청 상세
   │   └── MetricsDashboard.jsx  # 메트릭 시각화
   ├── api/
   │   └── client.js          # API 클라이언트
   └── App.jsx                # 라우터 설정
   ```

3. **실시간 업데이트**:
   ```javascript
   useEffect(() => {
       const interval = setInterval(loadRequests, 5000);
       return () => clearInterval(interval);
   }, [filter]);
   ```

4. **Docker 통합 용이**:
   ```yaml
   dashboard:
     image: node:20-alpine
     command: sh -c "npm install && npm run dev -- --host"
   ```

---

## Implementation Details

### 1. Project Structure

```
src/dashboard/
├── public/
│   └── vite.svg
├── src/
│   ├── api/
│   │   └── client.js         # fetch 래퍼
│   ├── components/
│   │   ├── RequestList.jsx   # 요청 목록 + 필터링 + 생성
│   │   ├── RequestDetail.jsx # 요청 상세 + 검색결과 + AI 분석
│   │   └── MetricsDashboard.jsx  # 차트 시각화
│   ├── App.jsx               # 라우터
│   ├── App.css
│   ├── main.jsx              # 엔트리포인트
│   └── index.css             # TailwindCSS
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

---

### 2. Key Components

#### RequestList.jsx
```javascript
// 요청 목록 조회 + 페이지네이션 + 필터링
function RequestList() {
    const [requests, setRequests] = useState([]);
    const [filter, setFilter] = useState('all');
    
    // 자동 새로고침 (5초)
    useEffect(() => {
        loadRequests();
        const interval = setInterval(loadRequests, 5000);
        return () => clearInterval(interval);
    }, [filter]);
    
    // 새 분석 요청 생성
    const handleCreateRequest = async (e) => {
        await createRequest(newTopic);
        await loadRequests();
    };
}
```

**기능**:
- ✅ 상태별 필터링 (all, completed, analyzing, searching, failed)
- ✅ 새 분석 요청 생성 폼
- ✅ 5초 자동 새로고침
- ✅ 상세 페이지 링크

#### RequestDetail.jsx
```javascript
// 요청 상세 + 검색 결과 + AI 분석 결과
function RequestDetail() {
    const { requestId } = useParams();
    const [data, setData] = useState(null);
    
    // 검색 결과 + 분석 결과 표시
    return (
        <>
            <RequestInfo request={data.request} />
            <SearchResults results={data.search_results} />
            <AISummary analysis={data.analysis_result} />
        </>
    );
}
```

**기능**:
- ✅ 요청 메타데이터 (ID, 생성일, 상태)
- ✅ 검색 결과 목록 (제목, URL, 콘텐츠 미리보기)
- ✅ AI 분석 결과 (요약, 추론 시간)
- ✅ 5초 자동 새로고침 (진행 중 요청용)

#### MetricsDashboard.jsx
```javascript
// Recharts 기반 시각화
function MetricsDashboard() {
    const [metrics, setMetrics] = useState(null);
    
    return (
        <div className="grid grid-cols-2 gap-6">
            {/* Overview Cards */}
            <Card title="Total Requests" value={metrics.total_requests} />
            <Card title="Success Rate" value={metrics.success_rate} />
            <Card title="Avg Inference Time" value={`${metrics.avg_inference_time_ms}ms`} />
            
            {/* Charts */}
            <LineChart data={metrics.requests_by_hour} />
            <PieChart data={metrics.requests_by_status} />
        </div>
    );
}
```

**기능**:
- ✅ 총 요청 수, 성공률, 평균 추론 시간
- ✅ 시간대별 요청 수 (24시간 LineChart)
- ✅ 상태별 분포 (PieChart)
- ✅ 30초 자동 새로고침

---

### 3. API Client

```javascript
// src/api/client.js
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchRequests(status = 'all') {
    const url = status === 'all' 
        ? `${API_BASE}/api/requests`
        : `${API_BASE}/api/requests?status=${status}`;
    const response = await fetch(url);
    return response.json();
}

export async function createRequest(topic) {
    const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic })
    });
    return response.json();
}
```

**환경 변수**:
- `VITE_API_URL`: API 서버 주소 (기본: http://localhost:8000)

---

### 4. Docker Configuration

```yaml
# docker-compose.yml
dashboard:
  image: node:20-alpine
  working_dir: /app
  ports:
    - "5173:5173"
  volumes:
    - ./src/dashboard:/app
    - /app/node_modules  # node_modules 덮어쓰기 방지
  command: sh -c "npm install && npm run dev -- --host"
  environment:
    - VITE_API_URL=http://localhost:8000
  depends_on:
    - api-server
```

**설계 결정**:
- **Volume Mount**: 소스 코드 실시간 반영
- **node_modules 보호**: 호스트 node_modules와 충돌 방지
- **--host 옵션**: 컨테이너 외부에서 접근 가능

---

### 5. API Server Extensions

대시보드용 새 엔드포인트 추가:

```python
# GET /api/requests - 요청 목록 (페이지네이션)
@app.get("/api/requests")
def list_requests(status: Optional[str] = None, limit: int = 20, offset: int = 0):
    # 필터링, 페이지네이션 처리
    return {"total": total, "items": [...]}

# GET /api/requests/{id} - 요청 상세
@app.get("/api/requests/{request_id}")
def get_request_detail(request_id: UUID):
    # 검색 결과 + 분석 결과 포함
    return {"request": {...}, "search_results": [...], "analysis_result": {...}}

# GET /api/metrics - 시스템 메트릭
@app.get("/api/metrics")
def get_metrics():
    return {
        "total_requests": count,
        "success_rate": rate,
        "avg_inference_time_ms": time,
        "requests_by_status": {...},
        "requests_by_hour": [...]
    }
```

**CORS 설정**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Consequences

### Positive

1. ✅ **가시성 향상**: 웹 브라우저에서 실시간 확인
2. ✅ **사용성 개선**: 클릭 기반 UI
3. ✅ **실시간 모니터링**: 자동 새로고침
4. ✅ **메트릭 시각화**: 차트로 시스템 상태 파악
5. ✅ **빠른 개발**: Vite HMR + TailwindCSS
6. ✅ **컨테이너화**: docker-compose로 통합 배포
7. ✅ **반응형**: 모바일 지원

### Negative

1. ❌ **의존성 증가**:
   - Node.js 20 컨테이너 추가
   - npm 패키지 관리
   
2. ❌ **리소스 소모**:
   - 개발 서버 RAM: ~150MB
   - node_modules: ~200MB 디스크

3. ❌ **Poll 기반 업데이트**:
   - WebSocket 미사용 (향후 개선 가능)
   - 5초 간격 폴링

---

## Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^7.1.1",
    "recharts": "^2.15.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "vite": "^6.0.5"
  }
}
```

---

## Status Colors

상태별 시각적 구분:

| Status | Color | Meaning |
|--------|-------|---------|
| pending | yellow | 대기 중 |
| searching | blue-100 | 검색 중 |
| processing_search | blue-200 | 검색 처리 중 (locked) |
| analyzing | purple-100 | AI 분석 중 |
| processing_analysis | purple-200 | AI 분석 처리 중 (locked) |
| completed | green | 완료 |
| failed | red | 실패 |

---

## Future Enhancements

### 1. WebSocket Real-time Updates
```javascript
// Replace polling with WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    updateRequest(update);
};
```

### 2. Dark Mode
```javascript
// TailwindCSS dark mode
<div className="dark:bg-gray-900 dark:text-white">
```

### 3. Export/Download
- 분석 결과 PDF 다운로드
- 검색 결과 CSV 내보내기

### 4. Advanced Filtering
- 날짜 범위 선택
- 토픽 검색
- 정렬 옵션

---

## Access

- **URL**: http://localhost:5173
- **API**: http://localhost:8000 (CORS 허용)

---

## References

- [Vite Documentation](https://vitejs.dev/)
- [TailwindCSS](https://tailwindcss.com/)
- [Recharts](https://recharts.org/)
- [React Router v7](https://reactrouter.com/)
