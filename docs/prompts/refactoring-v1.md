# tunapi 리팩토링 실행 프롬프트 v1

> **대상**: 코드 수정 권한이 있는 AI 코딩 에이전트 (Claude Code, Codex 등)
> **저장소**: `~/privateProject/tunapi` (`feat/roundtable` 브랜치)
> **생성일**: 2025-03-19

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
| `RoundtableConfig` | `src/tunapi/transport_runtime.py:24` | 라운드테이블 설정 dataclass |

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

3. 현재 코드가 정책과 일치하는지 검증하고, 불일치가 있으면 코드를 정책에 맞게 수정:
   - `loop.py:614`: `except Exception` 블록이 로그만 남기고 사용자에게 알리지 않음 — 정책과 일치하는지 확인
   - `roundtable.py:291-303`: 엔진별 에러 시 사용자에게 메시지 전송 + 다음 엔진으로 계속 — 정책과 일치

### 검증
```sh
just check  # format + lint + typecheck + tests 전부 통과해야 함
```

---

## Phase 2: Roundtable 단위 테스트

**목적**: 406줄, 테스트 0개인 `roundtable.py`의 핵심 순수 로직을 커버한다. async 함수(`run_roundtable` 등)는 이 Phase에서는 다루지 않는다.

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
class TestBuildRoundPrompt:
    def test_no_context(self): ...  # transcript 빈 경우 → topic 그대로 반환
    def test_with_previous_rounds(self): ...  # transcript 있으면 "이전 라운드 응답" 포함
    def test_with_current_round_responses(self): ...  # "이번 라운드 다른 에이전트 답변" 포함
    def test_long_answer_truncated(self): ...  # 4000자 초과 시 "..." 추가 확인
    def test_both_previous_and_current(self): ...  # 둘 다 있을 때 구분자 확인
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

**목적**: 313~622줄의 거대 함수를 역할별로 분리한다. 인터페이스(함수 시그니처)는 최대한 유지하고 내부만 분해한다.

### 분해 방향

현재 `_dispatch_message`의 실행 흐름:
1. 커맨드 파싱 + 디스패치 (329-442)
2. 자동 파일 업로드 (444-464)
3. 파일 + 텍스트 처리 (467-484)
4. 음성 전사 (487-492)
5. 트리거 모드 판단 (495-506)
6. 세션/컨텍스트 해석 (508-569)
7. 러너 실행 (590-621)

### 작업

1. `_dispatch_message`를 **3개 단계 함수**로 분리:

```python
# 기존 _dispatch_message는 orchestrator 역할만 남김
async def _dispatch_message(msg, cfg, running_tasks, sessions, chat_prefs, roundtables):
    """Dispatch: slash commands → prompt resolution → engine run."""
    # 1. Command handling
    if await _try_dispatch_command(msg, cfg, running_tasks, sessions, chat_prefs, roundtables):
        return

    # 2. Prompt resolution (files, voice, trigger, persona)
    prompt_info = await _resolve_prompt(msg, cfg, chat_prefs)
    if prompt_info is None:
        return

    # 3. Engine execution
    await _run_engine(prompt_info, msg, cfg, running_tasks, sessions, chat_prefs)
```

2. **`_try_dispatch_command`**: 현재 329-442줄의 match문 전체를 이동. `bool` 반환 (처리했으면 True).

3. **`_resolve_prompt`**: 파일 처리 + 음성 전사 + 트리거 판단 + mention 제거를 묶음. 결과를 담는 간단한 dataclass 반환:

```python
@dataclass(slots=True)
class _ResolvedPrompt:
    text: str
    file_context: str  # 빈 문자열이면 없음
```

4. **`_run_engine`**: 세션/컨텍스트 해석 → 러너 실행 → 에러 처리. Phase 1에서 정의한 에러 정책을 이 함수에 적용.

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

