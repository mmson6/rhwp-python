"""tests/test_ir_field.py — Stage S3 FieldBlock + FieldKind 매퍼.

ir-expansion.md §S3 + § 7 FieldBlock 검증:

- FieldBlock 직렬화 왕복 + frozen + extra=forbid
- FieldKind 닫힌 Literal 14 종 + "unknown" 안전판
- mapper RawField → FieldBlock — 미지 field_kind 는 "unknown" + field_type_code 보존
- TocOfContents 는 FieldBlock 으로 가지 않음 (TocBlock 으로 별도 라우팅)
- _flatten_paragraph 가 FieldBlock 도 emit
"""

import pytest
from pydantic import ValidationError
from rhwp.ir._mapper import _VALID_FIELD_KINDS, _build_field_block, _flatten_paragraph
from rhwp.ir._raw_types import RawField, RawParagraph
from rhwp.ir.nodes import (
    FieldBlock,
    FieldKind,
    HwpDocument,
    ParagraphBlock,
    Provenance,
)


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


def _raw_field(
    *,
    field_kind: str = "date",
    cached_value: str | None = None,
    raw_instruction: str | None = None,
    field_type_code: int | None = None,
    section_idx: int = 0,
    para_idx: int = 0,
) -> RawField:
    return RawField(
        section_idx=section_idx,
        para_idx=para_idx,
        field_kind=field_kind,
        cached_value=cached_value,
        raw_instruction=raw_instruction,
        field_type_code=field_type_code,
    )


def _raw_para_with_fields(fields: list[RawField]) -> RawParagraph:
    return RawParagraph(
        section_idx=0,
        para_idx=0,
        text="",
        char_runs=[],
        tables=[],
        pictures=[],
        formulas=[],
        tocs=[],
        fields=fields,
        list_info=None,
    )


# * 모델 단독


def test_field_block_minimal_roundtrip():
    f = FieldBlock(field_kind="date", prov=_prov())
    reloaded = FieldBlock.model_validate_json(f.model_dump_json())
    assert reloaded == f
    assert reloaded.kind == "field"
    assert reloaded.field_kind == "date"


def test_field_block_default_field_kind_is_unknown():
    f = FieldBlock(prov=_prov())
    assert f.field_kind == "unknown"
    assert f.cached_value is None
    assert f.raw_instruction is None
    assert f.field_type_code is None


def test_field_block_full_roundtrip():
    f = FieldBlock(
        field_kind="hyperlink",
        cached_value="https://example.com",
        raw_instruction='HYPERLINK "https://example.com"',
        field_type_code=42,
        prov=_prov(para_idx=5),
    )
    reloaded = FieldBlock.model_validate_json(f.model_dump_json())
    assert reloaded == f


def test_field_block_extra_forbidden():
    with pytest.raises(ValidationError):
        FieldBlock.model_validate(
            {"kind": "field", "prov": {"section_idx": 0, "para_idx": 0}, "extra": True}
        )


def test_field_block_frozen():
    f = FieldBlock(field_kind="date", prov=_prov())
    with pytest.raises(ValidationError):
        f.field_kind = "path"  # type: ignore[misc]


# * FieldKind 닫힌 Literal — 14 + unknown


def test_field_kind_literal_has_15_values():
    """spec § 7: 14 known FieldType + "unknown"."""
    from typing import get_args

    values = get_args(FieldKind)
    assert len(values) == 15
    assert "unknown" in values


@pytest.mark.parametrize(
    "field_kind",
    [
        "date",
        "doc_date",
        "path",
        "bookmark",
        "mailmerge",
        "crossref",
        "calc",
        "clickhere",
        "summary",
        "userinfo",
        "hyperlink",
        "memo",
        "private_info",
        "toc",
        "unknown",
    ],
)
def test_field_block_accepts_all_known_kinds(field_kind: str):
    f = FieldBlock(field_kind=field_kind, prov=_prov())  # type: ignore[arg-type]
    assert f.field_kind == field_kind


def test_field_block_rejects_invalid_field_kind():
    with pytest.raises(ValidationError):
        FieldBlock.model_validate(
            {
                "kind": "field",
                "field_kind": "foo_bar_kind",
                "prov": {"section_idx": 0, "para_idx": 0},
            }
        )


