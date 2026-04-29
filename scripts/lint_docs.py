#!/usr/bin/env python3
"""docs/ lint — full repo scan. Used by CI.

사용:
    uv run python scripts/lint_docs.py [TARGET_DIR]
    uv run python scripts/lint_docs.py docs/  # default

각 markdown 파일에 .claude/hooks/docs-lint.py 와 동일한 룰 (공통 lib
scripts/_doc_lint.py) 을 적용. 룰 일람은 _doc_lint.py docstring 참조.

exit 0: 위반 0 / exit 1: 위반 ≥1.
"""

import sys
from pathlib import Path

import typer

# ^ scripts/ 를 import path 에 추가하여 동일 디렉토리 _doc_lint 모듈 로드
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _doc_lint import lint_file  # noqa: E402


def main(
    target: str = typer.Argument("docs", help="repo 기준 상대 디렉토리"),
) -> None:
    repo = Path(__file__).resolve().parent.parent
    target_dir = (repo / target).resolve()
    if not target_dir.is_dir():
        typer.echo(f"error: {target_dir} is not a directory", err=True)
        raise typer.Exit(1)

    all_errors: list[str] = []
    for path in sorted(target_dir.rglob("*.md")):
        rel = path.relative_to(repo)
        rel_str = str(rel).replace("\\", "/")
        all_errors.extend(lint_file(rel_str, repo))

    if all_errors:
        for e in all_errors:
            typer.echo(e, err=True)
        typer.echo(
            f"\n{len(all_errors)} violation(s) under {target}/ — policy: docs/CONVENTIONS.md",
            err=True,
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
