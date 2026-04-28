"""tests/test_ir_list.py — Stage S3 ListItemBlock + RawListInfo 매퍼.

ir-expansion.md §S3 + § 4 ListItemBlock 검증:

- ListItemBlock 직렬화 왕복 + frozen + extra=forbid
- mapper RawParagraph + list_info → ListItemBlock (paragraph 자체가 list item)
- list_info=None 인 paragraph 는 ParagraphBlock 으로 출고 (호환)
- enumerated/marker/level 조합 (HWP head_type Number/Bullet/Outline 매핑)
- ListItemBlock 이 Block 유니온의 list_item variant 로 라우팅
- 본문 + 셀 안 + 각주 본문 안 모두에서 ListItemBlock 출현 가능
"""

import pytest
from pydantic import ValidationError
from rhwp.ir._mapper import _build_list_item_block, _flatten_paragraph
from rhwp.ir._raw_types import RawListInfo, RawParagraph
from rhwp.ir.nodes import (
    HwpDocument,
    ListItemBlock,
    ParagraphBlock,
    Provenance,
)


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


def _raw_para(
    *,
    text: str = "",
    list_info: RawListInfo | None = None,
    section_idx: int = 0,
    para_idx: int = 0,
) -> RawParagraph:
    return RawParagraph(
        section_idx=section_idx,
        para_idx=para_idx,
        text=text,
        char_runs=[],
        tables=[],
        pictures=[],
        formulas=[],
        tocs=[],
        fields=[],
        list_info=list_info,
    )


# * 모델 단독


def test_list_item_block_minimal_roundtrip():
    li = ListItemBlock(text="첫 항목", marker="•", enumerated=False, level=0, prov=_prov())
    reloaded = ListItemBlock.model_validate_json(li.model_dump_json())
    assert reloaded == li
    assert reloaded.kind == "list_item"


def test_list_item_block_default_fields():
    li = ListItemBlock(prov=_prov())
    assert li.text == ""
    assert li.inlines == []
    assert li.enumerated is False
    assert li.marker == "-"
    assert li.level == 0


def test_list_item_block_extra_forbidden():
    with pytest.raises(ValidationError):
        ListItemBlock.model_validate(
            {
                "kind": "list_item",
                "text": "x",
                "prov": {"section_idx": 0, "para_idx": 0},
                "extra": True,
            }
        )


def test_list_item_block_frozen():
    li = ListItemBlock(text="x", prov=_prov())
    with pytest.raises(ValidationError):
        li.text = "y"  # type: ignore[misc]


def test_list_item_block_routes_via_discriminator():
    raw = {
        "kind": "list_item",
        "text": "본문",
        "marker": "1.",
        "enumerated": True,
        "level": 2,
        "prov": {"section_idx": 0, "para_idx": 5},
    }
    doc = HwpDocument.model_validate({"body": [raw]})
    blk = doc.body[0]
    assert isinstance(blk, ListItemBlock)
    assert blk.marker == "1."
    assert blk.level == 2


# * mapper — _flatten_paragraph 가 list_info 보고 분기


def test_paragraph_without_list_info_yields_paragraph_block():
    raw = _raw_para(text="일반 단락", list_info=None)
    blocks = _flatten_paragraph(raw)
    assert len(blocks) == 1
    assert isinstance(blocks[0], ParagraphBlock)
    assert blocks[0].text == "일반 단락"


def test_paragraph_with_list_info_yields_list_item_block():
    raw = _raw_para(
        text="첫 항목",
        list_info=RawListInfo(head_type="number", level=0),
    )
    blocks = _flatten_paragraph(raw)
    assert len(blocks) == 1
    assert isinstance(blocks[0], ListItemBlock)
    assert blocks[0].text == "첫 항목"
    assert blocks[0].marker == "1."
    assert blocks[0].enumerated is True


@pytest.mark.parametrize(
    "head_type,expected_marker,expected_enum",
    [
        # ^ HWP HeadType 매핑 결과: Number/Outline → enumerated=True+"1.", Bullet → False+"•"
        ("number", "1.", True),
        ("outline", "1.", True),
        ("bullet", "•", False),
    ],
)
def test_build_list_item_marker_placeholder_by_head_type(
    head_type: str, expected_marker: str, expected_enum: bool
):
    raw = _raw_para(text="항목", list_info=RawListInfo(head_type=head_type, level=2))
    li = _build_list_item_block(raw)
    assert li.marker == expected_marker
    assert li.enumerated == expected_enum
    assert li.level == 2


def test_build_list_item_unknown_head_type_falls_back():
    """Rust 가 새 HeadType variant 추가 시 forward-compat — '-' / False 폴백."""
    raw = _raw_para(text="x", list_info=RawListInfo(head_type="future_head", level=0))
    li = _build_list_item_block(raw)
    assert li.marker == "-"
    assert li.enumerated is False


def test_build_list_item_preserves_provenance():
    raw = _raw_para(
        text="x",
        section_idx=2,
        para_idx=10,
        list_info=RawListInfo(head_type="bullet", level=0),
    )
    li = _build_list_item_block(raw)
    assert li.prov.section_idx == 2
    assert li.prov.para_idx == 10
    assert li.prov.char_start == 0
    assert li.prov.char_end == len("x")


def test_build_list_item_inlines_match_paragraph_pattern():
    """list_item 의 inlines 는 ParagraphBlock 과 동일 — char_runs 부재 시 단일 폴백 런."""
    raw = _raw_para(
        text="항목",
        list_info=RawListInfo(head_type="bullet", level=0),
    )
    li = _build_list_item_block(raw)
    assert len(li.inlines) == 1
    assert li.inlines[0].text == "항목"
    assert li.inlines[0].raw_style_id is None  # ^ char_runs 부재 폴백


def test_list_item_blocks_can_appear_in_table_cell():
    """ListItemBlock 이 셀 안 paragraph (list_info 가짐) 의 평탄화 결과로도 등장."""
    inner_raw = _raw_para(
        text="셀 안 항목",
        list_info=RawListInfo(head_type="number", level=0),
    )
    cell_blocks = _flatten_paragraph(inner_raw)
    assert isinstance(cell_blocks[0], ListItemBlock)


def test_build_list_item_raises_when_list_info_none():
    """fail-fast — _flatten_paragraph 가 분기 보장하지만 직접 호출 시 명확한 에러."""
    raw = _raw_para(text="x", list_info=None)
    with pytest.raises(ValueError, match="list_info"):
        _build_list_item_block(raw)


# * level / marker placeholder 한계 — spec § 4 의 v0.3.0 단순 정책 명시


def test_marker_is_placeholder_in_v0_3_0():
    """v0.3.0 매퍼는 marker placeholder 만 출고 — Numbering.level_formats lookup 은 v0.4.0+.

    실제 marker 정확도가 필요한 사용자는 외부 후처리 또는 v0.4.0 업그레이드.
    """
    raw = _raw_para(text="x", list_info=RawListInfo(head_type="number", level=3))
    li = _build_list_item_block(raw)
    # ^ level=3 이어도 marker 는 "1." placeholder — 실제는 "(가)" 등일 수 있음
    assert li.marker == "1."
    assert li.level == 3
