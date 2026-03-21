# tunadish 보류 배경 및 제품 방향 메모

> 상태: 보류  
> 작성일: 2026-03-20  
> 목적: tunadish 재개 전 참고용 정리

## 현재 판단

tunadish는 장기적으로 `tunapi` 전용 클라이언트로 가는 방향이 맞다. 다만 현재는 **같은 서버에서 tunapi를 실행하는 문제**가 남아 있어 구현을 보류한다.

이 문서는 보류 이유, 현재 `tunapi`의 준비 상태, 그리고 재개 시 우선순위를 정리한다.

## 왜 지금 보류하는가

현재 핵심 리스크는 UI나 transport 자체보다도 다음에 있다.

- tunadish 클라이언트가 같은 서버의 `tunapi` 실행 환경을 얼마나 안정적으로 제어할 수 있는지 불명확하다.
- 로컬/원격 실행, 세션 재개, 장기 연결, 프로세스 생명주기, 파일/브랜치 컨텍스트가 한 번에 얽힌다.
- 이 문제를 정리하지 않은 상태에서 클라이언트를 먼저 만들면, UI는 생겨도 실제 사용 흐름이 불안정해질 가능성이 높다.

즉 현재 보류는 제품 방향의 문제가 아니라 **실행 기반 안정성** 문제다.

## 현재 tunapi가 이미 갖고 있는 것

### 1. 프로젝트/브랜치 실행 기반

`tunapi`는 이미 프로젝트와 브랜치 컨텍스트를 해석하고, 필요시 git worktree에서 실행할 수 있다.

- `RunContext(project, branch)` 기반 컨텍스트 해석
- 프로젝트별 기본 엔진 선택
- 브랜치별 worktree 생성/재사용
- reply / directive / ambient context / default project 순서의 컨텍스트 해석

관련 코드:

- `src/tunapi/context.py`
- `src/tunapi/transport_runtime.py`
- `src/tunapi/worktrees.py`

### 2. 세션 유지와 handoff

대화 지속성의 기본기도 이미 있다.

- engine별 resume token 저장
- channel/thread 단위 세션 재개
- journal 기반 handoff preamble 생성
- cwd 변경 시 stale session 제거

관련 코드:

- `src/tunapi/core/chat_sessions.py`
- `src/tunapi/journal.py`

### 3. 토론 기능의 코어

roundtable은 더 이상 Mattermost 전용 핵심 로직이 아니다. 현재 순차 멀티에이전트 실행의 중심은 공통 코어로 올라와 있다.

지원되는 수준:

- 여러 엔진 순차 실행
- transcript 축적
- follow-up round
- 완료 세션 persistence

관련 코드:

- `src/tunapi/core/roundtable.py`

## 현재 tunapi에 없는 것

현재 부족한 것은 “실행”이 아니라 “프로젝트 중심 협업 메모리”다.

아직 없는 개념:

- 프로젝트 main 컨텍스트
- 대화 브랜치의 생성 / merge / abandon 수명주기
- 토론 결과의 resolution / action items / merge summary
- 리뷰 artifact
- 아이디어 backlog
- 프로젝트별 결정 로그

즉 현재 `tunapi`는 이미 **프로젝트/브랜치 실행 엔진**으로는 의미가 있지만, 아직 **프로젝트 협업 시스템**은 아니다.

## tunadish의 최종 목표

tunadish는 범용 챗앱이 아니라 **tunapi 전용 클라이언트**를 목표로 한다.

특히 다음이 중요하다.

- 프로젝트를 채팅 공간의 1급 개념으로 다룰 것
- 브랜치를 UI에서 자연스럽게 만들고 전환할 수 있을 것
- 토론 모드와 단일 에이전트 모드를 같은 흐름에서 사용할 수 있을 것
- merge / abandon / review / idea 기록이 프로젝트 문맥에 귀속될 것
- 최종적으로 tunapi의 주요 기능을 UI에서 100% 가깝게 쉽게 쓸 수 있을 것

## 지금 시점의 실질적 권장 방향

### 1. tunapi를 먼저 제품 서버처럼 다듬는다

tunadish를 바로 밀기보다, `tunapi` 쪽에 아래 계층을 먼저 추가하는 편이 맞다.

- `ProjectMemory`
- `BranchSession`
- `DiscussionRecord`
- `ReviewArtifact`

원칙:

- 기존 session/journal을 대체하지 말고 옆에 추가한다.
- 현재 transport 동작에 부작용이 없게 유지한다.
- tunadish가 읽기 쉬운 구조의 저장 모델을 먼저 만든다.

### 2. 브랜치 개념을 “Git branch”와 “대화 branch”로 분리해서 본다

현재 `tunapi`는 Git worktree 관점의 branch 실행은 잘한다.  
하지만 tunadish가 원하는 것은 여기에 더해 **대화 branch**도 필요하다.

정리하면:

- Git branch: 실제 코드 실행 위치
- Conversation branch: main 대화에서 파생된 논의/실험/리뷰 단위

둘은 연결될 수 있지만 같은 개념은 아니다.

### 3. 회의 기능은 새로 만들지 말고 상향한다

현재 roundtable 코어는 재사용 가치가 높다.  
새로 필요한 것은 transcript 자체보다 다음이다.

- summary
- resolution
- open questions
- action items
- merge-ready note

즉 “토론 실행기”에서 “토론 기록물 생성기”로 한 단계 올리는 작업이 필요하다.

## 재개 전 체크리스트

tunadish를 다시 밀기 전에 최소한 아래를 확인한다.

1. 같은 서버에서 tunapi 실행/제어 흐름 정리
2. 장기 연결과 세션 재개 방식 확정
3. 프로젝트 메모리 저장 모델 설계
4. branch merge / abandon의 서버측 상태 모델 설계
5. tunadish transport가 읽어야 할 최소 API surface 정리

## tunapi 측 우선 작업 제안

### P0

- 프로젝트 메모리 파일 구조 설계
- branch session 상태 모델 추가
- discussion archive 모델 추가

### P1

- review / idea artifact 저장
- merge / abandon 흐름 정의
- tunadish transport용 읽기 API/facade 설계

### P2

- tunadish UI에서 필요한 capability 목록 정리
- branch timeline / discussion timeline / review timeline 대응

## 의사결정 메모

현재 결론은 다음과 같다.

- tunadish 방향은 유지한다.
- 다만 지금은 구현보다 기반 정리가 우선이다.
- 당장 더 중요한 것은 `tunapi`를 프로젝트 중심 상태 모델까지 확장하는 일이다.
- 같은 서버 실행 이슈가 정리되기 전에는 tunadish를 본격 추진하지 않는다.
