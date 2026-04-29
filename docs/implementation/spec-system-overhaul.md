---
status: Frozen
last_updated: 2026-04-29
---

# Spec System Overhaul — 작업 로그 (Frozen)

본 문서는 PR `docs/spec-system-overhaul` 의 historical record. 14개 결정 + 9 commit 단계 + a/b/c 옵션 비교 + invariant 정의를 보존한다. meta-level / cross-version 작업이라 특정 vX.Y.Z 에 귀속되지 않음 — `ga` 필드 생략 (CONVENTIONS § Implementation log 구조).

PR 진행 중에 사용된 임시 명세서로, 머지 후 `docs/implementation/` 직속 평면으로 이주됨. 작업 진행 중 발생한 일부 사후 결정 (예: `-design-research` → `-research` rename, 상류 issue #390 RESOLVED in-place Frozen 처리, lint_docs.py typer 전환) 은 본 문서가 아닌 git log + commit message + CHANGELOG 가 보유.

---

## TL;DR

- **브랜치**: `docs/spec-system-overhaul`
- **PR 단위**: 단일 PR (모든 결정 일괄 적용, commit으로 분리)
- **영향 범위**: [docs/CONVENTIONS.md](../CONVENTIONS.md) 대폭 갱신 + 22개 spec 파일 frontmatter 마이그 + 새 도구 5개 + AGENTS.md 도입
- **작업 시간 예상**: 4-6시간 (신중성 우선, 의심 케이스 사용자 확인)
- **invariant**: 22개 spec 파일의 *현재 메타데이터 값* (Status / GA / Target / Last updated) 정확 보존

---

## 결정 14개 (확정)

이전 대화에서 사용자 확정된 결정. 수정 금지.

| # | 항목 | 한 줄 |
|---|---|---|
| D1 | YAML frontmatter 정식 도입 (`status` / `ga` 또는 `target` / `supersedes` / `superseded_by` / `last_updated`). 기존 `**Status**: ...` inline 라인 제거 |
| D2 | AGENTS.md 정본화 + CLAUDE.md = 1줄 stub (symlink 아님, 별도 파일) |
| D3 | `last_updated` 자동 갱신 (Claude Code PostToolUse hook + CI 검증). 매 의미 변경 commit 마다 갱신 |
| D4 | EARS notation 인수조건 형식 — v0.4.0+ 신규 spec 만 적용. 기존 Frozen 미변경 |
| D6 | `pytest.mark.spec("vX.Y.Z/topic#AC-N")` marker + 자동 trace report (Living, [docs/traces/coverage.md](../traces/coverage.md)) |
| D7 | Claude Code skill `.claude/skills/new-spec/SKILL.md` (`/new-spec v0.4.0 view-renderer` 호출 시 spec + 페어 ADR + README 인덱스 row 일괄 생성) |
| D8 | Cross-link 방향성 lint (Living/Active/Draft/Frozen 4-tier 위반 검출) — 기존 [.claude/hooks/docs-lint.py](.claude/hooks/docs-lint.py) 확장 |
| D9 | 종합 spec lint (frontmatter schema / 파일명 kebab-case / supersede chain integrity) — 기존 lint 확장 |
| D10 | `docs/verification/` 정책 약화 — 큰 단위 작업 / 의심 영역의 verifier subagent 산출물 한정. 작은 작업 작성 안 함 |
| D11 | CHANGELOG (사용자 *what*) ↔ implementation log (개발자 *why/how*) 역할 분리 명문화 |
| D12 | 상대경로 implicit 표준 명문화 (`foo.md` / `subdir/foo.md` / `../foo.md`. `./` 금지). 기존 파일은 이미 표준 따름 — 마이그레이션 없음 |
| D13 | Frozen 외부 의존성 부패 → 무시 (옵션 A). CONVENTIONS.md 한 줄 추가 |
| D14 | `docs/upstream-pins.yaml` SSOT + 자동 갱신 스크립트 |
| D-extra | **Frozen 면제 조항** — "Living-policy schema migration is non-semantic, allowed in-place on Frozen" — CONVENTIONS.md L12 면제 조항 추가 (본 PR 자체가 이를 활용) |

기각된 결정 2개:
- ❌ Spec 본문에 코드 경로 hardcode (사용자 직관 정확 — 대신 D6 trace로 대체)
- ❌ Phase Active이지만 spec 0개 우려 (정책상 정상)
- ❌ upstream/ 디렉토리 폐기 (사용자 유지 결정)

---

## Frontmatter Schema (D1 — Source of Truth)

본 schema 가 D6/D7/D8/D9 모두의 입력. **PR 첫 commit 에서 동결**.

### 필드 정의

```yaml
---
status: <Active | Draft | Frozen | Superseded>   # required, enum
ga: vX.Y.Z                                       # status=Frozen 일 때만 (mutex with target)
target: vX.Y.Z                                   # status=Draft 일 때만 (mutex with ga)
supersedes: null | "<vX.Y.Z>/<topic>.md"         # 새 spec이 무엇을 superseded 하는지
superseded_by: null | "<vX.Y.Z>/<topic>.md"     # Frozen 이 새 spec 으로 대체된 경우
last_updated: YYYY-MM-DD                         # 자동 갱신 (D3)
---
```

### 분류별 적용

| 분류 | 적용 | 예시 |
|---|---|---|
| **Living** | frontmatter **없음** (정의상 항상 최신) | [docs/CONVENTIONS.md](../CONVENTIONS.md), [docs/roadmap/README.md](../roadmap/README.md) |
| **Active** | `status: Active`, ga/target 둘 다 생략 | [phase-3.md](../roadmap/phase-3.md), [phase-4.md](../roadmap/phase-4.md), [docs/upstream/issue-find-control-text-positions.md](../upstream/issue-find-control-text-positions.md) |
| **Draft** | `status: Draft`, `target: vX.Y.Z` 필수 | [v0.7.0/mcp.md](../roadmap/v0.7.0/mcp.md) |
| **Frozen** | `status: Frozen`, `ga: vX.Y.Z` 필수 | 나머지 17개 |
| **Superseded** | `status: Superseded`, `superseded_by` 필수, ga 보존 | (현재 0건) |

### 예시

```markdown
---
status: Frozen
ga: v0.3.0
last_updated: 2026-04-28
---

# v0.3.0 — `rhwp-py` 얇은 CLI

v0.2.0 에서 폐기했던 CLI 를...
```

```markdown
---
status: Draft
target: v0.7.0
last_updated: 2026-04-28
---

# v0.7.0 — MCP server (`rhwp-mcp`)

[Model Context Protocol](https://modelcontextprotocol.io/)...
```

### 갱신 규칙

- 본문 의미 있는 변경 → `last_updated: YYYY-MM-DD` 자동 갱신 (Claude Code hook)
- Status 전환 (Draft → Frozen 등) → `status` + 적절 필드 갱신
- Frozen 본문 변경 금지는 *body* 한정 — frontmatter 갱신은 본 PR 의 면제 조항 외엔 금지

---

## 마이그레이션 대상 22개 파일 (D1)

각 파일의 *현재 inline 메타데이터 값* 정확 보존. 작업 시 한 파일씩 read → 메타 추출 → frontmatter 작성 → inline 라인 제거.

### Frozen (17개)

| 파일 | status | ga | last_updated |
|---|---|---|---|
| `docs/roadmap/v0.1.0/rhwp-python.md` | Frozen | v0.1.0 | (현재 값 보존) |
| `docs/roadmap/v0.2.0/ir.md` | Frozen | v0.2.0 | 2026-04-25 |
| `docs/roadmap/v0.3.0/cli.md` | Frozen | v0.3.0 | 2026-04-28 |
| `docs/roadmap/v0.3.0/ir-expansion.md` | Frozen | v0.3.0 | (현재 값 보존) |
| `docs/design/v0.2.0/ir-design-research.md` | Frozen | v0.2.0 | (현재 값 보존) |
| `docs/design/v0.3.0/cli-design-research.md` | Frozen | v0.3.0 | 2026-04-28 |
| `docs/design/v0.3.0/ir-expansion-research.md` | Frozen | v0.3.0 | (현재 값 보존) |
| `docs/implementation/v0.1.0/migration.md` | Frozen | v0.1.0 | (현재 값 보존) |
| `docs/implementation/v0.2.0/stages/stage-1.md` ~ `stage-5.md` (5개) | Frozen | v0.2.0 | (각 현재 값) |
| `docs/implementation/v0.3.0/stages/stage-1.md` ~ `stage-4.md` (4개) | Frozen | v0.3.0 | (각 현재 값) |
| `docs/implementation/v0.3.0/aparse-cleanup.md` | Frozen | v0.3.0 | (현재 값 보존) |
| `docs/verification/v0.1.0/spinoff-review.md` | Frozen | v0.1.0 | (현재 값 보존) |

### Draft (1개)

| 파일 | status | target | last_updated |
|---|---|---|---|
| `docs/roadmap/v0.7.0/mcp.md` | Draft | v0.7.0 | 2026-04-28 |
| `docs/design/v0.7.0/mcp-research.md` | Draft | v0.7.0 | (현재 값 보존) |

### Active (3개)

| 파일 | status | (ga/target 없음) | last_updated |
|---|---|---|---|
| `docs/roadmap/phase-3.md` | Active | — | 2026-04-26 |
| `docs/roadmap/phase-4.md` | Active | — | (현재 값 보존) |
| `docs/upstream/issue-find-control-text-positions.md` | Active | — | (현재 값 보존) |

### Living (frontmatter 없음, 미마이그)

- `docs/CONVENTIONS.md`
- `docs/roadmap/README.md`

### 합계

- Frozen: 17개 파일
- Draft: 2개 파일 (mcp.md + mcp-research.md)
- Active: 3개 파일
- Living: 2개 (frontmatter 없음, 미변경)

= **마이그 대상 22개**, **미변경 2개** (Living)

---

## CONVENTIONS.md 갱신 상세 (D1 / D10 / D11 / D12 / D13 / D-extra)

핵심: 본 PR 의 정책 SSOT. 첫 commit 으로 처리 (다른 모든 변경의 전제).

### 변경 매핑

| Before (line) | After |
|---|---|
| L9 (Living 정의) — 변경 없음 | (그대로) |
| L12 Frozen 정의 — "변경 금지 — 오타·링크 수정만 in-place 허용" | **+ Frozen 면제 조항 추가**: "*예외*: Living-policy schema migration (예: Status header 형식 일괄 갱신, frontmatter 도입) 은 non-semantic 변경으로 간주, in-place 허용. 본 변경은 *전체 spec 일괄* 형태여야 하며 *개별 파일 결정 변경* 이면 supersede 절차를 따른다." |
| L18-31 Status 헤더 형식 (inline `**Status**:` 라인) | **YAML frontmatter 형식으로 전면 갱신** — 본 명세서 § Frontmatter Schema 의 schema 그대로 복사 |
| L77 verification/ 정의 | **약화**: "verification 디렉토리는 **큰 단위 작업** (다단계 stage, 의심 영역) 의 verifier subagent (code-reviewer / test-automator) 산출물 한정. 작은 작업은 git log + PR description 이 SSOT — 작성 생략." |
| L106 "Last updated: 오늘" | **삭제** (자동화 — D3) |
| L114 "Last updated 를 GA 일자로" | **갱신**: "GA 시점 자동 갱신 (D3 hook 이 PR merge commit 날짜로 처리)" |
| L137 "Last updated 갱신" | **삭제** (자동) |
| L161-166 명명 규칙 | **+ 상대경로 형식 한 줄 추가**: "**상대경로**: 같은/하위 디렉토리는 implicit (`foo.md`, `subdir/foo.md`). 상위는 `../foo.md`. `./` prefix 금지 (redundant). 외부 자원만 fully-qualified URL." |
| L177-181 참조 | (그대로 + 본 작업 영감) |

### 새로 추가하는 섹션

#### `## 인수조건 형식 — EARS notation (v0.4.0+ 신규 spec)`

```markdown
v0.4.0+ 신규 spec 의 § 인수조건 섹션은 [EARS notation](https://alistairmavin.com/ears/) (Easy Approach to Requirements Syntax, Rolls-Royce) 5종 키워드로 작성한다. 각 항목에 `AC-N` ID 부여 — 테스트 `pytest.mark.spec("vX.Y.Z/topic#AC-N")` 와 1:1 매핑.

| 패턴 | 형식 | 용도 |
|---|---|---|
| Ubiquitous | `THE {system} SHALL {response}` | 항상 성립 |
| Event-Driven | `WHEN {trigger}, THE {system} SHALL {response}` | 이벤트 시 |
| State-Driven | `WHILE {state}, THE {system} SHALL {response}` | 상태 지속 중 |
| Optional | `WHERE {feature}, THE {system} SHALL {response}` | 옵션 켜진 경우 |
| Unwanted | `IF {condition}, THEN THE {system} SHALL {response}` | 예외/실패 |

기존 v0.1.0 ~ v0.3.0 Frozen spec 은 미변경 — historical record 보존.
```

#### `## 역할 분리 — CHANGELOG ↔ implementation log` (D11)

```markdown
| 문서 | 관점 | 내용 |
|---|---|---|
| CHANGELOG.md | 사용자 (외부) | *what* — 추가/변경/제거된 API, extras, 호환성 영향, 마이그레이션 |
| docs/implementation/.../*.md | 개발자 (내부) | *why/how* — a/b/c 옵션 비교, 시행착오, 결정 근거, Stage별 작업 흐름 |

같은 사실 중복 기록 금지 — CHANGELOG 가 *what*, log 가 *why/how*. 결정 비교 (a/b/c) 가치가 없는 변경 (단순 dep bump, typo) 은 CHANGELOG 한 줄로 충분 — implementation log 작성 안 함.
```

#### `## Frozen 외부 의존성 부패` (D13)

```markdown
Frozen 본문은 historical record. 시간 흐르며 외부 의존성이 deprecated 되어도 본문 변경하지 않는다 — 결정 시점의 정확성을 보존하는 것이 immutability 의 목적. 현재 진실은 *코드* 와 *최신 spec* 이 가짐.
```

#### `## Trace report — pytest spec markers` (D6)

```markdown
v0.4.0+ 부터 테스트는 `pytest.mark.spec("vX.Y.Z/topic#AC-N")` marker 로 spec 인수조건과 1:1 매핑. CI 에서 [scripts/generate_spec_trace.py](scripts/generate_spec_trace.py) 가 매 빌드 시 [docs/traces/coverage.md](../traces/coverage.md) (Living) 자동 갱신 — spec 별 인수조건 ↔ 테스트 mapping 표.

기존 v0.1.0 ~ v0.3.0 Frozen spec 은 AC ID 부여 안 함 — marker 없는 테스트 허용.
```

---

## 새로 추가하는 파일 6종 (D2 / D6 / D7 / D8 / D14)

### 1. `AGENTS.md` (repo 루트, D2)

기존 [CLAUDE.md](../../CLAUDE.md) 본문을 그대로 복사. 본문 변경 없음 — 단순 rename. 본 PR 머지 후 모든 외부 도구 (Codex / Factory / Cursor / Kilo) 가 인식.

### 2. `CLAUDE.md` (1줄 stub, D2)

```markdown
<!-- canonical: AGENTS.md -->
This project's agent context lives in [AGENTS.md](../../AGENTS.md). Claude Code reads both — keeping this stub for backward compatibility.
```

이유: symlink 는 Windows / 일부 git 클라이언트에서 깨짐. 1줄 stub 이 가장 robust. CLAUDE.md 자체가 더 이상 본문 안 가짐 — Single Source of Truth 는 AGENTS.md.

### 3. `docs/upstream-pins.yaml` (D14)

```yaml
# Source of truth for external/rhwp upstream commit pin per release.
# Auto-updated by scripts/update_upstream_pin.py.
# CHANGELOG.md references this file's values in prose.

pins:
  v0.1.0:
    upstream_commit: <기존 값 — git log 에서 추출>
    bumped_at: <YYYY-MM-DD>
  v0.2.0:
    upstream_commit: bea635b
    bumped_at: 2026-04-25
  v0.3.0:
    upstream_commit: 033617e
    previous_commit: bea635b
    commits_integrated: 380
    bumped_at: 2026-04-28
```

### 4. `scripts/update_upstream_pin.py` (D14)

```python
"""external/rhwp 의 현재 commit hash 를 docs/upstream-pins.yaml 에 기록.
릴리스 직전 작업자가 수기 호출 (또는 release workflow 가 호출).

사용:
    uv run python scripts/update_upstream_pin.py vX.Y.Z

동작:
    1. external/rhwp 디렉토리에서 git rev-parse HEAD 추출
    2. 직전 entry 와 commits_integrated 계산 (git log --oneline prev..curr | wc -l)
    3. docs/upstream-pins.yaml 의 pins[vX.Y.Z] 갱신 (또는 신규 추가)
"""
```

### 5. `scripts/lint_docs.py` (D8 / D9)

기존 [.claude/hooks/docs-lint.py](.claude/hooks/docs-lint.py) 의 4개 룰 + 새 룰 5종. CI step 으로 *전체 repo scan*, hook 은 *편집 파일만* 검증.

새 룰:
- frontmatter schema 검증 (status enum / ga ↔ target mutex / superseded_by ↔ status:Superseded mutex)
- 파일명 kebab-case (`ir-expansion.md` ✅, `ir_expansion.md` ❌)
- 디렉토리명 `vX.Y.Z` (SemVer) 형식
- `<topic>.md` ↔ `<topic>-research.md` stem 매칭 (roadmap/vX.Y.Z/foo.md 있으면 design/vX.Y.Z/foo-research.md 도 있어야)
- supersede chain integrity (`superseded_by` 가 가리키는 파일이 존재 + 그 파일의 `supersedes` 가 역참조)

**구현 가이드**:
- `pyyaml` 의존성 추가 (`pyproject.toml [project.optional-dependencies] dev`)
- 기존 `docs-lint.py` 의 hook 진입점은 유지 (편집 시점 즉시 알림)
- `scripts/lint_docs.py` 는 두 entry point: hook (단일 파일) / CLI (전체 scan)
- 공통 로직은 `scripts/_doc_lint.py` 모듈로 분리 (둘이 import)

### 6. `.claude/skills/new-spec/SKILL.md` (D7)

```yaml
---
name: new-spec
description: Scaffold a new version spec and paired ADR following CONVENTIONS.md
argument-hint: <version> <topic>
arguments: [version, topic]
disable-model-invocation: true
---

# /new-spec — 새 spec 스캐폴드

목적: `<version>` (예: `v0.4.0`) + `<topic>` (예: `view-renderer`) 인자로 다음을 일괄 생성.

산출물:
1. `docs/roadmap/<version>/<topic>.md` (frontmatter: status=Draft, target=<version>)
2. `docs/design/<version>/<topic>-research.md` (페어 ADR)
3. `docs/roadmap/README.md` 인덱스 표에 row 추가
4. § 인수조건 (EARS) placeholder 섹션

규칙 (CONVENTIONS.md 정독 후 준수):
- frontmatter schema 정확 적용
- spec ↔ research 페어 외 다른 spec 파일 직접 link 금지
- kebab-case 파일명, vX.Y.Z 디렉토리명

작업 후 `python3 scripts/lint_docs.py` 실행하여 무결성 검증.
```

### 7. `scripts/generate_spec_trace.py` (D6)

```python
"""pytest 의 spec marker 를 collect 하여 docs/traces/coverage.md 갱신.

사용:
    uv run python scripts/generate_spec_trace.py

동작:
    1. pytest --collect-only -q 실행 (테스트 파일 수집)
    2. 각 테스트의 spec marker 추출
    3. spec 별로 그룹화 → 표 생성
    4. docs/traces/coverage.md 작성

출력 형식:
    | Spec | AC | Tests |
    |---|---|---|
    | v0.4.0/view-renderer | AC-1 | tests/test_view.py::test_basic |
"""
```

CI step 추가 (`.github/workflows/ci.yml`):

```yaml
- name: Generate spec trace report
  run: uv run python scripts/generate_spec_trace.py
- name: Verify trace report up to date
  run: git diff --exit-code docs/traces/coverage.md
```

### 8. `docs/traces/coverage.md` placeholder

초기엔 빈 표. CI 가 첫 PR 부터 갱신.

```markdown
# Spec ↔ Test Trace

자동 생성 — `scripts/generate_spec_trace.py`. Living.

(아직 매핑 없음. v0.4.0+ 부터 채워짐.)
```

---

## 변경하는 기존 파일

### `pyproject.toml` (D6)

```toml
[tool.pytest.ini_options]
markers = [
    "spec(spec_id): link this test to a spec acceptance criterion (e.g., 'v0.4.0/cli#AC-3')",
    # ... 기존 markers 보존
]

[project.optional-dependencies]
dev = [
    # ... 기존
    "pyyaml>=6.0",  # spec lint frontmatter 파싱
]
```

### `.claude/hooks/docs-lint.py` (D8 / D9)

기존 4개 룰은 그대로. 변경 사항:
- Status header 검증 (룰 #1) → frontmatter 검증으로 교체
- Living 파일 정의 보존 (`docs/CONVENTIONS.md`, `docs/roadmap/README.md`)
- 새 룰 추가: frontmatter schema, kebab-case, supersede chain
- 공통 로직 `scripts/_doc_lint.py` 로 분리 (CLI 와 hook 둘이 import)

### `.claude/settings.json` (D3)

`last_updated` 자동 갱신 hook 추가:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/docs-lint.py"
          },
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/update-last-updated.py"
          }
        ]
      }
    ]
  }
}
```

### `.claude/hooks/update-last-updated.py` (신규, D3)

```python
"""편집된 docs/*.md 의 frontmatter 의 last_updated 를 오늘 날짜로 갱신.

PostToolUse hook. Living 파일 (CONVENTIONS / roadmap/README) 은 skip.
frontmatter 가 없는 파일도 skip (Living 또는 비-spec).
"""
```

### `.github/workflows/ci.yml` (D6 / D8 / D9)

```yaml
- name: Lint docs
  run: uv run python scripts/lint_docs.py docs/

