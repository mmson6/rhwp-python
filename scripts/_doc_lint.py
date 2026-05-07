"""docs lint shared library — used by .claude/hooks/docs-lint.py (single file)
and scripts/lint_docs.py (whole repo scan).

CONVENTIONS.md 정책 enforcement. 룰 일람:

1. **Frontmatter (YAML)** — Living 외 모든 spec
   - status enum: Active / Draft / Frozen / Superseded
   - last_updated: YYYY-MM-DD (필수)
   - description: 필수 (non-empty string)
   - status:Active → ga / target 둘 다 금지
   - status:Draft → target 필수, ga 금지
   - status:Frozen → ga 필수 (예외: meta-level docs/implementation/<topic>.md /
     resolved docs/upstream/<topic>.md / pre-GA stage log)
   - status:Frozen + target 허용 — `docs/implementation/vX.Y.Z/...` 경로의 pre-GA
     stage log 에 한해 (CONVENTIONS § Implementation log 구조 § 131). 본문은
     작성 즉시 immutable 이지만 부모 버전 GA 전까지 release 라벨 미부여 — Rust
     RFC / PEP / ADR 의 editorial vs release 차원 분리 패턴
   - status:Superseded → ga 필수 + superseded_by 필수
   - ga ↔ target mutex (단, Frozen pre-GA stage 예외)
   - ga / target SemVer (vX.Y.Z)
2. **Supersede chain integrity** — superseded_by 가 가리키는 파일이 실재 +
   해당 파일의 supersedes 가 역참조
3. **파일명 kebab-case** — README / CONVENTIONS 등 ALL-CAPS 는 예외
4. **vX.Y.Z 디렉토리 SemVer** — v 로 시작하는 디렉토리는 SemVer 정확
5. **<topic>.md ↔ <topic>-research.md 페어** — roadmap ↔ design 동시 존재
6. **upstream monorepo 잔재 키워드** — v0.1.0 historical 예외
7. **same-version spec ↔ spec direct link** — pair 페어만 예외
8. **broken .md link** — relative path 가 실제 파일을 가리키는지
"""

import re
from pathlib import Path

# * 정책 상수
LIVING_FILES = {
    "docs/CONVENTIONS.md",
    "docs/roadmap/README.md",
    "docs/traces/coverage.md",
    "docs/upstream/README.md",
}
HISTORICAL_FROZEN_PREFIXES = ("docs/implementation/v0.1.0/",)
FORBIDDEN_KEYWORDS = (
    "사용자 Fork",
    "rhwp 본체",
    "pyo3-sandbox",
    "/Cargo.toml (루트)",
    "pyo3-bindings.md",
)
STATUS_ENUM = {"Active", "Draft", "Frozen", "Superseded"}


