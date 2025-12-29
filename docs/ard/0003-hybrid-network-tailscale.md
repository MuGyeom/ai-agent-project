# 3. Hybrid Networking with Tailscale Overlay

* Status: Accepted
* Date: 2025-12-27
* Context: Phase 1 & 2 (Inter-node Communication)

## Context and Problem Statement
Control Plane(Mac)과 Worker Node(Windows)가 서로 다른 물리적 네트워크(또는 NAT 환경)에 위치해 있습니다.
Mac에서 구동되는 Kafka 브로커에 Windows의 AI Worker가 접근해야 합니다.
공유기 포트 포워딩(Port Forwarding)이나 공인 IP 노출은 보안상 위험하고 설정이 번거로우며, 유동 IP 환경에서 불안정합니다.

## Decision Drivers
* **Security:** 브로커 포트(9092)를 공공 인터넷(Public Internet)에 노출하지 않아야 함.
* **Connectivity:** 복잡한 NAT/Firewall 설정을 최소화하고 즉시 연결 가능해야 함.
* **Stability:** 기기가 재부팅되더라도 고정된 사설 IP로 통신할 수 있어야 함.

## Considered Options
* **Public IP + Port Forwarding:** 보안 취약점 높음, IP 변경 시 재설정 필요.
* **SSH Tunneling:** 연결 끊김 시 재연결 관리 복잡, 설정이 까다로움.
* **VPN Overlay (Tailscale/WireGuard):** 암호화된 터널링, 고정 IP 제공, NAT Traversal 지원.

## Decision Outcome
**Tailscale**을 사용하여 Mesh Network를 구성하기로 결정했습니다.

### 세부 결정 사항
1.  **Network Topology:**
    * 모든 노드(Mac, Windows)는 Tailscale VPN에 접속하여 `100.x.y.z` 대역의 고정 IP를 할당받음.
2.  **Kafka Configuration Strategy:**
    * Kafka는 `0.0.0.0`으로 바인딩하여 모든 인터페이스의 트래픽을 수신(`LISTENERS`).
    * 클라이언트에게 알려주는 주소(`ADVERTISED_LISTENERS`)에는 **Mac의 Tailscale IP**를 명시하여, 외부(Windows)에서도 정확히 찾아올 수 있도록 함.
3.  **Firewall Policy:**
    * OS 레벨(Mac 방화벽)에서 9092 포트 수신을 허용해야 함.
    * Windows Docker는 `network_mode: host` 대신 기본 브리지 모드를 사용하되, 호스트의 VPN 경로를 따르도록 구성.

## Consequences
* **Positive:** 복잡한 라우터 설정 없이 안전한 사설망(VPC)과 유사한 환경 구축 성공. 물리적 위치와 무관하게 노드 확장 가능.
* **Negative:** 각 호스트 머신에 Tailscale 클라이언트 설치 필수. Kafka 설정 시 `ADVERTISED_LISTENERS`에 대한 명확한 이해 필요(오설정 시 `NoBrokersAvailable` 빈발).