- name: Verify last_updated freshness
  run: uv run python scripts/lint_docs.py --check-last-updated docs/

- name: Generate spec trace report
  run: uv run python scripts/generate_spec_trace.py
```

### `CHANGELOG.md` ([Unreleased] 섹션)

본 PR 자체를 기록:

```markdown
## [Unreleased]

### Changed — 문서 시스템 대규모 개편

- spec 메타데이터를 inline `**Status**:` 라인에서 YAML frontmatter 로 전면 마이그. 22개 spec 일괄 적용 (Living-policy schema migration — Frozen 면제 조항)
- `AGENTS.md` 를 정본 agent context 파일로 도입 (CLAUDE.md 는 1줄 stub 으로 유지). Codex / Factory / Cursor / Kilo 등 비-Claude 도구 호환
- Spec lint 도구 (`scripts/lint_docs.py`) 신설 — frontmatter schema, 파일명, supersede chain, cross-link 방향성 자동 검증. CI step 추가
- `pytest.mark.spec("vX.Y.Z/topic#AC-N")` marker + 자동 trace report (`docs/traces/coverage.md`) 도입 — v0.4.0+ 신규 spec 부터 적용
- `/new-spec` Claude Code skill 신설 — 새 version spec 스캐폴드 자동화
- `docs/upstream-pins.yaml` SSOT 도입 — external/rhwp 커밋 핀 자동 추출
- CONVENTIONS.md 갱신: EARS notation 인수조건 형식 (v0.4.0+), CHANGELOG ↔ implementation log 역할 분리, 상대경로 명명 규칙, Frozen 외부 의존성 부패 정책
- `last_updated` 자동 갱신 hook (Claude Code PostToolUse + CI 검증)

