# Slack Transport 운영 보강 계획

## 현재 상태 분석

### 치명적 문제
1. **Socket Mode URL 재사용** — `websockets.connect(wss_url)`의 내장 재연결이 만료된 URL을 재사용. Slack Socket Mode URL은 일회용이므로 재연결 실패 확정.
2. **`disconnect` envelope 무시** — `SocketModeEnvelope.type`에 `"disconnect"` 정의만 있고 처리 로직 없음. Slack이 서버 측 재연결을 요청해도 무시.
3. **접근 제어 미적용** — `allowed_channel_ids`/`allowed_user_ids`가 config에 존재하지만 `parse_envelope()`에서 필터링하지 않음.

### 중간 문제
4. **doctor Socket Mode 미검증** — `auth.test` + `conversations.info`만 체크. app_token 유효성, Socket Mode 활성화 여부 미검증.
5. **dead config** — `files`/`voice` 설정이 `settings.py`에 정의되어 있지만 `backend.py`에서 `SlackBridgeConfig`에 전달하지 않음. 사용자에게 기능이 있는 것처럼 보이지만 미동작.
6. **shutdown/heartbeat/pending run** — Mattermost에는 구현되어 있지만 Slack loop.py에 없음.

### 양호
- ACK 처리: envelope_id 기반 ACK 구현됨
- outbox 큐/rate limiting: Mattermost 패턴 동일
- journal/ledger 연결: 이미 loop.py에 통합됨

---

## 구현 단계

### S1: Socket Mode 재연결 안정화

**대상**: `src/tunapi/slack/client_api.py`

**변경 내용**:
1. `socket_mode_connect()` 재작성:
   - `websockets.connect()` 내장 재연결(같은 URL 반복) 제거
   - 외부 루프에서 매 연결마다 `apps.connections.open` 호출 → 새 URL 획득
   - `disconnect` envelope 수신 시 즉시 break → 외부 루프가 새 URL로 재연결
   - exponential backoff: 1s → 2s → 4s → 8s → 16s (max), 성공 시 리셋
   - `ConnectionClosed` 예외 시에도 새 URL로 재연결

2. `SocketModeEnvelope`에서 `disconnect` type을 이벤트 스트림에서 특별 처리:
   - disconnect envelope은 yield하지 않고 내부에서 break

**코드 경로**:
```
apps.connections.open → wss_url
  └→ websockets.connect(wss_url) (단일 연결, auto_reconnect 없음)
       └→ async for message in ws:
            ├→ hello → 로그, continue
            ├→ disconnect → 로그, break (→ 외부 루프에서 새 URL)
            ├→ events_api → ACK + yield
            └→ ConnectionClosed → break (→ 외부 루프에서 새 URL)
```

### S2: 접근 제어 강제

**대상**: `src/tunapi/slack/parsing.py`, `src/tunapi/slack/loop.py`

**변경 내용**:
1. `parse_envelope()` 시그니처 변경:
   ```python
   def parse_envelope(
       envelope, *,
       bot_user_id: str,
       allowed_channel_ids: Iterable[str] | None = None,
       allowed_user_ids: Iterable[str] | None = None,
   ) -> SlackMessageEvent | SlackReactionEvent | None
   ```
2. Mattermost `parse_ws_event()` 패턴 적용:
   - bot 자신의 메시지 필터링 (user_id == bot_user_id)
   - channel_id 화이트리스트 (DM은 항상 허용)
   - user_id 화이트리스트
   - 필터링 시 debug 로그
3. `loop.py`에서 `parse_envelope()` 호출 시 필터 파라미터 전달

### S3: loop.py 운영 안정성 보강

**대상**: `src/tunapi/slack/loop.py`

Mattermost loop.py에 이미 구현된 패턴을 Slack에 적용:
1. **shutdown state 저장** — SIGTERM/disconnect 시 `slack_last_shutdown.json` 저장
2. **재시작 알림** — 시작 시 shutdown state 읽고 채널에 알림
3. **heartbeat 루프** — 10초마다 `slack_heartbeat` 파일 갱신
4. **비정상 종료 감지** — heartbeat 파일 존재 + shutdown state 없음 → 비정상
5. **pending run 재시작 처리** — ledger에서 중단된 작업 확인, journal에 interrupted 마킹

### S4: doctor Socket Mode readiness 검증

**대상**: `src/tunapi/cli/doctor.py`

**변경 내용**:
1. `_doctor_slack_checks()`에 Socket Mode 검증 추가:
   - `apps.connections.open` 호출 → 성공 여부 확인
   - 실패 시 에러 메시지에 원인 구분:
     - app_token 미설정 → "app_token missing"
     - app_token 무효 → "invalid app_token"
     - Socket Mode 미활성화 → "Socket Mode not enabled (check Slack app settings)"
     - 네트워크 실패 → "network error"
2. bot_token과 app_token 검증을 분리하여 어디서 실패했는지 명확하게

### S5: dead config 정리

**대상**: `src/tunapi/slack/backend.py`, `src/tunapi/slack/bridge.py`

**변경 내용**:
1. `backend.py`에서 `files`/`voice` 설정을 `SlackBridgeConfig`에 전달
2. 실제 file/voice 핸들러는 구현하지 않음 (이번 범위 밖)
3. `files.enabled = true` 또는 `voice.enabled = true`일 때:
   - 시작 시 warning 로그: "Slack file transfer is configured but not yet implemented"
   - doctor에서도 "not implemented" 상태 표시

### S6: 테스트 추가

**대상**: `tests/test_slack_parsing.py`, `tests/test_slack_client_api.py`, `tests/test_slack_doctor.py`

테스트 항목:
1. **parsing 접근 제어**:
   - 허용되지 않은 channel 이벤트 → None
   - 허용되지 않은 user 이벤트 → None
   - DM은 항상 허용
   - bot 자신의 메시지 → None
2. **disconnect envelope 처리**:
   - disconnect type envelope이 이벤트 스트림을 종료시키는지
3. **doctor Socket Mode**:
   - apps.connections.open 실패 시 에러 체크 생성 확인

### S7: 최종 검증
- `uv run ruff format --check src tests`
- `uv run ruff check src tests`
- `uv run pytest --no-cov -q`

---

## 명시적 비목표
- slack-sdk 전면 교체
- Block Kit 중심 재작성
- slash command / interactive payload
- file transfer / voice 실제 구현
- roundtable 지원 (Mattermost 전용 기능)

## 남은 리스크 (이번 범위 이후)
- Slack rate limit Tier별 세밀 제어 (현재 1 RPS 고정)
- `message_changed` 등 subtype coverage 확장
- 매우 긴 단일 문단의 split edge case
- file transfer / voice 실제 구현
