#!/usr/bin/env python3
"""docs/*.md 편집 시 frontmatter 의 last_updated 를 오늘 날짜로 자동 갱신.

PostToolUse hook 으로 Edit / Write / MultiEdit 후 실행. stdin 으로 받은 hook
event 의 ``tool_input.file_path`` 가 ``docs/*.md`` 면서 frontmatter 가 있으면
``last_updated:`` 라인을 오늘 날짜로 in-place 교체.

skip 조건:
- ``docs/`` 외부 파일
- frontmatter 없는 파일 (Living: CONVENTIONS / roadmap/README / traces/coverage)
- last_updated 가 이미 오늘 날짜
- frontmatter 의 status 가 Frozen 또는 Superseded — 본문 의미 변경 금지가
  원칙. 이런 파일을 편집한 경우는 (a) Frozen 면제 조항 활용 일괄 마이그
  (PR 단위 수기 처리) 또는 (b) 오타·링크 fix (last_updated 갱신 적절) 둘
  다 가능 → 자동 처리는 위험하니 hook 은 skip, 사용자가 명시 결정.

본 hook 은 silent (exit 0) — 갱신 결과는 git diff 로 확인.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

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

target = REPO / rel
if not target.is_file():
    sys.exit(0)

text = target.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    sys.exit(0)
end = text.find("\n---\n", 4)
if end < 0:
    sys.exit(0)

block = text[4:end]
status_match = re.search(r"^status:\s*(\S+)", block, re.MULTILINE)
if status_match and status_match.group(1) in ("Frozen", "Superseded"):
    # ^ Frozen / Superseded 자동 갱신 금지 — 사용자 명시 결정 필요
    sys.exit(0)

today = date.today().isoformat()
new_block, n = re.subn(
    r"^last_updated:\s*\S+",
    f"last_updated: {today}",
    block,
    count=1,
    flags=re.MULTILINE,
)
if n == 0 or new_block == block:
    sys.exit(0)

new_text = "---\n" + new_block + text[end:]
target.write_text(new_text, encoding="utf-8")
sys.exit(0)