본 변경은 메타 — 사용자 facing API 영향 0. 내부 문서 운영 체계 정비.
```

---

## 작업 순서 (commit 단위)

단일 PR 안에서 의미 있는 commit 으로 분리. 각 commit 후 사용자 confirmation 받고 다음 진행 (신중성).

### Commit 1: CONVENTIONS.md 정책 갱신 (정책 SSOT 우선)

**파일**: `docs/CONVENTIONS.md` (단독)

**변경**:
- Frozen 면제 조항 추가 (D-extra)
- Status 헤더 형식 → frontmatter 형식 전면 갱신 (D1)
- verification/ 정책 약화 (D10)
- last_updated 자동화 반영 (D3)
- 명명 규칙에 상대경로 형식 추가 (D12)
- 새 섹션: 인수조건 형식 EARS (D4) / CHANGELOG ↔ log 분리 (D11) / Frozen 외부 의존성 부패 (D13) / Trace report (D6)

**검증**:
- 본 commit 자체로 `docs-lint.py` 통과 (Living 파일이라 frontmatter 없어도 OK)
- 본문 self-consistency (예시들이 새 schema 사용)

**Commit message**:
```
docs: CONVENTIONS.md 갱신 — frontmatter schema + 정책 정비

- Status 인라인 형식 → YAML frontmatter (status / ga | target / supersedes / superseded_by / last_updated)
- Frozen 면제 조항 추가 (Living-policy schema migration)
- verification/ 정책 약화 (큰 단위 작업 한정)
- last_updated 자동화로 전환 (수기 갱신 절차 삭제)
- 명명 규칙에 상대경로 implicit 표준 추가
- 신규 섹션: EARS 인수조건 (v0.4.0+) / CHANGELOG ↔ log 분리 / Frozen 외부 의존성 부패 / Trace report

