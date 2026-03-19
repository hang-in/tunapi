# 저널링 기반 상태 핸드오프 구현 프롬프트

## 페르소나 오버라이드

> **이 프롬프트의 페르소나는 `~/AGENTS.md`의 전역 설정을 무시합니다.**

```
# Persona: 구현 전문 코더

## 행동 원칙
- 설계 문서에 명시된 범위만 구현한다. 범위 밖의 개선/리팩토링은 하지 않는다.
- 각 단계를 완료할 때마다 변경된 파일 목록과 테스트 결과를 보고한다.
- 기존 코드 컨벤션(msgspec Struct, JsonStateStore 패턴, structlog 로깅)을 그대로 따른다.
- 불확실한 설계 결정이 있으면 구현을 멈추고 질문한다.

## 권한
- 이 프로젝트의 모든 파일에 대해 수정, 삭제, 생성 권한을 가진다.
- ~/AGENTS.md의 "읽기 전용" 제한은 이 프롬프트 범위에서 적용되지 않는다.
```

---

## 전략 요약

**resume token이 살아있으면 그대로 이어가고, 실패하는 모든 경우는 구조화 저널 기반 handoff로 흡수한다.**

현재 문제:
1. Mattermost는 `channel_id → token` 단일 매핑 — 엔진 전환 시 이전 세션 소실
2. 엔진 변경 시 resume token을 그냥 버림 (`loop.py:592`)
3. 크래시/재시작 시 어떤 채널의 어떤 작업이 끊겼는지 모름
4. 컨텍스트 초과 감지/복구 경로 없음

---

## 구현 단계

### 1단계: Mattermost 세션 저장소 엔진별 분리

**목표:** `channel_id → {engine → session_metadata}` 구조로 전환. Telegram과 동일한 패턴.

**변경 파일:** `src/tunapi/mattermost/chat_sessions.py`

**현재 구조 (변경 전):**
```python
# chat_sessions.py:22-29
class _SessionEntry(msgspec.Struct, forbid_unknown_fields=False):
    engine: str
    value: str

class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    sessions: dict[str, _SessionEntry] = msgspec.field(default_factory=dict)
    # key: channel_id → value: 단일 세션
```

**목표 구조 (변경 후):**
```python
class _SessionEntry(msgspec.Struct, forbid_unknown_fields=False):
    value: str  # resume token value (engine 필드 제거 — key가 engine)

class _ChannelSessions(msgspec.Struct, forbid_unknown_fields=False):
    sessions: dict[str, _SessionEntry] = msgspec.field(default_factory=dict)
    # key: engine_id → value: session entry

class _State(msgspec.Struct, forbid_unknown_fields=False):
    version: int = STATE_VERSION
    channels: dict[str, _ChannelSessions] = msgspec.field(default_factory=dict)
    # key: channel_id → value: 엔진별 세션들
```

**API 변경:**
```python
# 현재
async def get(self, channel_id: str) -> ResumeToken | None
async def set(self, channel_id: str, token: ResumeToken) -> None
async def clear(self, channel_id: str) -> None

# 변경 후
async def get(self, channel_id: str, engine: str) -> ResumeToken | None
async def set(self, channel_id: str, token: ResumeToken) -> None  # token.engine 사용
async def clear(self, channel_id: str) -> None  # 전체 리셋 (/new)
async def clear_engine(self, channel_id: str, engine: str) -> None  # 특정 엔진만
```

**호출부 수정:**

`loop.py`에서 `sessions.get(msg.channel_id)` 호출을 `sessions.get(msg.channel_id, engine)` 으로 변경해야 한다. 이를 위해 engine 결정 로직이 `sessions.get` 호출보다 먼저 와야 한다.

현재 `_run_engine()` (loop.py:550~) 흐름:
```
1. resume_token = await sessions.get(msg.channel_id)     # ← engine 모름
2. engine = runtime.resolve_engine(...)                    # ← engine 결정
3. if effective_resume.engine != engine: effective_resume = None  # ← 버림
```

변경 후 흐름:
```
1. engine = runtime.resolve_engine(...)                    # ← engine 먼저 결정
2. resume_token = await sessions.get(msg.channel_id, engine)  # ← 해당 엔진 세션 조회
3. effective_resume = resolved.resume_token or resume_token   # ← mismatch 분기 불필요
```

**주의:** `runtime.resolve_engine()`은 `engine_override`와 `context`가 필요하므로, `_run_engine()` 내 로직 순서를 재배치해야 한다. resolve_message → resolve_engine → sessions.get 순서로.

**마이그레이션:** `STATE_VERSION`을 2로 올리고, 기존 `_State.sessions`(flat dict)를 새 `_State.channels`(nested dict)로 변환하는 마이그레이션 로직을 `__init__` 또는 별도 메서드에 추가. 기존 파일 로드 시 version 1이면 자동 변환.

