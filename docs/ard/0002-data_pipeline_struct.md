# 2. Local Orchestration with Docker Compose

* Status: Accepted
* Date: 2025-12-27
* Context: Phase 0 (Local Development & Validation)

## Context and Problem Statement
실제 운영 환경은 Kubernetes(K8s) 기반의 분산 클러스터지만, 초기 개발 단계에서 물리 서버(Windows) 없이 로컬(Mac) 환경에서 전체 시스템의 데이터 파이프라인(API -> Kafka -> Workers)을 빠르고 가볍게 검증해야 합니다.
또한, Kafka와 같은 무거운 인프라 서비스와 다수의 Python 컨테이너를 일관되게 실행하고 제어할 수 있는 오케스트레이션 도구가 필요합니다.

## Decision Drivers
* **개발 속도:** 복잡한 K8s 설정 없이 즉시 실행 가능해야 함(`docker-compose up`).
* **네트워크 시뮬레이션:** 컨테이너 간의 서비스 이름(`kafka:29092`) 기반 통신 검증.
* **환경 일치:** 로컬 개발 환경과 향후 배포될 프로덕션 환경의 논리적 아키텍처 일치.
* **안정성:** Kafka 초기화 지연 및 컨테이너 종료 시그널 처리 문제 해결.

## Considered Options
* **Local Kubernetes (Minikube/K3s):** 실제 환경과 가장 유사하나, 설정 오버헤드가 크고 리소스를 많이 소모함.
* **Docker Compose:** 설정이 간편하고 로컬 테스트에 최적화됨.
* **Raw Process:** 터미널 여러 개를 띄워 직접 실행. 의존성 관리가 어렵고 환경 오염 위험.

## Decision Outcome
초기 개발 및 로컬 테스트를 위해 **Docker Compose**를 표준 오케스트레이션 도구로 채택했습니다.

### 세부 결정 사항
1.  **Service Definition:**
    * `zookeeper`, `kafka`: 메시지 브로커 인프라. (Kafka 버전은 KRaft 이슈 회피를 위해 `7.4.0`으로 고정)
    * `api-server`, `search-worker`, `ai-worker`: 애플리케이션 서비스.
2.  **Build Strategy:**
    * 모든 서비스의 빌드 컨텍스트(`context`)를 프로젝트 루트(`.`)로 설정하여 `src/common` 모듈 접근 허용.
    * Dockerfile 내부에서 `COPY src/api-server .` 및 `COPY src/common ./common` 패턴을 사용하여 컨테이너 내부 경로 구조를 단순화(Flatten).
3.  **Stability Configuration:**
    * `restart: on-failure`: Kafka 부팅 지연 등으로 인한 초기 연결 실패 시 자동 복구.
    * `init: true`: 좀비 프로세스 방지 및 SIGTERM 시그널의 올바른 전달.
    * `stop_grace_period`: Kafka 및 Stateful 서비스의 데이터 저장을 위한 충분한 종료 대기 시간 설정.
4.  **Network & Environment:**
    * 루트 `.env` 파일을 `env_file` 옵션으로 주입하여 단일 설정 관리.
    * Docker 내부 네트워크 DNS를 활용하여 서비스 디스커버리 구현.

## Consequences
* **Positive:** `docker-compose up --build` 명령어 하나로 전체 파이프라인을 구동 및 테스트 가능. 인프라 의존성을 코드로 정의(IaC)하여 팀원 간 환경 격차 해소.
* **Negative:** 단일 머신 리소스(CPU/RAM)의 한계가 있으며, 실제 네트워크 지연(Latency)이나 이기종 OS 간의 문제는 감지하지 못함(추후 Phase 1에서 해결).