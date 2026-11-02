# agentic-rail

**코딩 에이전트가 팀의 협업 규칙과 설계 결정을 건너뛰지 않도록 개발 단계·승인 범위·검증 근거를 관리하는 경량 워크플로우 도구입니다.**

`agentic-rail`은 AI 에이전트에게 작업을 맡길 때 **"왜 이렇게 설계했는지(설계 결정)", "어디까지 수정해도 되는지(승인 범위)", "실제로 테스트를 통과했는지(검증 근거)"**가 유실되지 않도록 잡아주는 독립 실행형 도구(MVP)입니다.

기존 `agentic-core`의 작업 기록 방식과 설계 결정 전달 방식을 결합해 처음부터 새로 구현했으며, 기존 프로젝트의 단순 포크(Fork)가 아닙니다. 외부 패키지 설치 없이 **Python 3.10 이상 표준 라이브러리**만으로 바로 동작합니다. (현재 버전: **0.2.0**)

## 왜 필요한가요? (핵심 역할)

코딩 에이전트와 협업할 때 흔히 겪는 문제를 다음과 같이 해결합니다.

| 핵심 기능 | 쉽게 풀어쓴 설명 |
| :--- | :--- |
| **8단계 개발 프로세스 관리** | `분석(analyze) → 설계(design) → 구현(implement) → 검증(verify) → 리뷰(review) → 통합(integrate) → 인계(handoff) → 회고(reflect)` 순서로 진행하며, 각 단계를 넘어갈 조건과 근거를 확인합니다. |
| **경로별 설계 결정(`PRECEDENT.md`) 자동 추출** | 에이전트가 전체 문서를 다 읽느라 토큰을 낭비하지 않도록, 현재 수정할 파일 경로(상위·하위 폴더 포함)에 적용되는 설계 결정과 이유만 뽑아 전달합니다. |
| **임의 설계 변경 차단 및 승인 이력 보존** | 기존에 합의된 설계를 바꿔야 할 때, 상위 에이전트의 임의 지시("그냥 진행해")로는 규칙을 깰 수 없습니다. 실제 사용자의 승인 문구·출처·변경 범위·해시를 기록해야만 변경이 허용됩니다. |
| **가짜 완료(Mock 통과) 방지** | 검증 상태를 `PASS` / `FAIL` / `NOT_RUN`으로 엄격히 구분하여, 단순 Mock 테스트만 통과한 상태에서 실제 연동(Integration) 없이 작업을 완료 처리하는 것을 막습니다. |
| **위임 브리핑(`brief`) 생성** | 서브 에이전트나 다른 모델에게 작업을 넘길 때 목표, 담당 파일, 선행 작업, 적용할 설계 결정, 승인 근거를 하나로 묶은 브리핑 텍스트를 만들어 줍니다. |
| **협업 맥락 및 재작업 지표 기록** | 담당자, API 계약(Contract) 참조, 선행 작업 완료 여부, 통합 방식(PR별 또는 마일스톤 묶음별)을 유지하고, 단계별 소요 시간·결함 수·재작업(Rework) 시간을 집계합니다. |
| **특정 모델·호스트 비종속** | 모델 호출이나 테스트 실행은 기존 개발 환경(Claude Code, Cursor, CI 등)에 맡기고, `agentic-rail`은 명시적인 CLI를 통해 문맥과 상태만 관리합니다. |

## 빠른 시작 (설치 및 초기화)

먼저 이 저장소를 클론한 폴더에서 버전과 기본 테스트를 확인할 수 있습니다.

```bash
python3 -m agentic_rail --version
python3 -m unittest discover -s tests -v
```

이제 실제로 **적용할 대상 프로젝트 폴더**를 지정해 초기화(`init`)합니다.

```bash
# 1. 어떤 파일이 추가·수정되는지 미리 확인 (실제 변경 없음)
python3 -m agentic_rail --root /path/to/project init --dry-run

# 2. 대상 프로젝트에 런타임(.rail/) 및 안내 문서 설치
python3 -m agentic_rail --root /path/to/project init
```

* **Claude Code 사용 시**: `init --claude` 옵션을 주면 `CLAUDE.md` 안내 블록을 함께 생성합니다. (런타임 훅은 설치하지 않습니다.)
* **전역 명령어로 설치하고 싶을 때**: `python3 -m pip install -e .`를 실행하면 `agentic-rail` 명령어를 바로 쓸 수 있습니다.
* **안전한 로컬 설치**: `init`은 지정한 프로젝트 폴더 내부에만 파일을 기록하며, 전역 설정이나 원격 저장소, 기존 소스 코드는 건드리지 않습니다. 기존 `AGENTS.md`나 `CLAUDE.md`가 있으면 내용을 보존한 채 관리 블록만 덧붙이고, 최초 수정 시 `.agentic-rail.bak` 백업본을 남깁니다(백업 파일에는 기존 설정이 들어 있을 수 있으니 외부에 공유하지 마세요). 여러 번 다시 실행해도 안전하며(멱등성 보장), 사용자가 직접 수정한 flow 설정은 덮어쓰지 않습니다.

