"""tests/test_ir_marker_char_offset.py — v0.3.1 inline 컨트롤 마커 character offset.

[v0.3.1/ir-marker-char-offset](../docs/roadmap/v0.3.1/ir-marker-char-offset.md)
의 AC-1 ~ AC-14 검증. 짝 페어 ADR:
[v0.3.1/ir-marker-char-offset-research](../docs/design/v0.3.1/ir-marker-char-offset-research.md).

전략:

- AC-1 ~ AC-7 (블록별 char_start/char_end 채움): direct mapper 단위 + 가능하면 real
  fixture 통합. mapper 단위 테스트는 결정론적으로 양쪽 슬롯 동일 정수값 보증.
- AC-8 (빈 char_offsets 폴백): mapper 에 ``char_offset=None`` 입력 → ``prov.char_start
  /char_end`` 둘 다 ``None``. 실제 파일 데이터 (aift.hwp) 도 다수 None 케이스 보유
  — fail-fast 폴백이 실 사용 경로에서 작동함을 회귀 보증.
- AC-9 (Schema 1.1 유지): ``CURRENT_SCHEMA_VERSION == "1.1"`` + Provenance 의
  ``anyOf [integer, null]`` 정의 동결.
- AC-10 (jsonschema validator): 본 파일은 schema 슬롯 정의 + SchemaVersion 동결만
  가드한다. 실제 jsonschema validator 호출은
  ``test_ir_schema_export.py::test_real_hwp_document_validates_against_schema`` 가
  담당 — 본 spec 의 v0.3.1 AC-10 marker 도 그쪽에 부착. jsonschema extras 없는
  환경에서 module-level importorskip 으로 1 skip 수렴 → ``test-without-extras`` CI
  카운트 4 보존.
- AC-11 (zero-width invariant): ``char_start == char_end`` 인 정수 슬롯의 프로젝트
  전반 검증.
- AC-12 (Rust assert): ``src/ir.rs`` 에 ``assert_eq!`` (release-active) 와
  ``#[should_panic]`` 단위 테스트가 정의되어 있다 — ``cargo clippy --all-targets`` 가
  test target 컴파일을 검증한다. **runtime panic 검증** (실제 mismatch 시 panic 발생)
  은 PyO3 ``extension-module`` cdylib + libpython 링크 제약으로 본 프로젝트 CI 에서
  ``cargo test`` 가 실행되지 않아 미실행. Python 측 본 테스트는 source-level 회귀 가드
  (``assert_eq!`` 가 ``debug_assert_eq!`` 로 약화되거나 helper 가 제거되는 회귀 차단)
  까지만 담당.
- AC-13 (submodule pin + CHANGELOG): submodule HEAD 검증 + CHANGELOG 항목 양쪽 검사.
- AC-14 (fixture 정책): 본 파일이 기존 ``aift.hwp`` / ``table-vpos-01.hwpx`` 만으로
  AC-1 ~ AC-8 을 커버 — 합성 fixture 미도입을 사실로 가드 (``tests/fixtures/v0_3_1/``
  부재 검증).
"""

import re
from pathlib import Path

import pytest
import rhwp
from rhwp.ir._mapper import (
    _build_endnote_block,
    _build_field_block,
    _build_footnote_block,
    _build_formula_block,
    _build_picture_block,
    _build_table_block,
    _build_toc_block,
)
from rhwp.ir._raw_types import (
    RawEndnote,
    RawField,
    RawFootnote,
    RawFormula,
    RawImageRef,
    RawParagraph,
    RawPicture,
    RawTable,
    RawToc,
)
from rhwp.ir.nodes import (
    CURRENT_SCHEMA_VERSION,
    EndnoteBlock,
    FieldBlock,
    FootnoteBlock,
    FormulaBlock,
    HwpDocument,
    PictureBlock,
    TableBlock,
    TocBlock,
)
from rhwp.ir.schema import load_schema

pytestmark = pytest.mark.spec("v0.3.1/ir-marker-char-offset")

REPO_ROOT = Path(__file__).resolve().parent.parent


# * mapper helper factories — 각 raw struct 의 최소 필수 필드를 채운다


def _empty_raw_para(*, section_idx: int = 0, para_idx: int = 0) -> RawParagraph:
    return RawParagraph(
        section_idx=section_idx,
        para_idx=para_idx,
        text="",
        char_runs=[],
        tables=[],
        pictures=[],
        formulas=[],
        tocs=[],
        fields=[],
        list_info=None,
    )


def _raw_table(*, char_offset: int | None) -> RawTable:
    return RawTable(
        rows=1,
        cols=1,
        cells=[],
        caption=None,
        caption_block=None,
        char_offset=char_offset,
    )