**목적**: `mattermost/chat_sessions.py`가 `telegram/state_store.py`의 `JsonStateStore[T]` 패턴을 직접 재구현하고 있다. 기존 베이스 클래스를 재사용하도록 정렬한다.

### 현재 상태
- `telegram/state_store.py`: `JsonStateStore[T]` 제네릭 — 버전 관리, mtime 기반 리로드, atomic write, lock 전부 내장
- `mattermost/chat_sessions.py`: 동일 패턴을 수동으로 재구현 (버전 체크, lock, load/save)
- `mattermost/chat_prefs.py`: 역시 동일 패턴을 수동 재구현

### 작업

1. `telegram/state_store.py`를 `src/tunapi/state_store.py`(또는 `src/tunapi/utils/state_store.py`)로 이동하여 공용 모듈로 승격. 기존 telegram import는 새 위치에서 re-export하지 말고, import 경로를 직접 수정.

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

# After: JsonStateStore 재사용
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
```

3. `mattermost/chat_prefs.py`에도 동일하게 적용 가능한지 평가. 가능하면 적용, 구조가 많이 다르면 이 Phase에서는 스킵.

### 주의
- `JsonStateStore`는 현재 `async with self._lock`가 아니라 일반 메서드에서 `_reload_locked_if_needed`를 호출하는 패턴. Mattermost 쪽이 async lock을 쓰고 있으므로, 호환성을 확인할 것.
- `JsonStateStore`가 `atomic_write_json`을 사용하지만, Mattermost 쪽은 `write_bytes`를 직접 사용. atomic write로 통일하는 것이 개선.

### 검증
```sh
just check
uv run pytest tests/ -v --no-cov
```

---

## Phase 5: Mattermost 커맨드 → 코어 `commands.py` 정렬

**목적**: `mattermost/commands.py`의 인라인 핸들러들이 코어 `CommandBackend` Protocol을 활용하지 않고 있다. 새 레지스트리를 만드는 것이 아니라, 기존 코어 추상화에 맞추는 것.

### 현재 상태
- 코어 `commands.py`: `CommandBackend` Protocol, `CommandContext`, `CommandResult` 정의 + 플러그인 로드 시스템
- `mattermost/commands.py`: `handle_help()`, `handle_model()`, `handle_rt()` 등이 독립 async 함수로 존재, `send` 콜백을 직접 받음

### 작업

1. 현재 `mattermost/commands.py`의 각 핸들러가 코어 `CommandBackend`를 구현할 수 있는지 **먼저 평가**. 핸들러마다 필요한 의존성(`chat_prefs`, `runtime`, `running_tasks` 등)이 `CommandContext`에 매핑 가능한지 확인.

2. 매핑이 자연스러운 핸들러(예: `handle_help`, `handle_status`)부터 `CommandBackend`로 전환. 매핑이 어색한 핸들러(예: `handle_rt`는 roundtable 전용 콜백이 필요)는 현재 형태를 유지.

3. `_dispatch_message`(또는 Phase 3에서 분리한 `_try_dispatch_command`)의 match문에서, `CommandBackend` 기반 핸들러는 통일된 디스패치로 호출.

### 제약
- 코어 `CommandBackend` Protocol을 수정하지 않는다.
- 모든 핸들러를 강제로 맞추지 않는다. 자연스럽게 맞는 것만 전환.
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
3. **telegram 디렉토리는 읽기만** 한다. 패턴 참조용이지 수정 대상이 아니다.
4. **새 추상화 클래스/프레임워크를 만들지 않는다**. 기존 패턴 재사용이 원칙.
5. **과도한 docstring이나 주석을 추가하지 않는다**. Phase 1의 에러 정책 주석과 복잡한 로직의 인라인 설명만 허용.
6. **커밋 메시지 형식**: `refactor(mattermost): Phase N - 한줄 설명`
7. Phase 4에서 `state_store.py` 이동은 telegram import 경로 변경을 수반하므로, import만 바꾸고 로직은 건드리지 않는다.

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