초기화가 끝나면 대상 프로젝트 안에 `.rail/runtime/rail.py`가 복사되므로, 이후에는 **작업 프로젝트 폴더에서** 별도 패키지 설치 없이 바로 명령을 실행할 수 있습니다.

```bash
# PRECEDENT.md 문법 및 설정 점검
python3 .rail/runtime/rail.py audit

# 특정 파일/경로에 적용되는 설계 결정 조회
python3 .rail/runtime/rail.py context src/user.py
```

## 1. 8단계 개발 프로세스(`process`) 사용하기

기존 프로젝트의 담당자 배정, Contract-first(계약 우선) 개발, 선행 작업 규칙, PR 리뷰·병합 정책을 그대로 유지하면서 8단계 개발 흐름을 관리합니다.

* **진행 순서**: `analyze` → `design` → `implement` → `verify` → `review` → `integrate` → `handoff` → `reflect`
* **재작업(`rework`)**: 중간에 검증이 실패하거나 소스 코드가 바뀌면 `process rework` 명령으로 다시 분석·설계·구현 단계로 되돌아갑니다.
* **6대 운영 영역 매핑**: `Governance`, `Knowledge`, `Orchestration`, `Engineering`, `Quality`, `Intelligence`는 순서대로 거치는 단계가 아니라 모든 개발 단계에 걸쳐 점검하는 운영 기준이며, `.rail/process.json`에서 각 단계와 연결됩니다.

```bash
# 새 프로세스 작업 시작
python3 .rail/runtime/rail.py process start permission-02 \
  --goal '권한 조회 API 구현' --owner permission-worker \
  --path backend/permission.py --path frontend/permission.ts \
  --contract-ref 'contract@<accepted-commit>' \
  --integration-mode milestone --batch M1

# 작업 위임용 브리핑 출력
python3 .rail/runtime/rail.py process brief permission-02

# 현재 진행 단계 및 상태 확인
python3 .rail/runtime/rail.py process status permission-02

# 전체 상태 그래프 확인 (기본 텍스트/Mermaid 또는 JSON)
python3 .rail/runtime/rail.py process graph
python3 .rail/runtime/rail.py process graph --format json
```

### 완료 상태 구분과 주의사항

* **구현 완료 vs 통합 완료 vs 작업 완료(`done`)**:
  * 코드 리뷰까지 마치면 **구현 완료**로 표시됩니다.
  * 실제 통합 검증(Integration)까지 `PASS`해야 **통합 완료**로 표시됩니다.
  * 작업 상태가 `done`이 되었다는 것은 **PR 인계(handoff)와 회고(reflect)까지 마쳤다**는 뜻이며, 최종 브랜치 병합(Merge)이나 배포 완료와는 별개입니다.
* **단계 우회 불가**: `process`로 시작한 작업은 기존 `task finish` 명령으로 중간 단계를 건너뛰어 완료 처리할 수 없습니다. (반대로 기존 `task start`로 만든 작업은 예전 완료 규칙을 그대로 따르며 자동으로 `process` 방식으로 바뀌지 않습니다.)
* **역할 경계**: 단계 전환 조건은 `agentic-rail`이 코드로 검사하지만, 실제 LLM 호출·테스트 구동·리뷰어 인증은 실행 환경(호스트)과 기존 CI가 담당합니다. 자세한 단계별 실행 예시와 그래프는 [개발 프로세스 상세 문서](docs/development-process.md)를 참고하세요.

## 2. 설계 결정(`PRECEDENT.md`) 작성하기

팀과 프로젝트에서 합의된 설계 원칙은 루트 폴더나 각 기능 폴더의 `PRECEDENT.md`에 기록합니다. 반드시 실제로 합의된 규칙만 적으세요. (기존에 다른 형식으로 작성된 `PRECEDENT.md`가 있다면 임의로 자동 변환하지 않고 `audit` 실행 시 오류로 알려줍니다.)

```markdown
# Decisions

### DEC-ERROR-001 공통 오류 응답
- Scope: backend/*, frontend/*
- Status: active
- Decision: 오류 코드와 응답 형태는 승인된 OpenAPI 계약을 따른다.
- Forbidden: 소비자 한쪽에서만 오류 코드를 임의로 변경한다.
- Reason: Mock 테스트 성공만으로 실제 FE/BE 호환성을 확인할 수 없다.
```