def _raw_picture(*, char_offset: int | None) -> RawPicture:
    return RawPicture(
        section_idx=2,
        para_idx=4,
        image=RawImageRef(bin_data_id=1, extension="png", has_content=True),
        description=None,
        caption=None,
        char_offset=char_offset,
    )


def _raw_formula(*, char_offset: int | None) -> RawFormula:
    return RawFormula(
        section_idx=3,
        para_idx=5,
        script="x^2",
        text_alt=None,
        char_offset=char_offset,
    )


def _raw_field(*, char_offset: int | None) -> RawField:
    return RawField(
        section_idx=1,
        para_idx=2,
        field_kind="hyperlink",
        cached_value=None,
        raw_instruction=None,
        field_type_code=None,
        char_offset=char_offset,
    )


def _raw_toc(*, char_offset: int | None) -> RawToc:
    return RawToc(
        section_idx=4,
        para_idx=6,
        entries=[],
        char_offset=char_offset,
    )


def _raw_footnote(*, marker_char_offset: int | None) -> RawFootnote:
    return RawFootnote(
        marker_section_idx=0,
        marker_para_idx=10,
        marker_char_offset=marker_char_offset,
        number=1,
        blocks=[_empty_raw_para()],
    )


def _raw_endnote(*, marker_char_offset: int | None) -> RawEndnote:
    return RawEndnote(
        marker_section_idx=0,
        marker_para_idx=12,
        marker_char_offset=marker_char_offset,
        number=2,
        blocks=[_empty_raw_para()],
    )


# * AC-1 — FootnoteBlock.marker_prov.char_start/char_end (zero-width)


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-1")
def test_footnote_marker_char_offset_populated_zero_width():
    """`marker_char_offset` 정수 입력 시 marker_prov 양쪽 슬롯에 동일 값 복제."""
    fn = _build_footnote_block(_raw_footnote(marker_char_offset=7))
    assert fn.marker_prov.char_start == 7
    assert fn.marker_prov.char_end == 7
    # ^ prov 도 marker 와 동일 위치 공유 (mapper 가 marker_prov 를 prov 로 재사용)
    assert fn.prov.char_start == 7
    assert fn.prov.char_end == 7


# * AC-2 — EndnoteBlock.marker_prov.char_start/char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-2")
def test_endnote_marker_char_offset_populated_zero_width():
    en = _build_endnote_block(_raw_endnote(marker_char_offset=11))
    assert en.marker_prov.char_start == 11
    assert en.marker_prov.char_end == 11
    assert en.prov.char_start == 11
    assert en.prov.char_end == 11


# * AC-3 — PictureBlock.prov.char_start/char_end (TAC / floating 무관)


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-3")
def test_picture_char_offset_populated_zero_width():
    pic = _build_picture_block(_raw_picture(char_offset=3))
    assert pic.prov.char_start == 3
    assert pic.prov.char_end == 3


# * AC-4 — FormulaBlock.prov.char_start/char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-4")
def test_formula_char_offset_populated_zero_width():
    eq = _build_formula_block(_raw_formula(char_offset=2))
    assert eq.prov.char_start == 2
    assert eq.prov.char_end == 2


# * AC-5 — FieldBlock.prov.char_start/char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-5")
def test_field_char_offset_populated_zero_width():
    fld = _build_field_block(_raw_field(char_offset=5))
    assert fld.prov.char_start == 5
    assert fld.prov.char_end == 5


# * AC-6 — TocBlock.prov.char_start/char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-6")
def test_toc_char_offset_populated_zero_width():
    toc = _build_toc_block(_raw_toc(char_offset=0))
    assert toc.prov.char_start == 0
    assert toc.prov.char_end == 0


# * AC-7 — TableBlock.prov.char_start/char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-7")
def test_table_char_offset_populated_zero_width():
    raw_para = _empty_raw_para(section_idx=1, para_idx=8)
    tbl = _build_table_block(raw_para, _raw_table(char_offset=4))
    assert tbl.prov.char_start == 4
    assert tbl.prov.char_end == 4


