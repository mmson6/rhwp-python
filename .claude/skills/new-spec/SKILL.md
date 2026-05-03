---
name: new-spec
description: Scaffold a new version spec and paired ADR following docs/CONVENTIONS.md. Invoke when the user wants to start a new version spec (e.g. "v0.4.0 view 렌더러 시작", "phase 3 첫 spec"). Idempotent — aborts if spec already exists. State the version + topic before invoking and wait for user confirmation.
argument-hint: <version> <topic>
arguments:
  - version
  - topic
---

# /new-spec — scaffold a new version spec

Given `<version>` (e.g. `v0.4.0`) and `<topic>` (e.g. `view-renderer`), create a new per-version spec, its paired ADR (design research), and the index entry in one shot.

## Outputs

1. `docs/roadmap/<version>/<topic>.md` — the spec body (frontmatter `status: Draft`, `target: <version>`)
2. `docs/design/<version>/<topic>-research.md` — the paired ADR (same frontmatter)
3. `docs/roadmap/README.md` — append a row to the active spec index table

## Procedure

When this skill is invoked, execute the following steps in order:

1. **Validate arguments**
   - `version` must match the SemVer pattern `vX.Y.Z`
   - `topic` must be kebab-case (`[a-z0-9]+(-[a-z0-9]+)*`)
   - Abort if `docs/roadmap/<version>/<topic>.md` already exists — never overwrite an existing spec

2. **Read the four files** which are the SSOT for body structure:
   - [`templates/spec.md`](templates/spec.md) — spec body skeleton (placeholder 만, 직접 복사 대상)
   - [`templates/adr.md`](templates/adr.md) — ADR skeleton (placeholder 만, 직접 복사 대상)
   - [`references/spec.md`](references/spec.md) — spec body 섹션별 작성 룰 (title 단일 phrase, 인트로 핵심 요약만 디테일 제외, AC-N behavior-driven 등)
   - [`references/adr.md`](references/adr.md) — ADR 섹션별 작성 룰 (인트로 표준 phrase, 4-소절 (`### 팩트` / `### 검증자 반박` / `### 최종 결정` / `### 1차 소스`))

   Also re-read `docs/CONVENTIONS.md` for cross-cutting policy: § Status 메타데이터 (frontmatter schema), § 섹션 역할 분리 (정보 배치 룩업), § Cross-link 방향성 규칙, § 명명 규칙, § 인수조건 형식. Conventions are Living and may have evolved since the last skill invocation.

3. **Create directories** if missing:
   - `docs/roadmap/<version>/`
   - `docs/design/<version>/`

4. **Write `docs/roadmap/<version>/<topic>.md`** by copying [`templates/spec.md`](templates/spec.md) verbatim and substituting placeholders (`<version>` / `<topic>` / `<topic phrase>` / 인트로 prose / 결정 사항 표 entries / AC bullets / 영구 비목표 bullets). Apply [`references/spec.md`](references/spec.md) 섹션별 작성 룰 — *especially* 인트로 룰 (디테일 제외, 결정 사항 표 셀로 미룸), which is the most-violated rule.

5. **Write `docs/design/<version>/<topic>-research.md`** by copying [`templates/adr.md`](templates/adr.md) verbatim and substituting placeholders. Apply [`references/adr.md`](references/adr.md) 섹션별 작성 룰 — *especially* 인트로 표준 phrase (정확한 표현 + meta narrative 첨가 금지) and 4-소절 고정 순서.

6. **Append a row to `docs/roadmap/README.md`** in the active spec index table (find `## 활성 spec 인덱스` section, add at the end of the table):

   ```markdown
   | <version> (<topic>) | Draft | [<version>/<topic>.md](<version>/<topic>.md) | [design/<version>/<topic>-research.md](../design/<version>/<topic>-research.md) |
   ```

7. **Run integrity check**: `uv run --no-project --with "typer>=0.12" python scripts/lint_docs.py docs/`. If violations are reported, surface them to the user and propose corrections — do not silently fix.

8. **Spawn fresh-context architect-reviewer subagent** for independent review (작성자 ≠ 검증자 원칙). Use the `Agent` tool with `subagent_type: "architect-reviewer"` and a self-contained prompt that includes:
   - Project context (rhwp-python, spec-driven release model, `docs/CONVENTIONS.md` SSOT)
   - The exact paths of the new spec body, paired ADR, and the README index row
   - Cross-check sources to read (`docs/CONVENTIONS.md` for convention compliance, primary code/files relevant to the spec's technical claims)
   - Explicit ask: P0/P1/P2 findings with file:line citations covering — (a) internal consistency (decisions ↔ ACs ↔ ADR matrix), (b) convention compliance, (c) technical accuracy of upstream/code claims, (d) logical gaps / unstated assumptions, (e) scope discipline (anything in spec that's actually a future version's work, anything in non-goals that's actually in scope)
   - Output verdict: `APPROVE` / `REQUEST CHANGES` / `REJECT`
   - Length cap (~600 words)

   Surface findings verbatim to the user. **Do not silently apply fixes** — the user reviews the findings and decides which to address. False-positive rate is non-zero (~30% in practice); the user is the final arbiter. After fixes, re-run lint (step 7) and re-run review (step 8) only if the user requests a second pass — don't auto-loop.

## Rules (must comply with `docs/CONVENTIONS.md`)

본 § 는 quick-reference 만 — 권위 SSOT 는 `docs/CONVENTIONS.md`. 재인용된 룰이 본 파일과 SSOT 사이에서 drift 하면 SSOT 가 우선.

- **Frontmatter schema** (§ Status 메타데이터): `status` enum / `target` SemVer (Draft 시) / `last_updated` `YYYY-MM-DD` / description quoting (큰따옴표 + inline identifier 작은따옴표)
- **Body structure SSOT** (§ Spec 본문 구조 + § ADR 본문 구조): 본 skill 의 step 4 / 5 skeleton 은 *구조* 만, *내용 룰* 은 CONVENTIONS § 가 SSOT
- **정보 배치** (§ 섹션 역할 분리): 디테일은 인트로 아닌 결정 사항 표 셀, 옵션 비교는 ADR §N 4-소절
- **Cross-link 방향성** (§ Cross-link 방향성 규칙): 짝 페어만 spec ↔ spec 직접 링크 허용. 다른 spec ↔ spec 직접 링크 금지 — README 경유
- **명명** (§ 명명 규칙): kebab-case 파일명, `vX.Y.Z` 디렉토리, `./` prefix 금지, 외부만 fully-qualified URL

## Limits

- Skeletons in step 4 / 5 are *structural* — actual decisions / acceptance criteria / non-goals / decision matrix entries must be filled per CONVENTIONS § Spec 본문 구조 + § ADR 본문 구조 (not by mimicking recent specs)
- This skill automates **structural consistency** (frontmatter / pair / index / skeleton, step 1–7) and **delegates independent review** (step 8) — but content judgment, accept/reject of reviewer findings, and any fix application remain the user's call. False-positive rate of the reviewer is non-zero; never blindly accept.
- Auto-spawned review (step 8) is intentional for *new spec* creation (high-stakes, low-frequency, Frozen-after-GA). Other skills (commit-message / docstring-edit / etc.) should NOT copy this pattern by default — verifier-spawn cost is justified only when miss-cost outweighs invocation overhead.
