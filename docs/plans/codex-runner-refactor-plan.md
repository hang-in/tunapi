# Codex 러너 리팩토링 실행 문서

> 목적: roundtable 합의 내용을 실제 작업 가능한 범위로 다시 고정한다.
> 대상: `tunapi` 내부 러너 계층
> 원칙: 같은 것만 추상화하고, 다른 것은 남겨둔다.

## 결론

이번 작업은 전면 리팩토링이 아니다. 아래 두 가지에만 집중한다.

1. `src/tunapi/runners/codex.py`의 Codex 이벤트 변환 로직을 별도 모듈로 분리한다.
2. `msgspec.DecodeError` 처리처럼 러너들 사이에 실제로 동일한 JSONL 보일러플레이트만 제한적으로 공통화한다.

이번 범위에서 하지 않는 것:

- `process_error_events()` 공통화
- `stream_end_events()` 공통화
- 러너별 완료 시맨틱 통합
- `runner_bridge.py` / `progress.py` / `markdown.py` 동작 변경
- `completed.answer` 선택 정책 변경

## 합의된 프레이밍

핵심 문제는 단순히 `codex.py`가 길다는 것이 아니다. 더 정확히는 다음이다.

- Codex의 원시 이벤트를 Tunapi 액션 이벤트로 바꾸는 규칙이 거대한 `match/case` 안에 묻혀 있다.
- 이 규칙은 UI 소비 레이어가 기대하는 `Action.kind`, `title`, `detail`, `phase`, `ok` shape와 직접 연결된다.
- 반면 완료 판단은 러너별로 상태 의미가 다르므로, 같은 추상화에 묶기 어렵다.

즉 이번 작업의 본질은 `Codex의 UI 이벤트 계약을 러너 본체에서 분리`하는 것이다.

## 실제 소비 경계

이 문서에서 말하는 "client 영향"은 별도 프론트엔드 앱이 아니라 아래 소비 경계를 뜻한다.

- `src/tunapi/runner_bridge.py`
- `src/tunapi/progress.py`
- `src/tunapi/markdown.py`

여기서 중요한 것은 파일 위치가 아니라 이벤트 shape다. 따라서 이번 리팩토링은 구현 위치만 바꾸고, 아래 계약은 유지해야 한다.

- `Action.kind`
- `Action.title`
- `Action.detail`
- `ActionEvent.phase`
- `ActionEvent.ok`
- `CompletedEvent.answer`
- `CompletedEvent.error`

## 범위

### P0: Codex 이벤트 해석 분리

새 모듈:

- `src/tunapi/runners/codex_events.py`

이 모듈의 역할:

- Codex 원시 이벤트를 Tunapi `StartedEvent` / `ActionEvent`로 변환
- UI가 소비하는 액션 이벤트 매핑 규칙을 한곳에 모음
- 상태 없는 순수 변환 계층으로 유지

옮길 대상:

- `_short_tool_name`
- `_summarize_tool_result`
- `_normalize_change_list`
- `_format_change_summary`
- `_TodoSummary`
- `_summarize_todo_list`
- `_todo_title`
- `_translate_item_event`
- `translate_codex_event`

`codex.py`에 남길 대상:

- `_RESUME_RE`
- `_RECONNECTING_RE`
- `_parse_reconnect_message`
- `_AgentMessageSummary`
- `_select_final_answer`
- `CodexRunState`
- `CodexRunner`
- `build_runner`

명시적으로 이번 범위에서 남겨둘 것:

- `TurnStarted` / `TurnCompleted` / `TurnFailed` 처리
- reconnect 메시지 처리
- `AgentMessageItem` 누적
- `_select_final_answer()`를 통한 `state.final_answer` 계산

중요:

- `_select_final_answer()`는 이번 작업에서 `codex_events.py`로 옮기지 않는다.
- 이 로직은 UI 액션 계약보다 러너 내부 완료 시맨틱에 가깝다.

### P1: 제한적 msgspec 공통화

목표는 "진짜 동일한 처리"만 올리는 것이다.

공통화 대상:

- `msgspec.DecodeError` 발생 시 warning 로그를 남기고 `[]` 반환

선택적 공통화 대상:

- 현재 동일 동작을 쓰는 러너에 한해 `invalid_json_events() -> []`

적용 후보 러너:

- `src/tunapi/runners/claude.py`
- `src/tunapi/runners/codex.py`
- `src/tunapi/runners/gemini.py`
- `src/tunapi/runners/pi.py`
- `src/tunapi/runners/opencode.py`

권장 형태:

```python
class MsgspecJsonlRunnerMixin:
    def decode_error_events(...):
        if isinstance(error, msgspec.DecodeError):
            self.get_logger().warning(...)
            return []
        return super().decode_error_events(...)
```

`invalid_json_events()`는 모든 러너에 강제로 올리지 말고, 실제로 동일 정책을 쓰는 러너에만 적용한다.

## 비범위

아래는 이번 작업에서 건드리지 않는다.

