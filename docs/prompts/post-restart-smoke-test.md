# 서비스 재시작 후 이어서 할 일

> 이전 세션에서 멀티 transport smoke test를 위해 서비스를 재시작했다.
> 아래 순서대로 확인하고 진행하라.

## 1. 멀티 transport smoke test 결과 확인

서비스 재시작 전에 `tunapi.toml`에 `transports_enabled = ["mattermost", "slack"]`을 추가했다.

확인할 것:
```bash
# 두 서비스가 모두 실행 중인지
ps aux | grep tunapi | grep -v grep

# 로그에 multi_transport.starting 또는 에러가 있는지
journalctl --user -u tunapi.service --since "5 min ago" --no-pager | tail -30

# Mattermost 채널에서 메시지 응답이 오는지
# Slack 채널에서 메시지 응답이 오는지
```

### 성공 기준
- 두 transport가 동시에 실행되고 있다
- 각각의 채널에서 에이전트가 응답한다
- 에러 로그가 없다

### 실패 시
- `transports_enabled`를 제거하고 기존 단일 transport로 복구
- 로그에서 에러 원인 확인
- 필요하면 코드 수정

## 2. 성공하면 다음 작업

### 2-1. transport 테스트 커버리지 Phase 1
- `docs/plans/transport-test-coverage-plan.md` 참고
- trigger_mode, render, commands 테스트 추가
- 72% → 75% 목표

### 2-2. !memory/!branch 커맨드 구현
- `docs/plans/memory-branch-commands-plan.md` 참고
- !context → !memory → !branch → !review 순서

### 2-3. tunaDish 피드백 반영
- 외부 세션에서 받은 추가 요청 확인

## 3. 실패하면 복구 방법

```bash
# tunapi.toml에서 transports_enabled 줄 삭제
# 서비스 재시작
systemctl --user restart tunapi.service
systemctl --user restart tunapi-slack.service
```
