# tunadish — Claude Code 브리핑 문서

> 목적: 레포 초기 세팅 및 구현 플랜 수립  
> 작성일: 2026-03-20  
> 이 문서는 설계 논의 결과와 PRD를 통합한 Claude Code 전달용 문서다.

---

## 1. 프로젝트 배경 및 맥락

### tunapi란
- Mattermost/Slack/Telegram ↔ AI CLI(claude, gemini, codex) 브릿지 프로젝트
- Python 기반, 현재 Slack 트랜스포트 개발 중
- CLI를 채팅앱에서 제어하는 구조

### tunadish 탄생 배경
- AI 에이전트와만 채팅하는데 Mattermost 같은 범용 채팅앱 백엔드가 과함
- 새 트랜스포트를 기존 채팅앱에 추가하는 것도 번거로움
- 결론: AI 채팅 전용 경량 클라이언트를 직접 만들자

### tunapi와의 관계
- tunadish는 tunapi의 **transport 플러그인**으로 동작
- tunapi 코드 수정 없이 Python entry_point 등록만으로 연결
- tunapi의 Transport/Presenter 추상화 인터페이스를 구현하면 됨
- **별도 레포**로 관리 (기술스택이 다르고 릴리즈 사이클도 독립적)

### tunapi transport 플러그인 등록 방식 (참고)
```toml
# pyproject.toml
[project.entry-points."tunapi.transport_backends"]
tunadish = "tunadish_transport:TunadishBackend"
```
- `Transport` 인터페이스: `send()`, `edit()`, `delete()`, `close()`
- `Presenter` 인터페이스: `render_progress()`, `render_final()`
- `TransportBackend` 인터페이스: `check_setup()`, `build_and_run()`, `lock_token()`
- tunapi 메시지 파이프라인: CLI stdout(JSONL) → TunapiEvent → ProgressState → RenderedMessage → Transport.send()

### 미래 방향
- tunapi Slack 트랜스포트 완료 후 대규모 리팩토링 예정
- 공통 코어는 `tunapi-core`로 분리될 수 있음
- tunadish는 이후 `tunapi-core` 의존성으로 교체 예정
- 지금은 tunapi를 설치된 패키지로 참조하는 것으로 충분

---

## 2. 기술 스택 (확정)

| 영역 | 기술 | 결정 이유 |
|---|---|---|
| 클라이언트 UI | React + TypeScript | Claude Code AI 코드 생성 품질 최우수, 생태계 풍부 |
| 컴포넌트 라이브러리 | shadcn/ui | Tauri + React 조합에서 가장 검증됨 |
| 상태 관리 | Zustand | 가볍고 Claude Code 친화적 |
| 데스크탑/모바일 | Tauri | Electron 사용 금지 |
| 백엔드 (transport) | Python | tunapi와 동일 언어, 코드 참조 용이 |
| 프로토콜 | WebSocket + JSON-RPC 2.0 | 실시간 양방향, 요청/응답+이벤트 혼합 구조 |

- **Electron 절대 사용 금지**
- 모바일: Android만 (iOS 제외)

---

## 3. 레포 구조 (확정)

모노레포 — 클라이언트 + Python transport 같은 레포:

```
tunadish/
  ├─ client/                # Tauri + React 클라이언트
  │   ├─ src/
  │   ├─ src-tauri/
  │   └─ package.json
  ├─ transport/             # Python tunapi 플러그인
  │   ├─ src/
  │   │   └─ tunadish_transport/
  │   └─ pyproject.toml
  ├─ docs/
  │   └─ prd.md
  └─ README.md
```

---

## 4. 지원 플랫폼

- Windows / macOS / Linux (데스크탑)
- Android (모바일)
- 터미널 환경(AI CLI가 돌아가는 곳)이면 어디서든 설치/설정이 쉬워야 함

---

## 5. 핵심 기능 (PRD 초안)

### 5.1 프로젝트
- 프로젝트 생성 / 관리
- 프로젝트 = 채팅 공간의 단위 (Slack 채널 개념)
- 프로젝트별 에이전트 + 페르소나 + 스킬 바인딩
- 프로젝트 컨텍스트는 서버 프로젝트 디렉토리 기준 (tunapi.toml의 path)