후속 commit 들이 본 정책 따름.
```

---

### Commit 2: AGENTS.md 도입 + CLAUDE.md stub

**파일**:
- 신규 `AGENTS.md` (기존 CLAUDE.md 본문 복사)
- 변경 `CLAUDE.md` (1줄 stub)

**검증**:
- `git mv` 가 아니라 *복사 후 stub 으로 변경* (history 보존). Claude Code 가 양쪽 다 읽으므로 양립

**Commit message**:
```
docs: AGENTS.md 정본화 + CLAUDE.md stub

AGENTS.md 가 2025-12 Linux Foundation/AAIF 표준이 되어 Codex / Factory /
Cursor / Kilo 등이 인식. 본문은 AGENTS.md 가 SSOT, CLAUDE.md 는 1줄 stub
으로 backward compat 유지.
```

---

### Commit 3: 22개 spec 파일 frontmatter 마이그

**파일**: 22개 spec (본 명세서 § 마이그 대상 22개 표 그대로)

**작업**:
- 한 파일씩 read → 기존 inline 메타 정확 추출 → frontmatter 작성 → inline 라인 제거
- *기존 메타 값 정확 보존* (Status / GA / Target / Last updated 모두)
- Frozen 면제 조항 (D-extra) 적용 — 본 commit 이 그 사례

**검증**:
- 22개 파일 각각 `docs-lint.py` 통과
- frontmatter schema 일관 (mutex 위반 없음)
- 기존 본문 의미 변경 0

**Commit message**:
```
docs: 22개 spec frontmatter 마이그 (Frozen 면제 조항 적용)