# * AC-8 — empty char_offsets paragraph → None 폴백 (모든 7 종 블록)


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-8")
@pytest.mark.parametrize(
    "label, build_fn",
    [
        (
            "footnote_marker",
            lambda: _build_footnote_block(_raw_footnote(marker_char_offset=None)).marker_prov,
        ),
        (
            "endnote_marker",
            lambda: _build_endnote_block(_raw_endnote(marker_char_offset=None)).marker_prov,
        ),
        ("picture", lambda: _build_picture_block(_raw_picture(char_offset=None)).prov),
        ("formula", lambda: _build_formula_block(_raw_formula(char_offset=None)).prov),
        ("field", lambda: _build_field_block(_raw_field(char_offset=None)).prov),
        ("toc", lambda: _build_toc_block(_raw_toc(char_offset=None)).prov),
        (
            "table",
            lambda: _build_table_block(_empty_raw_para(), _raw_table(char_offset=None)).prov,
        ),
    ],
)
def test_char_offsets_empty_falls_back_to_none(label, build_fn):
    """부모 paragraph 의 char_offsets 가 빈 케이스 — char_start/char_end 둘 다 None."""
    prov = build_fn()
    assert prov.char_start is None, label
    assert prov.char_end is None, label


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-8")
def test_real_sample_has_none_fallback_paragraphs(parsed_hwp: rhwp.Document):
    """aift.hwp 안 inline 컨트롤 중 일부는 char_offsets 가 빈 paragraph 안에 위치 —
    spec § 결정사항 3 의 폴백이 실 사용 경로에서 None 으로 출고됨을 보증."""
    ir = parsed_hwp.to_ir()
    target_types = (TableBlock, PictureBlock, FormulaBlock, FieldBlock)
    blocks = [b for b in ir.iter_blocks(scope="all", recurse=True) if isinstance(b, target_types)]
    none_count = sum(1 for b in blocks if b.prov.char_start is None)
    assert none_count > 0, "샘플에 None 폴백 케이스가 하나도 없음 — AC-8 회귀 가드 무력화"


# * AC-9 — SchemaVersion 1.1 유지 + 슬롯 정의 동결


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-9")
def test_schema_version_remains_1_1():
    assert CURRENT_SCHEMA_VERSION == "1.1"


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-9")
def test_schema_provenance_char_start_anyof_integer_or_null():
    """``Provenance.char_start`` schema 는 v0.3.0 과 동일 ``anyOf [integer, null]``.
    스키마 본문이 v0.3.1 에서 변경되지 않음을 보증."""
    schema = load_schema()
    char_start = schema["$defs"]["Provenance"]["properties"]["char_start"]
    assert char_start["anyOf"] == [{"type": "integer"}, {"type": "null"}]
    char_end = schema["$defs"]["Provenance"]["properties"]["char_end"]
    assert char_end["anyOf"] == [{"type": "integer"}, {"type": "null"}]


# * AC-10 — jsonschema validator 호출은 ``test_ir_schema_export.py`` 가 담당
# (jsonschema extras gate — module-level importorskip 으로 카운트 1 수렴).


# * AC-11 — zero-width invariant: 모든 non-None marker 에 대해 char_start == char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-11")
def test_real_sample_zero_width_invariant(parsed_hwp: rhwp.Document):
    """non-None 출고된 모든 marker 의 ``char_start == char_end`` (zero-width point)."""
    ir = parsed_hwp.to_ir()
    target_types = (TableBlock, PictureBlock, FormulaBlock, FieldBlock, TocBlock)
    invariants_checked = 0
    for b in ir.iter_blocks(scope="all", recurse=True):
        if isinstance(b, target_types) and b.prov.char_start is not None:
            assert isinstance(b.prov.char_start, int)
            assert b.prov.char_start == b.prov.char_end
            invariants_checked += 1
        elif isinstance(b, (FootnoteBlock, EndnoteBlock)) and b.marker_prov.char_start is not None:
            assert isinstance(b.marker_prov.char_start, int)
            assert b.marker_prov.char_start == b.marker_prov.char_end
            invariants_checked += 1
    assert invariants_checked > 0, "샘플에서 non-None marker 가 한 건도 발견되지 않음"


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-11")
def test_zero_width_invariant_holds_across_distinct_offsets():
    """동일 값 복제 (mapper 가 char_start = char_end = char_offset) 의 정수 입력
    여러 개에 대해 비대칭이 발생하지 않음을 결정론적으로 보증."""
    for i in (0, 1, 7, 100):
        pic = _build_picture_block(_raw_picture(char_offset=i))
        assert pic.prov.char_start == i
        assert pic.prov.char_end == i


# * AC-12 — Rust 빌드의 fail-fast invariant (source-level 회귀 가드)


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-12")
def test_rust_uses_assert_eq_not_debug_assert():
    """``assert_position_invariant`` 가 ``assert_eq!`` (release-active) 사용 보증.

    본 파일 docstring § AC-12 참고: runtime panic 검증은 ``cargo test`` 가 PyO3
    cdylib 제약으로 CI 미실행이라 source-level 만 가드한다. ``debug_assert_eq!`` 로
    약화되거나 helper 가 제거되는 회귀를 차단."""
    src = (REPO_ROOT / "src" / "ir.rs").read_text(encoding="utf-8")
    assert "fn assert_position_invariant" in src
    impl_match = re.search(r"fn assert_position_invariant\([^)]*\) \{[^}]*\}", src, re.DOTALL)
    assert impl_match is not None, "assert_position_invariant 함수 본체를 찾을 수 없음"
    body = impl_match.group(0)
    assert "assert_eq!" in body, "assert_eq! 가 사라짐 — fail-fast 보장 회귀"
    assert "debug_assert" not in body, "debug_assert 로 약화됨 — release 빌드에서 무력화"


