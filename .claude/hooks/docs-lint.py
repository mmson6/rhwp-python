#!/usr/bin/env python3
"""docs/*.md 편집 후 자동 검증 — CONVENTIONS.md 정책 enforcement.

PostToolUse hook 으로 Edit / Write / MultiEdit 후 실행. stdin 으로 받은 hook
event 의 ``tool_input.file_path`` 가 ``docs/*.md`` 면 검증, 그 외는 즉시 종료.

검증 항목 (CONVENTIONS.md 의 hard rule 4 종):

1. **Status 헤더** — Living 외 모든 spec 은 ``**Status**: ...`` 메타 라인 보유
2. **업스트림 monorepo 잔재 키워드** — 분사 리포 컨벤션 위배 (``사용자 Fork`` /
   ``rhwp 본체`` / ``pyo3-sandbox`` 등). v0.1.0 historical Frozen 본문은 예외
3. **같은 vX.Y.Z 디렉토리 내 spec ↔ spec 직접 link** — pair 페어
   (``<topic>.md`` ↔ ``<topic>-research.md``) 만 예외
4. **깨진 .md 링크** — relative path 가 실제 파일을 가리키는지

위반 발견 시 exit 2 + stderr — Claude Code 가 stderr 를 LLM 컨텍스트에
주입하여 모델이 위반 사항을 인지하고 후속 조치 결정. exit 1 은 non-blocking
이라 LLM 에 노출되지 않으므로 사용 금지 (hooks 명세).
"""

import json
import re
import sys
from pathlib import Path

# * stdin 에서 hook event 파싱
try:
    event = json.loads(sys.stdin.read() or "{}")
except json.JSONDecodeError:
    sys.exit(0)

tool_input = event.get("tool_input") or {}
file_path = tool_input.get("file_path") or ""
if not file_path:
    sys.exit(0)

repo = Path(__file__).resolve().parents[2]
try:
    rel = Path(file_path).resolve().relative_to(repo)
except ValueError:
    sys.exit(0)

rel_str = str(rel).replace("\\", "/")
if not (rel_str.startswith("docs/") and rel.suffix == ".md"):
    sys.exit(0)

target = repo / rel
if not target.is_file():
    sys.exit(0)

text = target.read_text(encoding="utf-8")
errors: list[str] = []


# * 1. Status metadata (YAML frontmatter or legacy inline) — required outside Living docs
# ^ Commit 3 (spec-system-overhaul): accept either YAML frontmatter or legacy inline
#   format during the transition. Commit 4 will tighten to frontmatter-only + add
#   schema validation (status enum, ga ↔ target mutex, supersede chain).
LIVING_FILES = {"docs/CONVENTIONS.md", "docs/roadmap/README.md"}
if rel_str not in LIVING_FILES:
    has_inline = re.search(r"^\*\*Status\*\*:", text, re.MULTILINE)
    has_frontmatter = text.startswith("---\n") and re.search(r"^status:\s*", text, re.MULTILINE)
    if not (has_inline or has_frontmatter):
        errors.append(
            "missing Status metadata — add YAML frontmatter "
            "'---\\nstatus: <Active|Draft|Frozen|Superseded>\\n"
            "ga|target: vX.Y.Z\\nlast_updated: YYYY-MM-DD\\n---' "
            "(CONVENTIONS § Status 메타데이터)"
        )


# * 2. Upstream monorepo residue keywords (v0.1.0 Frozen historical exempted)
HISTORICAL_FROZEN = ("docs/implementation/v0.1.0/",)
if not any(rel_str.startswith(p) for p in HISTORICAL_FROZEN):
    forbidden = [
        "사용자 Fork",
        "rhwp 본체",
        "pyo3-sandbox",
        "/Cargo.toml (루트)",
        "pyo3-bindings.md",
    ]
    for kw in forbidden:
        if kw in text:
            errors.append(
                f"upstream monorepo residue keyword {kw!r} — "
                "this is a spinoff binding repo, not the source-of-truth repo"
            )


# * 3. Same-version spec ↔ spec direct link (pair files exempted)
# ^ SemVer 정확 매칭 (vMAJOR.MINOR.PATCH) — 이전의 [\d.]+ 기반은 catastrophic
#   backtracking 위험 (CodeQL py/redos). v0.3.0 / v0.3.1 등 모두 cover.
m = re.match(r"docs/(roadmap|design)/(v\d+\.\d+\.\d+)/(.+)\.md$", rel_str)
if m:
    base = m.group(3)
    pair_topic = base.removesuffix("-research")
    # ^ pair: <topic>.md ↔ <topic>-research.md (the only allowed direct link)
    if base.endswith("-research"):
        allowed_link = f"{pair_topic}.md"
    else:
        allowed_link = f"{base}-research.md"
    self_link = f"{base}.md"
    for link in re.findall(r"\]\(([^)]+\.md)[^)]*\)", text):
        link_target = link.split("#")[0]
        # only same-directory .md candidates qualify
        if "/" in link_target:
            continue
        if link_target in (allowed_link, self_link):
            continue
        errors.append(
            f"same-version spec direct link {link!r} — "
            "route through phase-N.md or roadmap/README.md "
            "(CONVENTIONS § Cross-link direction rule)"
        )


# * 4. Broken .md link
dir_path = target.parent
for link in re.findall(r"\]\(([^)]+\.md)[^)]*\)", text):
    link_target = link.split("#")[0].split("?")[0]
    if not link_target or link_target.startswith("http"):
        continue
    resolved = (dir_path / link_target).resolve()
    if not resolved.exists():
        errors.append(f"broken .md link {link!r} (resolved: {resolved})")


if errors:
    sys.stderr.write(f"\ndocs-lint: {rel_str} — {len(errors)} violation(s)\n")
    for i, e in enumerate(errors, 1):
        sys.stderr.write(f"  {i}. {e}\n")
    sys.stderr.write("policy: docs/CONVENTIONS.md\n")
    sys.exit(2)
