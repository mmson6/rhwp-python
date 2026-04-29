# Documentation Conventions

본 프로젝트의 문서 관리 정책. **Spec-driven + immutable per-version** 패턴을 채택한다. 새 문서를 작성하거나 기존 문서를 수정하기 전 본 문서를 확인.

## 문서 수명 4 분류

| 분류 | 의미 | 갱신 정책 | 예시 |
|---|---|---|---|
| **Living** | 항상 최신 — 다른 문서의 위치 포인터 + 시간선 + 규칙 | 자유 갱신, 매 변경 시 손봐도 무방 | `docs/CONVENTIONS.md` (자체), `docs/roadmap/README.md`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`, `README.md` |
| **Active** | 현재 진행 중 — 의도/스코프 수준의 진화하는 문서 | 큰 변경만, in-place 갱신 OK | `docs/roadmap/phase-N.md` |
| **Draft** | 작성 중인 spec — 해당 버전 GA 전까지 활발 갱신 | 버전 GA 전까지 자유 갱신, GA 후 Frozen 으로 전환 | `docs/roadmap/v0.7.0/mcp.md` (현재 v0.7.0 GA 전) |
| **Frozen** | GA 완료된 spec / 완료된 stage / 완료된 검증 | **변경 금지** — 오타·링크 수정만 in-place 허용. 큰 변경은 새 spec + supersede | `docs/roadmap/v0.2.0/ir.md` (v0.2.0 GA 완료), `docs/implementation/v0.2.0/stages/*.md` |

`Frozen` 은 [Rust RFC](https://rust-lang.github.io/rfcs/) / [Python PEP](https://peps.python.org/) 의 운영 모델. 결정의 historical record 가 보존되어 "왜 그렇게 설계됐는지" 가 명확해진다.

### Frozen 면제 조항 — Living-policy schema migration

Frozen 본문 변경 금지의 예외. **결정·인용·본문 의미를 보존하고 메타데이터의 표현 형식만 갱신하는** non-semantic 변경은 in-place 허용 — 예: inline `**Status**:` 라인 → YAML frontmatter 일괄 마이그.

조건:

- **non-semantic** — 결정 변경 / 새 인용 / 본문 의미 추가 모두 없음. 메타 형식만 갱신
- **전체 spec 일괄** — 단일 PR 로 모든 영향 파일 동시 적용. 개별 파일 단발 갱신 금지
- 면제 조항 활용 commit 은 PR description 에 *어떤 schema migration 인지* 명시

semantic 변경 (결정 / 인용 / 본문 의미) 은 그대로 supersede 절차 적용.

### Frozen 외부 의존성 부패

Frozen 본문은 historical record. 시간 흐르며 외부 의존성 (라이브러리 버전 / API 시그니처 / 외부 URL) 이 deprecated 되어도 본문 변경하지 않는다 — 결정 시점의 정확성을 보존하는 것이 immutability 의 목적. 현재 진실은 *코드* 와 *최신 spec* 이 가짐.

## Status 메타데이터 — YAML frontmatter

`Living` 을 제외한 모든 spec 의 첫 행에 YAML frontmatter 블록을 둔다:

```markdown
---
status: Frozen
ga: v0.3.0
last_updated: 2026-04-28
---

# <문서 제목>

<본문 시작>
```

### 필드 schema

| 필드 | 타입 | 규칙 |
|---|---|---|
| `status` | enum: `Active` / `Draft` / `Frozen` / `Superseded` | 필수 |
| `ga` | `vX.Y.Z` SemVer | `status: Frozen` 또는 `Superseded` 일 때 필수. `target` 과 mutex |
| `target` | `vX.Y.Z` SemVer | `status: Draft` 일 때 필수. `ga` 와 mutex |
| `supersedes` | `<vX.Y.Z>/<topic>.md` 또는 생략 | 새 spec 이 무엇을 대체하는지 |
| `superseded_by` | `<vX.Y.Z>/<topic>.md` | `status: Superseded` 일 때 필수 |
| `last_updated` | `YYYY-MM-DD` | 필수. 의미 변경 commit 시 자동 갱신 ([D3 hook](#last_updated-자동-갱신)) |

`Active` (예: `phase-N.md`, `upstream/<topic>.md`) 는 `ga` / `target` 둘 다 생략.

`Living` 은 frontmatter 없음 — 정의상 항상 최신. 대신 README 같은 인덱스가 다른 문서들의 Status 를 노출.

### 예시

**Frozen** (GA 완료 spec):

```markdown
---
status: Frozen
ga: v0.3.0
last_updated: 2026-04-28
---

# v0.3.0 — `rhwp-py` 얇은 CLI

v0.2.0 에서 폐기했던 CLI 를...
```

**Draft** (GA 전 작업 중):

```markdown
---
status: Draft
target: v0.7.0
last_updated: 2026-04-28
---

# v0.7.0 — MCP server (`rhwp-mcp`)

[Model Context Protocol](https://modelcontextprotocol.io/)...
```

**Active** (Phase 진행 중):

```markdown
---
status: Active
last_updated: 2026-04-26
---

# Phase 3 — view 렌더러 + RAG 프레임워크 통합

**대상 버전**: v0.4.0 ~ v0.6.0
```

**Superseded** (새 spec 으로 대체된 Frozen):

```markdown
---
status: Superseded
ga: v0.2.0
superseded_by: v0.4.0/ir-correction.md
last_updated: 2026-04-25
---

# v0.2.0 — Document IR v1
```

### last_updated 자동 갱신

Claude Code PostToolUse hook (`.claude/hooks/update-last-updated.py`) 이 docs/*.md 의 frontmatter `last_updated` 를 편집 시점 오늘 날짜로 자동 갱신. CI lint 가 frontmatter `last_updated` 와 git history 일치 여부 검증. **수기 갱신 절차는 폐기** — frontmatter 에 직접 손대지 않는다.

면제 조항 활용 마이그 commit 은 hook 실행을 건너뛴다 (non-semantic — 본문 의미 변경 없음). 이 경우 `last_updated` 는 기존 값 그대로 frontmatter 로 이전.

## 디렉토리별 정책

```
docs/
├── CONVENTIONS.md                    Living  — 본 문서. 정책 SSOT
├── roadmap/
│   ├── README.md                     Living  — 활성 spec 인덱스
│   ├── phase-{2,3,4}.md              Active  — Phase 의도/스코프 (구체 결정 미포함)
│   └── v<X.Y.Z>/<topic>.md           Draft → Frozen on GA — per-version spec
├── design/
│   └── v<X.Y.Z>/<topic>-research.md  Draft → Frozen on GA — ADR-style 결정 증거
├── implementation/
│   ├── v<X.Y.Z>/...                  Frozen  — 완료된 stage 작업 로그
│   └── <topic>.md                    Frozen  — meta-level / cross-version 작업
├── traces/
│   └── coverage.md                   Living  — spec ↔ test 자동 매핑
├── upstream/
│   └── <topic>.md                    Active  — 외부 (rhwp Rust 코어) 이슈 초안. 업스트림 머지 시 archive
├── upstream-pins.yaml                Living  — external/rhwp 커밋 핀 SSOT
└── verification/
    └── v<X.Y.Z>/...                  Frozen  — 큰 단위 작업 검증 리포트 (한정)
```

### roadmap/

- `README.md` (Living) — 활성 spec 인덱스. 어느 spec 이 어느 버전을 향하는지의 SSOT
- `phase-N.md` (Active) — Phase 의 의도/스코프만. **구체 결정/미결 이슈는 두지 않음** — 그것들은 `vX.Y.Z/*.md` 의 영역. Phase 의 대상 버전이 바뀌거나 phase boundary 가 이동할 때만 갱신
- `vX.Y.Z/<topic>.md` (Draft → Frozen) — per-version spec. v0.2.0 의 `ir.md` 처럼 한 릴리스의 한 큰 주제 = 한 파일

### design/

- `vX.Y.Z/<topic>-research.md` (Draft → Frozen) — ADR-style 결정 증거. 결정 매트릭스 + 항목별 (팩트/검증자 반박/최종 결정/출처). 짝이 되는 roadmap spec 과 1:1 페어

### implementation/

- `vX.Y.Z/migration.md` 또는 `vX.Y.Z/stages/stage-N.md` (Frozen) — 작업 로그. 완료 즉시 Frozen. 산출물 / 검증 결과 / 이월 사항 기록
- 작은 작업 (단일 세션·수일 규모) 은 단일 `migration.md`. 큰 작업 (여러 주, 의존성 추적 필요) 은 `stages/stage-N.md` 분할
- **stage 작성 시점이 부모 버전 GA 전이면** frontmatter 는 `status: Frozen`, `target: vX.Y.Z` 로 표기 (작성 즉시 immutable, GA 라벨은 미부여). 부모 버전 GA 시 `target` → `ga` 로 일괄 전환

### upstream/

- `<topic>.md` (Active) — 업스트림 (`edwardkim/rhwp` 등) 에 제출 검토 중인 이슈/제안 초안. per-version 매핑 없음
- 본 디렉토리는 외부 시스템 (GitHub Issues) 으로 흘러가기 전 단계의 staging — 정식 spec 의 일부가 아님
- **해결 시** — 두 가지 옵션:
  - **삭제** — 다른 spec 이 본 파일을 참조하지 않을 때. 정보는 GitHub permalink + 본 PR commit history 가 보존
  - **in-place Frozen 전환** — 다른 Frozen spec 이 본 파일을 참조할 때. frontmatter `status: Frozen` (`ga` 생략 — 특정 버전 미귀속), 본문 첫 헤더 위에 `> **RESOLVED** — 상류 PR/commit 참조 …` 한 줄 인용 블록 추가. 기존 body 보존 (historical record)

### verification/

- `vX.Y.Z/<scope>-review.md` (Frozen) — verifier subagent (code-reviewer / test-automator) 산출물. **큰 단위 작업** (다단계 stage / 의심 영역 / cross-cutting refactor) 한정
- 작은 작업 (단일 세션 PR / typo / dep bump) 은 작성 생략 — git log + PR description 이 SSOT

## Cross-link 방향성 규칙

문서 간 의존성을 단방향화하여 "한 문서 변경이 다른 문서 갱신을 강제하는" 연쇄를 끊는다.

```
Living  ───→  Active  ───→  Draft  ───→  Frozen
  ↑              ↑             ↑             ↑
  └──────────────┴─────────────┴─────────────┘
           (위로 거슬러 link 만 OK)
```

- **Living → 모든 곳** OK (인덱스 역할)
- **Active → Draft / Frozen** OK (Phase 가 spec 을 가리킴)
- **Draft → Active / Living / Frozen** OK
- **Frozen → 다른 곳** 가급적 자제 (Frozen 후에 새 cross-link 추가하면 본문 수정이 됨)

### Spec ↔ spec 직접 link 금지 (예외 1 종)

- **금지**: 같은 디렉토리 안의 spec 끼리 직접 link (예: `v0.3.0/cli.md` ↔ `v0.3.0/ir-expansion.md`). 새 spec 추가 시 기존 spec 도 손봐야 하는 연쇄 발생
- **대신**: `roadmap/README.md` 또는 `phase-N.md` 가 묶어서 노출
- **예외**: **짝 페어** — `roadmap/vX.Y.Z/<topic>.md` 와 `design/vX.Y.Z/<topic>-research.md` 는 1:1 짝 (spec ↔ ADR). 짝끼리는 직접 link 유지 (두 문서가 사실상 한 결정의 두 면)

## 새 spec 추가 절차

`/new-spec <version> <topic>` Claude Code skill 이 본 절차를 자동화 (`.claude/skills/new-spec/SKILL.md`).

### v<X.Y.Z> 신설 시

1. 디렉토리 생성: `docs/roadmap/v<X.Y.Z>/`, `docs/design/v<X.Y.Z>/`
2. spec 파일 작성 — frontmatter `status: Draft`, `target: vX.Y.Z`
3. 짝이 되는 design research 파일 작성 — 같은 frontmatter
4. `docs/roadmap/README.md` 의 인덱스 표에 행 추가
5. 해당 phase 가 있다면 `phase-N.md` 의 § 대상 버전 / § 산하 spec 갱신 (Active 갱신은 자유)

### 버전 GA 후

1. 해당 vX.Y.Z 디렉토리 안의 spec 들 frontmatter `status: Draft → Frozen`, `target: vX.Y.Z` → `ga: vX.Y.Z` 로 전환
2. `docs/roadmap/README.md` 인덱스 갱신 (Status 컬럼)
3. `CHANGELOG.md` 의 해당 버전 섹션 마무리
4. 구현 로그 작성 — `docs/implementation/v<X.Y.Z>/...` (작성 즉시 Frozen)

### Phase 완료 후

`phase-N.md` 의 모든 대상 vX.Y.Z 가 GA 되면 해당 phase 문서를 삭제한다.

1. cross-link 정리 — Frozen spec 본문의 `phase-N.md` 참조: link 만 제거 (인용된 결정 텍스트는 본문에 흡수). 진행 중 spec / Active 문서의 참조: README 인덱스로 redirect 또는 단순 제거
2. `docs/roadmap/README.md` § Phase 인덱스 표에서 해당 행 제거
3. `docs/roadmap/phase-N.md` 파일 삭제
4. CHANGELOG 에 phase 정리 기록

근거: phase 문서는 진행 중 phase 의 의도/스코프 SSOT — 모두 GA 되면 historical record 는 `v<X.Y.Z>/*.md` spec 들이 보유. phase 문서를 보존하면 활성 인덱스가 비대해지고 "phase 가 살아있는 것처럼" 오해 유발.

### Frozen 후 결정 변경이 필요한 경우

1. **새 spec 작성** — 기존 파일 수정 금지. 새 파일 (예: `docs/roadmap/v0.4.0/ir-correction.md`)
2. **기존 Frozen spec 의 frontmatter** 만 갱신: `status: Superseded`, `superseded_by: v0.4.0/ir-correction.md`. `ga` 보존
3. 새 spec frontmatter 의 `supersedes` 에 역참조 — 양방향 chain 형성
4. 새 spec 본문에 § Supersedes 섹션 추가하여 무엇을 어떻게 바꾸는지 명시
5. CHANGELOG 에 변경 사유 기록

오타·깨진 링크·외부 URL 변경 같은 비-의미 변경은 in-place 가능 (last_updated 자동 갱신).

## Implementation log 구조

`docs/implementation/` 안의 세 종류 분류:

- `vX.Y.Z/stages/stage-N.md` — 해당 release 의 spec § 구현 스테이지 분할 에 명시된 작업 (대규모, 다단계). spec 의 stage 표와 1:1 mapping
- `vX.Y.Z/<topic>.md` (vX.Y.Z 직속 평면) — spec 없는 작은 작업 (refactor / chore / perf / dep bump 등). 결정 비교 (a/b/c 옵션) 가치 있어 CHANGELOG 한 줄로 부족할 때만 작성. branch prefix `<type>/<topic>` 와 1:1 mapping (예: branch `refactor/aparse-stdlib` → log `aparse-cleanup.md`)
- `<topic>.md` (vX.Y.Z 외부 직속 평면) — meta-level / cross-version 작업 (예: 문서 시스템 개편). 작성 즉시 Frozen, frontmatter `ga` 필드 생략 가능 (해당 사항 없음 — 특정 버전 귀속 안 됨)

CHANGELOG 한 줄로 충분한 변경 (typo 정리, 단순 dep bump, 작은 docstring 갱신 등) 은 파일 작성 안 함 — git log + CHANGELOG 가 SSOT.

미래 ad-hoc note 가 5개 이상 모이면 그때 `chores/` 디렉토리화 검토 (YAGNI).

## CHANGELOG ↔ implementation log 역할 분리

| 문서 | 관점 | 내용 |
|---|---|---|
| `CHANGELOG.md` | 사용자 (외부) | *what* — 추가/변경/제거된 API, extras, 호환성 영향, 마이그레이션 안내 |
| `docs/implementation/.../*.md` | 개발자 (내부) | *why/how* — a/b/c 옵션 비교, 시행착오, 결정 근거, Stage별 작업 흐름 |

같은 사실 중복 기록 금지 — CHANGELOG 가 *what*, log 가 *why/how*. 결정 비교 (a/b/c) 가치가 없는 변경 (단순 dep bump, typo) 은 CHANGELOG 한 줄로 충분 — implementation log 작성 안 함.

## 인수조건 형식 — EARS notation (v0.4.0+ 신규 spec)

v0.4.0+ 신규 spec 의 § 인수조건 섹션은 [EARS notation](https://alistairmavin.com/ears/) (Easy Approach to Requirements Syntax, Rolls-Royce) 5종 키워드로 작성한다. 각 항목에 `AC-N` ID 부여 — 테스트 `pytest.mark.spec("vX.Y.Z/topic#AC-N")` 와 1:1 매핑.

| 패턴 | 형식 | 용도 |
|---|---|---|
| Ubiquitous | `THE {system} SHALL {response}` | 항상 성립 |
| Event-Driven | `WHEN {trigger}, THE {system} SHALL {response}` | 이벤트 시 |
| State-Driven | `WHILE {state}, THE {system} SHALL {response}` | 상태 지속 중 |
| Optional | `WHERE {feature}, THE {system} SHALL {response}` | 옵션 켜진 경우 |
| Unwanted | `IF {condition}, THEN THE {system} SHALL {response}` | 예외/실패 |

기존 v0.1.0 ~ v0.3.0 Frozen spec 은 미변경 — historical record 보존.

## Trace report — pytest spec markers

v0.4.0+ 부터 테스트는 `pytest.mark.spec("vX.Y.Z/topic#AC-N")` marker 로 spec 인수조건과 1:1 매핑. CI 에서 `scripts/generate_spec_trace.py` 가 매 빌드 시 `docs/traces/coverage.md` (Living) 자동 갱신 — spec 별 인수조건 ↔ 테스트 mapping 표.

기존 v0.1.0 ~ v0.3.0 Frozen spec 은 AC ID 부여 안 함 — marker 없는 테스트 허용.

## Archive 정책 (v1.0+)

Major release GA 시점에 직전 major 의 frozen spec 들을 archive 디렉토리로 이동한다 — README 인덱스 비대화 / 검색 노이즈 완화. 파일 이동만, 본문 변경 없음.

- v1.0 GA → 모든 v0.X.Y frozen spec 을 `docs/archive/v0/` 로 이동 (동일 구조 유지: `archive/v0/roadmap/v0.3.0/...`)
- 이후 v2.0 GA → `docs/archive/v1/`, ... 로 누적
- `roadmap/README.md` 인덱스는 active major 만 노출, archive 는 별도 페이지 (`docs/archive/README.md`) 에 한 줄 link
- git size 자체는 무관 (markdown delta compression 효율적) — 본 정책은 인덱스/검색 가독성 목적

v1.0 GA 전까지 아무것도 안 함 — 본 정책은 v1.0 GA 직전 작업으로 잡아둠.

## 명명 규칙

- 파일명: kebab-case (`ir-expansion.md`, not `ir_expansion.md`)
- 디렉토리: `v` prefix + SemVer (`v0.3.0/`, not `0.3.0/`)
- ADR 파일: `<topic>-research.md` (roadmap spec `<topic>.md` 와 stem 일치)
- stage 파일: `stage-<N>.md` (1-indexed)
- **상대경로**: 같은 / 하위 디렉토리는 implicit (`foo.md`, `subdir/foo.md`). 상위는 `../foo.md`. `./` prefix 금지 (redundant). 외부 자원만 fully-qualified URL

## 본 문서의 갱신

CONVENTIONS.md 자체는 Living. 정책 변경 시 in-place 갱신. **단** 본 문서의 변경은 모든 spec 작성에 영향을 주므로:

- 큰 변경 (예: Status 분류 추가/삭제, frontmatter schema 변경) 시 PR 에 영향 받는 기존 문서 일괄 마이그레이션 포함 (Frozen 면제 조항 활용 가능)
- 작은 변경 (예: 명명 규칙 추가) 는 in-place + 신규 문서부터 적용, 기존은 점진 정리

## 참조

- Rust RFC 운영: <https://rust-lang.github.io/rfcs/>
- Python PEP 절차: <https://peps.python.org/pep-0001/>
- ADR 패턴 (Architecture Decision Records): <https://adr.github.io/>
- Diátaxis 4-axis: <https://diataxis.fr/>
- GitHub Spec Kit: <https://github.com/github/spec-kit>
- EARS notation: <https://alistairmavin.com/ears/>