### 5.2 채팅
- AI 전용 채팅 (claude / gemini / codex), 인간 간 채팅 없음
- 프로젝트별 독립 채팅 공간
- 마크다운 렌더링, 코드블록 처리

### 5.3 브랜치 (서브 대화)
Git 개념을 채팅에 도입:

```
main (프로젝트 메인 컨텍스트)
  ├─ branch: "인증 방식 검토" → 결론 → merge
  ├─ branch: "DB 스키마 토론" (토론 모드) → 결론 → merge
  └─ branch: "실험적 접근" → abandon
```

- main 대화에서 브랜치 생성
- 브랜치 실행 방식 선택: **단일 에이전트** / **토론 모드**
- 종료 방식:
  - **merge**: AI 정리 텍스트 + 사용자 코멘트 → main 컨텍스트에 append
  - **abandon**: 결론 없이 닫기
- checkout: 과거 분기점으로 돌아가 재탐색 (미결)

> merge 시 "자동 요약"이 아니라 AI가 결정사항/근거 위주로 **정리**한 텍스트 + 사용자 코멘트

### 5.4 토론 모드
- 브랜치의 실행 방식 옵션 (별도 기능이 아님)
- 설정: 주제 / 참여 에이전트 / 역할 및 페르소나 / 발언 순서(턴 오더) / 라운드 수
- 진행: 턴 오더 기반 순차 실행
- **사용자 개입 포인트** (비동기 이벤트):
  - 특정 에이전트에게 질문
  - 정리 지시
  - 턴 오더 변경
  - 새 에이전트 투입
- 종료: 결론 정리 + 코멘트 → main에 merge 가능
- WebSocket이 필요한 이유이기도 함 (비동기 개입)

### 5.5 페르소나
- 프리셋 CRUD
- 에이전트와 **독립적으로** 존재 (tunapi의 1:1 고정 방식 탈피)
- 프로젝트별, 브랜치별 자유롭게 조합 가능
- 토론 모드에서 에이전트별로 다른 페르소나 할당 가능

### 5.6 스킬
- 특정 작업의 수행 방식 정의 (claude.ai Skills 개념)
- 재사용 가능한 프리셋 (예: "코드 리뷰 기준", "문서 포맷", "테스트 전략")
- 프로젝트별 등록 및 적용
- 페르소나와 레이어 구분:
  - **페르소나**: 에이전트의 성격/태도
  - **스킬**: 작업 수행 방식

### 5.7 에이전트 관리
- 에이전트 실행 / 종료 / 재시작 (tunapi를 통해)
- 프로젝트별 에이전트 할당
- 지원 엔진: claude / gemini / codex

### 5.8 입력창
- 마크다운 입력 + 프리뷰 (토글)
- 코드블록 (언어 지정, 하이라이팅)
- 파일 / 이미지 첨부
- 드래그앤드롭
- Shift+Enter 멀티라인
- 경량 에디터 수준

### 5.9 커맨드 체계 (3개 레이어)

| | `/` 커맨드 | `!` 커맨드 | 스니펫 |
|---|---|---|---|
| **용도** | 앱 UI/기능 제어 | 에이전트/세션 제어 | 사용자 정의 프롬프트 단축키 |
| **예시** | `/new` `/branch` `/settings` | `!rt` `!persona` `!project` | `!정리` `!리뷰` `!의견` |
| **결과** | 앱 동작 | 에이전트/세션 동작 | 텍스트 → 에이전트 전송 |
| **관리** | 시스템 고정 | 시스템 고정 | 사용자 CRUD |
| **기존 tunapi** | 없음 | ✅ 이미 사용 중 | 없음 |

스니펫:
- 사용자가 직접 생성/편집/삭제
- 프로젝트별 또는 전역으로 관리
- 입력창에서 트리거 입력 시 자동완성

### 5.10 컨텍스트
- 프로젝트 내 대화 히스토리 유지
- 브랜치 merge 내용이 main 컨텍스트에 축적
- 상세 구현은 tunapi 컨텍스트 고도화 참고 (진행 중)

---

## 6. UI/UX

### 디자인 레퍼런스
- **구조**: Slack / Mattermost (사이드바 + 채팅 패널)
- **대화 스타일**: Claude.ai (문서형, 마크다운, 버블 아님)
- **새로 필요한 것**: 브랜치 탭, 토론 모드 진행 UI (턴 표시, 라운드 카운터), merge/abandon 액션

