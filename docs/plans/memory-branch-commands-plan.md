# `!memory` / `!branch` Transport 커맨드 인터페이스 계획

> 상태: 계획
> 작성일: 2026-03-20
> 의존: P0~P2 완료 (✅), facade 통합 (✅)

## 목표

현재 `ProjectMemoryFacade`는 코드에서만 호출 가능하다. 사용자가 Mattermost/Slack에서 직접 프로젝트 메모리를 읽고 쓸 수 있는 커맨드 인터페이스를 추가한다.

## 커맨드 설계

### `!memory`

```
!memory                          → 현재 프로젝트의 최근 엔트리 5개 요약
!memory list [type]              → 엔트리 목록 (type: decision/review/idea/context)
!memory add <type> <title> <내용> → 엔트리 추가
!memory search <query>           → 검색
!memory delete <id>              → 삭제
```

### `!branch`

```
!branch                          → 현재 프로젝트의 active conversation branch 목록
!branch create <label>           → 새 대화 분기 생성
!branch merge <id>               → 분기 병합
!branch discard <id>             → 분기 폐기
!branch link-git <id> <git-branch> → git branch 연결
```

### `!review`

```
!review                          → pending review 목록
!review approve <id> [comment]   → 승인
!review reject <id> [comment]    → 거절
```

### `!context`

```
!context                         → 현재 프로젝트의 전체 컨텍스트 출력 (get_project_context)
```

## 제약

- 모든 커맨드는 현재 채널에 바인딩된 프로젝트 기준으로 동작
- 프로젝트가 바인딩되지 않은 채널에서는 "프로젝트를 먼저 설정하세요" 안내
- MM은 `**bold**`, Slack은 `*bold*` — 기존 커맨드 패턴 유지
- 각 핸들러는 `commands.py`에 추가, `loop.py`의 dispatcher에 case 추가
- facade 인스턴스는 이미 loop에 주입됨 — `_try_dispatch_command`에 전달만 하면 됨

## 구현 순서

1. `!context` (가장 단순 — `get_project_context` 호출만)
2. `!memory list/add/search`
3. `!branch create/merge/discard`
4. `!review approve/reject`

## 파일 수정 범위

- `mattermost/commands.py`: 핸들러 추가 (handle_memory, handle_branch, handle_review, handle_context)
- `slack/commands.py`: 동일
- `mattermost/loop.py`: dispatcher에 case 추가
- `slack/loop.py`: 동일
- help 텍스트 업데이트

## 아직 결정하지 않은 것

- `!memory add`에서 source를 자동으로 현재 엔진으로 채울지, 아니면 "user"로 고정할지
- `!branch` ID를 짧은 prefix로 입력 가능하게 할지 (예: `!branch merge abc1` → ID가 `1742486400000_abc1...`인 항목 매칭)
- `!review` 대상이 여러 개일 때 인라인으로 선택하게 할지
