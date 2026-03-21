# tunaDish가 소비할 tunapi API Surface

> 상태: 검토 대기
> 작성일: 2026-03-20
> 목적: tunaDish 재개 시 참고할 서버측 API 현황

## 핵심 진입점

`ProjectMemoryFacade` (`src/tunapi/core/memory_facade.py`)

tunaDish는 이 facade의 메서드만 호출한다. 개별 store에 직접 접근하지 않는다.

## Read API (tunaDish UI 렌더링용)

| 메서드 | 반환 | 용도 |
|--------|------|------|
| `get_project_context_dto(project)` | `ProjectContextDTO` | 프로젝트 전체 상태 스냅샷 — 구조화된 데이터로 UI 렌더링 |
| `get_project_context(project)` | `str` | Markdown 문자열 — 에이전트 프롬프트 앞에 붙이기 |
| `get_handoff_uri(project, ...)` | `str` | `tunapi://open?project=...` deep link — 비동기 재진입 |

### ProjectContextDTO 필드

```python
@dataclass
class ProjectContextDTO:
    memory_entries: list[MemoryEntry]           # 결정/리뷰/아이디어/컨텍스트
    active_branches: list[BranchRecord]          # git branch 메타데이터
    conv_branches: list[ConversationBranch]       # 대화 분기
    discussions: list[DiscussionRecord]           # open + resolved 토론
    pending_reviews: list[ReviewRequest]          # 대기 중 리뷰
    synthesis_artifacts: list[SynthesisArtifact]  # 정제된 산출물
    structured_sessions: list[StructuredRoundtableSession]  # 구조화된 RT
    markdown: str                                 # get_project_context() 동일
```

## Write API

| 메서드 | 용도 |
|--------|------|
| `add_memory(project, type, title, content, source, tags)` | 결정/아이디어 기록 |
| `save_roundtable(session, project, summary, branch_name, auto_synthesis, auto_structured)` | RT 완료 → discussion + synthesis + structured 한 번에 |
| `link_discussion_to_branch(project, discussion_id, branch_name)` | discussion ↔ branch 양방향 연결 |
| `save_synthesis_from_discussion(project, discussion_id)` | discussion → synthesis 변환 |
| `request_review_for_synthesis(project, artifact_id)` | synthesis → review 요청 |

## 하위 Store 직접 접근 (facade 속성)

tunaDish가 필요하면 `facade.{store}` 로 직접 접근 가능:

| 속성 | Store | 주요 API |
|------|-------|----------|
| `facade.memory` | `ProjectMemoryStore` | `add_entry`, `list_entries`, `search`, `delete_entry`, `get_context_summary` |
| `facade.branches` | `BranchSessionStore` | `create_branch`, `merge_branch`, `abandon_branch`, `link_entry` |
| `facade.discussions` | `DiscussionRecordStore` | `create_record`, `update_resolution`, `add_action_item`, `archive_record` |
| `facade.conv_branches` | `ConversationBranchStore` | `create`, `merge`, `discard`, `link_session`, `link_git_branch` |
| `facade.synthesis` | `SynthesisStore` | `create`, `update_version`, `from_discussion_record` |
| `facade.reviews` | `ReviewStore` | `request_review`, `approve`, `reject` |
| `facade.rt_structured` | `StructuredRoundtableStore` | `create`, `add_utterance`, `complete`, `cancel` |

## Handoff URI

```
tunapi://open?project=myproj&session=sess1&branch=br1&focus=review_42&run=run1
```

tunaDish가 이 URI를 받으면 해당 프로젝트/브랜치/포커스로 자동 이동.

## 저장 위치

모든 데이터: `~/.tunapi/project_memory/{project_alias}_*.json`

## tunaDish가 구현해야 할 것

1. WebSocket + JSON-RPC transport plugin (tunapi 측)
2. facade 메서드를 JSON-RPC로 노출하는 서버
3. `ProjectContextDTO`를 UI 컴포넌트로 렌더링하는 프론트엔드
4. handoff URI 핸들러

## tunaDish가 구현하지 않아도 되는 것

- 저장 로직 (facade가 처리)
- 파일 I/O (JsonStateStore가 처리)
- roundtable 실행 (기존 transport가 처리)
- session/journal 관리 (기존 코드가 처리)
