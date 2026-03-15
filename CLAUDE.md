# Argus Insight

Argus Insight는 데이터의 전 생명주기를 관리하는 확장 가능한 Data + AI Platform입니다.

## 프로젝트 구조

```
argus-insight/
├── CLAUDE.md                    # 이 파일 (루트 가이드)
├── argus-insight-agent/         # 서버 관리 에이전트 (Python/FastAPI)
└── README.md
```

## 서브 프로젝트

### argus-insight-agent
서버에 설치되어 원격으로 서버를 관리하는 에이전트입니다. 셸 명령 실행, 시스템 모니터링, 패키지 관리, 원격 터미널 기능을 REST/WebSocket API로 제공합니다. 자세한 내용은 `argus-insight-agent/CLAUDE.md`를 참고하세요.

## 공통 규칙

- 언어: Python 3.11+
- 라이선스: Apache License 2.0
- 커밋 메시지: 영문으로 작성, 간결하고 명확하게
- 코드 스타일: 각 서브 프로젝트의 lint 설정을 따름
