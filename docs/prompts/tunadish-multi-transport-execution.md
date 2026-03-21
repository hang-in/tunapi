# tunapi Multi-transport 작업 시작 프롬프트

> 대상: 코드 수정 권한이 있는 AI 코딩 에이전트
> 저장소: `~/privateProject/tunapi`
> 기준 계획서: `docs/plans/tunadish-multi-transport-execution-plan.md`
> 목적: tunaDish 재개를 막는 `tunapi` 측 blocker를 계획서 순서대로 제거한다.

아래 지시만 따르고, 계획서의 순서를 바꾸지 마라.

## 시작 지시

너는 지금부터 `tunapi` 저장소에서 multi-transport 작업을 수행하는 구현 에이전트다.

반드시 아래 순서로만 진행하라.

1. Step 1: DTO/Handoff 인터페이스 확정
2. Step 2: 멀티 transport 동시 실행 구현
3. Step 3: 멀티 transport 타겟 테스트 보강

중요 제약:

- Step 1이 끝나기 전에는 Step 2로 넘어가지 마라.
- Step 2가 끝나기 전에는 Step 3으로 넘어가지 마라.
- 기존 단일 transport 동작을 깨지 않는 하위호환을 최우선으로 둬라.
- 계획서 범위 밖 작업은 하지 마라.
- 새 추상화는 최소화하고 기존 패턴을 우선 재사용하라.
- 변경 전에는 관련 구현과 테스트를 먼저 읽고, 변경 후에는 해당 Step 범위 테스트를 반드시 실행하라.

## 이번 작업의 범위

포함:

1. `ProjectContextDTO` 필드 확장
2. `HandoffURI` 파라미터 확장
3. 멀티 transport 동시 실행 인프라
4. 위 변경분을 보호하는 테스트

제외:

- Discord transport 탐색/구현
- `!memory`, `!branch`, `!context` 명령 구현
- 무관한 리팩토링
- 전체 커버리지 숫자만 올리기 위한 테스트 작업
- tunaDish UI 작업

## 작업 방식

각 Step에서 아래 순서를 지켜라.

1. 관련 파일과 테스트를 읽는다.
2. 현재 구조와 병목을 짧게 요약한다.
3. 해당 Step 범위만 구현한다.
4. 관련 테스트를 실행한다.
5. Step 결과를 짧게 보고한다.

Step 보고는 반드시 아래 형식을 따른다.

### Step 보고 형식

```text
[Step N 완료]
- 변경 파일:
- 핵심 변경:
- 하위호환 영향:
- 실행 테스트:
- 남은 리스크:
```

## Step 1. 인터페이스 확정

먼저 아래를 읽어라.

- `src/tunapi/core/memory_facade.py`
- `src/tunapi/core/handoff.py`
- 관련 테스트 파일

그 다음 아래를 구현하라.

1. `ProjectContextDTO`에 optional 필드를 추가한다.
   - `project_alias`
   - `project_path`
   - `default_engine`
2. DTO 생성 경로가 새 필드를 실제 값으로 채우게 만든다.
3. `HandoffURI`에 optional 필드를 추가한다.
   - `engine`
   - `conversation_id`
4. `build_handoff_uri(...)`와 `parse_handoff_uri(...)`가 아래 query param을 처리하게 만든다.
   - `engine`
   - `conv_id`
5. 관련 테스트를 추가하거나 갱신한다.

Step 1 완료 기준:

- 기존 필드는 그대로 유지된다.
- 새 필드는 모두 optional이다.
- handoff 직렬화/역직렬화 round-trip 테스트가 존재한다.

## Step 2. 멀티 transport 동시 실행

Step 1 테스트 통과 후에만 진행하라.

먼저 아래를 읽어라.

- `src/tunapi/settings.py`
- `src/tunapi/cli/run.py`
- `src/tunapi/transports.py`
- `src/tunapi/telegram/backend.py`
- `src/tunapi/mattermost/backend.py`
- `src/tunapi/slack/backend.py`
- 관련 실행/설정 테스트 파일

그 다음 아래 순서로 구현하라.

1. 설정 해석 규칙을 정리한다.
   - 기존 `transport` 단일값은 유지
   - 복수 transport 실행용 표현을 추가
   - 기존 사용자 설정은 그대로 동작
2. CLI 실행 경로를 복수 transport 대응 구조로 리팩토링한다.
   - validation
   - runtime spec 생성
   - lock 취득
   - 실행
   - 종료
3. transport backend 진입점을 상위 orchestration에서 병렬 실행 가능하게 정리한다.
4. `anyio.create_task_group()`으로 복수 transport를 동시에 실행한다.
5. lock 및 shutdown 동작이 transport별로 분리되는지 확인한다.

Step 2에서 특히 확인할 것:

- backend가 내부에서 자체 이벤트 루프를 여는지
- 상위 orchestration 기준 async 진입점 분리가 필요한지
- transport 하나의 실패가 전체 시작/종료 정책에 어떤 영향을 주는지

Step 2 완료 기준:

- 단일 transport 기존 실행이 유지된다.
- 복수 transport 설정으로 두 개 이상 동시 실행 가능하다.
- 설정/실행/종료/lock 정책이 코드와 테스트에서 일치한다.

## Step 3. 멀티 transport 타겟 테스트

Step 2 완료 후에만 진행하라.

우선순위는 아래와 같다.

1. 설정 해석 테스트
2. CLI orchestration 테스트
3. backend 진입점 smoke 테스트
4. Step 1 DTO/Handoff 회귀 테스트 보강

최소한 아래를 자동 테스트로 보호하라.

- 단일 `transport` 설정
- 복수 transport 설정
- CLI override 우선순위
- 복수 backend 시작 여부
- lock 인자 분리 여부
- DTO/Handoff round-trip

## 검증 원칙

각 Step 종료 시 관련 테스트를 실행하라.

가능하면 마지막에 전체 회귀 테스트 또는 최소 회귀 세트를 실행하라.

예시:

```sh
uv run pytest tests -q
```

프로젝트에 더 적절한 표준 검증 명령이 있으면 그것을 우선 사용하라.

## 최종 응답 형식

최종 응답은 아래 3가지만 포함해라.

1. 변경한 것
2. 검증한 것
3. 남은 리스크 또는 후속 과제

그리고 아래 문장을 마지막에 포함해라.

```text
범위를 벗어난 작업은 수행하지 않았다.
```

## 바로 시작할 첫 행동

지금 즉시 Step 1부터 시작하라.

첫 응답에서는 아래를 짧게 보고한 뒤 바로 파일을 읽고 구현에 들어가라.

```text
- Step 1부터 시작한다.
- 먼저 `memory_facade.py`, `handoff.py`, 관련 테스트를 읽고 인터페이스 변경 지점을 확인한다.
```
