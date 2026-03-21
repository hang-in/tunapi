# tunaDish 재개용 Multi-transport 실행 계획

> 상태: 승인된 실행 계획
> 작성일: 2026-03-21
> 목적: tunaDish 재개를 막는 `tunapi` 측 선행 작업을 가장 낮은 리스크 순서로 수행한다.

## 결정 요약

라운드테이블 결과, 우선순위는 아래로 확정한다.

1. `ProjectContextDTO`와 `HandoffURI` 인터페이스를 먼저 확장한다.
2. 바로 이어서 멀티 transport 동시 실행을 구현한다.
3. 마지막으로 멀티 transport 경로만 보호하는 테스트를 추가한다.

이 순서를 택한 이유는 명확하다.

- Step 1은 변경 범위가 작고 기존 동작을 거의 건드리지 않는다.
- Step 2는 tunaDish MVP의 직접 blocker다.
- Step 3은 Step 2의 회귀를 방지하는 목적이어야 가치가 크다.

## 현재 구현 기준 확인 포인트

아래는 2026-03-21 시점 저장소 기준 확인된 현재 구조다.

- `ProjectContextDTO`는 현재 협업 상태 스냅샷만 담고 있다: `src/tunapi/core/memory_facade.py`
- `HandoffURI`는 현재 `project`, `session`, `branch`, `focus`, `run`만 직렬화한다: `src/tunapi/core/handoff.py`
- CLI 실행 경로는 단일 transport를 전제로 `settings.transport` 하나만 해석한다: `src/tunapi/cli/run.py`
- 설정 모델은 `transport: str` 단일 선택을 기본 경로로 가진다: `src/tunapi/settings.py`
- `TransportBackend.build_and_run()`는 동기 시그니처다: `src/tunapi/transports.py`

## 목표

### 1. tunaDish 연동 인터페이스 조기 확정

tunaDish가 기다리지 않고 연동 개발을 시작할 수 있어야 한다.

### 2. tunapi에서 복수 transport 동시 실행

예: Mattermost + Slack, 혹은 Telegram + Mattermost를 한 프로세스에서 함께 실행할 수 있어야 한다.

### 3. 새 동작을 보호하는 최소 테스트 확보

기존 전체 커버리지 숫자보다, 멀티 transport 설정/실행/종료 경로를 직접 검증하는 테스트가 우선이다.

## 범위 밖

지금 계획에 포함하지 않는다.

- Discord transport 탐색/구현
- `!memory`, `!branch`, `!context` 명령 구현
- 전체 테스트 커버리지 85% 달성 작업
- tunaDish UI 구현

## 실행 순서

## Step 1. 인터페이스 확정

### 작업

- `ProjectContextDTO`에 아래 필드 추가
  - `project_alias: str | None = None`
  - `project_path: str | None = None`
  - `default_engine: str | None = None`
- `ProjectMemoryFacade.get_project_context_dto(...)`가 위 필드를 채우도록 확장
- `HandoffURI`에 아래 필드 추가
  - `engine: str | None = None`
  - `conversation_id: str | None = None`
- `build_handoff_uri(...)`와 `parse_handoff_uri(...)`가 새 query param을 직렬화/역직렬화하도록 확장
  - `engine`
  - `conv_id`
- 관련 단위 테스트 추가 또는 갱신

### 기대 효과

- tunaDish가 프로젝트 식별자, 로컬 경로, 기본 엔진을 바로 소비할 수 있다.
- deep link로 재진입 시 엔진과 대화 분기 컨텍스트를 더 정확히 복구할 수 있다.

### 완료 기준

- 기존 필드는 하위호환으로 유지된다.
- 새 필드는 모두 optional이다.
- handoff URI 파싱/직렬화 round-trip 테스트가 추가된다.

## Step 2. 멀티 transport 동시 실행

### 핵심 설계 원칙

- 기존 단일 transport 사용자는 깨지지 않아야 한다.
- 설정은 단일값과 복수값을 모두 받아야 한다.
- 실행 실패는 transport 단위로 분리하되, 시작 단계에서 잘못된 설정은 명확히 실패시킨다.
- lock은 transport별 충돌을 막되 같은 설정 파일을 공유하는 정상 조합은 허용해야 한다.

### 작업

#### 2-1. 설정 파싱