def test_field_block_calc_distinguishes_from_formula_block():
    """spec § 7: ``"calc"`` 는 HWP FieldType::Formula (계산 필드, 표 합계 등) — 수식 (Equation) 과 다름.

    이름 충돌 회피용 별도 어휘 — Equation 은 ``FormulaBlock`` (kind="formula") 로 매핑.
    """
    f = FieldBlock(field_kind="calc", prov=_prov())
    assert f.field_kind == "calc"
    assert f.kind == "field"
    # ^ FormulaBlock 의 kind="formula" 와 다름


def test_field_block_routes_via_discriminator():
    raw = {
        "kind": "field",
        "field_kind": "crossref",
        "cached_value": "[표 1 참조]",
        "prov": {"section_idx": 0, "para_idx": 5},
    }
    doc = HwpDocument.model_validate({"body": [raw]})
    blk = doc.body[0]
    assert isinstance(blk, FieldBlock)
    assert blk.field_kind == "crossref"


# * mapper — RawField → FieldBlock


def test_build_field_block_known_kind_passes_through():
    blk = _build_field_block(_raw_field(field_kind="date", cached_value="2026-04-26"))
    assert blk.field_kind == "date"
    assert blk.cached_value == "2026-04-26"
    assert blk.raw_instruction is None


def test_build_field_block_unknown_kind_falls_back_to_unknown():
    """spec § 7: 미지의 field_kind 는 "unknown" 으로 강제 + field_type_code 보존."""
    blk = _build_field_block(
        _raw_field(field_kind="future_kind_unknown_to_v0_3_0", field_type_code=99)
    )
    assert blk.field_kind == "unknown"
    assert blk.field_type_code == 99


def test_build_field_block_preserves_provenance():
    blk = _build_field_block(_raw_field(field_kind="path", section_idx=2, para_idx=10))
    assert blk.prov.section_idx == 2
    assert blk.prov.para_idx == 10
    assert blk.prov.char_start is None
    assert blk.prov.char_end is None


def test_build_field_block_preserves_raw_instruction():
    """raw_instruction 은 round-trip 보존용 — Word <w:instrText> 대응."""
    blk = _build_field_block(
        _raw_field(field_kind="hyperlink", raw_instruction='HYPERLINK "https://x"')
    )
    assert blk.raw_instruction == 'HYPERLINK "https://x"'


@pytest.mark.parametrize("field_kind", sorted(_VALID_FIELD_KINDS))
def test_valid_field_kinds_set_matches_literal(field_kind: str):
    """``_VALID_FIELD_KINDS`` 는 FieldKind Literal 의 모든 value 와 정확히 일치."""
    blk = _build_field_block(_raw_field(field_kind=field_kind))
    assert blk.field_kind == field_kind


# * _flatten_paragraph 가 FieldBlock emit


def test_flatten_paragraph_yields_field_block_when_fields_present():
    raw_para = _raw_para_with_fields([_raw_field(field_kind="date")])
    blocks = _flatten_paragraph(raw_para)
    # ^ paragraph + field 두 블록
    assert len(blocks) == 2
    assert isinstance(blocks[0], ParagraphBlock)
    assert isinstance(blocks[1], FieldBlock)


def test_flatten_paragraph_multiple_fields_in_order():
    raw_para = _raw_para_with_fields(
        [
            _raw_field(field_kind="date"),
            _raw_field(field_kind="path"),
            _raw_field(field_kind="hyperlink"),
        ]
    )
    blocks = _flatten_paragraph(raw_para)
    field_kinds = [b.field_kind for b in blocks if isinstance(b, FieldBlock)]
    assert field_kinds == ["date", "path", "hyperlink"]


# * TableOfContents 는 FieldBlock 이 아니라 TocBlock 으로 (별도 테스트는 test_ir_toc.py)


def test_field_block_with_toc_kind_is_user_constructible_only():
    """``"toc"`` field_kind 는 Literal 에 있지만 mapper 는 항상 TocBlock 으로 라우팅한다.

    사용자가 직접 ``FieldBlock(field_kind="toc")`` 로 구성하면 호환을 위해 허용 —
    그러나 to_ir() 경로에서는 TocBlock 으로 분리되므로 등장하지 않는다.
    """
    blk = FieldBlock(field_kind="toc", prov=_prov())
    assert blk.field_kind == "toc"