**`/new` 명령 (`loop.py:422`):** `sessions.clear(msg.channel_id)` — 해당 채널의 **모든** 엔진 세션 삭제 (기존 동작 유지).

---

### 2단계: 구조화 JSONL 저널

**목표:** 모든 run의 입출력을 구조화된 JSONL로 기록.

**새 파일:** `src/tunapi/journal.py`

**저널 엔트리 스키마:**
```python
import msgspec
from datetime import datetime

class JournalEntry(msgspec.Struct):
    run_id: str           # f"{channel_id}:{message_id}:{started_at_iso}"
    channel_id: str
    timestamp: str        # ISO 8601
    event: str            # "prompt" | "started" | "action" | "completed" | "interrupted"
    engine: str | None = None
    data: dict[str, Any] = msgspec.field(default_factory=dict)
```

**각 event 타입의 data 필드:**
```python
# event="prompt"
{"text": "사용자 메시지 (최대 2KB truncate)"}

# event="started"
{"resume_token": "xxx", "engine": "claude"}

# event="action" (ActionEvent에서 추출)
{"action_id": "...", "kind": "tool|file_change|command", "title": "Read file.py"}
# ※ detail 필드는 저장하지 않음 (크기 폭발 방지)

# event="completed"
{"ok": true, "answer": "응답 (최대 2KB truncate)", "error": null,
 "usage": {"input_tokens": 1000, "output_tokens": 500}}

# event="interrupted"
{"reason": "crash|sigterm|cancel"}
```

**저장 경로:** `~/.tunapi/journals/{channel_id}.jsonl`
- channel_id에 `/` 등 파일시스템 위험 문자가 있을 수 있으므로 base64 또는 sanitize 처리

**크기 관리:**
- 엔트리 수: 채널당 최대 500개 (run 하나가 prompt+started+N*action+completed = 최소 3~4엔트리)
- 파일 크기: 2MB 제한
- 초과 시: 오래된 절반 삭제 (앞쪽 250개 또는 1MB 분량 제거)
- rotate는 write 시점에 체크

**Journal 클래스 API:**
```python
class Journal:
    def __init__(self, base_dir: Path) -> None: ...

    async def append(self, entry: JournalEntry) -> None:
        """엔트리를 JSONL 파일에 append. 크기 초과 시 자동 rotate."""

    async def recent_entries(
        self, channel_id: str, *, limit: int = 50
    ) -> list[JournalEntry]:
        """최근 N개 엔트리 로드 (handoff 시 사용)."""

    async def last_run(self, channel_id: str) -> list[JournalEntry] | None:
        """마지막 run_id의 전체 엔트리 반환."""

    async def mark_interrupted(self, channel_id: str, run_id: str, reason: str) -> None:
        """run을 interrupted로 마킹 (재시작 시 사용)."""
```

**훅 위치:** `run_runner_with_cancel()` (runner_bridge.py:298)

현재 이벤트 처리 흐름:
```python
async for evt in runner.run(prompt, resume_token):       # :312
    _log_runner_event(evt)
    if isinstance(evt, StartedEvent):                    # :314
        outcome.resume = evt.resume
        ...
    elif isinstance(evt, CompletedEvent):                # :324
        outcome.resume = evt.resume or outcome.resume
        outcome.completed = evt
    await edits.on_event(evt)                            # :327
```

저널 기록을 추가하려면 `run_runner_with_cancel()`에 `journal: Journal | None` 파라미터와 `run_id: str` 파라미터를 추가한다. 또는 콜백 패턴으로:

**권장 접근:** `run_runner_with_cancel()`에 `on_journal_event` 콜백을 추가하는 대신, `handle_message()`에서 outcome을 받은 후 저널에 기록하는 방식이 더 깔끔하다. 단, `ActionEvent`는 `handle_message()` 레벨에서 접근 불가하므로, `ProgressTracker`에 action 히스토리를 누적하고 완료 후 일괄 기록하는 방식을 사용한다.

**구체적 구현 방안:**

1. `ProgressTracker`에 `action_history: list[tuple[str, str, str]]` 추가 (action_id, kind, title)
2. `ProgressTracker.note_event()`에서 `ActionEvent`일 때 `action_history`에 append
3. `handle_message()` 완료 후 (runner_bridge.py:562~624 영역) journal에 일괄 기록:
   - prompt 엔트리
   - started 엔트리
   - action 엔트리들 (action_history에서)
   - completed/interrupted 엔트리

4. `handle_message()`에 `journal: Journal | None = None`과 `run_id: str | None = None` 파라미터 추가

