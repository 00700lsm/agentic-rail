# agentic-rail

**작업은 flow로 진행하고, 설계는 해당 파일의 결정에 근거하며, 위임할 때 승인 범위를 보존합니다.**

agentic-core의 작업 흐름·기록 방식과 Context-Rail의 결정 본문 주입·변경 권한 관점을
결합한 독립 구현 MVP입니다. 기존 두 프로젝트를 그대로 합친 포크는 아닙니다.
Python 3.10 이상, 런타임 외부 패키지 없음. 현재 버전: **0.1.0**.

## 무엇을 하는가

| 기능 | 구현 |
|---|---|
| 작은 진입점 + 선택적 절차 | Core와 code / contract / integrate flow |
| 필요한 결정만 읽기 | 경로에 맞는 PRECEDENT.md 절의 본문과 근거 전달 |
| 공통 결정 누락 방지 | 상위·하위 디렉터리의 적용 가능한 결정을 함께 사용 |
| 결정 변경 근거 유지 | 작업·결정 ID·내용 해시·실제 사용자 지시·출처·변경 범위 기록 |
| 위임 | 목표·소유 파일·선행 작업·flow·결정·승인 근거가 포함된 brief 생성 |
| 검증 상태 | PASS / FAIL / NOT_RUN 구분, 실제 연동 없는 code 완료 방지 |
| Claude Code | 읽기 후 문맥 주입 + 문맥을 받지 못한 첫 편집 보류 |
| Codex 및 기타 호스트 | AGENTS.md와 명시적 CLI. 네이티브 훅 지원을 주장하지 않음 |

## 빠른 시작

이 저장소를 내려받은 폴더에서:

```bash
python3 -m agentic_rail --version
python3 -m unittest discover -s tests -v

# 실제 작업할 프로젝트에 적용할 변경을 먼저 확인
python3 -m agentic_rail --root /path/to/project init --claude --dry-run
python3 -m agentic_rail --root /path/to/project init --claude
```

Codex에서만 사용할 때는 `--claude`를 생략합니다. Python 실행 파일이 `python`인 환경은
명령을 바꾸고, Claude 설정에 생성된 훅의 `python3`도 해당 실행 파일로 변경하세요.
자동 생성 훅 명령은 POSIX 셸/Git Bash 기준입니다. PowerShell 네이티브 훅은 검증하지 않았습니다.
원하면 `python3 -m pip install -e .`로 `agentic-rail` 명령을 설치할 수도 있습니다.

init은 프로젝트 안에만 기록합니다. 전역 설정·원격 저장소·기존 프로젝트 소스는 변경하지
않습니다. 기존 AGENTS.md/CLAUDE.md 내용과 사용자 훅은 보존하고 관리 블록만 추가합니다.
기존 파일을 처음 바꾸면 옆에 `.agentic-rail.bak` 사본을 남깁니다. 사본에도 기존 설정이
포함될 수 있으므로 공유하지 마세요. 재실행은 멱등적이고 사용자 flow 수정은 보존합니다.

설치 후 **작업 프로젝트 폴더에서** 아래 명령을 사용합니다. 이후 별도 패키지 설치 없이
프로젝트에 복사된 런타임으로 실행됩니다.

```bash
python3 .rail/runtime/rail.py audit
python3 .rail/runtime/rail.py context src/user.py
```

## 결정 작성

아래는 문법 예시입니다. 루트 또는 기능 디렉터리의 `PRECEDENT.md`에 작성합니다.
기존에 이 형식과 다른 PRECEDENT.md가 있으면 자동 변환하지 않고 audit에서 오류로 알립니다.
프로젝트에 실제로 합의된 내용만 기록하세요.

```markdown
# Decisions

### DEC-ERROR-001 공통 오류 응답
- Scope: backend/*, frontend/*
- Status: active
- Decision: 오류 코드와 응답 형태는 승인된 OpenAPI 계약을 따른다.
- Forbidden: 소비자 한쪽에서만 오류 코드를 임의로 변경한다.
- Reason: Mock 테스트 성공만으로 실제 FE/BE 호환성을 확인할 수 없다.
```

각 `### ID 제목`이 하나의 결정입니다. 다섯 필드는 필수이고 ID는 프로젝트 전체에서
유일합니다. `Scope`는 해당 PRECEDENT.md 폴더 기준의 쉼표 구분 패턴입니다.
Python fnmatch 규칙으로 `*`는 `/`를 포함하므로 `backend/*`는 그 아래 전체에 적용됩니다.
경로 밖으로 나가는 패턴은 금지합니다. `retired` 결정은 기록만 남고 주입하지 않습니다.
[사용자 관리 예시](examples/user-management/PRECEDENT.md)는 실제 저장소 계약을 확정한 내용이 아닙니다.

## 작업과 위임