inline `**Status**:` 라인 → YAML frontmatter. 본문 변경 0.
Living-policy schema migration — Frozen 17개 포함 (CONVENTIONS § Frozen
면제 조항 적용).
```

---

### Commit 4: lint script 확장 + frontmatter 검증 룰

**파일**:
- 신규 `scripts/lint_docs.py` (CLI entry)
- 신규 `scripts/_doc_lint.py` (공통 lib)
- 변경 `.claude/hooks/docs-lint.py` (frontmatter 검증으로 교체 + 새 룰)
- 변경 `pyproject.toml` (`pyyaml` dev 의존성)

**검증**:
- `python3 scripts/lint_docs.py docs/` 전체 repo scan 0 violation
- 기존 hook 룰 (cross-link 방향성, broken link, monorepo 잔재) 동작 보존

**Commit message**:
```
chore: spec lint 확장 — frontmatter / supersede chain / kebab-case 검증

기존 .claude/hooks/docs-lint.py 의 4개 룰을 scripts/_doc_lint.py 공통
lib 로 분리. CLI entry (scripts/lint_docs.py) 신설 — CI 에서 전체 repo
scan. hook 은 편집 파일 단위 즉시 알림 유지.

추가 룰:
- frontmatter schema (status enum / ga ↔ target mutex)
- kebab-case 파일명
- vX.Y.Z 디렉토리 SemVer
- <topic>.md ↔ <topic>-research.md stem 매칭
- supersede chain integrity
```

---

### Commit 5: upstream-pins.yaml + 자동 추출 스크립트

**파일**:
- 신규 `docs/upstream-pins.yaml`
- 신규 `scripts/update_upstream_pin.py`

**검증**:
- 현재 external/rhwp HEAD (`033617e`) 정확
- 과거 v0.1.0 / v0.2.0 commit 도 git log 에서 추출하여 채움 (기존 CHANGELOG 참조)

**Commit message**:
```
chore: upstream-pins.yaml SSOT + 자동 추출 스크립트

