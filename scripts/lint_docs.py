#!/usr/bin/env python3
"""docs/ lint — full repo scan. Used by CI.

사용:
    python3 scripts/lint_docs.py [target_dir]
    python3 scripts/lint_docs.py docs/  # default

각 markdown 파일에 .claude/hooks/docs-lint.py 와 동일한 룰 (공통 lib
scripts/_doc_lint.py) 을 적용. 룰 일람은 _doc_lint.py docstring 참조.

exit 0: 위반 0 / exit 1: 위반 ≥1.
"""

import sys
from pathlib import Path

# ^ scripts/ 를 import path 에 추가하여 동일 디렉토리 _doc_lint 모듈 로드
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _doc_lint import lint_file  # noqa: E402


def main(args: list[str]) -> int:
    repo = Path(__file__).resolve().parent.parent
    target = args[0] if args else "docs"
    target_dir = (repo / target).resolve()
    if not target_dir.is_dir():
        sys.stderr.write(f"error: {target_dir} is not a directory\n")
        return 1

    all_errors: list[str] = []
    for path in sorted(target_dir.rglob("*.md")):
        rel = path.relative_to(repo)
        rel_str = str(rel).replace("\\", "/")
        all_errors.extend(lint_file(rel_str, repo))

    if all_errors:
        for e in all_errors:
            sys.stderr.write(f"{e}\n")
        sys.stderr.write(
            f"\n{len(all_errors)} violation(s) under {target}/ — policy: docs/CONVENTIONS.md\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
