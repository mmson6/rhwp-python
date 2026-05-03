# Spec body writing rules — `docs/roadmap/vX.Y.Z/<topic>.md`

Section-by-section rules for filling placeholders in `templates/spec.md`. Loaded by `/new-spec` skill (step 2) alongside the template. Same rules apply to manual writes and Frozen-spec typo fixes. Final output is Korean — keep Korean section headers and standard phrases verbatim.

## Per-section rules

### Title — single phrase

- Format: `# v<X.Y.Z> — <topic phrase>`
- Single phrase preferred. Avoid combinations (`+` / `and`) — if combination feels needed, compress to a more abstract phrase
- Parenthetical subtitle allowed. Example: `# v0.3.0 — Document IR v1.1 (블록 타입 확장)`

### Intro — core summary only, no scattered detail

The most-violated rule:

- **Include**: spec's *core summary* (why + what + impact). Compatibility guarantees (schema / API / behavior unchanged)
- **OK to inline** (precedent: v0.1.0 #227, v0.3.1 #405, v0.3.2 #494):
  - *Single enabling change reference* — one PR / Issue / commit link that triggered the spec ("why now")
  - Version numbers (e.g. `v0.7.8`) — not raw commit hashes
  - Short method signatures / code refs when essential to "what changed"
- **Exclude** (no baseline ever has these in intro):
  - *Multiple* PR numbers / commit hashes scattered through the intro
  - Specific calendar dates (e.g. `2026-04-30`)
  - Inline policy quotes (block quote of project policy text)
  - Work breakdown enums `(1)(2)(3)...` — these belong in **결정 사항 table cells** or **ADR §N**
- Length scales with spec size:
  - PATCH: 1–2 paragraphs
  - MINOR: separate `## 배경` section allowed (precedent: v0.2.0/ir.md, v0.3.0/ir-expansion.md)
  - If intro exceeds 3 paragraphs OR mixes distinct sub-topics (e.g. "방향 전환 배경" + "current work"), split into separate sections

### Pair link — standard phrase

- Exact wording (Korean, verbatim): `주요 결정의 근거·대안·실패 시나리오는 짝 페어: [<topic>-research.md](../../design/vX.Y.Z/<topic>-research.md).`
- Required when ADR exists (PATCH / MINOR alike)
- No variant phrasings (`별도`, `관련 문서`, etc.) — standard phrase only

### 결정 사항 — table (`항목 / 값 / 근거`)

- Item format: `N — <label>` (e.g. `1 — API source`)
- 값 (value): single phrase or short sentence
- 근거 (rationale): 1–3 sentences
  - For longer comparison or option analysis, defer to ADR §N and add a one-line `자세한 본체 비교는 ADR §N` pointer in the cell
  - External citations (commit hash / PR # / date) inline OK — these are the details deferred from the intro

### 인수조건 — AC-N IDs + behavior-driven

- Each item: `**AC-N** — <statement>` format (CONVENTIONS § 인수조건 형식 — 1:1 with pytest markers)
- **Behavior-driven preferred** — input → output verification
- Avoid structural negatives (`<code/function/variable> does not exist`) — those are grep checks, not behavior
- Good: `AC-3 — 마지막 char_shape 의 end_utf16 = u32::MAX 인 paragraph 에서 출고 InlineRun.end_cp == para.text.chars().count()` (verifies behavior)
- Bad: `AC-3 — short-circuit 분기가 호출부에 남아있지 않다` (grep check)

### 영구 비목표 — preempt reader questions

- Items outside this spec's scope but *plausibly asked by external readers*
- Not just a "not doing" list — pair each item with **the reason** (why it's not in this spec)
- Must be consistent with 결정 사항 — if 결정 사항 entry 8 appears in 영구 비목표, that's a contradiction

### 참조

- Pair (ADR), upstream PRs / issues, precedent specs, policy citations
- *spec ↔ spec direct links forbidden* (CONVENTIONS § Cross-link 방향성) — pair files are the only exception

## Cross-cutting policies (CONVENTIONS.md SSOT)

- § 섹션 역할 분리 — info routing across spec / ADR / CHANGELOG / implementation log
- § Status 메타데이터 — frontmatter schema (status / target / ga / last_updated / description quoting)
- § 인수조건 형식 — AC-N ID applicability cutoff
- § 명명 규칙 — kebab-case, `vX.Y.Z` directories

## Effective from

These rules apply to specs newly authored after the effective date (2026-05-03). Existing Frozen specs (v0.1.0 ~ v0.3.1) are not retrofitted — Frozen body immutability takes priority.
