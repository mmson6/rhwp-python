"""tests/test_ir_formula.py — Stage S2 FormulaBlock + simple_eq_text_alt 매퍼.

ir-expansion.md §S2 + § 2 FormulaBlock 검증:

- FormulaBlock 직렬화 왕복 + frozen + extra=forbid
- script_kind 닫힌 Literal 검증 ("hwp_eq" / "latex" / "mathml" / 그 외 거부)
- mapper RawFormula → FormulaBlock 변환 (script + text_alt + Provenance)
- text_alt 단순 정규화 (over → /, sqrt → √, {} → ()) 동작 확인
- model_copy 패턴 (사용자가 외부 LaTeX 변환 후 script_kind 갱신) 가능
"""

import pytest
import rhwp
from pydantic import ValidationError
from rhwp.ir._mapper import _build_formula_block
from rhwp.ir._raw_types import RawFormula
from rhwp.ir.nodes import FormulaBlock, HwpDocument, Provenance


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


# * 모델 단독


def test_formula_block_minimal_roundtrip():
    f = FormulaBlock(script="1 over 2", prov=_prov())
    reloaded = FormulaBlock.model_validate_json(f.model_dump_json())
    assert reloaded == f
    assert reloaded.script_kind == "hwp_eq"
    assert reloaded.inline is False
    assert reloaded.text_alt is None


def test_formula_block_full_roundtrip():
    f = FormulaBlock(
        script=r"\frac{1}{2}",
        script_kind="latex",
        text_alt="1/2",
        inline=True,
        prov=_prov(para_idx=3),
    )
    reloaded = FormulaBlock.model_validate_json(f.model_dump_json())
    assert reloaded == f


def test_formula_block_kind_is_formula():
    assert FormulaBlock(script="x", prov=_prov()).kind == "formula"


def test_formula_block_extra_forbidden():
    with pytest.raises(ValidationError):
        FormulaBlock.model_validate(
            {
                "kind": "formula",
                "script": "x",
                "prov": {"section_idx": 0, "para_idx": 0},
                "extra": "y",
            }
        )


def test_formula_block_frozen():
    f = FormulaBlock(script="x", prov=_prov())
    with pytest.raises(ValidationError):
        f.script = "y"  # type: ignore[misc]


@pytest.mark.parametrize("script_kind", ["hwp_eq", "latex", "mathml"])
def test_formula_block_accepts_known_script_kinds(script_kind: str):
    f = FormulaBlock(script="x", script_kind=script_kind, prov=_prov())  # type: ignore[arg-type]
    assert f.script_kind == script_kind


def test_formula_block_rejects_unknown_script_kind():
    with pytest.raises(ValidationError):
        FormulaBlock.model_validate(
            {
                "kind": "formula",
                "script": "x",
                "script_kind": "asciimath",
                "prov": {"section_idx": 0, "para_idx": 0},
            }
        )


def test_formula_block_routes_via_discriminator():
    raw = {
        "kind": "formula",
        "script": "1 over 2",
        "prov": {"section_idx": 0, "para_idx": 5},
    }
    doc = HwpDocument.model_validate({"body": [raw]})
    blk = doc.body[0]
    assert isinstance(blk, FormulaBlock)
    assert blk.script == "1 over 2"


def test_formula_block_model_copy_pattern_for_external_latex_conversion():
    """사용자가 외부에서 LaTeX 변환 후 model_copy 로 IR 재구성 가능 (frozen 친화)."""
    raw = FormulaBlock(script="1 over 2", prov=_prov())
    converted = raw.model_copy(update={"script": r"\frac{1}{2}", "script_kind": "latex"})
    assert converted.script == r"\frac{1}{2}"
    assert converted.script_kind == "latex"
    assert raw.script_kind == "hwp_eq"  # ^ 원본 불변


# * mapper — RawFormula → FormulaBlock


def _raw_formula(
    *,
    section_idx: int = 0,
    para_idx: int = 0,
    script: str = "1 over 2",
    text_alt: str | None = None,
) -> RawFormula:
    return RawFormula(
        section_idx=section_idx,
        para_idx=para_idx,
        script=script,
        text_alt=text_alt,
    )


def test_build_formula_block_preserves_script_and_prov():
    blk = _build_formula_block(_raw_formula(section_idx=1, para_idx=2, script="x^2 + y^2"))
    assert blk.script == "x^2 + y^2"
    assert blk.script_kind == "hwp_eq"
    assert blk.prov.section_idx == 1
    assert blk.prov.para_idx == 2
    assert blk.prov.char_start is None
    assert blk.prov.char_end is None


def test_build_formula_block_preserves_text_alt():
    blk = _build_formula_block(_raw_formula(script="1 over 2", text_alt="1 / 2"))
    assert blk.text_alt == "1 / 2"


def test_build_formula_block_text_alt_can_be_none():
    blk = _build_formula_block(_raw_formula(text_alt=None))
    assert blk.text_alt is None


# * 실제 샘플 — equation 이 있으면 FormulaBlock 으로 노출, 없으면 skip


