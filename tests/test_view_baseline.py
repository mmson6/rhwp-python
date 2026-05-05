"""tests/test_view_baseline.py — v0.4.0 view-renderer 회귀 가드 (AC-11).

spec: docs/roadmap/v0.4.0/view-renderer.md (AC-11).

v0.4.0 변경은 ``HwpDocument`` 메서드 추가만 — schema / 파싱 경로 영향 0
(additive only, 결정 9). ``Document.to_ir()`` 출력은 v0.3.2 GA baseline 과
byte-equal 이어야 한다.

baseline 파일 (``tests/baselines/v0_3_2_<sample>_ir.json``) 은 v0.3.2 GA 시점에
``model_dump_json(indent=2, exclude={"source"})`` 로 캡처. ``source.uri`` 는 입력
파일 경로 (절대/상대) 의존이라 parsing/schema 회귀 신호가 아님 — 비교 대상에서
제외. 향후 schema / 파싱 경로 변경이 발생하면 별도 spec (예: schema_version
bump) 에서 baseline 도 함께 갱신.
"""

from pathlib import Path

import pytest
import rhwp

pytestmark = pytest.mark.spec("v0.4.0/view-renderer")

BASELINE_DIR = Path(__file__).parent / "baselines"


_REGEN_HINT = (
    "to_ir() drift detected — v0.4.0 must be additive only. "
    "If schema/parsing changed intentionally, regenerate baselines per "
    "docs/implementation/v0.4.0/migration.md §AC-11 baseline."
)


@pytest.mark.spec("v0.4.0/view-renderer#AC-11")
def test_aift_to_ir_byte_equal_to_v0_3_2_baseline(hwp_sample: Path):
    """``aift.hwp`` 의 ``to_ir()`` JSON (source 제외) 이 v0.3.2 baseline 과 일치."""
    baseline = (BASELINE_DIR / "v0_3_2_aift_ir.json").read_text(encoding="utf-8")
    current = rhwp.parse(str(hwp_sample)).to_ir().model_dump_json(indent=2, exclude={"source"})
    assert current == baseline, _REGEN_HINT


@pytest.mark.spec("v0.4.0/view-renderer#AC-11")
def test_table_vpos_to_ir_byte_equal_to_v0_3_2_baseline(hwpx_sample: Path):
    """``table-vpos-01.hwpx`` 의 ``to_ir()`` JSON (source 제외) 이 v0.3.2 baseline 과 일치."""
    baseline = (BASELINE_DIR / "v0_3_2_table_vpos_01_ir.json").read_text(encoding="utf-8")
    current = rhwp.parse(str(hwpx_sample)).to_ir().model_dump_json(indent=2, exclude={"source"})
    assert current == baseline, _REGEN_HINT