* **필수 항목**: 각 결정은 `### <ID> <제목>`으로 시작하며, 아래 5개 항목(`Scope`, `Status`, `Decision`, `Forbidden`, `Reason`)을 모두 적어주어야 합니다. ID는 프로젝트 전체에서 고유해야 합니다.
* **적용 범위(`Scope`)**: 해당 `PRECEDENT.md`가 위치한 폴더를 기준으로 적용할 경로 패턴을 쉼표(`,`)로 구분해 적습니다. Python `fnmatch` 규칙을 따르므로 `backend/*`라고 적으면 `backend/` 하위 모든 폴더와 파일에 적용됩니다. 상위 폴더(`..`)로 벗어나는 패턴은 사용할 수 없습니다.
* **만료된 결정(`retired`)**: `Status: retired`로 바꾼 결정은 히스토리로만 남고, 에이전트에게 전달하는 `brief`나 `context` 출력에서는 제외됩니다.
* 작성 예시는 [사용자 관리 PRECEDENT 예시](examples/user-management/PRECEDENT.md)에서 확인할 수 있습니다.

## 3. 경량 작업(`task`) 관리와 에이전트 위임

8단계 전체 프로세스 대신 가볍게 작업 단위를 관리할 때는 기존 `task` 명령어를 사용합니다.

```bash
# 작업 시작 (--flow는 code, contract, integrate 중 선택)
python3 .rail/runtime/rail.py task start permission-01 \
  --flow code --goal '권한 조회 API 구현 및 실제 연동 확인' \
  --path backend/permission.py --path frontend/permission.ts

# 에이전트에게 전달할 작업 브리핑 생성
python3 .rail/runtime/rail.py task brief permission-01

# 완료 조건 충족 여부 점검
python3 .rail/runtime/rail.py task check permission-01
```

* **선행 작업 연결(`--depends`)**: 먼저 끝나야 하는 작업이 있다면 `task start` 실행 시 `--depends contract-01`처럼 지정합니다. 선행 작업이 `done` 상태가 아니면 브리핑 생성과 완료 검사가 실패합니다. 예를 들어 API 계약(`contract-01`)을 먼저 완료한 뒤 Mock 기반으로 프론트/백엔드를 구현하고, 실제 연동 검증은 후속 `integrate` 작업에서 수행하도록 묶을 수 있습니다.
* **병렬 작업 규칙**: 동시에 여러 에이전트/작업자가 일할 때는 각기 다른 `task ID`와 담당 파일(`--path`)을 배정하세요. 하나의 task 상태 파일은 한 작업자만 수정해야 합니다.
* **브리핑 전달**: `task brief` 출력 결과를 복사해 에이전트 프롬프트에 함께 넣어주세요. 작업 도중 수정할 파일이 늘어나면 `context <추가 경로>`를 실행해 해당 경로의 설계 결정을 추가로 읽어오면 됩니다.

## 4. 기존 설계 결정과 충돌할 때 (승인 및 변경 절차)

작업 내용이 기존 `PRECEDENT.md`의 결정과 충돌할 때는 다음 원칙을 따릅니다.

1. **누가 승인할 수 있는가**: 사용자가 처음부터 해당 설계 변경을 명시적으로 지시했다면 바로 진행하지만, 요청이 모호한데 기존 결정과 충돌한다면 **어떤 결정과 왜 충돌하는지, 어디까지 바꿔야 하는지** 사용자에게 먼저 설명하고 확인받아야 합니다. 상위 오케스트레이션 에이전트가 내린 *"그냥 진행해"* 같은 지시는 사용자 승인으로 인정되지 않습니다.
2. **승인 근거 기록(`task approve`)**: 실제 사용자의 승인 지시가 있을 때만 아래처럼 승인 문구와 출처를 기록합니다.

```bash
python3 .rail/runtime/rail.py task approve permission-01 \
  --decision DEC-ERROR-001 \
  --quote '이 오류 계약을 새 공통 코드로 변경하고 FE/BE를 함께 수정해' \
  --source 'conversation:message-42' \
  --change '공통 오류 코드 변경 및 소비자 동시 반영'
```

3. **코드·결정 수정 후 동기화(`task reconcile`)**: 승인받은 범위대로 코드와 `PRECEDENT.md`를 수정한 뒤 아래 명령으로 반영합니다.

```bash
python3 .rail/runtime/rail.py task reconcile permission-01
python3 .rail/runtime/rail.py task brief permission-01
```