- `TunapiSettings`에서 기존 `transport`를 하위호환 용도로 유지한다.
- 복수 실행용 진입점으로 `transports_enabled` 같은 명시적 필드 또는 동등한 표현을 도입한다.
- 해석 규칙을 문서화한다.
  - 복수 설정이 있으면 그것을 우선 사용
  - 없으면 기존 `transport` 단일값을 1개 리스트로 승격
  - CLI `--transport`는 단일 override로 유지하거나, 필요시 반복 옵션으로 확장

#### 2-2. CLI 실행기 리팩토링

- `src/tunapi/cli/run.py`에서 단일 transport 선택 로직을 복수 transport 해석 로직으로 분리
- startup validation, runtime spec 생성, lock 취득, 실행, 종료를 transport 루프 또는 task group 구조로 재편
- 병렬 실행은 `anyio.create_task_group()` 기준으로 구현

#### 2-3. backend 진입점 async 분리

- `TransportBackend.build_and_run()`의 현재 동기 진입점 구조를 재검토
- 상위 task group에서 병렬 실행 가능하도록 transport별 async run 진입점을 도입
- Telegram, Mattermost, Slack backend에 동일 패턴 적용

#### 2-4. lock과 lifecycle 정리

- transport별 lock id 또는 token 전략 정리
- 한 transport shutdown이 다른 transport cleanup을 누락시키지 않도록 종료 순서 확인
- SIGINT/KeyboardInterrupt 처리에서 전체 task group이 정상 종료되는지 검증

### 핵심 리스크

- 가장 큰 리스크는 backend가 자체적으로 이벤트 루프를 열고 있는 경우다.
- 이 경우 상위 CLI에서 병렬 orchestration을 하려면 async 진입점을 분리해야 한다.
- 세 backend가 같은 패턴이면 해법은 한 번 정한 뒤 반복 적용 가능하다.

### 완료 기준

- 단일 transport 기존 실행이 계속 동작한다.
- 복수 transport 설정으로 동시에 두 개 이상 실행할 수 있다.
- transport 하나가 잘못 설정되면 어떤 지점에서 실패할지 규칙이 문서와 코드에서 일치한다.

## Step 3. 멀티 transport 타겟 테스트

### 작업

- 설정 해석 테스트
  - 단일 `transport`
  - 복수 transport 설정
  - CLI override 우선순위
- 실행 orchestration 테스트
  - 복수 backend가 모두 시작되는지
  - 한 backend 종료 시 전체 종료 정책이 기대대로 동작하는지
  - lock 획득 인자가 transport별로 분리되는지
- handoff/DTO 회귀 테스트
  - Step 1 변경분이 유지되는지

### 테스트 우선순위

1. 순수 함수/설정 해석 테스트
2. CLI orchestration 단위 테스트
3. backend 진입점 smoke 테스트

### 완료 기준

- 멀티 transport 관련 신규 경로에 대한 테스트가 존재한다.
- 최소한 설정 해석과 CLI orchestration은 자동 테스트로 보호된다.

## 실제 작업 단위

작업은 아래 3개 PR 또는 동등한 작은 배치로 나누는 것을 권장한다.

### PR 1. 인터페이스 확정

- DTO 필드 추가
- HandoffURI 필드 추가
- 관련 테스트 갱신

### PR 2. 멀티 transport 인프라

- settings 해석
- CLI 병렬 orchestration
- backend async 진입점 정리
- lock/lifecycle 조정

### PR 3. 멀티 transport 테스트

- 설정 해석 테스트
- orchestration 테스트
- 회귀 테스트

## 검증 순서

각 단계마다 아래 순서로 검증한다.

1. 관련 단위 테스트 실행
2. 전체 테스트 또는 최소 회귀 세트 실행
3. 필요 시 실제 단일 transport smoke run
4. Step 2 완료 후 복수 transport smoke run

예시 명령:

```sh
uv run pytest tests -q
```

프로젝트에 표준 검증 명령이 있다면 그것을 우선 사용한다.

## 에이전트 운영 규칙

- 한 번에 한 Step만 끝낸다.
- Step 경계에서 테스트 결과와 남은 리스크를 기록한다.
- Step 2는 특히 "설정", "실행", "종료", "lock" 네 축으로 나눠 검증한다.
- 새 추상화는 최소화하고 기존 패턴을 우선 재사용한다.

## 최종 완료 정의

아래를 모두 만족하면 이 계획은 완료다.

- tunaDish가 필요한 DTO/Handoff 인터페이스를 사용할 수 있다.
- tunapi가 복수 transport를 한 프로세스에서 동시 실행할 수 있다.
- 해당 경로를 보호하는 자동 테스트가 존재한다.
- 기존 단일 transport 사용 흐름이 하위호환으로 유지된다.