def _find_formulas(ir: HwpDocument) -> list[FormulaBlock]:
    return [b for b in ir.iter_blocks(scope="all", recurse=True) if isinstance(b, FormulaBlock)]


def test_formula_inside_table_cell_is_flattened():
    """Formula 가 셀 paragraph.controls 에 있으면 cell.blocks 에 FormulaBlock 출현."""
    from rhwp.ir._mapper import build_hwp_document
    from rhwp.ir._raw_types import RawDocument, RawParagraph
    from rhwp.ir.nodes import TableBlock

    raw_inner_para: RawParagraph = {
        "section_idx": 0,
        "para_idx": 0,
        "text": "셀 단락",
        "char_runs": [],
        "tables": [],
        "pictures": [],
        "formulas": [
            {
                "section_idx": 0,
                "para_idx": 0,
                "script": "x^2",
                "text_alt": None,
            }
        ],
        "tocs": [],
        "fields": [],
        "list_info": None,
    }
    raw_para_with_table: RawParagraph = {
        "section_idx": 0,
        "para_idx": 0,
        "text": "",
        "char_runs": [],
        "tables": [
            {
                "rows": 1,
                "cols": 1,
                "caption": None,
                "caption_block": None,
                "cells": [
                    {
                        "row": 0,
                        "col": 0,
                        "row_span": 1,
                        "col_span": 1,
                        "is_header": False,
                        "paragraphs": [raw_inner_para],
                    }
                ],
            }
        ],
        "pictures": [],
        "formulas": [],
        "tocs": [],
        "fields": [],
        "list_info": None,
    }
    raw = RawDocument(
        source_uri=None,
        section_count=1,
        paragraphs=[raw_para_with_table],
        headers=[],
        footers=[],
        footnotes=[],
        endnotes=[],
    )
    ir = build_hwp_document(raw)
    table = next(b for b in ir.body if isinstance(b, TableBlock))
    cell_blocks = table.cells[0].blocks
    formulas = [b for b in cell_blocks if isinstance(b, FormulaBlock)]
    assert len(formulas) == 1
    assert formulas[0].script == "x^2"


def test_formula_inside_footnote_body_is_flattened():
    """Formula 가 각주 본문 paragraph.controls 에 있으면 footnote.blocks 에 출현."""
    from rhwp.ir._mapper import build_hwp_document
    from rhwp.ir._raw_types import RawDocument, RawFootnote, RawParagraph

    raw_inner_para: RawParagraph = {
        "section_idx": 0,
        "para_idx": 0,
        "text": "각주 본문",
        "char_runs": [],
        "tables": [],
        "pictures": [],
        "formulas": [
            {
                "section_idx": 0,
                "para_idx": 0,
                "script": "1 over 2",
                "text_alt": "1 / 2",
            }
        ],
        "tocs": [],
        "fields": [],
        "list_info": None,
    }
    raw = RawDocument(
        source_uri=None,
        section_count=1,
        paragraphs=[],
        headers=[],
        footers=[],
        footnotes=[
            RawFootnote(
                marker_section_idx=0,
                marker_para_idx=5,
                number=1,
                blocks=[raw_inner_para],
            )
        ],
        endnotes=[],
    )
    ir = build_hwp_document(raw)
    fn = ir.furniture.footnotes[0]
    formulas = [b for b in fn.blocks if isinstance(b, FormulaBlock)]
    assert len(formulas) == 1
    assert formulas[0].script == "1 over 2"


@pytest.mark.parametrize(
    "text_alt_input,expected",
    [
        # ^ Rust 가 정규화한 결과가 들어왔을 때 Python mapper 는 보존만 한다.
        #   Rust 측 토큰 경계 단위 테스트는 src/ir.rs::tests::simple_eq_text_alt_*.
        ("1 / 2", "1 / 2"),
        ("√(x^2 + 1)", "√(x^2 + 1)"),
        ("sqrtish", "sqrtish"),  # ^ 토큰 경계 — 식별자 일부는 그대로
        ("discover", "discover"),
        (None, None),
    ],
)
def test_build_formula_block_preserves_text_alt_verbatim(
    text_alt_input: str | None, expected: str | None
):
    """mapper 는 Rust 가 정규화한 ``text_alt`` 를 그대로 보존 (재변환 금지).

    토큰 경계 인식 (``sqrtish`` 같은 식별자 부분 매치 회피) 은 Rust 측
    ``simple_eq_text_alt`` 의 책임이며, 본 테스트는 Python mapper 가 결과를
    재가공하지 않음을 픽스로 고정한다.
    """
    blk = _build_formula_block(_raw_formula(script="raw", text_alt=text_alt_input))
    assert blk.text_alt == expected


def test_real_sample_formulas_have_required_fields(parsed_hwp: rhwp.Document):
    ir = parsed_hwp.to_ir()
    formulas = _find_formulas(ir)
    if not formulas:
        pytest.skip("aift.hwp 샘플에 수식 컨트롤 없음")
    for f in formulas:
        assert f.kind == "formula"
        assert isinstance(f.script, str)
        assert f.script_kind == "hwp_eq"
        assert isinstance(f.prov, Provenance)