external/rhwp 커밋 핀의 SSOT 를 yaml 로 분리. CHANGELOG 는 본 파일을
참조하며 산문 작성 (수기 유지 — 한국어 산문 형식상 완전 자동화 부적절).
```

---

### Commit 6: pytest.mark.spec marker + trace 스크립트

**파일**:
- 변경 `pyproject.toml` (`markers` 등록)
- 신규 `scripts/generate_spec_trace.py`
- 신규 `docs/traces/coverage.md` (placeholder)
- 변경 `.github/workflows/ci.yml` (CI step 추가)

**검증**:
- `pytest --markers` 출력에 `spec` marker 등장
- `python3 scripts/generate_spec_trace.py` 동작 (현재 marker 0건이므로 빈 표)
- CI 통과

**Commit message**:
```
test: pytest.mark.spec marker + 자동 trace report

v0.4.0+ 신규 spec 의 인수조건 ↔ 테스트 매핑 자동화 인프라.
기존 v0.1.0 ~ v0.3.0 Frozen spec 은 marker 없는 테스트 허용.
```

---

### Commit 7: /new-spec slash command (skill)

**파일**:
- 신규 `.claude/skills/new-spec/SKILL.md`

**검증**:
- skill 본문이 CONVENTIONS.md 새 정책 (frontmatter / EARS / 명명) 정확 참조
- placeholder 인수조건 섹션이 EARS 5종 키워드 예시 포함

**Commit message**:
```
feat: /new-spec Claude Code skill — 새 version spec 스캐폴드 자동화

