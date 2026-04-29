#!/usr/bin/env python3
"""external/rhwp 의 현재 commit hash 를 docs/upstream-pins.yaml 에 기록.

사용:
    uv run python scripts/update_upstream_pin.py vX.Y.Z [--note "..."]

동작:
    1. external/rhwp 에서 git rev-parse --short HEAD 추출
    2. 직전 entry 의 upstream_commit 을 previous_commit 으로 설정
    3. previous..current 사이 commit 수 계산 (commits_integrated)
    4. docs/upstream-pins.yaml 의 pins[vX.Y.Z] 갱신 또는 신규 추가
    5. bumped_at 은 오늘 날짜

릴리스 직전 / pin lock 시점에 작업자가 호출. 자동화 (예: release workflow)
는 의도적 미적용 — 핀 결정은 사람의 판단 (어느 commit 까지 흡수할지) 이라
수기 한 단계 둠.
"""

import re
import subprocess
from datetime import date
from pathlib import Path

import typer
import yaml

REPO = Path(__file__).resolve().parent.parent
PINS_FILE = REPO / "docs" / "upstream-pins.yaml"
UPSTREAM_DIR = REPO / "external" / "rhwp"


def main(
    version: str = typer.Argument(..., help="릴리스 버전 (vX.Y.Z)"),
    note: str = typer.Option("", help="갱신 사유 한 줄 (선택)"),
) -> None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        typer.echo(f"error: version must be vX.Y.Z (got {version!r})", err=True)
        raise typer.Exit(1)

    if not UPSTREAM_DIR.is_dir():
        typer.echo(f"error: {UPSTREAM_DIR} not found", err=True)
        raise typer.Exit(1)

    current = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=UPSTREAM_DIR,
        text=True,
    ).strip()

    data = yaml.safe_load(PINS_FILE.read_text(encoding="utf-8")) or {}
    pins = data.setdefault("pins", {})

    previous_entry = _previous_pin(pins, version)
    # ^ 표준 field 순서: upstream_commit / previous_commit / commits_integrated /
    #   bumped_at / note. 조건부 필드는 건너뛰되 나머지 순서 유지 → round-trip 안정.
    entry: dict[str, object] = {"upstream_commit": current}
    if previous_entry:
        prev_commit = previous_entry["upstream_commit"]
        if prev_commit != current:
            entry["previous_commit"] = prev_commit
            entry["commits_integrated"] = _count_commits(prev_commit, current)
    # ^ date 객체 그대로 dump → YAML native date (unquoted), round-trip 안정
    entry["bumped_at"] = date.today()
    if note:
        entry["note"] = note

    pins[version] = entry
    _write_yaml(PINS_FILE, data)
    typer.echo(f"updated {PINS_FILE.relative_to(REPO)} — {version}: {current}")


def _previous_pin(pins: dict, current_version: str) -> dict | None:
    """SemVer 정렬에서 current_version 직전 entry 반환. 없으면 None."""

    def key(v: str) -> tuple[int, int, int]:
        m = re.match(r"v(\d+)\.(\d+)\.(\d+)", v)
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)

    target = key(current_version)
    candidates = sorted(
        ((k, v) for k, v in pins.items() if key(k) < target),
        key=lambda kv: key(kv[0]),
    )
    return candidates[-1][1] if candidates else None


def _count_commits(prev: str, curr: str) -> int:
    return len(
        subprocess.check_output(
            ["git", "log", "--oneline", f"{prev}..{curr}"],
            cwd=UPSTREAM_DIR,
            text=True,
        )
        .strip()
        .splitlines()
    )


def _write_yaml(path: Path, data: dict) -> None:
    # ^ default_flow_style=False → block style (사람 가독), allow_unicode → 한글 보존,
    #   width 매우 크게 → 긴 한글 note 줄바꿈 방지 (CI diff 안정).
    body = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=10000,
    )
    header = (
        "# external/rhwp 커밋 핀 SSOT — Living.\n"
        "# 각 vX.Y.Z 릴리스가 의존하는 상류 (edwardkim/rhwp) 커밋 hash 와 갱신 메타.\n"
        "# 갱신: scripts/update_upstream_pin.py vX.Y.Z (릴리스 직전 / pin lock 시점).\n"
        "# CHANGELOG.md 가 본 파일 값을 prose 로 인용 — 둘이 어긋나면 본 파일이 SSOT.\n\n"
    )
    path.write_text(header + body, encoding="utf-8")


if __name__ == "__main__":
    typer.run(main)