### 데스크탑 레이아웃
```
┌─────────┬──────────────────────┬─────────────┐
│ 사이드바  │ 채팅 메인             │ 컨텍스트 패널 │
│         │                      │             │
│ 프로젝트  │ [브랜치 탭]           │ 현재 프로젝트 │
│  └ main │                      │ 에이전트 상태 │
│  └ 브랜치│ 대화 영역             │ 페르소나     │
│  └ 브랜치│                      │ 스킬        │
│         │                      │             │
│ 설정     │ [입력창]              │             │
└─────────┴──────────────────────┴─────────────┘
```

### 모바일 레이아웃
- 사이드바: 스와이프 or 햄버거 메뉴
- 컨텍스트 패널: 하단 시트 (올려서 보기)
- 기본 상태: 채팅 영역만 표시

### 패널 토글
- 좌측 사이드바: 토글 가능
- 우측 컨텍스트 패널: 토글 가능
- 기본 상태(데스크탑): 둘 다 열림
- 좁은 창 / 모바일: 닫아서 채팅 집중

---

## 7. tunapi 코드베이스 핵심 참고사항

tunadish transport 구현 시 알아야 할 tunapi 내부 구조:

### CLI 프로세스 관리
- `anyio.open_process()` 로 CLI 실행 (PTY 미사용, 파이프 기반)
- stdout: JSONL 라인 단위 파싱 → TunapiEvent
- 프로세스 생명주기: `manage_subprocess()` 컨텍스트 매니저

### 메시지 파이프라인
```
CLI stdout (JSONL)
  → JsonlSubprocessRunner.translate() → TunapiEvent
  → ProgressTracker.note_event() → ProgressState
  → Presenter.render_progress/final() → RenderedMessage
  → Transport.send/edit() → 클라이언트
```
- 스트리밍: 토큰 단위 아님, **이벤트 단위 + 5초 주기 배치 업데이트**
- 오케스트레이터: `runner_bridge.py:handle_message()`

### 엔진별 차이
| 엔진 | stdin | 재개 방식 |
|---|---|---|
| Claude | None (arg로 전달) | `--resume TOKEN` |
| Codex | 프롬프트를 stdin으로 | `resume TOKEN -` |
| Gemini | None | `--resume TOKEN` |

### 토론 모드 현황
- `mattermost/roundtable.py` — **Mattermost에 종속**
- tunadish transport에서 재구현 필요
- 기본 구조: RoundtableSession, 엔진 리스트, 라운드 카운터, transcript 축적
- 순차 실행: 엔진별 `handle_message()` 호출, 이전 라운드 응답 주입

### 세션/컨텍스트
- `ChatSessionStore`: `~/.tunapi/mattermost_sessions.json`
- `channel_id → engine_id → ResumeToken` 구조
- tunadish는 전용 세션 파일 분리 필요

---

## 8. 레포 세팅 요청사항

아래 순서로 초기 세팅 및 구현 플랜을 수립해줘:

### 8.1 레포 구조 검토
- 위의 모노레포 구조가 적합한지 검토
- client (Tauri+React) + transport (Python) 모노레포 구성 방안 제안

### 8.2 클라이언트 스캐폴딩
- `npm create tauri-app@latest client` 기반
- React + TypeScript 선택
- shadcn/ui + Zustand 설치 및 초기 설정
- Android 빌드 설정 포함

### 8.3 Python transport 패키지 구조
- tunapi Transport/Presenter/TransportBackend 인터페이스 구현 골격
- WebSocket 서버 (JSON-RPC 2.0) 기본 구조
- pyproject.toml entry_point 등록

### 8.4 구현 플랜
- Phase별 구현 순서 제안 (MVP → 고도화)
- MVP에 포함되어야 할 최소 기능 정의
- 기술적 리스크 항목 파악

---

## 9. 미결 사항

- [ ] 컨텍스트 저장 방식 구체화 (tunapi 고도화 완료 후)
- [ ] 토론 모드 고도화 세부 설계
- [ ] 브랜치 checkout (과거 분기점 재탐색) 구현 방식
- [ ] 모바일 에이전트 제어 UX
- [ ] 설치/설정 방식 (패키지 배포 전략)
- [ ] tunadish transport의 토론 모드 재구현 범위 (mattermost/roundtable.py 참고)
