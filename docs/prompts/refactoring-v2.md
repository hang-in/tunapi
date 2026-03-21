# tunapi 리팩토링 실행 프롬프트 v2

> **대상**: 코드 수정 권한이 있는 AI 코딩 에이전트 (Claude Code, Codex 등)
> **저장소**: `~/privateProject/tunapi` (`feat/roundtable` 브랜치)
> **생성일**: 2026-03-19

---

## 페르소나 오버라이드

아래 페르소나는 `~/AGENTS.md`의 전역 설정을 **완전히 대체**한다. 이 프롬프트 실행 중에는 아래 규칙만 따를 것.

```
# Persona: 수술적 리팩터 (Surgical Refactorer)

## 행동 원칙
- 기존 코드 패턴과 컨벤션을 최대한 보존한다. 새 추상화를 만들기 전에 기존 패턴을 재사용할 수 있는지 먼저 확인한다.
- 한 번에 하나의 Phase만 실행한다. Phase 완료 후 테스트를 돌려 회귀가 없음을 확인한 뒤 다음 Phase로 넘어간다.
- 과잉 설계를 하지 않는다. EDA, 플러그인 프레임워크, 범용 이벤트 시스템 등은 도입하지 않는다.
- 코드를 건드리지 않는 파일은 수정하지 않는다. 특히 `src/tunapi/telegram/` 디렉토리는 이 리팩토링의 범위 밖이다.
- 각 Phase의 커밋은 독립적으로 revert 가능해야 한다.

## 권한
- `src/tunapi/mattermost/`, `tests/` 디렉토리의 파일 수정/생성 가능
- `src/tunapi/telegram/` 디렉토리는 **읽기 전용** (패턴 참조만 허용)
- 새 파일 생성은 최소화. 기존 파일 편집을 우선한다.
```

---

## 배경 컨텍스트

3개 에이전트(Claude, Gemini, Codex)가 라운드테이블을 통해 합의한 리팩토링 순서다.

**핵심 판단**: "새 아키텍처 도입"이 아니라, 이미 존재하는 코어 설계선(`transport.py`, `commands.py`, `telegram/state_store.py`)에 Mattermost/roundtable 구현을 정렬하는 것이 본질.

### 기존 코어 패턴 (반드시 참조)
| 패턴 | 위치 | 용도 |
|------|------|------|
| `CommandBackend` Protocol | `src/tunapi/commands.py` | 플러그인 커맨드 인터페이스 |
| `JsonStateStore[T]` 제네릭 | `src/tunapi/telegram/state_store.py` | 버전관리되는 JSON 상태 저장소 베이스 |
| `TransportRuntime` | `src/tunapi/transport_runtime.py` | 엔진/프로젝트 해석 런타임 |
| `RoundtableConfig` | `src/tunapi/transport_runtime.py` | 라운드테이블 설정 dataclass |

---

## Phase 1: 에러 바운더리 정책 주석

**목적**: `_dispatch_message` 분해(Phase 3) 전에 에러 처리 규칙을 확정한다. 별도 에러 클래스 계층은 만들지 않는다. 주석 수준 정책 명시로 충분하다.

### 작업

1. `src/tunapi/mattermost/loop.py`의 `_dispatch_message` 함수 상단(docstring 아래)에 아래 형식의 에러 정책 주석을 추가:

```python
async def _dispatch_message(...) -> None:
    """Dispatch: slash commands → roundtable → voice → trigger check → engine."""
    # Error boundary policy:
    # - Runner unavailable (resolve_runner.issue): warn user via message, return
    # - CWD resolution failure: warn user via message, return
    # - handle_message() failure: log only (no user message) — the bridge
    #   layer already sends error/timeout indicators
    # - Command handler errors: propagate (crash = bug in our code)
```

2. `src/tunapi/mattermost/roundtable.py`의 `_run_single_round` 함수 상단에 동일 형식으로:

```python
async def _run_single_round(...) -> list[tuple[str, str]]:
    """Run one round of agents and return the round transcript."""
    # Error boundary policy:
    # - Runner unavailable (resolve_runner.issue): warn user, skip engine, continue round
    # - CWD resolution failure: warn user, skip engine, continue round
    # - handle_message() failure: log + warn user, skip engine, continue round
    # - Cancel event: break loop immediately
```