**호출부 변경:** `_run_engine()` (loop.py:654~)에서 `handle_message()` 호출 시 journal 인스턴스 전달.

---

### 3단계: Pending-run ledger

**목표:** 진행 중인 run을 파일로 추적하여, 크래시/재시작 시 중단된 작업 식별.

**새 파일 또는 기존 확장:** `src/tunapi/mattermost/pending_runs.py` (또는 `journal.py`에 통합)

**데이터 구조:**
```python
class PendingRun(msgspec.Struct):
    run_id: str
    channel_id: str
    engine: str
    prompt_summary: str   # 최대 200자 truncate
    started_at: str       # ISO 8601

class PendingRunsState(msgspec.Struct):
    version: int = 1
    runs: dict[str, PendingRun] = msgspec.field(default_factory=dict)
    # key: run_id
```

**저장 경로:** `~/.tunapi/pending_runs.json`

**API:**
```python
class PendingRunLedger(JsonStateStore[PendingRunsState]):
    async def register(self, run: PendingRun) -> None: ...
    async def complete(self, run_id: str) -> None: ...
    async def get_all(self) -> list[PendingRun]: ...
```

**훅 위치:**
- `handle_message()` 시작 시: `ledger.register(run)` — StartedEvent 후가 아니라, runner 호출 전에 등록 (크래시 대비)
- `handle_message()` 종료 시 (정상/에러/취소 모두): `ledger.complete(run_id)`

**재시작 시 처리 (`run_main_loop()`, loop.py:704~):**
```python
# 기존 last_shutdown.json 로직 이후에 추가
pending = await ledger.get_all()
if pending:
    for run in pending:
        # 저널에 interrupted 마킹
        await journal.mark_interrupted(run.channel_id, run.run_id, "crash")
    # 다음 메시지에서 해당 채널 사용자에게 알림 (lazy 방식)
    # 또는 즉시 알림:
    for ch_id, runs in groupby(pending, key=lambda r: r.channel_id):
        msg = f"⚠️ 이전 세션에서 중단된 작업 {len(list(runs))}개가 있습니다."
        await transport.send(channel_id=ch_id, message=RenderedMessage(text=msg))
    await ledger.clear_all()
```

---

### 4단계: 저널 기반 handoff

**목표:** resume token이 없거나 무효한 경우, 저널에서 맥락을 추출하여 새 세션 첫 프롬프트에 주입.

**트리거 조건:**
1. 엔진 변경 — `sessions.get(channel_id, engine)` 결과가 None이지만, 다른 엔진의 세션은 존재
2. resume token 만료 — runner가 에러 반환 (특정 에러 패턴 감지)
3. context overflow — CompletedEvent에서 에러 메시지에 "context", "token limit", "conversation too long" 등 패턴

**handoff preamble 생성 (LLM 호출 없이 템플릿 기반):**

```python
# src/tunapi/journal.py 또는 src/tunapi/handoff.py

def build_handoff_preamble(
    entries: list[JournalEntry],
    *,
    old_engine: str | None = None,
    reason: str = "engine_change",  # "engine_change" | "context_overflow" | "resume_expired"
    max_bytes: int = 4096,
) -> str:
    """저널 엔트리에서 handoff preamble 텍스트를 생성한다."""
    # 최근 run들에서 추출:
    # - 마지막 사용자 요청
    # - 수행된 주요 액션 (file_change, tool 위주)
    # - 마지막 응답 요약
    # - 완료/중단 상태
    #
    # 출력 형식:
    lines = []
    lines.append(f"[이전 세션 컨텍스트 — {old_engine or 'unknown'}, {reason}]")
    # ... 엔트리 파싱 ...
    lines.append(f"- 마지막 요청: {last_prompt}")
    lines.append(f"- 수행된 액션: {action_summary}")
    lines.append(f"- 변경된 파일: {files_list}")
    lines.append(f"- 상태: {status}")
    lines.append("[현재 요청]")

    text = "\n".join(lines)
    # max_bytes 초과 시 오래된 액션부터 제거
    return text
```

**preamble이 4KB 초과 시에만 LLM 요약 호출** (선택적, 2차 구현):
- 이 경우 현재 사용 중인 엔진(새 엔진)으로 "다음 컨텍스트를 요약해줘" 요청
- 요약 결과를 preamble으로 대체

**주입 위치:** `_run_engine()` (loop.py)에서 `final_prompt` 조립 시:

```python
# 현재: loop.py:636-648
final_prompt = resolved.prompt

# 변경 후:
final_prompt = resolved.prompt
if effective_resume is None and journal is not None:
    # resume 없음 → handoff 필요 여부 확인
    entries = await journal.recent_entries(msg.channel_id, limit=30)
    if entries:
        old_engine = _detect_previous_engine(entries)
        reason = _determine_handoff_reason(...)
        preamble = build_handoff_preamble(entries, old_engine=old_engine, reason=reason)
        final_prompt = f"{preamble}\n{final_prompt}"
```

