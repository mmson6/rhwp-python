#!/usr/bin/env python3
"""tests/ 의 ``@pytest.mark.spec(...)`` marker 를 수집하여
``docs/traces/coverage.md`` (Living) 갱신.

사용:
    uv run python scripts/generate_spec_trace.py [--check]

``--check`` flag: 갱신 대신 git diff 검증만 (CI 용 — coverage.md 가 stale 이면 exit 1).

방식: AST 정적 분석. ``@pytest.mark.spec("vX.Y.Z/topic#AC-N")`` 데코레이터를
가진 ``test_*`` 함수를 찾아 ``(spec_id → nodeid)`` 매핑.

기존 v0.1.0 ~ v0.3.0 Frozen spec 은 AC ID 부여 안 함 — marker 없는 테스트는
그대로 통과 (CONVENTIONS § Trace report).
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

import typer

REPO = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO / "tests"
COVERAGE_FILE = REPO / "docs" / "traces" / "coverage.md"

# ^ spec_id: vX.Y.Z/<topic>[#AC-N]
SPEC_ID_RE = re.compile(r"^v\d+\.\d+\.\d+/[a-z0-9-]+(?:#AC-\d+)?$")


def main(
    check: bool = typer.Option(False, "--check", help="stale 검증만 (수정 안 함)"),
) -> None:
    mapping = _collect_spec_markers(TESTS_DIR)
    body = _render(mapping)

    if check:
        existing = COVERAGE_FILE.read_text(encoding="utf-8") if COVERAGE_FILE.exists() else ""
        if existing != body:
            typer.echo(
                f"error: {COVERAGE_FILE.relative_to(REPO)} is stale — "
                "run scripts/generate_spec_trace.py to refresh.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(f"{COVERAGE_FILE.relative_to(REPO)} up to date.")
        return

    COVERAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE_FILE.write_text(body, encoding="utf-8")
    n = sum(len(v) for v in mapping.values())
    typer.echo(
        f"updated {COVERAGE_FILE.relative_to(REPO)} — {len(mapping)} spec / {n} test mapping(s)"
    )


def _collect_spec_markers(tests_dir: Path) -> dict[str, list[str]]:
    """spec_id → list of pytest nodeids. ``class TestFoo`` 안의 메서드도 정확히
    `tests/x.py::TestFoo::test_bar` 형식으로 출력 (ast.walk 평탄화 회피)."""
    mapping: dict[str, list[str]] = defaultdict(list)
    if not tests_dir.is_dir():
        return mapping

    for py_file in sorted(tests_dir.rglob("test_*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = py_file.relative_to(REPO)
        visitor = _SpecMarkerVisitor(rel)
        visitor.visit(tree)
        for spec_id, nodeids in visitor.mapping.items():
            mapping[spec_id].extend(nodeids)
    return mapping


class _SpecMarkerVisitor(ast.NodeVisitor):
    """class 컨텍스트 stack 을 유지하며 @pytest.mark.spec(...) 추출."""

    def __init__(self, file_rel: Path) -> None:
        self.file_rel = file_rel
        self.class_stack: list[str] = []
        self.mapping: dict[str, list[str]] = defaultdict(list)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._maybe_add(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._maybe_add(node)
        self.generic_visit(node)

    def _maybe_add(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not node.name.startswith("test_"):
            return
        for decorator in node.decorator_list:
            spec_id = _extract_spec_id(decorator)
            if spec_id and SPEC_ID_RE.match(spec_id):
                parts = [*self.class_stack, node.name]
                self.mapping[spec_id].append(f"{self.file_rel}::{'::'.join(parts)}")


def _extract_spec_id(node: ast.AST) -> str | None:
    """``@pytest.mark.spec("vX.Y.Z/...")`` 또는 ``@mark.spec("...")`` 매칭."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "spec"):
        return None
    if not (isinstance(func.value, ast.Attribute) and func.value.attr == "mark"):
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None
    val = node.args[0].value
    return val if isinstance(val, str) else None


def _render(mapping: dict[str, list[str]]) -> str:
    header = (
        "# Spec ↔ Test Trace\n\n"
        "자동 생성 — `scripts/generate_spec_trace.py`. Living.\n\n"
        "v0.4.0+ 신규 spec 의 인수조건 ↔ 테스트 매핑. "
        "기존 v0.1.0 ~ v0.3.0 Frozen spec 은 AC ID 부여 안 함 "
        "(CONVENTIONS § Trace report).\n\n"
    )
    if not mapping:
        return header + "(아직 매핑 없음. v0.4.0+ 부터 채워짐.)\n"

    lines = ["| Spec | AC | Tests |", "|---|---|---|"]
    for spec_id in sorted(mapping):
        spec, _, ac = spec_id.partition("#")
        for nodeid in sorted(mapping[spec_id]):
            lines.append(f"| {spec} | {ac or '—'} | `{nodeid}` |")
    return header + "\n".join(lines) + "\n"


if __name__ == "__main__":
    typer.run(main)
