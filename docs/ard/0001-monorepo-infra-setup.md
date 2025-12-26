# 1. Monorepo Structure and Basic Infrastructure

* Status: Accepted
* Date: 2025-12-27
* Context: Phase 0 (Initial Setup)

## Context and Problem Statement
본 프로젝트는 **Control Plane(Mac)**과 **Worker Nodes(Linux, Windows/GPU)**가 물리적으로 분리된 하이브리드 클라우드 환경에서 동작하는 분산 AI 에이전트 시스템입니다.
각 서비스(API Server, Search Worker, AI Worker)는 서로 다른 역할을 수행하지만, 공통된 유틸리티(Kafka 연결, 로깅, 설정 관리 등)와 데이터 모델을 공유해야 합니다.
서비스별로 리포지토리를 분리할 경우 코드 중복이 발생하고 관리가 어려워질 우려가 있어, 효율적인 프로젝트 구조와 기반 기술 스택 선정이 필요했습니다.

## Decision Drivers
* **코드 재사용성:** Kafka 연결 로직, 설정(Config) 관리 등 공통 모듈의 중복 제거.
* **관리 편의성:** 단일 진실 공급원(Single Source of Truth)으로서의 코드베이스 관리.
* **이종 환경 지원:** Mac(ARM64)과 Windows(AMD64)를 아우르는 호환성.
* **확장성:** 추후 MSA(Microservices Architecture)로의 자연스러운 확장.

## Considered Options
* **Multi-repo:** 서비스별로 별도의 Git 저장소 사용.
* **Monorepo:** 하나의 저장소에서 모든 서비스 코드 관리.

## Decision Outcome
**Monorepo** 구조를 채택하고, Python 3.11 기반의 모듈화된 설계를 적용하기로 결정했습니다.

### 세부 결정 사항
1.  **Directory Structure:**
    * `src/api-server`: FastAPI 기반의 백엔드 서버.
    * `src/search-worker`: CPU 집약적 작업(크롤링)을 수행하는 워커.
    * `src/ai-worker`: GPU 집약적 작업(LLM 추론)을 수행하는 워커.
    * `src/common`: 모든 서비스가 공유하는 유틸리티 및 설정 파일.
2.  **Configuration Management:**
    * `pydantic-settings` 라이브러리를 도입하여 환경변수 관리의 타입 안전성(Type Safety) 확보.
    * `.env` 파일을 루트에서 통합 관리하며, Docker 실행 시 주입하는 방식 채택.
3.  **Language & Runtime:**
    * 호환성과 생태계를 고려하여 **Python 3.11**로 통일.
    * 각 서비스는 독립적인 `requirements.txt`를 가지지만, 핵심 의존성은 공유함.

## Consequences
* **Positive:** `src/common`을 통해 중복 코드를 제거(DRY)하고 유지보수성을 높임. 프로젝트 전체의 가시성이 확보됨.
* **Negative:** Docker 빌드 시 `Build Context`를 루트(`.`)로 설정해야 하므로 빌드 시간이 다소 증가할 수 있으며, 서비스 간 결합도를 낮추기 위해 의존성 관리에 주의가 필요함.