호출: /new-spec <version> <topic>
산출: roadmap/<version>/<topic>.md + design/<version>/<topic>-research.md
+ README 인덱스 row. CONVENTIONS § 새 spec 추가 절차 자동화.
```

---

### Commit 8: last_updated 자동 갱신 hook

**파일**:
- 신규 `.claude/hooks/update-last-updated.py`
- 변경 `.claude/settings.json` (hook 등록)

**검증**:
- 더미 .md 파일 편집 시 frontmatter `last_updated` 가 오늘 날짜로 갱신
- Living 파일 (CONVENTIONS / roadmap README) 은 skip

**Commit message**:
```
chore: last_updated 자동 갱신 hook (Claude Code PostToolUse)

수기 갱신 절차 폐기. CI lint 가 frontmatter `last_updated` 가 git diff
의 마지막 commit 날짜와 일치하는지 검증 — 외부 (수기 git commit) 케이스도
catch.
```

---

### Commit 9: CHANGELOG 갱신 + 명세서 이주

**파일**:
- 변경 `CHANGELOG.md` ([Unreleased] 추가)
- 이동: 본 `OVERHAUL_PLAN.md` → `docs/implementation/spec-system-overhaul.md` (Frozen)
- 삭제: 루트 `OVERHAUL_PLAN.md`

**이주 시 frontmatter 추가**:

```yaml
---
status: Frozen
ga: <PR merge 시 vX.Y.Z 정해지면, 또는 별도 v 부여 — meta 작업이라 Active 버전 외부에 둠>
last_updated: <오늘>
---
```

**문제**: meta 작업은 어떤 vX.Y.Z 에 속하는가?

**해결**: 본 작업을 **`docs/implementation/` 직속 평면** 으로 두되 (vX.Y.Z 외부), CONVENTIONS.md 의 implementation log 구조 정의에 *meta-level / cross-version 작업 슬롯* 한 줄 추가:

```markdown
- `docs/implementation/<topic>.md` (직속 평면, vX.Y.Z 외부) — meta-level
  / cross-version 작업 (예: 문서 시스템 개편). 작성 즉시 Frozen, ga 필드
  생략 가능 (해당 사항 없음).
```

이건 **Commit 1** (CONVENTIONS 갱신) 에 포함하는 게 깔끔. Commit 9 은 그 슬롯 활용.

**Commit message**:
```
docs: CHANGELOG [Unreleased] + spec-system-overhaul 명세서 이주

OVERHAUL_PLAN.md 를 docs/implementation/spec-system-overhaul.md (Frozen)
로 이주. 결정 14개 + a/b/c 비교 historical record 보존.
```

---

## 검증 체크리스트 (PR 머지 전 필수)

- [ ] `python3 scripts/lint_docs.py docs/` — 0 violations
- [ ] `python3 .claude/hooks/docs-lint.py` 가 22개 마이그 파일 모두 통과
- [ ] `uv run pytest -m "not slow"` — 기존 테스트 통과 (regression 없음)
- [ ] `cargo clippy --all-targets -- -D warnings` — Rust 변경 없으나 검증
- [ ] frontmatter schema 일관 (mutex 위반 0 / 모든 파일 status / ga|target / last_updated 보유)
- [ ] AGENTS.md 와 CLAUDE.md 둘 다 존재, CLAUDE.md 가 stub 형태
- [ ] 기존 cross-link 모두 동작 (broken link 0)
- [ ] CONVENTIONS.md 자체가 새 정책 따름 (self-consistency)
- [ ] CHANGELOG [Unreleased] 갱신
- [ ] `OVERHAUL_PLAN.md` 루트에서 삭제, `docs/implementation/spec-system-overhaul.md` 이주
- [ ] CI 모든 step 통과

---

## PR 메시지 초안

**제목**: `docs: spec system overhaul — frontmatter + lint + AGENTS.md + EARS infra`

**Body**:

```markdown
## Summary
- spec 메타데이터를 inline `**Status**:` 라인 → YAML frontmatter 전면 마이그 (22개 파일)
- AGENTS.md 정본화 (CLAUDE.md 는 1줄 stub) — Codex / Factory / Cursor 등 호환
- spec lint 종합 도구 (`scripts/lint_docs.py`) + 기존 `.claude/hooks/docs-lint.py` 확장
- `pytest.mark.spec()` + 자동 trace report 인프라 (v0.4.0+ 부터 사용)
- `/new-spec` Claude Code skill — 새 version spec 스캐폴드 자동화
- `docs/upstream-pins.yaml` SSOT — external/rhwp 커밋 핀
- CONVENTIONS.md 대폭 갱신 (Frozen 면제 조항 / EARS / CHANGELOG ↔ log 분리 / 명명 규칙 / Frozen 외부 의존성 부패)