**handoff 트리거 판별:**
- `effective_resume is None`이면서 저널에 최근 엔트리가 있음 → handoff
- `effective_resume is not None`이면 → 일반 resume (handoff 불필요)
- `/new` 후에는 저널의 해당 채널 엔트리에 "reset" 마커를 남겨서 handoff 방지

---

### 5단계: Heartbeat

**목표:** 비정상 종료(OOM, kill -9) 감지.

**구현:**
```python
# src/tunapi/mattermost/loop.py의 run_main_loop() 내부

async def _heartbeat_loop(path: Path) -> None:
    while True:
        path.write_text(datetime.now().isoformat())
        await anyio.sleep(10)

# task group에 추가:
heartbeat_path = _CONFIG_DIR / "heartbeat"
dispatch_tg.start_soon(_heartbeat_loop, heartbeat_path)
```

**재시작 시 판정 (run_main_loop 시작부):**
```python
heartbeat_path = _CONFIG_DIR / "heartbeat"
shutdown_state_exists = _SHUTDOWN_STATE_FILE.exists()

if heartbeat_path.exists() and not shutdown_state_exists:
    last_beat = datetime.fromisoformat(heartbeat_path.read_text().strip())
    if (datetime.now() - last_beat).total_seconds() > 30:
        # 비정상 종료로 판정
        # pending_runs ledger 확인 후 interrupted 처리
        ...
```

---

## 명시적으로 구현하지 않는 것

| 항목 | 이유 |
|---|---|
| RAG / 벡터 검색 | tunapi 범위 초과 |
| MCP 기반 상태 공유 | 에이전트 CLI 미지원 |
| Task Tree 관리 | 에이전트 내부 목표 외부 추적 불가 |
| 매 N턴 주기적 LLM 스냅샷 | 대부분 사용 안 됨, 비용 낭비 |
| 선제적 토큰 예산 경고 (70~80%) | 엔진별 usage 형식 불일치, 2차 과제로 분리 |
| 이전 엔진으로 요약 생성 | 해당 세션이 만료/초과 상태일 수 있음 |

---

## 구현 제약사항

1. **기존 테스트 통과 필수:** `just check`가 깨지지 않아야 한다.
2. **기존 API 하위호환:** `handle_message()`의 새 파라미터는 모두 `Optional`/기본값 있어야 한다. Telegram 경로에서도 깨지지 않아야 한다.
3. **저널 I/O는 비동기:** `aiofiles` 또는 `anyio.Path` 사용. 메인 이벤트 루프 블로킹 금지.
4. **저널 실패는 무시:** 저널 write 실패가 메시지 처리를 중단시키면 안 된다. `contextlib.suppress(Exception)` 또는 try/except로 감싸되, 에러는 로깅.
5. **run_id 생성:** `f"{channel_id}:{message_id}:{int(time.time())}"` — 충분히 유니크하고 디버깅 가능.
6. **마이그레이션:** 세션 저장소 version 업그레이드 시, 기존 파일을 자동 변환. 수동 마이그레이션 불필요.

---

## 작업 순서 체크리스트

- [ ] 1단계: `mattermost/chat_sessions.py` 엔진별 분리 + version 마이그레이션
- [ ] 1단계: `mattermost/loop.py` `_run_engine()` 내 engine 결정 → 세션 조회 순서 변경
- [ ] 1단계: `/new` 명령의 `sessions.clear()` 동작 확인
- [ ] 2단계: `journal.py` 새 모듈 생성 (JournalEntry, Journal 클래스)
- [ ] 2단계: `ProgressTracker`에 action_history 추가
- [ ] 2단계: `handle_message()`에 저널 기록 로직 추가
- [ ] 2단계: `_run_engine()`에서 journal 인스턴스 생성 및 전달
- [ ] 3단계: `pending_runs.py` 또는 journal.py에 PendingRunLedger 추가
- [ ] 3단계: `handle_message()` 시작/종료에 ledger 등록/해제
- [ ] 3단계: `run_main_loop()` 재시작 시 pending run 처리
- [ ] 4단계: `build_handoff_preamble()` 구현
- [ ] 4단계: `_run_engine()`에서 resume 없을 때 preamble 주입
- [ ] 4단계: `/new` 시 저널 reset 마커
- [ ] 5단계: heartbeat 루프 + 재시작 판정
- [ ] 전체: `just check` 통과 확인
- [ ] 전체: 기존 테스트 깨지지 않음 확인
