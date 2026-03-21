# tunapi core 추출 리팩토링 — 코더AI 실행 프롬프트

## Persona Override

```
이 작업에서는 AGENTS.md의 "구현 검증자" 페르소나를 무시한다.

# Persona: 리팩토링 실행자

## 행동 원칙
- 기존 동작을 깨뜨리지 않는 것이 최우선이다. 추출 전후 테스트가 동일하게 통과해야 한다.
- 한 번에 하나의 모듈만 추출하고, 추출 후 `just check`가 통과하는 것을 확인한 뒤 다음으로 넘어간다.
- 추상화는 최소한으로 — 현재 3개 transport의 공통 패턴을 "있는 그대로" 올리는 것이 목표다.
- 코드를 직접 작성하고 수정한다. 분석만 하고 멈추지 않는다.
- 오버엔지니어링 금지: 미들웨어 체인, Storage Interface, Hook 시스템 등 현재 불필요한 추상 계층을 도입하지 않는다.
```

---

## 목표

`loop.py`를 얇게 만들기 위한 중복 제거 작업. `src/tunapi/core/`에 3개 transport(Mattermost, Slack, Telegram)에서 반복되는 공통 로직을 추출한다.

## 핵심 설계 규칙

1. **`core` 내부에 `if transport == ...` 분기 금지.** transport별 차이는 정규식, Callable, 전략 객체를 생성자/팩토리 인자로 주입하여 처리한다.
2. **추출 기준:**
   - 동일성 높고 차이 적음 → 바로 공통화
   - 구조는 같지만 transport별 정책 차이 있음 → 전략 주입으로 공통화
   - API/렌더링/이벤트 모델이 다름 → transport 고유 유지 (추출하지 않음)
3. **기존 테스트를 먼저 확인하고, 추출 후 동일하게 통과하는지 검증한다.**

## 추출 대상 및 우선순위

### P0: `core/lifecycle.py` — 재시작/복구/종료

복붙 불일치 시 데이터 유실·좀비 프로세스 위험이 가장 높다.

**추출할 로직:**
- heartbeat 파일 쓰기 (10s interval)
- stale heartbeat 감지 (30s threshold) → 비정상 종료 판단
- SIGTERM 핸들러 등록 → shutdown event 설정
- restart notification (이전 shutdown state 읽기 → 알림 메시지)
- pending runs recovery (ledger → journal.mark_interrupted)
- graceful drain (running tasks 대기 + timeout)
- shutdown state 파일 저장

**기준 코드:**
- `src/tunapi/slack/loop.py` (L330 부근)
- `src/tunapi/mattermost/loop.py` (L745 부근)
- `src/tunapi/telegram/loop.py` (해당 lifecycle 로직)

**주입 포인트:**
- heartbeat 파일 경로
- shutdown state 파일 경로
- restart notification 전송 함수: `Callable[[str, str], Awaitable[None]]` (channel_id, message)
- pending runs 복구 시 사용할 journal/ledger 인스턴스

---

### P1: `core/chat_sessions.py` — 세션 저장소

3개 transport에서 스키마 100% 동일. 파일 경로만 다름.

**추출할 로직:**
- `get(channel_id, engine) → ResumeToken | None`
- `set(channel_id, engine, token)`
- `clear(channel_id, engine)`
- `clear_engine(engine)`
- `has_any(channel_id) → bool`
- JSON 파일 기반 persistence

**기준 코드:**
- `src/tunapi/slack/chat_sessions.py`
- `src/tunapi/mattermost/chat_sessions.py`
- `src/tunapi/telegram/chat_sessions.py`

**주입 포인트:**
- 저장 파일 경로 (Path)

---

### P1: `core/chat_prefs.py` — 채팅 선호 설정 저장소

MM/Slack 동일 + Telegram은 `engine_overrides` 추가.

**추출할 로직:**
- default engine get/set
- trigger mode get/set
- context get/set
- persona CRUD
- JSON 파일 기반 persistence

**기준 코드:**
- `src/tunapi/slack/chat_prefs.py`
- `src/tunapi/mattermost/chat_prefs.py`
- `src/tunapi/telegram/chat_prefs.py`

**구조:**
- 공통 base class → Telegram이 `engine_overrides` mixin 또는 subclass로 확장

---

### P1: `core/trigger.py` — 트리거 모드 해석

3개 transport 모두 동일 패턴: prefs 조회 → mentions/all 결정 → mention strip.

**추출할 로직:**
- `resolve_trigger_mode(channel_id, is_dm) → TriggerMode`
- `should_trigger(text, mode, bot_id) → bool`
- `strip_mention(text, bot_id) → str`

**기준 코드:**
- `src/tunapi/slack/trigger_mode.py`
- `src/tunapi/mattermost/trigger_mode.py`
- `src/tunapi/telegram/trigger_mode.py`

**주입 포인트:**
- `mention_pattern: re.Pattern` — 플랫폼별 멘션 형식 (`<@uid>` vs `@username`)
- `is_dm: Callable[[str], bool]` — DM 채널 판별
- default trigger mode 값

---

### P2: `core/outbox.py` — 메시지 전송 큐

3개 transport 모두 priority queue + dedup + retry-after + graceful close 패턴.

**추출할 로직:**
- `Generic Outbox[Op]`
- priority queue (heapq)
- deduplication (post_id 기반)
- retry-after 핸들링
- graceful drain on shutdown

**기준 코드:**
- `src/tunapi/slack/outbox.py`
- `src/tunapi/mattermost/outbox.py`
- `src/tunapi/telegram/outbox.py`

**주입 포인트:**
- `execute: Callable[[Op], Awaitable[T]]` — 실제 HTTP 전송 함수
- retry policy (max retries, backoff)
- Telegram 전용: chat별 interval 함수

---

### P2: `core/handoff.py` — 저널 핸드오프 프리앰블

resume token 부재 시 journal recent entries → 프롬프트 앞에 붙이는 공통 유틸. 독립 모듈 또는 프롬프트 준비 단계의 함수로 추출 — 구현 시 자연스러운 위치를 선택한다.

**기준 코드:**
- `src/tunapi/slack/loop.py` (L231 부근)
- `src/tunapi/mattermost/loop.py` (L640 부근)

---

## Transport 고유로 남기는 것 (추출하지 않음)

- `api_models.py` — 플랫폼 API 스키마
- `client_api.py` — HTTP/WebSocket 클라이언트
- `parsing.py` — 이벤트 정규화
- `render.py` / 프레젠터 — 플랫폼별 마크다운 변환
- `bridge.py` — Transport/Presenter 프로토콜 구현체
- Telegram topics, forward coalescing, media group buffering
- Mattermost roundtable

## 보류 항목 (이번 범위 제외)

- 미들웨어/Hook 체인 시스템
- Storage Interface 추상화 (JSON → SQLite 전환 대비)
- SQLite 전환
- Prometheus/Telemetry

## 작업 흐름

1. 대상 모듈의 기존 코드를 3개 transport에서 모두 읽는다
2. 공통 패턴을 식별하고 `src/tunapi/core/`에 추출한다
3. transport별 코드가 `core` 모듈을 import하도록 수정한다
4. `just check` 실행하여 format + lint + typecheck + tests 통과 확인
5. 통과하면 다음 모듈로 진행, 실패하면 수정
6. 모든 추출 완료 후 CLAUDE.md의 Architecture 섹션 업데이트

## 검증 명령어

```sh
uv sync --dev                  # 의존성 설치
just check                     # format + lint + typecheck + tests (모든 추출 단계마다 실행)
uv run pytest --no-cov         # 빠른 테스트
```
