# Discord Transport 조사 및 준비 문서

> 상태: 조사
> 작성일: 2026-03-20
> 착수 조건: P0~P1 안정화 + handoff protocol 검증 후 (core-model-completion-plan.md)

## Discord 공간 구조 → tunapi 매핑

| Discord | tunapi 대응 | 비고 |
|---------|------------|------|
| Guild (서버) | tunapi 인스턴스 | 1 guild = 1 tunapi |
| Category | 프로젝트 그룹 | 선택적 — 없어도 동작 |
| Text Channel | 프로젝트 바인딩 (`!project set`) | `#myproj` → `RunContext(project="myproj")` |
| Thread | session 또는 discussion | thread ≠ branch. metadata로 구분 |
| Forum Channel | discussion 전용 (향후) | 라운드테이블 결과 archive에 적합 |
| Voice Channel | voice session (향후) | 현재 미지원, 설계만 열어둠 |

## Discord Bot API 핵심 사항

### 연결 방식

- **Gateway (WebSocket)**: 실시간 이벤트 수신 — Mattermost와 유사
- **Interactions (HTTP webhook)**: Slash command 응답 — 3초 제한, defer 필요
- **REST API**: 메시지 CRUD, 채널/스레드 관리

### 메시지 제한

| 항목 | 제한 |
|------|------|
| 메시지 길이 | 2000자 (Telegram 4096, MM/Slack 무제한에 비해 가장 짧음) |
| Embed 필드 | 25개, 총 6000자 |
| Rate limit | 5 req/5s per channel (Tier 2 bot) |
| Thread | 기본 지원, `message_reference` + `thread_id` |

### Slash Command

Discord 고유 기능. Mattermost/Slack과 달리 네이티브 UI:
```
/model claude opus    → 자동완성 + 파라미터 힌트
/rt "topic"           → 모달 다이얼로그 가능
/review approve 42    → 인라인 버튼 응답 가능
```

### Buttons & Components

Discord는 메시지에 Action Row + Button/Select 컴포넌트를 붙일 수 있음:
- cancel 버튼 (현재 이모지 reaction 대체)
- approve/reject 버튼 (리뷰)
- branch merge/discard 버튼

## tunapi 구현 시 필요한 것

### 최소 파일 구조

```
src/tunapi/discord/
├── __init__.py
├── api_models.py        # Discord API 타입
├── client_api.py        # HTTP + Gateway 클라이언트
├── client.py            # outbox 큐 (core/outbox 재사용)
├── bridge.py            # DiscordTransport + DiscordPresenter
├── backend.py           # TransportBackend 엔트리포인트
├── loop.py              # Gateway 이벤트 루프
├── parsing.py           # Gateway 이벤트 → 내부 타입
├── commands.py          # Slash command 핸들러
└── trigger_mode.py      # @mention 감지 (DM은 항상 trigger)
```

### 재사용 가능한 기존 코드

| 모듈 | 재사용 방식 |
|------|------------|
| `core/lifecycle.py` | heartbeat, SIGTERM, graceful drain |
| `core/chat_sessions.py` | 채널별 세션 (re-export) |
| `core/chat_prefs.py` | 채널별 설정 (re-export) |
| `core/trigger.py` | `resolve_trigger_mode(default="mentions")` |
| `core/startup.py` | `build_startup_message(bold="**", line_break="\n")` |
| `core/presenter.py` | `ChatPresenter` — Discord Markdown은 MM과 거의 동일 |
| `core/commands.py` | `parse_command` — `/!` prefix 파싱 |
| `core/memory_facade.py` | 전체 project memory API |
| `core/roundtable.py` | RT 실행 엔진 |
| `core/outbox.py` | rate limiting 큐 |

### Discord 전용 구현 필요

| 항목 | 이유 |
|------|------|
| Gateway WebSocket 연결 | Discord 고유 프로토콜 (op code, heartbeat, resume) |
| Slash command 등록 | REST API로 글로벌/길드 커맨드 등록 |
| Interaction 응답 | 3초 defer + followup 패턴 |
| Component (버튼) 핸들링 | interaction_type=3 (MESSAGE_COMPONENT) |
| 2000자 split | Telegram(4096)보다 짧음, split 전략 필요 |
| Gateway Intent | `MESSAGE_CONTENT` intent 필요 (verified bot은 자동, 아니면 신청) |

## 의존성

### Python 라이브러리 선택지

| 옵션 | 특징 |
|------|------|
| `discord.py` (2.x) | 가장 인기, async, Gateway 내장, slash command 지원 |
| `nextcord` | discord.py 포크, API 유사 |
| 직접 구현 | Mattermost/Slack과 동일 패턴 (httpx + websockets) |

**권장**: 직접 구현 (기존 tunapi 패턴 일관성). `discord.py`는 프레임워크 수준이라 tunapi의 `JsonlSubprocessRunner` 파이프라인과 충돌 가능.

## 착수 전 확인 사항

1. [ ] Discord Bot 생성 + 토큰 발급
2. [ ] `MESSAGE_CONTENT` intent 활성화
3. [ ] 테스트 서버(guild) 준비
4. [ ] Slash command 등록 스크립트 작성
5. [ ] tunapi.toml에 `[transports.discord]` 섹션 설계

## 착수하면 안 되는 것

- voice 채널 통합 (복잡도 대비 가치 낮음)
- 채널 자동 생성/삭제 (서버 관리 권한 문제)
- Webhook 기반 transport (Gateway가 필수)
- embed 기반 렌더링 (일반 Markdown으로 시작)

## 예상 일정

| 단계 | 내용 | 규모 |
|------|------|------|
| 1 | Gateway 연결 + 메시지 수신/발신 | 2~3일 |
| 2 | Slash command 등록 + 기본 커맨드 | 1~2일 |
| 3 | Runner 연결 + 세션 관리 | 2~3일 |
| 4 | RT + project memory 통합 | 1~2일 |
| **합계** | 최소 MVP | **6~10일** |