# * frontmatter 파서 — flat key:value 한정 (멀티라인 / 중첩 미지원)
def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse simple YAML frontmatter at the top of `text`.

    Returns ``None`` if no ``---``-delimited block is present at the start.
    Comments (``# ...``) and blank lines are skipped. Values are stripped of
    surrounding whitespace and unwrapped from matching single/double quotes.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    block = text[4:end]
    meta: dict[str, str] = {}
    for raw in block.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        # ^ trailing inline comment ('foo: bar  # note') strip — quoted value 안의
        #   '#' 는 보호 (flat key:value 가정상 quote 처리 후 안전)
        if not (v.startswith(("'", '"'))):
            v = v.split(" #", 1)[0].rstrip()
        # ^ 양쪽 동일 quote 만 unwrap (mismatched 는 그대로)
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        meta[k.strip()] = v
    return meta


# * code fence stripper — fence 안 예시 link / 백틱 인라인 link 를 lint 대상에서 배제
def _strip_code(text: str) -> str:
    """Remove ```...``` 블록 + 인라인 `...` 백틱. lint regex 는 raw text 가
    아니라 본 출력에 적용 — fence 안 예시 link 가 broken/cross-link 위반으로
    오인식되는 false positive 방지."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


# * Rule 1+2: frontmatter schema + supersede chain
def validate_frontmatter(rel_str: str, meta: dict[str, str], repo: Path) -> list[str]:
    errors: list[str] = []

    status = meta.get("status")
    if not status:
        return ["frontmatter: missing 'status' field"]
    if status not in STATUS_ENUM:
        return [f"frontmatter: invalid 'status' {status!r} — must be one of {sorted(STATUS_ENUM)}"]

    last_updated = meta.get("last_updated", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_updated):
        errors.append(f"frontmatter: 'last_updated' must be YYYY-MM-DD (got {last_updated!r})")

    if not meta.get("description", "").strip():
        errors.append("frontmatter: 'description' is required (non-empty string)")

    has_ga = "ga" in meta
    has_target = "target" in meta

    if status == "Active":
        if has_ga or has_target:
            errors.append("frontmatter: status:Active forbids 'ga' and 'target'")
    elif status == "Draft":
        if not has_target:
            errors.append("frontmatter: status:Draft requires 'target'")
        if has_ga:
            errors.append("frontmatter: status:Draft forbids 'ga' (use 'target')")
    elif status == "Frozen":
        # ^ 면제: meta-level (vX.Y.Z 외부) implementation, resolved upstream
        is_meta_level = rel_str.startswith("docs/implementation/") and not re.match(
            r"docs/implementation/v\d+\.\d+\.\d+/", rel_str
        )
        is_upstream_resolved = rel_str.startswith("docs/upstream/")
        # ^ 면제: pre-GA stage log — CONVENTIONS § Implementation log 구조 § 131.
        #   Rust RFC / PEP / ADR 와 동일한 editorial vs release 차원 분리 패턴.
        #   stage 본문은 작성 즉시 immutable (= Frozen) 이지만 부모 버전 GA 전까지
        #   ga 라벨 미부여 — 그 구간에는 target 으로 표기. GA 시점 일괄 target → ga.
        is_pre_ga_stage = (
            re.match(r"docs/implementation/v\d+\.\d+\.\d+/", rel_str) is not None
            and has_target
            and not has_ga
        )
        if not has_ga:
            if not (is_meta_level or is_upstream_resolved or is_pre_ga_stage):
                errors.append(
                    "frontmatter: status:Frozen requires 'ga' "
                    "(except meta-level docs/implementation/<topic>.md, "
                    "docs/upstream/<topic>.md, and pre-GA stage log)"
                )
        if has_target and not is_pre_ga_stage:
            errors.append("frontmatter: status:Frozen forbids 'target'")
    elif status == "Superseded":
        if not has_ga:
            errors.append("frontmatter: status:Superseded requires 'ga' (preserved)")
        if has_target:
            errors.append("frontmatter: status:Superseded forbids 'target'")
        if "superseded_by" not in meta:
            errors.append("frontmatter: status:Superseded requires 'superseded_by'")

    if has_ga and has_target:
        errors.append("frontmatter: 'ga' and 'target' are mutually exclusive")

    for field in ("ga", "target"):
        val = meta.get(field, "")
        if val and not re.fullmatch(r"v\d+\.\d+\.\d+", val):
            errors.append(f"frontmatter: {field!r} must be SemVer 'vX.Y.Z' (got {val!r})")

    errors.extend(_validate_supersede_chain(rel_str, meta, repo))
    return errors


def _validate_supersede_chain(rel_str: str, meta: dict[str, str], repo: Path) -> list[str]:
    errors: list[str] = []
    rel = Path(rel_str)

    superseded_by = meta.get("superseded_by")
    # ^ supersede 경로 base: vX.Y.Z 하위면 docs/<kind>/, meta-level 평면이면 docs/<kind>/
    #   format: vX.Y.Z 파일은 '<vX.Y.Z>/<topic>.md', meta-level 은 '<topic>.md'.
    base, expected = _supersede_base(rel)

    if superseded_by:
        target_rel = base / superseded_by
        target = repo / target_rel
        if not target.exists():
            errors.append(
                f"frontmatter: superseded_by {superseded_by!r} not found (resolved: {target_rel})"
            )
        else:
            target_meta = parse_frontmatter(target.read_text(encoding="utf-8"))
            if target_meta is None:
                errors.append(
                    f"frontmatter: superseded_by target {superseded_by!r} lacks frontmatter"
                )
            elif target_meta.get("supersedes") != expected:
                errors.append(
                    f"frontmatter: supersede chain broken — target's "
                    f"'supersedes' is {target_meta.get('supersedes')!r}, "
                    f"expected {expected!r}"
                )

    supersedes = meta.get("supersedes")
    if supersedes:
        target_rel = base / supersedes
        if not (repo / target_rel).exists():
            errors.append(
                f"frontmatter: supersedes {supersedes!r} not found (resolved: {target_rel})"
            )

    return errors


def _supersede_base(rel: Path) -> tuple[Path, str]:
    """supersede chain 의 base 디렉토리 + 본 파일의 expected 역참조 ID.

    vX.Y.Z 파일 (`docs/<kind>/<vX.Y.Z>/<file>.md`) → base=`docs/<kind>/`,
    expected=`<vX.Y.Z>/<file>.md`.
    Meta-level 평면 (`docs/<kind>/<file>.md`) → base=`docs/<kind>/`,
    expected=`<file>.md`.
    """
    if re.fullmatch(r"v\d+\.\d+\.\d+", rel.parent.name):
        return rel.parent.parent, str(rel.relative_to(rel.parent.parent))
    return rel.parent, rel.name


# * Rule 3+4: filename kebab-case + vX.Y.Z directory SemVer
def validate_filename(rel_str: str) -> list[str]:
    errors: list[str] = []
    parts = rel_str.split("/")

    stem = parts[-1].removesuffix(".md")
    if not (re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", stem) or re.fullmatch(r"[A-Z]+", stem)):
        errors.append(
            f"filename {parts[-1]!r} must be kebab-case (or ALL-CAPS for "
            "README / CONVENTIONS / CHANGELOG)"
        )

    for part in parts[:-1]:
        if re.match(r"^v\d", part) and not re.fullmatch(r"v\d+\.\d+\.\d+", part):
            errors.append(f"version directory {part!r} must be 'vX.Y.Z' (SemVer)")

    return errors


# * Rule 5: <topic>.md ↔ <topic>-research.md pair existence
# ^ Pair-exempt: v0.1.0 (spinoff transfer, design research 미진행 — 역사적 예외).
PAIR_EXEMPT_VERSIONS = {"v0.1.0"}


def validate_pair(rel_str: str, repo: Path) -> list[str]:
    m = re.match(r"docs/(roadmap|design)/(v\d+\.\d+\.\d+)/(.+)\.md$", rel_str)
    if not m:
        return []
    side, ver, base = m.group(1), m.group(2), m.group(3)
    if ver in PAIR_EXEMPT_VERSIONS:
        return []

    if side == "roadmap":
        pair = repo / "docs" / "design" / ver / f"{base}-research.md"
        if not pair.exists():
            return [f"pair file missing — expected docs/design/{ver}/{base}-research.md"]
    else:
        if not base.endswith("-research"):
            return [f"design file {base!r} must end with '-research'"]
        topic = base.removesuffix("-research")
        pair = repo / "docs" / "roadmap" / ver / f"{topic}.md"
        if not pair.exists():
            return [f"pair file missing — expected docs/roadmap/{ver}/{topic}.md"]
    return []


# * Rule 6: upstream monorepo residue keywords
def validate_monorepo_residue(rel_str: str, text: str) -> list[str]:
    if any(rel_str.startswith(p) for p in HISTORICAL_FROZEN_PREFIXES):
        return []
    return [
        f"upstream monorepo residue keyword {kw!r} — "
        "this is a spinoff binding repo, not the source-of-truth repo"
        for kw in FORBIDDEN_KEYWORDS
        if kw in text
    ]


# * Rule 7: same-version spec ↔ spec direct link (pair only)
def validate_cross_link(rel_str: str, text: str) -> list[str]:
    m = re.match(r"docs/(roadmap|design)/(v\d+\.\d+\.\d+)/(.+)\.md$", rel_str)
    if not m:
        return []
    base = m.group(3)
    if base.endswith("-research"):
        allowed_link = f"{base.removesuffix('-research')}.md"
    else:
        allowed_link = f"{base}-research.md"
    self_link = f"{base}.md"

    errors: list[str] = []
    for link in re.findall(r"\]\(([^)]+\.md)[^)]*\)", _strip_code(text)):
        link_target = link.split("#")[0]
        if "/" in link_target:
            continue
        if link_target in (allowed_link, self_link):
            continue
        errors.append(f"same-version spec direct link {link!r} — route through roadmap/README.md")
    return errors


# * Rule 8: broken .md link
# ^ external/ submodule (예: external/rhwp/) 안의 파일은 lint 검증 skip —
#   외부 의존성 추적은 docs/upstream-pins.yaml 이 담당. CI 가 submodule
#   체크아웃 안 해도 lint 통과하도록.
def validate_broken_link(rel_str: str, text: str, repo: Path) -> list[str]:
    target_dir = (repo / rel_str).parent
    errors: list[str] = []
    for link in re.findall(r"\]\(([^)]+\.md)[^)]*\)", _strip_code(text)):
        link_target = link.split("#")[0].split("?")[0]
        if not link_target or link_target.startswith("http"):
            continue
        resolved = (target_dir / link_target).resolve()
        try:
            resolved_rel = resolved.relative_to(repo)
        except ValueError:
            # ^ repo 외부 절대경로 — 검증 skip
            continue
        if str(resolved_rel).startswith("external/"):
            continue
        if not resolved.exists():
            errors.append(f"broken .md link {link!r} (resolved: {resolved})")
    return errors


def lint_file(rel_str: str, repo: Path) -> list[str]:
    """Run all rules on a single docs/*.md path. Returns list of error strings
    prefixed with the file path. Empty list = clean."""
    target = repo / rel_str
    if not target.is_file():
        return []
    text = target.read_text(encoding="utf-8")
    errors: list[str] = []

    if rel_str not in LIVING_FILES:
        meta = parse_frontmatter(text)
        if meta is None:
            errors.append(
                "missing YAML frontmatter — add "
                "'---\\nstatus: <Active|Draft|Frozen|Superseded>\\n"
                "[ga|target]: vX.Y.Z\\nlast_updated: YYYY-MM-DD\\n---' "
                "(CONVENTIONS § Status 메타데이터)"
            )
        else:
            errors.extend(validate_frontmatter(rel_str, meta, repo))

    errors.extend(validate_filename(rel_str))
    errors.extend(validate_pair(rel_str, repo))
    errors.extend(validate_monorepo_residue(rel_str, text))
    errors.extend(validate_cross_link(rel_str, text))
    errors.extend(validate_broken_link(rel_str, text, repo))

    return [f"{rel_str}: {e}" for e in errors]
