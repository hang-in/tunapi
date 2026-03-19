# Roundtable

Roundtable(`!rt`)은 여러 에이전트에게 동일한 주제를 순차적으로 물어보고 의견을 수집하는 기능입니다.
에이전트들은 같은 라운드 안에서도 앞선 에이전트의 답변을 참고하며, 다중 라운드를 통해 점진적으로 논의를 심화할 수 있습니다.

## 새 라운드테이블 시작

```
!rt "Python vs Go for CLI tools"
!rt "이 아키텍처의 병목 지점은?" --rounds 2
```

- `!rt` 또는 `/rt` 모두 사용 가능
- `--rounds N`: 라운드 수 지정 (기본값은 설정 파일에서 결정)
- 따옴표 없이 `!rt 이것도 주제가 됩니다` 형태도 가능

## 에이전트 간 참조

같은 라운드 안에서도 순차적으로 실행되므로, 두 번째 에이전트는 첫 번째 에이전트의 답변을 참고합니다.

```
Round 1:
  claude  → 주제만 받고 답변
  gemini  → 주제 + claude 답변을 보고 답변

Round 2:
  claude  → Round 1 전체 + 주제로 재답변
  gemini  → Round 1 전체 + Round 2 claude 답변 + 주제로 재답변
```

## 후속 토론 (`!rt follow`)

라운드테이블이 완료된 스레드에서 후속 질문을 할 수 있습니다.
기존 토론 내용(transcript)이 컨텍스트로 유지됩니다.

### 전체 에이전트에게

```
!rt follow "보안 관점에서 다시 검토해줘"
```

### 특정 에이전트만 지정

에이전트 이름을 질문 앞에 적습니다:

```
!rt follow claude "좀 더 구체적으로 설명해줘"
!rt follow gemini,claude "둘이 비교해봐"
```

- 첫 단어가 알려진 엔진 이름(쉼표 구분)이면 에이전트 필터로 인식
- 아니면 전체가 질문으로 처리

### 예시 시나리오

```
사용자: !rt "마이크로서비스 vs 모놀리스" --rounds 2
  ↓ claude, gemini, codex가 2라운드 토론
  ↓ 🏁 Roundtable 완료

사용자: !rt follow "비용 측면에서 다시 비교해줘"
  ↓ 전체 에이전트가 기존 토론 + 새 질문으로 1라운드

사용자: !rt follow claude "아까 언급한 장애 전파 문제 구체적으로"
  ↓ claude만 답변
```

## 완료된 세션 유효 시간

후속 토론은 라운드테이블 완료 후 **1시간** 동안 가능합니다.
1시간이 지나면 세션이 자동 정리되며, 새 `!rt` 명령으로 다시 시작해야 합니다.

## 취소

진행 중인 라운드테이블은 `!cancel`로 취소할 수 있습니다.

## 설정

```toml
[roundtable]
engines = ["claude", "gemini"]   # 비워두면 사용 가능한 모든 엔진
rounds = 1                        # 기본 라운드 수
max_rounds = 3                    # 최대 허용 라운드 수
```

## 관련 문서

- [Switch engines](switch-engines.md)
- [Chat sessions](chat-sessions.md)
