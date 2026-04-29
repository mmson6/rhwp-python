#!/usr/bin/env python3
"""docs/*.md PostToolUse lint — single file mode.

stdin 으로 받은 hook event 의 ``tool_input.file_path`` 가 ``docs/*.md`` 면
공통 lib (``scripts/_doc_lint.py``) 의 룰 일괄 적용. 그 외 즉시 종료.

위반 시 exit 2 + stderr — Claude Code 가 stderr 를 LLM 컨텍스트에 주입하여
모델이 위반 사항을 인지. exit 1 은 non-blocking 이라 사용 금지.

룰 일람 / 정책 SSOT: ``scripts/_doc_lint.py`` docstring + ``docs/CONVENTIONS.md``.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from _doc_lint import lint_file  # noqa: E402

try:
    event = json.loads(sys.stdin.read() or "{}")
except json.JSONDecodeError:
    sys.exit(0)

tool_input = event.get("tool_input") or {}
file_path = tool_input.get("file_path") or ""
if not file_path:
    sys.exit(0)

try:
    rel = Path(file_path).resolve().relative_to(REPO)
except ValueError:
    sys.exit(0)

rel_str = str(rel).replace("\\", "/")
if not (rel_str.startswith("docs/") and rel.suffix == ".md"):
    sys.exit(0)

errors = lint_file(rel_str, REPO)
if errors:
    sys.stderr.write(f"\ndocs-lint: {len(errors)} violation(s)\n")
    for i, e in enumerate(errors, 1):
        sys.stderr.write(f"  {i}. {e}\n")
    sys.stderr.write("policy: docs/CONVENTIONS.md\n")
    sys.exit(2)