3. 현재 코드가 정책과 일치하는지 검증하고, 불일치가 있으면 코드를 정책에 맞게 수정. 함수명 기준으로 위치를 찾을 것 (라인 번호는 편집 후 밀릴 수 있음):
   - `_dispatch_message` 끝부분의 `except Exception` 블록: 로그만 남기고 사용자에게 알리지 않음 — 정책("log only")과 일치하는지 확인
   - `_run_single_round`의 `except Exception` 블록: 사용자에게 메시지 전송 + 다음 엔진으로 계속 — 정책과 일치

### 검증
```sh
just check  # format + lint + typecheck + tests 전부 통과해야 함
```

---

## Phase 2: Roundtable 단위 테스트

**목적**: 테스트 0개인 `roundtable.py`의 핵심 순수 로직을 커버한다. async 함수(`run_roundtable` 등)는 이 Phase에서는 다루지 않는다.

### 선행 작업: 매직 넘버 상수 추출

`_build_round_prompt` 내부의 `4000` (답변 truncation 길이)을 모듈 레벨 상수로 추출한다. 테스트에서 이 상수를 참조하여 값 변경 시 테스트가 깨지지 않도록 한다.

```python
# roundtable.py 모듈 상단
_MAX_ANSWER_LENGTH = 4000

# _build_round_prompt 내부에서 사용
trimmed = answer[:_MAX_ANSWER_LENGTH] + "..." if len(answer) > _MAX_ANSWER_LENGTH else answer
```

### 작업

`tests/test_mattermost_roundtable.py` 파일을 생성하고, 아래 함수들의 단위 테스트를 작성한다.

#### 2-1. `RoundtableStore` 테스트
```python
# 참고: time.monotonic()을 모킹하여 TTL 만료를 테스트할 것
class TestRoundtableStore:
    def test_put_and_get(self): ...
    def test_get_returns_none_for_unknown(self): ...
    def test_complete_marks_session(self): ...
    def test_get_completed_returns_none_for_active(self): ...
    def test_get_completed_returns_session_for_completed(self): ...
    def test_remove(self): ...
    def test_evict_expired_sessions(self): ...  # monotonic mock으로 TTL 초과 시뮬레이션
    def test_evict_keeps_active_sessions(self): ...  # completed가 아닌 세션은 TTL 무관
```

#### 2-2. `parse_rt_args` 테스트
```python
# RoundtableConfig(engines=(), rounds=1, max_rounds=3)을 기본값으로 사용
class TestParseRtArgs:
    def test_simple_topic(self): ...  # "리팩토링 논의" → ("리팩토링 논의", 1, None)
    def test_quoted_topic(self): ...  # '"multi word topic"' → 파싱 확인
    def test_rounds_flag(self): ...  # '"topic" --rounds 2' → rounds=2
    def test_rounds_exceeds_max(self): ...  # --rounds 10 → 에러 메시지
    def test_rounds_zero(self): ...  # --rounds 0 → 에러 메시지
    def test_invalid_rounds(self): ...  # --rounds abc → 에러 메시지
    def test_empty_args(self): ...  # "" → ("", 0, None) — usage 표시용
    def test_parse_error(self): ...  # 닫히지 않은 따옴표 → 에러
```

#### 2-3. `parse_followup_args` 테스트
```python
class TestParseFollowupArgs:
    def test_topic_only(self): ...  # "새 질문" → ("새 질문", None, None)
    def test_engine_filter_and_topic(self): ...  # "claude,gemini 새 질문"
    def test_unknown_engine_treated_as_topic(self): ...  # "unknown 새 질문"
    def test_partial_engine_match(self): ...  # "claude,unknown topic" → 전체가 topic
    def test_empty_args(self): ...
    def test_case_insensitive_engine(self): ...  # "Claude" matches "claude"
```

#### 2-4. `_build_round_prompt` 테스트
```python
from tunapi.mattermost.roundtable import _MAX_ANSWER_LENGTH

class TestBuildRoundPrompt:
    def test_no_context(self): ...  # transcript 빈 경우 → topic 그대로 반환
    def test_with_previous_rounds(self): ...  # transcript 있으면 "이전 라운드 응답" 포함
    def test_with_current_round_responses(self): ...  # "이번 라운드 다른 에이전트 답변" 포함
    def test_long_answer_truncated(self): ...  # _MAX_ANSWER_LENGTH 초과 시 "..." 추가 확인
    def test_both_previous_and_current(self): ...  # 둘 다 있을 때 구분자 "---" 확인
```

