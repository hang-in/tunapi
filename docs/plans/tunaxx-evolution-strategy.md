# tunaXX 고도화 전략 메모

> 목적: `tunapi` + `tunaDish` + future Discord transport를 한 방향으로 끌고 가기 위한 참고 문서
>
> 참고 사례:
> - `takopi-slack-plugin`
> - `takopi_swarm`
> - `takopi-discord`

## 한 줄 요약

세 프로젝트를 그대로 따라가는 것이 아니라, 아래처럼 역할을 나눠서 흡수하는 것이 맞다.

- `takopi-slack-plugin`: 운영 UX 참고
- `takopi_swarm`: orchestration primitive 참고
- `takopi-discord`: workspace 정보 구조 참고

즉 `tunapi`는 범용 코어를 유지하고, `tunaDish`는 프로젝트 중심 UI를 강화하며, future Discord transport는 Discord 공간 구조를 잘 활용하는 쪽으로 간다.

## 현재 전제

현재 `tunapi`는 이미 아래를 갖고 있다.

- project + branch + worktree 실행
- multi-engine runner bridge
- multi-transport 구조
- roundtable
- project memory / branch session / discussion record의 뼈대

현재 `tunaDish`는 아래 방향으로 가고 있다.

- `tunapi` 전용 클라이언트
- 프로젝트 중심 채팅 UI
- main / branch / discussion / context panel 중심 UX
- 장기적으로 Git branch 개념과 conversation branch 개념을 함께 다룰 계획

따라서 다음 고도화는 "새 transport 하나 더 추가"보다, 아래 3축 정리가 먼저다.

1. 공통 상태 모델
2. orchestration primitive
3. 공간 구조와 UX

## 참고 사례에서 가져올 것

### 1. `takopi-slack-plugin`에서 가져올 것

가치가 큰 부분:

- Slack 전용 운영 UX
- archive 확인 플로우
- custom action button
- thread / top-level reply 선택
- stale worktree reminder
- command output routing

`tunapi`에 번역하면:

- Slack/Mattermost transport에 action button 체계 추가
- archive / merge / abandon / review 요청 같은 확인 플로우 추가
- 오래된 branch/worktree에 대한 정리 리마인더
- 특정 command 결과를 별도 채널/스레드로 라우팅하는 기능 검토

주의:

- Slack 전용 구조를 core로 끌어올리면 안 된다.
- session 모델을 Slack thread 기준으로 재정의하면 안 된다.

### 2. `takopi_swarm`에서 가져올 것

가치가 큰 부분:

- `control`과 `trigger`의 분리
- synthetic message injection
- topic/branch/worktree를 coordination 단위로 보는 관점

`tunapi`에 번역하면:

- `control`
  - coordination note
  - review note
  - decision note
  - branch handoff note
- `trigger`
  - 특정 project/branch/discussion에 대한 synthetic run request

이 primitive는 future automation뿐 아니라, 사용자 중심 workflow에도 유용하다.

- 사용자가 discussion 정리만 남기고 싶을 때: `control`
- 실제 작업을 특정 branch agent에 넘길 때: `trigger`

주의:

- `takopi_swarm`은 Telegram topic 중심 설계다.
- `tunapi`는 transport-independent 모델이 필요하다.
- 완전 자율 swarm이 아니라, 사용자 승인 중심 구조를 유지해야 한다.

### 3. `takopi-discord`에서 가져올 것

가치가 큰 부분:

- 공간 구조가 매우 직관적임
- Category / Channel / Thread / Voice Channel을
  - project
  - branch/session
  - voice session
  로 깔끔하게 매핑함
- `/bind`, `/ctx`, `/agent`, `/model`, `/trigger` 같은 제품 개념이 잘 드러남
- voice가 "부가 기능"이 아니라 context-aware session으로 연결됨

`tunapi`와 `tunaDish`에 번역하면:

- 프로젝트가 최상위 단위여야 함
- branch와 discussion이 UI 구조에 명확히 보여야 함
- Git branch와 conversation branch를 구분해야 함
- voice는 나중에 붙여도, context-bound session으로 설계해야 함

주의:

- Discord 구조를 core 모델로 착각하면 안 된다.
- `thread = branch`로 단순화하면 discussion/review 흐름을 담기 어렵다.

## 권장 공통 모델

세 참고 사례를 섞을 때 핵심은 transport보다 상위의 상태 모델이다.

### 1. Project

프로젝트는 모든 transport와 `tunaDish`가 공유하는 최상위 단위다.

포함해야 할 것:

- repo path
- default branch
- active branch sessions
- decisions
- reviews
- ideas
- discussion records

### 2. Git Branch

실제 코드 실행 위치다.

- worktree와 연결
- merge / abandon / cleanup 대상
- 실행 runner context와 연결

### 3. Conversation Branch

main 대화에서 갈라진 논의 단위다.

- 설계 실험
- 리뷰
- 대안 검토
- 정리되지 않은 feature discussion

이 개념은 Git branch와 1:1이 아닐 수 있다.

### 4. Discussion Session

roundtable이나 리뷰 회의를 담는 단위다.

- participants
- summary
- resolution
- open questions
- action items
- linked project
- linked branch (optional)

### 5. Control / Trigger

오케스트레이션 primitive다.

- `control`: 기록, 조정, handoff, 상태 공유
- `trigger`: 실제 run 시작

이 둘은 나중에 transport UI와도 잘 맞는다.

- Slack button
- Discord slash command
- `tunaDish` action button

