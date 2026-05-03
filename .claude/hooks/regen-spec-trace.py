#!/usr/bin/env python3
"""tests/*.py PostToolUse hook — spec trace report 자동 재생성.

stdin 으로 받은 hook event 의 ``tool_input.file_path`` 가 ``tests/**/*.py`` 면
``scripts/generate_spec_trace.py`` (write mode) 실행하여 ``docs/traces/coverage.md``
를 자동 갱신. 그 외 즉시 종료.

배경: trace 는 ``@pytest.mark.spec(...)`` marker 변경으로 invalidate 되지만 기존
docs-lint hook 은 ``docs/*.md`` 만 감시. ``tests/*.py`` 마커 추가/이름변경/제거가
로컬에서 재생성을 trigger 하지 않아 CI ``--check`` 까지 가서야 staleness 발견.

위반(generator failure) 시 exit 2 + stderr — 모델 컨텍스트 주입.
정상 갱신 또는 적용 안 되는 파일은 exit 0.
"""

import json
import subprocess
import sys
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
if not (rel_str.startswith("tests/") and rel.suffix == ".py"):
    sys.exit(0)

# * trace 재생성 — CI 와 동일한 무프로젝트 + ad-hoc typer install 패턴.
#   project venv 의 extras 설치 상태와 무관하게 동작.
result = subprocess.run(
    [
        "uv",
        "run",
        "--no-project",
        "--with",
        "typer>=0.12",
        "python",
        str(REPO / "scripts" / "generate_spec_trace.py"),
    ],
    cwd=str(REPO),
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    sys.stderr.write("\nregen-spec-trace: generator failed\n")
    sys.stderr.write(result.stderr)
    sys.exit(2)