### 테스트 스타일 규칙
- `pytest` + 표준 `unittest.mock` 사용 (기존 `tests/test_mattermost_bridge.py` 패턴 따름)
- async 테스트가 필요한 경우 `pytestmark = pytest.mark.anyio` 사용
- Fake/Mock은 최소한으로. 순수 함수 테스트가 우선
- `RoundtableSession` 생성 시 `anyio.Event()` 때문에 anyio backend가 필요할 수 있음 — 필요시 fixture로 처리

### 검증
```sh
uv run pytest tests/test_mattermost_roundtable.py -v --no-cov
just check
```

---

## Phase 3: `_dispatch_message` 분해

**목적**: `_dispatch_message` 함수를 역할별로 분리한다. 인터페이스(함수 시그니처)는 최대한 유지하고 내부만 분해한다.

### 분해 방향

현재 `_dispatch_message`의 실행 흐름 (함수명 기준):
1. `parse_command` + match 문 디스패치
2. 자동 파일 업로드 (`handle_file_put`)
3. 파일 + 텍스트 처리 (`handle_file_put` + path 추가)
4. 음성 전사 (`_handle_voice`)
5. 트리거 모드 판단 (`should_trigger` + `strip_mention`)
6. 세션/컨텍스트 해석 (`resolve_message` + `resolve_runner` + `resolve_run_cwd`)
7. 페르소나 프리픽스 (`_resolve_persona_prefix`)
8. 러너 실행 (`handle_message`)

### 작업

1. `_dispatch_message`를 **3개 단계 함수**로 분리:

```python
# 기존 _dispatch_message는 orchestrator 역할만 남김
async def _dispatch_message(msg, cfg, running_tasks, sessions, chat_prefs, roundtables):
    """Dispatch: slash commands → prompt resolution → engine run."""
    # 1. Command handling
    if await _try_dispatch_command(msg, cfg, running_tasks, sessions, chat_prefs, roundtables):
        return

    # 2. Prompt resolution (files, voice, trigger, mention strip)
    resolved = await _resolve_prompt(msg, cfg, chat_prefs)
    if resolved is None:
        return

    # 3. Engine execution (context, runner, persona, session → run)
    await _run_engine(resolved, msg, cfg, running_tasks, sessions, chat_prefs)
```

2. **`_try_dispatch_command`**: 현재 match문 전체를 이동. `bool` 반환 (처리했으면 True).

3. **`_resolve_prompt`**: 자동 파일 업로드 + 파일 처리 + 음성 전사 + 트리거 판단 + mention 제거를 묶음. dataclass 반환:

```python
@dataclass(slots=True)
class _ResolvedPrompt:
    """Result of prompt resolution before engine dispatch."""
    text: str              # mention이 제거되고 file_context가 합쳐진 최종 프롬프트 텍스트
    file_context: str      # 빈 문자열이면 파일 없음
```

> **설계 의도**: `_ResolvedPrompt`는 의도적으로 얇게 유지한다. engine override, ambient context, resume token, thread 정보, persona prefix는 모두 `_run_engine` 내부에서 해석한다. 이들은 `msg`, `cfg`, `sessions`, `chat_prefs`에서 직접 도출되는 값이므로, dataclass에 넣으면 파라미터 중복이 발생한다. `_resolve_prompt`의 역할은 "사용자 입력 → 정제된 텍스트"까지만이고, "어떤 엔진에 보낼지"는 `_run_engine`의 책임이다.

4. **`_run_engine`**: 세션/컨텍스트 해석 → 페르소나 프리픽스 → 러너 실행 → 에러 처리. Phase 1에서 정의한 에러 정책을 이 함수에 적용.

### 제약
- `_dispatch_message`의 **외부 시그니처는 변경하지 않는다** (호출부인 `run_main_loop`에서 `tg.start_soon`으로 호출)
- `_start_roundtable`, `_handle_file_command`, `_handle_voice`, `_resolve_persona_prefix`는 그대로 유지
- 새 파일을 만들지 않는다. 전부 `loop.py` 내부에서 분리

### 검증
```sh
just check
# 기존 mattermost 관련 테스트가 있다면 전부 통과 확인
uv run pytest tests/test_mattermost*.py -v --no-cov
```

