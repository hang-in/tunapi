# Roundtable 고도화 메모

> 목적: 현재 `tunapi` roundtable의 한계를 정리하고, `tunaDish` 고도화 과정에서 더 강한 RT를 만들기 위한 방향을 남긴다.

## 현재 상태 요약

현재 roundtable은 아래에 가깝다.

- 여러 엔진을 순차 실행
- 이전 응답을 다음 엔진 프롬프트에 주입
- 여러 라운드 반복 가능
- 완료 후 follow-up 가능
- Slack/Mattermost에서 `!rt`로 실행

즉 지금 RT는 "다중 엔진 의견 수집기"로는 충분하다.

하지만 아직 아래는 약하다.

- 페르소나를 엔진과 별개로 다루지 못함
- 참여자별 역할 지시를 구조적으로 저장하지 못함
- moderator / synthesizer / critic 같은 역할을 명시적으로 운영하지 못함
- discussion summary / resolution / open questions를 실행 중에 관리하지 못함
- 사용자 승인 지점이 UI 레벨에서 잘 드러나지 않음

## 현재 구조의 실제 한계

현재 RT가 강하지 않은 이유는 구조가 단순하기 때문이다.

- participant = engine id
- session state = topic + engines + transcript + rounds
- prompt context = transcript 단순 누적

즉 아래가 없다.

- participant role
- participant-specific instruction
- stage-based agenda
- moderator state
- conflict tracking
- synthesis step
- user approval checkpoint

따라서 "5개 페르소나 토론"을 하려면 지금은 세션을 쪼개서 수동 운영하는 편이 더 안전하다.

## 지금 당장 권장하는 운영 방식

`tunapi` 현재 구조에서는 아래 방식이 맞다.

### 1. 분할 토론

한 번에 5명을 넣지 말고 두 세션으로 나눈다.

- 세션 A
  - architect
  - product
  - transport pragmatist
- 세션 B
  - workflow critic
  - operator
  - synthesizer

### 2. 사용자 수동 개입

현재는 사용자가 아래를 해줘야 한다.

- 라운드 종료 후 중간 정리
- 다음 세션에 넘길 핵심 쟁점 선정
- 최종 합의안 채택

이건 지금 구조에선 약점이 아니라, 오히려 안전장치에 가깝다.

## `tunaDish`에서 목표로 할 강한 RT

`tunaDish` 고도화 과정에서는 RT를 단순 명령이 아니라 "회의 워크스페이스"로 올리는 것이 맞다.

### 목표 1. 엔진과 페르소나 분리

현재:

- 엔진 = 참여자

미래:

- 엔진 = 실행 수단
- 페르소나 = 역할

예:

- `claude`가 architect 역할
- `gemini`가 critic 역할
- `codex`가 implementer 역할
- 같은 엔진이라도 역할만 다르게 여러 participant로 배치 가능

즉 participant는 아래 형태가 되어야 한다.

- `participant_id`
- `engine`
- `role`
- `system_prompt`
- `priority`
- `enabled`

### 목표 2. stage-based discussion

회의를 한 덩어리로 돌리지 말고 단계로 나눠야 한다.

권장 단계:

1. framing
2. proposal
3. critique
4. synthesis
5. decision

각 단계마다:

- 발언 가능한 participant
- 입력 컨텍스트
- 출력 기대 형식

이 달라져야 한다.

### 목표 3. moderator 개념 추가

강한 RT에는 moderator가 필요하다.

역할:

- 주제 재정의
- 쟁점 정리
- 중복 발언 압축
- 다음 라운드 질문 생성
- 합의점 / 비합의점 분리

처음엔 자동 moderator가 아니라, 사용자 + assistant 혼합 moderator로 시작하는 게 맞다.

### 목표 4. synthesis artifact 생성

회의의 가치가 transcript에만 있으면 약하다.

최소 산출물:

- summary
- agreements
- disagreements
- open questions
- action items
- recommended next step

이 결과는 `discussion_records`나 project memory와 연결되어야 한다.

### 목표 5. user gate 명시화

완전 자율 회의보다 사용자 승인 지점을 드러내는 게 중요하다.

예:

- "이 쟁점으로 계속 진행"
- "이 participant 제거"
- "이 의견을 action item으로 채택"
- "이 discussion을 branch 작업으로 trigger"

이건 `tunaDish`에서 버튼/패널 UX로 표현하기 좋다.

## 권장 상태 모델

강한 RT를 위해선 상태 모델이 더 필요하다.

### DiscussionSession

- discussion_id
- project
- branch_name
- title
- status
- current_stage
- created_by
- created_at

### DiscussionParticipant

- participant_id
- engine
- role
- instruction
- state
- order

### DiscussionTurn

- turn_id
- stage
- participant_id
- input_summary
- output_text
- created_at

### DiscussionSynthesis

- summary
- agreements
- disagreements
- open_questions
- action_items
- decision

## `control` / `trigger`와의 연결

강한 RT는 결국 orchestration primitive와 연결된다.

### control

회의 기록, 상태 업데이트, handoff note

예:

- "architect와 critic이 DB 스키마에서 충돌"
- "user가 option B 선호"

### trigger

회의 결과를 실제 작업으로 넘김

예:

- branch 생성 후 구현 시작
- 특정 participant에게 follow-up run 요청
- review branch 생성

## 단계별 구현 제안

### 1단계: 현재 RT 유지 + artifact 강화

- `discussion_records`와 연결 강화
- summary / resolution / action items 정리 흐름 보강
- follow-up 저장 구조 정리

### 2단계: participant role 도입

- engine id만이 아니라 role metadata 저장
- 프롬프트 수준에서 역할 지시 주입

### 3단계: staged discussion 도입

- proposal / critique / synthesis 구간 분리
- moderator prompt 추가

### 4단계: `tunaDish` UI 통합

- participant panel
- stage indicator
- agreements / disagreements panel
- user approval actions

### 5단계: control / trigger 연결

- discussion 결과를 branch 작업이나 review 흐름으로 직접 연결

## 하지 말아야 할 것

- 현재 RT에 한 번에 모든 기능을 억지로 넣기
- transport별 UI 차이를 core에 밀어넣기
- 완전 자율 토론을 먼저 구현하기
- discussion / branch / review를 한 개념으로 뭉개기

## 결론

지금 `tunapi`의 RT는 약한 것이 아니라, 범위를 잘 지키는 상태다.

따라서 현재는:

- 분할 토론
- 사용자 수동 개입
- 결과 기록 강화

로 운영하고,

장기적으로는 `tunaDish`에서:

- participant role
- staged discussion
- moderator
- synthesis artifact
- user gate

를 얹어서 "강한 RT"로 발전시키는 것이 맞다.