- `process_error_events()` / `stream_end_events()`의 베이스 통합
- `final_answer`, `last_assistant_text`, `saw_step_finish` 같은 종료 의미의 통합
- `runner_bridge.py`의 오케스트레이션 리팩토링
- `progress.py` / `markdown.py`의 렌더링 정책 수정
- 이벤트 타입 추가
- 액션 제목 문구 재설계

이유:

- 겉보기 공통점보다 러너별 차이가 더 크다.
- 여기까지 베이스 클래스로 올리면 차이를 숨기는 추상화가 된다.

## 변경 금지 계약

이번 작업은 "이동"과 "얇은 공통화"가 목적이다. 아래 항목은 결과가 바뀌면 안 된다.

- `file_change.detail["changes"]` 구조
- `tool.detail["result_summary"]` 유무와 형식
- todo 관련 `kind="note"` 및 `detail={"done", "total"}` 형태
- `note` / `warning` / `tool` / `command` / `web_search` / `file_change` 분류
- `completed.answer` 선택 방식
- 러너별 오류 종료 동작

특히 `src/tunapi/markdown.py`가 특별 취급하는 `file_change.detail["changes"]`는 그대로 유지한다.

## 구현 가이드

### P0 구현 가이드

`CodexRunner.translate()`는 아래 역할만 남기는 것이 목표다.

- reconnect 스트림 메시지 처리
- `TurnStarted` 처리
- `TurnCompleted` 처리
- `TurnFailed` 처리
- `AgentMessageItem` 누적과 `_select_final_answer()` 호출
- 나머지 이벤트를 `translate_codex_event()`에 위임

`codex_events.py`는 아래 성격을 유지한다.

- 상태 없는 순수 함수 중심
- `factory`를 받아 이벤트 생성
- 기존 액션 shape 보존
- 러너 상태와 완료 정책에 접근하지 않음

### P1 구현 가이드

공통화는 최소 범위로 끝낸다.

- `decode_error_events()`만 먼저 올린다.
- `invalid_json_events()`는 동일 동작이 확인된 러너에서만 올린다.
- `process_error_events()` / `stream_end_events()`는 그대로 둔다.

공통화 위치는 `src/tunapi/runner.py`가 우선 후보지만, 베이스 클래스를 더 복잡하게 만들면 안 된다. 얇은 mixin이 더 자연스럽다면 mixin을 택한다.

## 테스트와 검증

이번 작업의 검증 포인트는 "파일이 분리되었는가"가 아니라 "이벤트 shape와 완료 의미가 그대로인가"다.

기존 테스트 우선 확인:

- `tests/test_codex_runner_helpers.py`
- `tests/test_codex_tool_result_summary.py`
- `tests/test_codex_schema.py`
- `tests/test_runner_contract.py`
- `tests/test_claude_runner.py`
- `tests/test_pi_runner.py`
- `tests/test_opencode_runner.py`

권장 추가 테스트:

- `tests/test_codex_events.py`

최소 케이스:

- `command_execution`
- `mcp_tool_call`
- `web_search`
- `file_change`
- `todo_list`
- `reasoning`
- `error`
- `agent_message(commentary)`

이 테스트의 목적은 `codex_events.py` 추출 이후에도 액션 이벤트 계약이 그대로임을 고정하는 것이다.

추가 회귀 관점:

- `msgspec.DecodeError`에서 warning log 후 스트림이 계속 소비되는지
- `invalid_json_events() -> []`로 바꾼 러너가 있다면, 기존 note 이벤트 의존 테스트가 없는지

## 작업 순서

1. 현재 Codex 번역 계약을 테스트로 먼저 확인한다.
2. `codex_events.py`를 만들고 P0 대상 함수를 이동한다.
3. `codex.py`에서 import와 위임 경로를 정리한다.
4. Codex 관련 테스트로 이벤트 shape 보존을 확인한다.
5. 제한적 `msgspec` 공통화를 도입한다.
6. 영향받는 러너 테스트를 다시 돌린다.
7. 마지막에 전체 회귀를 확인한다.

## 검증 명령

우선순위는 빠른 회귀 확인이다.

```sh
uv run pytest tests/test_codex_runner_helpers.py tests/test_codex_tool_result_summary.py tests/test_runner_contract.py tests/test_claude_runner.py tests/test_pi_runner.py tests/test_opencode_runner.py
uv run pytest
```

가능하면 마지막에:

```sh
just check
```

## 완료 조건

- `src/tunapi/runners/codex.py`가 실행/상태 관리 중심 파일로 줄어 있다.
- Codex 액션 이벤트 매핑 규칙이 `src/tunapi/runners/codex_events.py`에서 읽힌다.
- `msgspec.DecodeError` 중복이 제거되어 있다.
- 러너별 완료 시맨틱은 그대로 남아 있다.
- 소비 레이어 기준 이벤트 계약이 바뀌지 않는다.

## 리뷰 체크리스트

- 추상화가 차이를 숨기지 않았는가
- P0가 `_select_final_answer()`까지 끌고 가지 않았는가
- `file_change.detail["changes"]`가 동일한가
- `tool.detail["result_summary"]`가 동일한가
- todo / note / warning 분류가 바뀌지 않았는가
- `process_error_events()` / `stream_end_events()` 공통화가 슬쩍 섞이지 않았는가
