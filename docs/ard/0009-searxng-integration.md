# 9. SearXNG Meta-Search Engine Integration

* Status: Accepted
* Date: 2026-01-14
* Context: Phase 3 (Search Enhancement)

## Context and Problem Statement

DuckDuckGo Search API 사용 시 다음과 같은 제약이 있었습니다:

1. **단일 검색 엔진 의존**: DuckDuckGo 장애 시 전체 검색 실패
2. **결과 다양성 부족**: 한 검색 엔진의 결과만 사용
3. **Rate Limiting**: API 호출 제한에 취약
4. **프라이버시**: 외부 API 의존

**필요사항**:
- 다중 검색 엔진 통합
- 자체 호스팅 가능
- DuckDuckGo와 호환되는 인터페이스

## Decision Drivers

* **확장성**: 다중 소스에서 검색 결과 수집
* **안정성**: 단일 장애점 제거
* **프라이버시**: 검색 쿼리 로깅 최소화
* **유연성**: 검색 엔진 전환 용이

## Considered Options

### Option 1: SearXNG (Self-hosted Meta-Search)
**Pros**:
- ✅ 100+ 검색 엔진 통합 (Google, Bing, DuckDuckGo 등)
- ✅ 자체 호스팅, 프라이버시 보장
- ✅ JSON API 지원
- ✅ Docker 이미지 제공

**Cons**:
- ❌ 추가 컨테이너 필요
- ❌ 일부 검색 엔진 불안정할 수 있음

### Option 2: Google Custom Search API
**Pros**:
- ✅ 안정적인 결과

**Cons**:
- ❌ 유료 (100 쿼리/일 무료)
- ❌ API 키 필요

### Option 3: 다중 API 직접 통합
**Pros**:
- ✅ 세밀한 제어

**Cons**:
- ❌ 각 API 별도 구현 필요
- ❌ 유지보수 부담

## Decision Outcome

**SearXNG**를 메타 검색 엔진으로 추가하고, **DuckDuckGo와 전환 가능**한 구조로 구현했습니다.

---

## Implementation Details

### 1. Search Engine Abstraction Layer

```python
# src/common/search_engine.py
class SearchEngine:
    """Base class for search engines."""
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        raise NotImplementedError

class DuckDuckGoSearch(SearchEngine):
    """DuckDuckGo search implementation."""
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"url": r["href"], "title": r["title"], "snippet": r["body"]} for r in results]

class SearXNGSearch(SearchEngine):
    """SearXNG search implementation."""
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.search_endpoint = f"{base_url}/search"
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        params = {"q": query, "format": "json", "categories": "general"}
        response = requests.get(self.search_endpoint, params=params)
        data = response.json()
        return [{"url": r["url"], "title": r["title"], "snippet": r["content"]} 
                for r in data.get("results", [])[:max_results]]

def get_search_engine() -> SearchEngine:
    """Factory function - returns configured search engine."""
    if settings.SEARCH_ENGINE == "searxng" and settings.SEARXNG_URL:
        return SearXNGSearch(settings.SEARXNG_URL)
    return DuckDuckGoSearch()
```

### 2. Configuration

```python
# src/common/config.py
class Settings(BaseSettings):
    SEARCH_ENGINE: str = "duckduckgo"  # 'searxng' or 'duckduckgo'
    SEARXNG_URL: str | None = None     # e.g., http://searxng:8080
```

### 3. Docker Compose

```yaml
# docker-compose.yml
searxng:
  image: searxng/searxng:latest
  profiles:
    - searxng  # Only starts with: docker compose --profile searxng up
  ports:
    - "8080:8080"
  volumes:
    - ./searxng:/etc/searxng:rw
  environment:
    - SEARXNG_BASE_URL=http://localhost:8080/
  cap_drop: [ALL]
  cap_add: [CHOWN, SETGID, SETUID]
```

### 4. SearXNG Settings

```yaml
# searxng/settings.yml
use_default_settings: true

search:
  formats:
    - html
    - json  # Required for API access

engines:
  - name: google
    disabled: false
  - name: bing
    disabled: false
  - name: duckduckgo
    disabled: false
```

---

## Usage

```bash
# DuckDuckGo 사용 (기본값)
docker compose up

# SearXNG 사용
docker compose --profile searxng up

# .env 설정
SEARCH_ENGINE=searxng
SEARXNG_URL=http://searxng:8080
```

---

## Consequences

### Positive

1. ✅ **다중 소스 검색**: Google, Bing, DuckDuckGo 결과 통합
2. ✅ **프라이버시 보장**: 자체 호스팅, 로깅 없음
3. ✅ **장애 대응**: 한 엔진 실패해도 다른 엔진 사용
4. ✅ **호환성 유지**: DuckDuckGo로 언제든 롤백 가능

### Negative

1. ❌ **추가 리소스**: SearXNG 컨테이너 ~100MB
2. ❌ **간헐적 파싱 에러**: 일부 엔진(Startpage 등) 불안정

---

## References

- [SearXNG Documentation](https://docs.searxng.org/)
- [SearXNG Docker](https://github.com/searxng/searxng-docker)