## `tunapi`에 넣어야 할 것

### 1. control / trigger 추상 모델

새 transport를 추가하기 전에, core 차원에서 이 개념을 명확히 두는 편이 좋다.

예상 역할:

- control event 저장
- trigger request 생성
- project/branch/discussion 대상 해석

중요:

- transport가 아니라 core event/model로 둬야 한다.
- Telegram의 JSONL inbox 같은 구현은 transport별 어댑터로만 둔다.

### 2. branch 수명주기 정리

현재는 worktree branch와 conversation branch가 아직 약하게 분리되어 있다.

보강 방향:

- git branch metadata
- conversation branch metadata
- merge summary
- abandon reason
- review links
- discussion links

### 3. action surface

Slack/Mattermost/Discord/future `tunaDish` 모두에서 쓰기 쉬운 공통 action 개념이 필요하다.

예:

- cancel
- archive
- merge
- abandon
- request review
- open discussion
- trigger follow-up run

core는 action 의미만 알고, 실제 button/slash command/rendering은 transport가 맡는 구조가 맞다.

### 4. 오래된 branch/worktree 관리

`takopi-slack-plugin`의 stale reminder는 실용적이다.

`tunapi`에서는 아래 형태가 좋다.

- stale branch session reminder
- stale worktree reminder
- merge/abandon 후보 표시

이는 `tunaDish`의 branch inbox나 review panel에도 연결할 수 있다.

## `tunaDish`에 넣어야 할 것

### 1. 프로젝트 중심 정보 구조

`takopi-discord`의 공간 모델을 UI에 번역하면 다음 구조가 적합하다.

- Project
  - Main
  - Branch Conversations
  - Discussions
  - Reviews
  - Files / Voice (future)

즉 `tunaDish`는 일반 채팅앱이 아니라 프로젝트 워크스페이스처럼 보여야 한다.

### 2. Git branch와 conversation branch 동시 표기

UI에서 이 둘을 명확히 구분해야 한다.

- Git branch
  - 실제 코드가 실행되는 위치
  - merge / abandon 대상
- Conversation branch
  - main 대화에서 갈라진 논의
  - 요약/정리/비교의 대상

가장 나쁜 UX는 둘을 같은 것으로 보이게 만드는 것이다.

### 3. discussion panel

`takopi_swarm`의 control/trigger와 `roundtable`을 합치면, `tunaDish`에는 discussion panel이 필요하다.

최소 구성:

- participants
- current status
- summary
- open questions
- action items
- trigger next step
- record review note

### 4. action-first UI

`takopi-slack-plugin`의 button UX는 `tunaDish`에도 잘 맞는다.

필요한 액션:

- merge
- abandon
- archive
- ask review
- continue on branch
- open discussion
- trigger implementation

### 5. voice는 뒤로 미루되 구조는 열어두기

`takopi-discord`의 voice session 개념은 좋지만, 지금 당장 우선순위는 아니다.

다만 나중에 붙일 때를 위해:

- voice transcript
- linked project
- linked branch/discussion

정도는 설계상 고려해 둘 가치가 있다.

## future Discord transport 방향

Discord transport를 만든다면, `takopi-discord`의 공간 활용은 적극 참고할 가치가 있다.

권장 방향:

- Channel = project binding
- Thread = session/discussion
- `@branch` = Git branch target
- Slash command = explicit action surface
- Voice channel = future voice session

단, 그대로 복제하지는 않는다.

`tunapi` 기준으로는 아래가 더 적합하다.

- thread는 무조건 branch가 아니라, session/discussion 둘 다 가능
- branch와 discussion을 metadata로 분리
- project memory와 직접 연결

## 권장 단계별 로드맵

### 1단계: core 정리

- project memory 보강
- branch session 보강
- discussion record 보강
- control / trigger 모델 설계

### 2단계: action surface 정리

- Slack/Mattermost action button 보강
- archive / merge / abandon / review flow 정리
- stale reminder 설계

### 3단계: `tunaDish` 제품화

- 프로젝트 중심 sidebar
- branch / discussion / review 패널
- Git branch vs conversation branch 구분 UI
- mock 기반 UX 먼저 다듬기

### 4단계: Discord transport 탐색

- 최소 transport MVP
- `/bind`, `/ctx`, `/model`, `/trigger` 계열 명령
- thread/session mapping 검증

### 5단계: 오케스트레이션 확장

- 사용자 승인 중심 control / trigger
- manager/worker 같은 완전 자율이 아니라,
  user-in-the-loop coordination으로 시작

## 하지 말아야 할 것

- Slack/Discord/Telegram 구조를 core 모델로 착각하기
- `thread = branch = discussion`으로 단순화하기
- 완전 자율 swarm을 먼저 만들기
- project memory 없이 orchestration부터 크게 올리기
- `tunaDish`를 범용 채팅앱처럼 디자인하기

## 최종 정리

세 참고 사례는 방향이 서로 다르다.

- `takopi-slack-plugin`: transport UX
- `takopi_swarm`: orchestration primitive
- `takopi-discord`: workspace structure

`tunaXX`는 이 셋을 그대로 합치는 것이 아니라, 아래 공식을 따라야 한다.

- `tunapi`는 범용 코어 + 상태 모델
- `tunaDish`는 프로젝트 중심 전용 클라이언트
- future Discord transport는 Discord의 공간 구조를 적극 활용
- orchestration은 `control / trigger` primitive로 작게 시작
- 최종 승인과 방향 수정은 계속 사용자가 맡는다