* 승인 기록은 결정 내용의 해시(Hash)와 묶여 있어, 이후 결정 내용이 또 바뀌면 이전 승인을 재사용할 수 없습니다.
* 승인 없이 기존 결정을 수정하면 `reconcile` 단계에서 거부됩니다. (새로운 결정을 추가하는 것은 허용되며, 내용은 코드 리뷰에서 확인합니다.)
* 작업 성격(`flow`) 자체가 바뀌었다면 기존 작업을 고치기보다 새 `task`로 다시 계획하세요.
* **보안 안내**: 승인 기록 파일은 **작업 과정의 근거를 남기는 용도**이며, 암호학적 전자서명이나 위조 방지 보안 기능이 아닙니다.

## 5. 검증 결과 기록 및 작업 완료 (`task record-check` & `finish`)

테스트나 연동 확인을 마친 뒤 결과를 직접 기록합니다. (`--evidence`에 적은 문자열은 기록용 메모일 뿐, `agentic-rail`이 해당 문자열을 셸 명령으로 실행하지는 않습니다.)

```bash
# 아직 실제 백엔드가 준비되지 않아 통합 테스트를 못 돌린 경우
python3 .rail/runtime/rail.py task record-check permission-01 \
  --name permission-live --kind integration --result NOT_RUN \
  --evidence '실제 Backend 준비 전: mock 결과와 별도'

# 실제 연동 테스트까지 통과한 뒤 같은 이름으로 PASS 결과 갱신
python3 .rail/runtime/rail.py task record-check permission-01 \
  --name permission-live --kind integration --result PASS \
  --evidence '실행 명령, contract/FE/BE 커밋 SHA, 테스트 로그 위치를 여기에 기록'

# 모든 필수 검사가 PASS 상태일 때 작업 완료 처리
python3 .rail/runtime/rail.py task finish permission-01
```

* 등록한 모든 검사 항목의 최신 결과가 `PASS`여야 `task finish`가 성공합니다 (`code`/`integrate` 플로우는 `integration PASS` 필수, `contract` 플로우는 `contract PASS` 필수).
* 만약 설계 결정 스냅샷이 중간에 바뀌었다면 이전 테스트 결과는 무효가 되므로 다시 검증해 기록해야 합니다. 소스 코드 커밋 변경을 자동으로 감시하지는 않으므로, 어떤 커밋(SHA)을 기준으로 검증했는지 `--evidence`에 함께 적어두세요.

## 현재 버전(v0.2.0)의 동작 한계 및 이전 버전에서 업데이트하기

### 알아두어야 할 한계

* **런타임 훅(Hook) 제거**: 에이전트가 파일을 읽고 쓸 때마다 실시간으로 가로채서 규칙을 주입하거나 첫 편집을 막던 훅 기능은 제거했습니다. 대신 명시적인 CLI(`context`, `brief`, `approve`, `reconcile`)로 설계 결정과 승인 근거를 주고받습니다.
* **출력 크기 제한**: `context` 조회 결과가 기본 한도(8,000바이트)를 넘으면 내용을 몰래 잘라내지 않고 즉시 오류를 반환합니다.
* **운영자 기록 기반**: 단계별 근거, 리뷰어, 커밋 리비전, 측정 수치는 작업자/에이전트가 기록한 값을 신뢰하며 시스템이 자동으로 진위를 검증하지는 않습니다.
* **실제 모델 연동 실험**: 다양한 LLM 세션에서의 준수율이나 생산성 향상 수치는 아직 별도 벤치마크로 측정 전(`NOT_RUN`)입니다.

### 구버전 설치 환경에서 업데이트하는 방법

기존 프로젝트에 이전 버전의 `agentic-rail`이 설치되어 있다면, 새 버전 CLI로 `init --dry-run`을 확인한 뒤 `init`을 다시 실행하세요.

* 이전 버전의 `agentic-rail`이 자동 등록했던 훅 명령만 골라 제거하며, 사용자가 직접 추가한 다른 훅과 설정은 건드리지 않습니다. (단, 기존 훅 명령을 직접 수정해 두었다면 자동으로 식별되지 않으니 수동으로 지워주세요.)
* 예전에 복사된 `hooks.py`는 백업 후 삭제되고, `CLAUDE.md`의 관리 블록도 새 버전에 맞게 갱신됩니다. (`.rail/state/receipts/` 기록은 더 이상 쓰지 않습니다.)
* 업데이트 후에는 현재 열려 있는 에이전트(호스트) 세션을 종료했다가 다시 시작해야 변경된 설정이 반영됩니다.

## 관련 문서

* [아키텍처·권한 경계·설계 배경](docs/architecture.md)
* [호스트 환경 수동 검증 가이드](docs/validation.md)
* [협업 규칙 및 8단계 개발 프로세스 모델](docs/development-process.md)

*2026-11-02 업데이트 — 기존 레퍼런스 프로젝트의 소스를 복제하지 않고 핵심 관점을 결합해 독자적으로 구현한 프로젝트입니다.*