```bash
python3 .rail/runtime/rail.py task start permission-01 \
  --flow code --goal '권한 조회 API 구현 및 실제 연동 확인' \
  --path backend/permission.py --path frontend/permission.ts

python3 .rail/runtime/rail.py task brief permission-01
python3 .rail/runtime/rail.py task check permission-01
```

선행 작업이 있으면 `task start`에 `--depends contract-01`을 붙입니다. 해당 작업이 done이
아니면 brief와 완료 검사가 실패합니다. Mock 기반 구현을 먼저 진행할 경우 완료된 계약
작업을 선행 조건으로 두고, 아직 없는 실제 제공자는 후속 integrate 작업에서 검증합니다.
각 병렬 작업에는 다른 task ID와 소유 파일을 부여하세요. 동일 task 파일은 한 작업자만 씁니다.

## 충돌과 승인

사용자가 이미 해당 결정 변경까지 명확히 승인했다면 다시 묻지 않습니다. 모호한 요청이
기존 결정과 충돌할 때만 결정·충돌·필요한 변경 범위를 설명해 확인합니다.
상위 에이전트의 “그냥 진행해”는 새 사용자 승인이 아닙니다.

실제 승인 지시가 있을 때만 그 근거를 기록합니다. 아래 따옴표 내용은 사용 예시입니다.

```bash
python3 .rail/runtime/rail.py task approve permission-01 \
  --decision DEC-ERROR-001 \
  --quote '이 오류 계약을 새 공통 코드로 변경하고 FE/BE를 함께 수정해' \
  --source 'conversation:message-42' \
  --change '공통 오류 코드 변경 및 소비자 동시 반영'
```

그 후 승인 범위대로 코드와 결정 기록을 수정하고:

```bash
python3 .rail/runtime/rail.py task reconcile permission-01
python3 .rail/runtime/rail.py task brief permission-01
```

이전 해시의 승인은 새 해시에 재사용되지 않습니다. 승인 없는 기존 결정 변경은 reconcile이
거부합니다. 새 결정 추가는 기록되고, 그 의미의 적절성은 리뷰로 확인해야 합니다.
flow가 바뀌었다면 새 task로 다시 계획합니다. 승인 파일은 **운영자가 기록한 근거**이지
사용자 본인임을 인증한 서명이 아닙니다. 임의 위조를 차단하는 보안 경계는 아닙니다.

## 검증과 완료

실행 결과를 보고 기록하세요. Rail은 evidence 문자열을 명령으로 실행하지 않습니다.

```bash
python3 .rail/runtime/rail.py task record-check permission-01 \
  --name permission-live --kind integration --result NOT_RUN \
  --evidence '실제 Backend 준비 전: mock 결과와 별도'

# 실제 연동을 수행한 뒤 같은 이름으로 최신 결과를 기록
python3 .rail/runtime/rail.py task record-check permission-01 \
  --name permission-live --kind integration --result PASS \
  --evidence '실행 명령, contract/FE/BE 커밋, 테스트 로그 위치를 여기에 기록'

python3 .rail/runtime/rail.py task finish permission-01
```

기록한 각 검사 이름의 최신 결과가 PASS여야 합니다. code/integrate는 integration PASS,
contract는 contract PASS가 필요합니다. 결정 snapshot 변경 전의 검사 결과는 재실행해야
합니다. 소스 커밋의 변경까지 자동 감시하지는 않으므로 실제 검사 대상 SHA도 근거에 적으세요.

## Claude 동작과 한계

- Read 및 리터럴 파일 경로를 포함한 Bash 결과에서 결정 **본문**을 주입합니다.
- 실패한 Bash도 PostToolUseFailure로 처리합니다. 셸을 실행하거나 전체 의미를 추론하지 않습니다.
- 현재 결정 문맥을 받지 않은 Edit/Write/MultiEdit는 한 번 보류하고 내용을 전달합니다.
  AI는 검토 후 다시 시도합니다. 정상 변경에 매번 사용자 승인을 요구하지 않습니다.
- 세션·에이전트·문맥 해시별 전달 기록을 구분합니다. 결정이 바뀌면 다시 전달합니다.
- 8,000바이트 초과 문맥을 조용히 자르지 않습니다. 결정/범위를 나눠야 합니다.
- 임의 스크립트, 셸 쓰기, 변수·glob·cd 조합 등은 완전히 통제하지 못합니다.
  이런 경로는 `context`로 직접 읽고 프로젝트 검증/리뷰를 함께 사용하세요.
- 훅 payload/CLI는 자동 테스트했지만 **실제 Claude/Codex 세션 연동은 NOT_RUN**입니다.
  LLM 준수율·비용 절감·생산성 향상을 입증한 버전은 아닙니다.

## 문서

- [구조·권한 경계·원문 출처](docs/architecture.md)
- [호스트 수동 검증 절차](docs/validation.md)

2026-10-29 작성. upstream 프로젝트의 소스 복제 없이 관점을 결합한 초기 구현입니다.
