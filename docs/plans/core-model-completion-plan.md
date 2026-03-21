# Core Model Completion 실행 계획

> 상태: 실행 대기
> 작성일: 2026-03-20
> 근거: RT 5라운드 합의 + 사용자 검토

## 한 줄 요약

tunapi의 제품 본체는 `core 상태 모델 + 모바일 웹 tunaDish`이고, transport는 알림·트리거·단일 액션·handoff 링크만 담당한다.

## 구현 우선순위

| 순서 | 모듈 | 범위 | 비고 |
|---|---|---|---|
| P0 | `core/conversation_branch.py` | branch_id, parent_branch_id, status, label, session linkage | ✅ 완료 |
| P0 | `core/review.py` | review 요청·approve·reject·comment, artifact version 참조 | ✅ 완료 |
| P0 | `core/synthesis.py` | thesis, agreements, disagreements, open_questions, action_items | ✅ 완료 |
| P1 | `core/memory_facade.py` 강화 | P0 모델 3개를 통합 read API로 노출 | ✅ 완료 (ProjectContextDTO) |
| P1 | `core/handoff.py` | project/session/branch/focus/pending_run을 URI로 패키징 | ✅ 완료 |
| P2 | `core/roundtable.py` 구조화 | Participant(role), Utterance(stage, reply_to), staged progression | ✅ 완료 (rt_participant, rt_utterance, rt_structured) |
| P3 | tunaDish 모바일 웹 | branch/review/discussion 비선형 탐색, focused landing | P0~P2 안정화 후 착수 |

## 설계 원칙

### Core 상태 소유권

- 모든 상태 전이는 core command를 통해 발생한다.
- transport는 core store를 직접 읽거나 쓰지 않는다. facade의 read API 또는 command 발행만 가능.
- 기존 패턴 준수: `JsonStateStore`, per-project lazy init, async lock, msgspec.Struct.

### Transport 기능 표면

- 현재 command surface(`/help`, `/model`, `/trigger`, `/status`, `/cancel`, `/new`, `/project`, `/persona`, `/rt`) 동결.
- P0 모델에 대해서는 **알림 + 단일 액션 + handoff link**만 추가.
  - 예: "Review #42 대기 중. `/approve 42` | [상세 보기](tunapi://...)"
- branch graph 탐색, review diff, synthesis 편집은 transport에 넣지 않는다.

### RT 설계-구현 분리

- SynthesisArtifact 저장 모델은 RT 구조화와 같이 **설계**한다 (P0에서 스키마 확정).
- RT 진행 구조 변경(staged progression, moderator)은 P2에서 **구현**한다.
- 이유: 나중에 RT를 다시 뜯어고치지 않기 위해.

### Handoff = 비동기 재진입

- 실시간 커서 동기화가 아니라 `resume target + pending work + focus anchor`.
- "자리 비운 사이 걸어둔 작업을 다른 기기에서 이어받는다"가 핵심.
- deep link 수준으로 시작: `tunapi://open?project={}&session={}&branch={}&focus={}`.

## 금지 사항

1. transport가 core store를 직접 변경하는 코드
2. Git branch와 conversation branch를 같은 ID 공간으로 합치는 설계
3. review, discussion, branch를 하나의 thread 개념으로 뭉개는 설계
4. flat `list[tuple[str, str]]` RT transcript만 유지하는 설계
5. Discord/Slack/Mattermost의 공간 구조를 core 도메인 모델로 역수입하는 설계

## 보류 사항

| 항목 | 재개 조건 |
|---|---|
| Discord transport | P0~P1 안정화 + handoff protocol 검증 후 |
| tunaDish 웹 프론트엔드 | P0~P2 안정화 후 |
| 실시간 멀티디바이스 동기화 | tunaDish 존재 후 필요성 재평가 |
| 멀티 유저 identity resolver | 멀티 유저 시나리오 현실화 시 |
| Transport 복잡 UI (branch 탐색기 등) | tunaDish가 이 역할을 대신함 |

## 기존 코드 기반

P0 구현 시 활용할 기존 자산:

- `branch_sessions.py` — `BranchRecord` 패턴 (msgspec.Struct, status enum, per-project store)
- `discussion_records.py` — `DiscussionRecord`, `ActionItem` 패턴
- `memory_facade.py` — 통합 조회 + 양방향 링크 패턴
- `roundtable.py` — `RoundtableSession` (확장 대상)
- `project_memory.py` — `MemoryEntry` type enum 패턴

## P0 데이터 모델 스케치

```python
# conversation_branch.py
class ConversationBranch(msgspec.Struct):
    branch_id: str
    parent_branch_id: str | None
    label: str
    status: Literal["active", "merged", "discarded"]
    session_id: str           # chat_sessions의 키와 연결
    git_branch: str | None    # 선택적 Git branch 연결
    created_at: str
    updated_at: str

# review.py
class ReviewRequest(msgspec.Struct):
    review_id: str
    artifact_id: str          # synthesis 또는 코드 변경 참조
    artifact_version: int
    status: Literal["pending", "approved", "rejected"]
    reviewer_comment: str
    created_at: str
    resolved_at: str | None

# synthesis.py
class SynthesisArtifact(msgspec.Struct):
    artifact_id: str
    source_type: Literal["roundtable", "discussion", "manual"]
    source_id: str            # RT session_id 또는 discussion_id
    version: int
    thesis: str
    agreements: list[str]
    disagreements: list[str]
    open_questions: list[str]
    action_items: list[ActionItem]
    created_at: str
```

## 다음 액션

1. 이 문서 리뷰 및 승인
2. P0 모델 3개 구현 착수 (ConversationBranch → ReviewRequest → SynthesisArtifact)
3. 기존 테스트 패턴(`tests/test_core_chat_sessions.py`) 참고하여 각 모델 테스트 작성