---

## Phase 4: Mattermost 상태 저장소 → `JsonStateStore` 패턴 정렬

**목적**: `mattermost/chat_sessions.py`와 `mattermost/chat_prefs.py`가 `telegram/state_store.py`의 `JsonStateStore[T]` 패턴을 직접 재구현하고 있다. 기존 베이스 클래스를 재사용하도록 정렬한다.

### 현재 상태

- `telegram/state_store.py`의 `JsonStateStore[T]`: **sync** 내부 메서드 (`_reload_locked_if_needed`, `_save_locked`). `_lock`은 `anyio.Lock()`이지만, lock 획득은 서브클래스의 책임.
- `mattermost/chat_sessions.py`의 `ChatSessionStore`: **async** 퍼블릭 메서드에서 `async with self._lock` 후 load/save 호출. mtime 체크 없음, `write_bytes` 직접 사용.
- `mattermost/chat_prefs.py`의 `ChatPrefsStore`: 동일한 async 패턴. 메서드가 더 많음 (persona API 포함).

### sync/async 호환 전략

`JsonStateStore`의 `_reload_locked_if_needed()`와 `_save_locked()`는 sync 메서드다. Mattermost 쪽 퍼블릭 API는 async이지만, 실제 I/O는 `Path.read_bytes()`/`Path.write_bytes()` 수준이므로 sync로 충분하다 (현재도 `await`가 아닌 sync 호출 사용). 따라서:

```python
# 서브클래스의 async 퍼블릭 메서드에서 sync 부모 메서드를 호출하는 패턴
class ChatSessionStore(JsonStateStore[_State]):
    async def get(self, channel_id: str) -> ResumeToken | None:
        async with self._lock:
            self._reload_locked_if_needed()  # sync — 파일 I/O가 경량이므로 OK
            entry = self._state.sessions.get(channel_id)
            ...

    async def set(self, channel_id: str, token: ResumeToken) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            self._state.sessions[channel_id] = _SessionEntry(...)
            self._save_locked()  # sync — atomic_write_json 사용
```

이 패턴은 기존 telegram 코드의 사용 방식과 동일하다. `JsonStateStore`는 lock 획득을 서브클래스에 위임하므로 sync/async 불일치 문제가 없다.

### 작업

1. `telegram/state_store.py`를 `src/tunapi/state_store.py`로 이동하여 공용 모듈로 승격. 기존 telegram import 경로를 새 위치로 직접 수정 (re-export 하지 않음).

2. `mattermost/chat_sessions.py`를 `JsonStateStore[_State]` 기반으로 리팩토링:

```python
# Before: 직접 구현한 load/save/lock
class ChatSessionStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._state = _State()
        self._lock = anyio.Lock()
        self._loaded = False
    async def _load(self): ...
    async def _save(self): ...

# After: JsonStateStore 재사용 + sync 내부 메서드 호출
class ChatSessionStore(JsonStateStore[_State]):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            version=STATE_VERSION,
            state_type=_State,
            state_factory=_State,
            log_prefix="chat_sessions",
            logger=logger,
        )

    async def get(self, channel_id: str) -> ResumeToken | None:
        async with self._lock:
            self._reload_locked_if_needed()
            entry = self._state.sessions.get(channel_id)
            if entry is None:
                return None
            return ResumeToken(engine=entry.engine, value=entry.value)

    async def set(self, channel_id: str, token: ResumeToken) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            self._state.sessions[channel_id] = _SessionEntry(
                engine=token.engine, value=token.value,
            )
            self._save_locked()

    async def clear(self, channel_id: str) -> None:
        async with self._lock:
            self._reload_locked_if_needed()
            if self._state.sessions.pop(channel_id, None) is not None:
                self._save_locked()
```

3. `mattermost/chat_prefs.py`에도 동일 패턴 적용. `ChatPrefsStore`의 메서드가 많지만(10개), 모두 `async with self._lock → _load → 로직 → _save` 패턴이므로 기계적으로 전환 가능.

### 개선 효과
- mtime 기반 리로드 자동 적용 (여러 프로세스가 같은 파일을 공유할 때 일관성)
- atomic write 자동 적용 (쓰기 중 크래시 시 데이터 손실 방지)
- 버전 불일치 감지 + 로깅 자동 적용

### 검증
```sh
just check
uv run pytest tests/ -v --no-cov
```

