# Roundtable Plan

채널에서 여러 AI 에이전트에게 동일한 질문을 던지고 의견을 순차 수집하는 기능.
핵심 원칙: **자연어 한 줄로 실행** — `!rt "질문"` 하나면 끝.

## 설계 철학

- 페르소나는 각 CLI 전역 설정에 이미 존재 (`~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md` 등)
- tunapi는 페르소나를 주입하지 않고, 엔진 목록과 라운드 수만 관리
- 설정은 `tunapi.toml`의 `[roundtable]` 섹션에서 한번만

## 설정 (tunapi.toml)

```toml
[roundtable]
engines = ["claude", "gemini", "codex"]  # 참여 엔진 (빈 배열 = 모든 available 엔진)
rounds = 1                                # 기본 라운드 수
max_rounds = 3                            # 최대 라운드 제한
```

## 현재 상태

### 완료

- ✅ Phase 1: `!project` + context 배선 (채널-프로젝트 바인딩)
- ✅ Phase 3: `!persona` + `@persona` prefix (채팅 내 페르소나 관리)
- ✅ `!`/`/` 접두어 모두 지원
- ✅ **Roundtable v0**: `!rt` 명령 + 자동 멀티라운드 + transcript 컨텍스트

### v0 구현 상세

#### 사용법
```
!rt "질문"              # config 기반 1라운드
!rt "질문" --rounds 2   # 2라운드 (이전 응답을 컨텍스트로)
!rt                     # 사용법 + 현재 설정 표시
```

#### 동작 플로우
```
!rt "이 설계 어떤가?" --rounds 2

1. 헤더 포스트 → 스레드 생성
   "🔵 Roundtable
    Topic: 이 설계 어떤가?
    Engines: claude, gemini, codex | Rounds: 2 rounds"

2. Round 1:
   claude에 "이 설계 어떤가?" 전달 → 스레드에 게시 (🤖 claude 라벨)
   gemini에 동일 전달 → 게시
   codex에 동일 전달 → 게시

3. Round 2 (이전 응답을 컨텍스트로):
   각 엔진에 전달:
     "이전 라운드 응답:
      [claude]: ...
      [gemini]: ...
      [codex]: ...
      ---
      위 의견들을 참고하여 다시 답변해주세요: 이 설계 어떤가?"

4. 🏁 Roundtable 완료 (2/2 rounds)
```

#### 안전장치
- 🛑 리액션으로 라운드 사이 cancel (헤더 포스트에)
- 한 엔진 실패해도 나머지 계속 진행
- `max_rounds` 제한 (config, 기본 3)
- 봇 자신의 응답에 재반응 루프 방지 (parsing.py에서 bot_user_id 필터)

#### 변경 파일
- `settings.py`: `RoundtableSettings` 모델 추가
- `transport_runtime.py`: `RoundtableConfig` dataclass + property
- `runtime_loader.py`: roundtable config 배선
- `runner_bridge.py`: `handle_message` → `str | None` 반환 (응답 텍스트 캡처)
- `roundtable.py`: 세션 관리 + 멀티라운드 실행 + transcript 컨텍스트
- `commands.py`: `handle_rt()` — `!rt "topic" --rounds N` 파싱
- `loop.py`: `/rt` 디스패치 + 🛑 cancel 연동

#### 세션 구조
```python
@dataclass
class RoundtableSession:
    thread_id: str
    channel_id: str
    topic: str
    engines: list[str]
    total_rounds: int
    current_round: int
    transcript: list[tuple[str, str]]  # (engine, answer)
    cancel_event: anyio.Event
```

## v1 (이후): 스레드 내 후속 메시지

- 스레드에서 사용자 메시지 → 새 라운드 트리거 (모든 엔진 재순회)
- 특정 엔진만 호출: `@claude 추가 질문`
- 에이전트별 worktree 분리 (`debate/<topic>/<agent>` 브랜치)
- Interactive Button UI (Mattermost 콜백 처리 필요)
- 비용 추적: JSONL usage 이벤트에서 수집

## 비고

- Phase 2 (명령어 디스패치 일반화): 현재 match 블록으로 충분. 명령어가 10개 이상 될 때 리팩터링
- config watcher: Mattermost에도 Telegram처럼 연결 필요 (별도 이슈)