# * AC-13 — submodule pin + CHANGELOG 기재


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-13")
def test_changelog_records_pin_bump():
    """CHANGELOG.md 의 v0.3.1 항목이 v0.7.7 → 신규 핀 (0fb3e67) bump 와 PR #405 / Task #390 인용을 모두 보유."""
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = re.search(r"## \[0\.3\.1\].*?(?=^## \[)", changelog, re.DOTALL | re.MULTILINE)
    assert section is not None, "CHANGELOG 에 v0.3.1 섹션 없음"
    body = section.group(0)
    assert "033617e" in body, "v0.7.7 핀 (033617e) 미기재"
    assert "0fb3e67" in body, "post-v0.7.8 핀 (0fb3e67) 미기재"
    assert "v0.7.7" in body
    assert "PR #405" in body or "/pull/405" in body, "PR #405 인용 누락"
    assert "Task #390" in body or "issues/390" in body, "Task #390 인용 누락"


# * AC-14 — fixture 정책: 기존 sample 만 사용, 합성 fixture 미도입


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-14")
def test_no_synthetic_fixture_directory():
    """spec § AC-14: 우선 기존 fixture 로 검증 시도. ``tests/fixtures/v0_3_1/`` 합성 fixture
    디렉토리는 *부족 시* 도입 — 본 v0.3.1 GA 시점에는 미도입 (AC-1 ~ AC-8 모두 기존 sample
    + mapper 단위 테스트로 커버)."""
    synthetic_dir = REPO_ROOT / "tests" / "fixtures" / "v0_3_1"
    assert not synthetic_dir.exists(), (
        "tests/fixtures/v0_3_1/ 발견 — 합성 fixture 도입 시 본 가드 갱신 필요"
    )


# * 통합 테스트 — real sample 의 적용 대상 7 종에서 (필요 시 skip) 실데이터 회귀 보증


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-7")
def test_real_sample_table_marker_populates_or_falls_back(parsed_hwp: rhwp.Document):
    """aift.hwp 의 90개 표 중 일부는 부모 paragraph 가 텍스트를 가져 char_start 가
    int, 일부는 텍스트 없는 anchor paragraph 라 None — 둘 다 정상."""
    ir = parsed_hwp.to_ir()
    tables = [b for b in ir.iter_blocks(scope="all", recurse=True) if isinstance(b, TableBlock)]
    assert len(tables) > 0
    for tbl in tables:
        if tbl.prov.char_start is not None:
            assert isinstance(tbl.prov.char_start, int)
            assert tbl.prov.char_start == tbl.prov.char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-3")
def test_real_sample_picture_marker_populates_or_falls_back(parsed_hwp: rhwp.Document):
    ir = parsed_hwp.to_ir()
    pictures = [b for b in ir.iter_blocks(scope="all", recurse=True) if isinstance(b, PictureBlock)]
    if not pictures:
        pytest.skip("aift.hwp 샘플에 그림 컨트롤 없음")
    for pic in pictures:
        if pic.prov.char_start is not None:
            assert isinstance(pic.prov.char_start, int)
            assert pic.prov.char_start == pic.prov.char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-1")
def test_real_sample_footnote_marker_populates_or_falls_back(parsed_hwp: rhwp.Document):
    ir = parsed_hwp.to_ir()
    if not ir.furniture.footnotes:
        pytest.skip("aift.hwp 샘플에 각주 컨트롤 없음")
    for fn in ir.furniture.footnotes:
        cs = fn.marker_prov.char_start
        if cs is not None:
            assert isinstance(cs, int)
            assert cs == fn.marker_prov.char_end


@pytest.mark.spec("v0.3.1/ir-marker-char-offset#AC-5")
def test_real_sample_field_marker_populates_or_falls_back(parsed_hwp: rhwp.Document):
    ir = parsed_hwp.to_ir()
    fields = [b for b in ir.iter_blocks(scope="all", recurse=True) if isinstance(b, FieldBlock)]
    if not fields:
        pytest.skip("aift.hwp 샘플에 field 컨트롤 없음")
    for fld in fields:
        if fld.prov.char_start is not None:
            assert isinstance(fld.prov.char_start, int)
            assert fld.prov.char_start == fld.prov.char_end


# * HwpDocument 통째 모델 단위 — Pydantic frozen 직렬화 왕복 보존


def test_real_sample_ir_json_roundtrip(parsed_hwp: rhwp.Document):
    """v0.3.1 출고 IR 의 JSON 왕복 — non-null char_start 가 보존되어 schema 호환."""
    ir = parsed_hwp.to_ir()
    reloaded = HwpDocument.model_validate_json(ir.model_dump_json())
    assert reloaded.schema_version == "1.1"
    assert reloaded == ir