---

## Phase 5: Mattermost 커맨드 → 코어 `CommandBackend` 정렬 평가

**목적**: `mattermost/commands.py`의 핸들러들이 코어 `CommandBackend` Protocol에 정렬 가능한지 **평가**한다. 전환은 자연스러운 경우에만 수행하며, 평가 결과에 따라 이 Phase는 스킵될 수 있다.

### 선행 분석 (코드 수정 전에 수행)

코어 `CommandBackend.handle(ctx: CommandContext)`의 `CommandContext`에는 `CommandExecutor`가 필수 필드다. `CommandExecutor`는 `send`, `run_one`, `run_many`를 요구한다.

현재 Mattermost 핸들러들은 단순한 `send` 콜백만 받는 구조다. `CommandExecutor` 구현체를 만들려면 `run_one`/`run_many`(엔진 실행)까지 구현해야 하므로, 단순 전환이 아닌 새로운 어댑터 레이어가 필요하다.

### 평가 기준

각 핸들러를 아래 기준으로 분류:

| 분류 | 조건 | 예상 핸들러 |
|------|------|-------------|
| **전환 가능** | `send`만 사용, `CommandContext`의 기존 필드로 충분 | 평가 후 결정 |
| **전환 불가** | transport 고유 의존성 (`chat_prefs`, `roundtables`, `running_tasks` 등) 필요 | `handle_rt`, `handle_cancel`, `handle_trigger`, `handle_project` 등 대부분 |

### 작업

1. 위 평가를 수행하고 결과를 Phase 5 커밋 메시지에 기록한다.

2. **전환 가능한 핸들러가 있는 경우에만** `CommandBackend`로 전환하고, `_try_dispatch_command`에서 통일 디스패치로 호출한다.

3. **전환 가능한 핸들러가 없거나, `CommandExecutor` 구현 비용이 전환 이득보다 큰 경우**: 이 Phase를 스킵하고, 커밋 메시지에 평가 결과와 스킵 사유를 기록한다.

### 제약
- 코어 `CommandBackend` Protocol을 수정하지 않는다.
- `CommandExecutor` 구현체를 만들기 위해 대규모 어댑터를 작성하지 않는다 — 그것은 이 리팩토링의 범위를 초과한다.
- 이 Phase는 **Phase 3 완료 후** 진행해야 함 (분해된 함수 구조에 맞춰야 하므로).

### 검증
```sh
just check
uv run pytest tests/test_mattermost*.py -v --no-cov
```

---

## 전체 실행 규칙

1. **Phase 순서를 반드시 지킨다** (1→2→3→4→5). 각 Phase는 이전 Phase 완료를 전제로 한다.
2. **각 Phase 완료 후 `just check` 통과를 확인**한 뒤 커밋한다.
3. **telegram 디렉토리는 읽기만** 한다. 패턴 참조용이지 수정 대상이 아니다. 단, Phase 4에서 `state_store.py` 이동 시 import 경로만 수정한다.
4. **새 추상화 클래스/프레임워크를 만들지 않는다**. 기존 패턴 재사용이 원칙.
5. **과도한 docstring이나 주석을 추가하지 않는다**. Phase 1의 에러 정책 주석과 복잡한 로직의 인라인 설명만 허용.
6. **커밋 메시지 형식**: `refactor(mattermost): Phase N - 한줄 설명`
7. **코드 위치 참조는 함수명/클래스명 기준**으로 한다. 라인 번호는 편집 후 밀리므로 의존하지 않는다.

---

## 범위 밖 (명시적 제외)

| 항목 | 이유 |
|------|------|
| `telegram/loop.py` 분해 | 회귀 테스트가 두껍고, 현재 브랜치에서 수정 안 함 |
| EDA/이벤트 디스패처 도입 | 트랜스포트 2개인 프로젝트에 과잉 |
| Roundtable 코어 격상/일반화 | 안정화 전에 일반화는 순서가 틀림 |
| Transport 공통 Protocol 추출 | 영향 범위 최대, 이 리팩토링 이후 별도 작업 |
| i18n 분리 | 이 리팩토링 이후 별도 작업 |
| 커스텀 예외 계층 도입 | 주석 수준 정책으로 충분 |
| `CommandExecutor` 대규모 구현 | Phase 5 평가 결과에 따라 별도 작업으로 분리 |
