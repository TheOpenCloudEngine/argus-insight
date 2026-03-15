# Argus Insight

Argus Insight는 '백 개의 눈'을 가진 신화 속 수호자처럼, 방대한 데이터를 빈틈없이 관측하여 숨겨진 가치를 찾아내는 지능형 Data + AI Platform입니다. 데이터의 전 생명주기 동안 활용할 수 있는 소프트웨어 스택과 관리 방법을 제공합니다.

## 프로젝트 구조

```
argus-insight/
├── CLAUDE.md                    # 이 파일 (루트 가이드)
├── argus-insight-agent/         # 서버 관리 에이전트 (Python/FastAPI)
└── README.md
```

## 서브 프로젝트

### argus-insight-agent
관리 대상 서버에 설치되어 root 권한으로 동작하는 서버 관리 에이전트입니다. Argus Insight 플랫폼의 중앙 관리 서버가 이 에이전트를 통해 원격 서버를 제어합니다.

주요 기능:
- **커맨드 실행**: 원격 서버에서 셸 명령을 실행하고 결과를 반환
- **서버 자원 모니터링**: CPU, 메모리, 디스크, 네트워크 상태를 실시간 수집 및 스트리밍
- **애플리케이션 설치 및 관리**: dnf/yum/apt를 통한 패키지 설치, 삭제, 업데이트
- **원격 터미널**: PTY 기반 WebSocket 터미널 세션 제공

자세한 내용은 `argus-insight-agent/CLAUDE.md`를 참고하세요.

## 공통 규칙

- 언어: Python 3.11+
- 라이선스: Apache License 2.0
- 커밋 메시지: 영문으로 작성, 간결하고 명확하게
- 코드 스타일: 각 서브 프로젝트의 lint 설정을 따름
