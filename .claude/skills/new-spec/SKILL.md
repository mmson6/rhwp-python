---
name: new-spec
description: Scaffold a new version spec and paired ADR following docs/CONVENTIONS.md
argument-hint: <version> <topic>
arguments:
  - version
  - topic
disable-model-invocation: true
---

# /new-spec — scaffold a new version spec

Given `<version>` (e.g. `v0.4.0`) and `<topic>` (e.g. `view-renderer`), create a new per-version spec, its paired ADR (design research), and the index entry in one shot.

## Outputs

1. `docs/roadmap/<version>/<topic>.md` — the spec body (frontmatter `status: Draft`, `target: <version>`)
2. `docs/design/<version>/<topic>-research.md` — the paired ADR (same frontmatter)
3. `docs/roadmap/README.md` — append a row to the active spec index table
4. EARS notation placeholder section inside the spec body

## Procedure

When this skill is invoked, execute the following steps in order:

1. **Validate arguments**
   - `version` must match the SemVer pattern `vX.Y.Z`
   - `topic` must be kebab-case (`[a-z0-9]+(-[a-z0-9]+)*`)
   - Abort if `docs/roadmap/<version>/<topic>.md` already exists — never overwrite an existing spec

2. **Re-read `docs/CONVENTIONS.md`** before writing — apply the current frontmatter schema, naming rules, cross-link direction, and EARS notation section. Conventions may have evolved since the last skill invocation.

3. **Create directories** if missing:
   - `docs/roadmap/<version>/`
   - `docs/design/<version>/`

4. **Write `docs/roadmap/<version>/<topic>.md`** using this template (placeholders in `<...>` must be filled by Claude based on user intent; section headers and Korean prose stay as-is — they become Korean docs):

   ```markdown
   ---
   status: Draft
   target: <version>
   last_updated: <today YYYY-MM-DD>
   ---

   # <version> — <Korean summary title for the topic>

   <One paragraph in Korean — what this spec introduces and why>.

   주요 결정의 근거·대안·실패 시나리오는 짝 페어: [<topic>-research.md](../../design/<version>/<topic>-research.md).

   ## 결정 사항

   | 항목 | 값 | 근거 |
   |---|---|---|
   | 1 | (placeholder) | (placeholder) |

   ## 인수조건

   <!-- EARS notation (CONVENTIONS § 인수조건 형식) — assign AC-N IDs;
        each maps 1:1 to a `pytest.mark.spec("<version>/<topic>#AC-N")` -->

   - **AC-1** (Ubiquitous) — `THE <system> SHALL <response>`
   - **AC-2** (Event-Driven) — `WHEN <trigger>, THE <system> SHALL <response>`
   - **AC-3** (State-Driven) — `WHILE <state>, THE <system> SHALL <response>`
   - **AC-4** (Optional) — `WHERE <feature>, THE <system> SHALL <response>`
   - **AC-5** (Unwanted) — `IF <condition>, THEN THE <system> SHALL <response>`

   ## 영구 비목표

   - <items explicitly out of scope for this spec>

   ## 참조

   - 짝 페어 (ADR): [<topic>-research.md](../../design/<version>/<topic>-research.md)
   ```

5. **Write `docs/design/<version>/<topic>-research.md`** using this template:

   ```markdown
   ---
   status: Draft
   target: <version>
   last_updated: <today YYYY-MM-DD>
   ---

   # <version> <topic> — 설계 의사결정 리서치 요약

   [<version>/<topic>.md](../../roadmap/<version>/<topic>.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 N건의 업계 선례·대안·실패 시나리오를 기록한다. <topic>.md 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

   ## 결정 매트릭스

   | # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
   |---|---|---|---|---|
   | 1 | (placeholder) | A: ... / B: ... / C: ... | (?) | (?) |

   ## 1. <first decision item>

   ### 팩트
   ### 검증자 반박
   ### 최종 결정
   ### 1차 소스

   ## 참조

   - [roadmap/<version>/<topic>.md](../../roadmap/<version>/<topic>.md) — 본 리서치의 결정 요약
   ```

6. **Append a row to `docs/roadmap/README.md`** in the active spec index table (find `## 활성 spec 인덱스` section, add at the end of the table):

   ```markdown
   | <version> (<topic>) | Draft | [<version>/<topic>.md](<version>/<topic>.md) | [design/<version>/<topic>-research.md](../design/<version>/<topic>-research.md) |
   ```

7. **Run integrity check**: `uv run --no-project --with "typer>=0.12" python scripts/lint_docs.py docs/`. If violations are reported, surface them to the user and propose corrections — do not silently fix.

## Rules (must comply with `docs/CONVENTIONS.md`)

- Frontmatter schema: `status` enum, `target` SemVer, `last_updated` `YYYY-MM-DD`
- Spec ↔ research pair files may link directly; **all other spec ↔ spec direct links are forbidden** — route through index pages
- Filenames must be kebab-case; directories use `vX.Y.Z` SemVer
- Relative paths are implicit (`foo.md`, `subdir/foo.md`); no `./` prefix; external resources use fully-qualified URLs

## Limits

- Spec body and decision matrix are placeholders — actual decisions / acceptance criteria / non-goals must be filled by the user
- This skill automates **structural consistency** only (frontmatter / pair / index / EARS placeholder). Content judgment is the user's.