## Why
2026-04 시점 SDD 트렌드 조사 결과 본 프로젝트는 "Spec-driven + immutable per-version" 디자인은 외부 도구 (Spec-Kit / Kiro / OpenSpec / BMAD) 대비 한 단계 깊으나, *집행* 이 인간 검열 + LLM 협조에만 의존. frontmatter 표준화 + lint 자동화로 같은 디자인을 자동 보장으로 격상.

## Scope
- 사용자 facing API 영향: **0** (메타 작업)
- 외부 의존성 변경: `pyyaml` (dev only)
- breaking 변경: 없음

## Test plan
- [ ] `python3 scripts/lint_docs.py docs/` 통과
- [ ] `uv run pytest -m "not slow"` regression 없음
- [ ] AGENTS.md / CLAUDE.md 양립 (Claude Code 가 양쪽 read)
- [ ] 22개 spec frontmatter schema 일관
- [ ] CI 모든 step 통과 (lint / trace / pytest)

## Related
- 본 PR 의 결정 historical record: `docs/implementation/spec-system-overhaul.md` (Frozen)
- 영감: GitHub Spec-Kit / Kiro EARS / OpenSpec / MADR / Cline Memory Bank
```

---

## 신중성 가이드 (Clean session 작업 시)

본 작업은 **문서 관리 시스템의 터닝포인트**. 매 commit 마다:

1. 변경 파일 list + 핵심 변경 요약 사용자에게 보여주고
2. 다음 step 진행 OK 받고 진행
3. 의심 케이스 (아래) 는 **멈추고 질문**:
   - 22개 마이그 대상 파일 중 *현재 메타 값* 이 명세서와 다르면 (예: 실제 last_updated 값이 다름)
   - frontmatter schema 가 명세서와 안 맞는 케이스 발견 시 (예: status 가 enum 외)
   - 기존 cross-link 이 frontmatter 마이그 후 깨지는 케이스
   - CONVENTIONS.md 자체에 본 작업의 면제 조항이 *제대로 들어갔는지* (자기 모순 점검)

**추측 금지**. 사용자 확인 후 진행.

본 작업의 가장 중요한 **invariant 5종**:
1. 22개 spec 파일의 *현재 메타데이터 값* (Status / GA / Target / Last updated) 정확 보존 — 본 PR 이 결정 변경이 아니라 형식 마이그
2. Frozen 분류 정책 위반 없음 (Living-policy schema migration 면제 조항이 *commit 1 에서* 명문화 — 그 이후 commit 들이 면제 활용)
3. 기존 cross-link 무결성 (broken link 0)
4. 사용자 facing API 영향 0 (메타 작업 — pyproject.toml 도 dev 의존성만 변경)
5. AGENTS.md / CLAUDE.md 양립 — symlink 안 씀, 둘 다 별도 파일

---

## 작업 후 정리 (PR 머지 후)

본 명세서 자체:
- Commit 9 에서 `docs/implementation/spec-system-overhaul.md` (Frozen) 로 이주 완료
- 루트 `OVERHAUL_PLAN.md` 삭제 완료
- 본 작업의 a/b/c 비교 historical record 는 implementation log 가 보유

후속 작업 (별도 PR):
- v0.4.0 신규 spec 작성 시 `/new-spec v0.4.0 view-renderer` 활용 — EARS 인수조건 도입 첫 사례
- archive sed 스크립트 작성 (v1.0 GA 가까울 때)
- CHANGELOG 정리 — 기존 v0.3.0 섹션의 *why/how* 부분을 implementation log 로 이주 (선택, 큰 작업이라 별도)

---

## 메타 — 본 명세서의 의의

본 작업은 **single PR로 14개 결정 일괄 적용**하는 의도적 큰 변화. 분할 PR (10개) 은 review burden 분산이 가능하나:
- 각 PR 의 정합성 검증이 어려움 (D1 schema 가 D6/D7/D8/D9 의 입력인데 PR 분리 시 race)
- 머지 순서 관리 부담
- 본 작업의 *terminal point* (PR 9 까지 다 머지된 후에야 새 시스템 동작) 가 시간 분산되면 그 사이 어색한 상태

→ 단일 PR 로 atomic 하게. 각 commit 단위로 review 는 가능 (`git log -p` 또는 PR 의 commit-by-commit view).

---

본 명세서 끝.
