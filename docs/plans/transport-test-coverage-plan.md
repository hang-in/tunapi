# Transport 레벨 테스트 커버리지 강화 계획

> 상태: 계획
> 작성일: 2026-03-20
> 목표: 전체 커버리지 72% → 85%
> 현재 테스트: 987개

## 현재 상태

전체 커버리지: **71.74%** (15251 stmts, 3670 miss, 4658 branches, 787 partial)

### 커버리지가 낮은 모듈 (50% 미만)

| 모듈 | 현재 | Stmts | Miss | 주요 미커버 영역 |
|------|------|-------|------|-----------------|
| `slack/commands.py` | 6% | 266 | 242 | handle_model, handle_models, handle_trigger, handle_project, handle_persona, handle_rt, handle_cancel 전부 |
| `slack/render.py` | 12% | 62 | 52 | prepare_slack, markdown_to_mrkdwn, split 전부 |
| `slack/loop.py` | 14% | 377 | 310 | 전체 dispatch 흐름 |
| `slack/client_api.py` | 17% | 154 | 122 | HTTP/WebSocket 클라이언트 |
| `mattermost/loop.py` | 19% | 376 | 292 | 전체 dispatch 흐름 |
| `slack/files.py` | 23% | 36 | 26 | Slack 파일 다운로드 |
| `mattermost/trigger_mode.py` | 24% | 23 | 15 | should_trigger, strip_mention |
| `mattermost/commands.py` | 27% | 269 | 185 | 대부분의 핸들러 |
| `mattermost/files.py` | 32% | 22 | 13 | MM 파일 다운로드 |
| `slack/trigger_mode.py` | 37% | 15 | 8 | should_trigger, strip_mention |
| `telegram/builtin_commands.py` | 39% | 55 | 31 | dispatch_builtin_command |
| `slack/client.py` | 46% | 72 | 38 | outbox 큐 |
| `mattermost/client.py` | 52% | 67 | 32 | outbox 큐 |

### 커버리지가 이미 높은 모듈 (80%+)

Telegram 대부분, core 전체, runners 전체, parsing, api_models 등

## 85% 달성 전략

### 절대로 하지 말 것

- 실제 Mattermost/Slack/Telegram API 호출
- WebSocket/Socket Mode 실 연결
- transport 구조 리팩토링
- 기존 동작 변경
- 의미 없는 `assert True` 테스트

### 우선순위별 작업

#### Tier 1: 가장 효과적 (각 모듈이 크고 커버리지가 매우 낮음)

**1. `slack/commands.py` (6% → 80%+)**
- 266 stmts, 242 miss → 약 200줄 커버 가능
- handle_model, handle_models는 MM에서 이미 테스트됨 → 동일 패턴으로 Slack 테스트 작성
- handle_trigger, handle_project, handle_persona, handle_rt, handle_cancel
- 기존 `tests/test_slack_commands.py`에 추가

**2. `mattermost/commands.py` (27% → 80%+)**
- 269 stmts, 185 miss
- handle_help, handle_trigger, handle_status, handle_project, handle_persona, handle_rt, handle_cancel
- `tests/test_mattermost_commands.py` 신규 생성 (또는 기존에 있으면 확장)

**3. `slack/render.py` (12% → 80%+)** + `mattermost/render.py` (90% 이미)
- prepare_slack, markdown_to_mrkdwn, split_mrkdwn_body
- 순수 함수 → 단위 테스트 쉬움

**4. `mattermost/trigger_mode.py` (24% → 90%+)** + `slack/trigger_mode.py` (37% → 90%+)
- should_trigger, strip_mention
- 순수 함수 → 단위 테스트 가장 쉬움

#### Tier 2: 중간 효과

**5. `telegram/builtin_commands.py` (39% → 80%+)**
- dispatch_builtin_command 각 branch 테스트
- FakeContext 패턴으로 가능

**6. `telegram/message_context.py` (0% → 80%+)**
- 48 stmts, 전부 miss

**7. `telegram/update_routing.py` (0% → 80%+)**
- 67 stmts, 전부 miss

#### Tier 3: 낮은 효과 (mock 비용 높음)

**8. `slack/loop.py` (14%)**, **`mattermost/loop.py` (19%)**
- 전체 dispatch 흐름은 mock 비용이 매우 높음
- `_archive_roundtable`은 이미 테스트됨 (16개)
- 나머지는 integration-level mock이 필요 → 비용 대비 효과 낮음

**9. `*/client.py`, `*/client_api.py`**
- HTTP/WebSocket mock 필요 → 단위 테스트보다 integration test 영역
- 기존 `test_mattermost_client_api.py` 패턴 참조 가능

## 예상 커버리지 변화

| 작업 | 예상 신규 stmt 커버 | 누적 커버리지 |
|------|---------------------|--------------|
| 현재 | - | 72% |
| Tier 1-1: slack/commands | +200 | 73.3% |
| Tier 1-2: mattermost/commands | +150 | 74.3% |
| Tier 1-3: slack/render | +50 | 74.6% |
| Tier 1-4: trigger_mode (양쪽) | +23 | 74.8% |
| Tier 2-5~7: telegram 3개 | +130 | 75.6% |
| **Tier 1+2 합계** | ~553 | ~76% |

**76%까지는 Tier 1+2로 도달 가능. 85%는 Tier 3(loop, client) 포함 필요.**

## 테스트 파일 구성

```
tests/
├── test_slack_commands.py          ← 기존 확장 (help/dispatcher consistency + 핸들러 테스트)
├── test_mattermost_commands.py     ← 신규 (핸들러 단위 테스트)
├── test_slack_render.py            ← 신규 (prepare_slack, markdown_to_mrkdwn)
├── test_trigger_mode.py            ← 신규 (MM/Slack should_trigger, strip_mention)
├── test_telegram_builtin_cmds.py   ← 신규 (dispatch_builtin_command)
├── test_telegram_message_ctx.py    ← 신규 (message_context.py)
├── test_telegram_update_routing.py ← 신규 (update_routing.py)
└── (Tier 3은 별도 세션)
```

## 실행 순서

### Phase 1: Tier 1 (순수 함수 + 핸들러)
1. `test_trigger_mode.py` — should_trigger / strip_mention (MM/Slack 양쪽)
2. `test_slack_render.py` — prepare_slack, markdown_to_mrkdwn
3. `test_slack_commands.py` 확장 — 핸들러별 단위 테스트
4. `test_mattermost_commands.py` — 핸들러별 단위 테스트

### Phase 2: Tier 2 (Telegram 0% 모듈)
5. `test_telegram_builtin_cmds.py`
6. `test_telegram_message_ctx.py`
7. `test_telegram_update_routing.py`

### Phase 3: Tier 3 (integration mock)
8. slack/mattermost loop dispatch 통합
9. client/client_api mock 테스트

## 제약

- 각 Phase 후 `uv run pytest --no-cov` 전체 통과 확인
- 기존 테스트 수정 금지 (추가만)
- transport 코드 리팩토링 금지 (테스트만 추가)
- Phase 완료마다 커밋

## 완료 기준

- [ ] Phase 1 완료: 75%+
- [ ] Phase 2 완료: 76%+
- [ ] Phase 3 완료: 85%+
- [ ] `pyproject.toml` threshold 85%로 상향
