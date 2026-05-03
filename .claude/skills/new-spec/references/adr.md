# ADR writing rules — `docs/design/vX.Y.Z/<topic>-research.md`

Section-by-section rules for filling placeholders in `templates/adr.md`. Loaded by `/new-spec` skill (step 2) alongside the template. ADR is paired 1:1 with the spec body — asymmetry between this reference and `references/spec.md` weakens the pair-file discipline. Final output is Korean — keep Korean section headers and standard phrases verbatim.

## Per-section rules

### Title — standard phrase

- Format: `# v<X.Y.Z> <topic> — 설계 의사결정 리서치 요약`
- No variants (`설계 결정 문서`, `의사결정 기록`, etc.)

### Intro — standard phrase

- Exact wording (one paragraph, Korean verbatim):
  > [<X.Y.Z>/<topic>.md](../../roadmap/vX.Y.Z/<topic>.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 **N**건의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.
- Substitute **N** with the actual decision count (`4건` for 4 items)
- No comparative narrative or meta commentary in the intro (e.g. "본 ADR 은 v0.3.1 와 비슷하다") — such comparisons belong inside the §N four-subsection blocks

### 결정 매트릭스 — table (`# / 항목 / 옵션 비교 / 채택 / 1차 근거`)

- `#` = 1, 2, 3 ... (1:1 with §N decision sections)
- 항목: decision label (must match the spec body 결정 사항 cell label exactly)
- 옵션 비교: terse phrasing `A: <label> / B: <label> / C: <label>` — detailed comparison goes in §N
- 채택: single letter `A` / `B` / `C`
- 1차 근거: one-phrase reason for adoption — full reasoning chain goes in §N

### `## N. <decision item>` — fixed four-subsection order

For each decision, write all four subsections in this exact order:

#### `### 팩트` (Facts)

- Measurable / citable facts
- No opinions or decision statements ("좋다", "권장된다", etc.)
- Citations: `<file>:<line>` or external URLs — no one-line speculation

#### `### 검증자 반박` (Validator counter-arguments)

- Questions a critical reader would ask + answers
- Self-expose the decision's weak points — be honest, not defensive
- Format: `- "Question?" → answer`

#### `### 최종 결정` (Final decision)

- Which option (A/B/C) + 1–2 sentence core reasoning
- Must match the "채택" column of the decision matrix

#### `### 1차 소스` (Primary sources)

- External citable sources — upstream PRs / commits / RFCs / W3C / IETF / official docs
- Avoid secondary sources (blogs / SEO posts)
- No personal-machine paths (`~/.claude/...`, etc.) — invisible to external readers

### 참조

- Pair (spec body), external PRs / issues / standards
- *spec ↔ spec direct links forbidden* — pair files are the only exception

## Cross-cutting policies (CONVENTIONS.md SSOT)

- § 섹션 역할 분리 — info routing between spec and ADR
- § Status 메타데이터 — frontmatter schema
- § Cross-link 방향성 — spec ↔ spec direct link prohibition

## Effective from

These rules apply to ADRs newly authored after the effective date (2026-05-03). Existing Frozen ADRs are not retrofitted.
