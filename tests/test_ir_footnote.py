"""tests/test_ir_footnote.py — Stage S2 FootnoteBlock + EndnoteBlock 매퍼 + furniture 라우팅.

ir-expansion.md §S2 + § 3 검증:

- FootnoteBlock / EndnoteBlock 직렬화 왕복 + frozen + extra=forbid + 분리된 두 타입
- mapper RawFootnote/RawEndnote → 블록 변환 (number, blocks 평탄화, marker_prov)
- build_hwp_document 가 footnotes / endnotes 를 furniture 로 라우팅
- iter_blocks(scope="furniture") 순서 보장: page_headers → page_footers → footnotes → endnotes
- recurse=True 가 FootnoteBlock.blocks 안 paragraphs 를 yield (재귀)
"""

import pytest
import rhwp
from pydantic import ValidationError
from rhwp.ir._mapper import _build_endnote_block, _build_footnote_block, build_hwp_document
from rhwp.ir._raw_types import RawDocument, RawEndnote, RawFootnote, RawParagraph
from rhwp.ir.nodes import (
    EndnoteBlock,
    FootnoteBlock,
    Furniture,
    HwpDocument,
    ParagraphBlock,
    Provenance,
    TableBlock,
    TableCell,
)


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


def _empty_raw_para(*, section_idx: int = 0, para_idx: int = 0, text: str = "") -> RawParagraph:
    return RawParagraph(
        section_idx=section_idx,
        para_idx=para_idx,
        text=text,
        char_runs=[],
        tables=[],
        pictures=[],
        formulas=[],
    )


def _empty_raw_doc(
    *,
    footnotes: list[RawFootnote] | None = None,
    endnotes: list[RawEndnote] | None = None,
) -> RawDocument:
    return RawDocument(
        source_uri=None,
        section_count=1,
        paragraphs=[],
        headers=[],
        footers=[],
        footnotes=footnotes or [],
        endnotes=endnotes or [],
    )


# * 모델 단독 — FootnoteBlock / EndnoteBlock


def test_footnote_block_minimal_roundtrip():
    fn = FootnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="각주 본문", prov=_prov(para_idx=10))],
        marker_prov=_prov(para_idx=5),
        prov=_prov(para_idx=5),
    )
    reloaded = FootnoteBlock.model_validate_json(fn.model_dump_json())
    assert reloaded == fn
    assert reloaded.kind == "footnote"
    assert reloaded.number == 1
    assert len(reloaded.blocks) == 1


def test_endnote_block_minimal_roundtrip():
    en = EndnoteBlock(
        number=2,
        blocks=[ParagraphBlock(text="미주 본문", prov=_prov(para_idx=12))],
        marker_prov=_prov(para_idx=6),
        prov=_prov(para_idx=6),
    )
    reloaded = EndnoteBlock.model_validate_json(en.model_dump_json())
    assert reloaded == en
    assert reloaded.kind == "endnote"


def test_footnote_block_separate_from_endnote_block():
    """FootnoteBlock 과 EndnoteBlock 은 별개 타입 — HWP 가 분리하므로 IR 도 분리."""
    fn = FootnoteBlock(number=1, marker_prov=_prov(), prov=_prov())
    en = EndnoteBlock(number=1, marker_prov=_prov(), prov=_prov())
    assert fn.kind != en.kind
    assert not isinstance(fn, EndnoteBlock)
    assert not isinstance(en, FootnoteBlock)


def test_footnote_block_extra_forbidden():
    with pytest.raises(ValidationError):
        FootnoteBlock.model_validate(
            {
                "kind": "footnote",
                "number": 1,
                "blocks": [],
                "marker_prov": {"section_idx": 0, "para_idx": 0},
                "prov": {"section_idx": 0, "para_idx": 0},
                "extra": "x",
            }
        )


def test_footnote_block_frozen():
    fn = FootnoteBlock(number=1, marker_prov=_prov(), prov=_prov())
    with pytest.raises(ValidationError):
        fn.number = 2  # type: ignore[misc]


def test_footnote_block_routes_via_discriminator():
    raw = {
        "kind": "footnote",
        "number": 7,
        "blocks": [],
        "marker_prov": {"section_idx": 0, "para_idx": 5},
        "prov": {"section_idx": 0, "para_idx": 5},
    }
    fn = HwpDocument.model_validate(
        {"furniture": {"page_headers": [], "page_footers": [], "footnotes": [raw], "endnotes": []}}
    ).furniture.footnotes[0]
    assert isinstance(fn, FootnoteBlock)
    assert fn.number == 7


def test_footnote_block_marker_and_prov_separately_assignable():
    """spec § 3: marker_prov 는 본문 인용 위치, prov 는 각주 본문 위치 — 다른 값 가능."""
    fn = FootnoteBlock(
        number=1,
        marker_prov=_prov(section_idx=0, para_idx=3),
        prov=_prov(section_idx=0, para_idx=3),
    )
    assert fn.marker_prov.para_idx == 3
    assert fn.prov.para_idx == 3


def test_footnote_block_blocks_supports_recursion_with_table():
    """spec § 3: 각주 본문 안에 표가 있어도 ``blocks`` 재귀로 자연 지원."""
    inner = ParagraphBlock(text="셀 텍스트", prov=_prov(para_idx=99))
    cell = TableCell(row=0, col=0, grid_index=0, blocks=[inner])
    inner_table = TableBlock(rows=1, cols=1, cells=[cell], prov=_prov(para_idx=99))
    fn = FootnoteBlock(
        number=1,
        blocks=[inner_table],
        marker_prov=_prov(),
        prov=_prov(),
    )
    reloaded = FootnoteBlock.model_validate_json(fn.model_dump_json())
    assert isinstance(reloaded.blocks[0], TableBlock)


# * mapper — RawFootnote → FootnoteBlock


def test_build_footnote_block_preserves_number_and_marker():
    raw = RawFootnote(
        marker_section_idx=2,
        marker_para_idx=15,
        number=3,
        blocks=[_empty_raw_para(text="본문")],
    )
    fn = _build_footnote_block(raw)
    assert fn.number == 3
    assert fn.marker_prov.section_idx == 2
    assert fn.marker_prov.para_idx == 15
    assert fn.prov.section_idx == 2
    assert fn.prov.para_idx == 15
    assert len(fn.blocks) == 1


def test_build_footnote_block_flattens_inner_paragraphs():
    """각주 본문 안에 여러 paragraph + 표 가 있으면 평탄화 적용."""
    raw = RawFootnote(
        marker_section_idx=0,
        marker_para_idx=5,
        number=1,
        blocks=[_empty_raw_para(text="첫 줄"), _empty_raw_para(text="둘째 줄")],
    )
    fn = _build_footnote_block(raw)
    assert len(fn.blocks) == 2
    texts = [b.text for b in fn.blocks if isinstance(b, ParagraphBlock)]
    assert texts == ["첫 줄", "둘째 줄"]


def test_build_endnote_block_mirrors_footnote_pattern():
    raw = RawEndnote(
        marker_section_idx=1,
        marker_para_idx=8,
        number=42,
        blocks=[_empty_raw_para(text="미주 텍스트")],
    )
    en = _build_endnote_block(raw)
    assert en.number == 42
    assert en.marker_prov.section_idx == 1
    assert en.marker_prov.para_idx == 8


# * build_hwp_document — furniture.footnotes / endnotes 라우팅


def test_build_hwp_document_routes_footnotes_to_furniture():
    raw = _empty_raw_doc(
        footnotes=[
            RawFootnote(
                marker_section_idx=0,
                marker_para_idx=2,
                number=1,
                blocks=[_empty_raw_para(text="footnote body")],
            )
        ]
    )
    ir = build_hwp_document(raw)
    assert ir.body == []
    assert len(ir.furniture.footnotes) == 1
    fn = ir.furniture.footnotes[0]
    assert isinstance(fn, FootnoteBlock)
    assert fn.number == 1


def test_build_hwp_document_routes_endnotes_to_furniture():
    raw = _empty_raw_doc(
        endnotes=[
            RawEndnote(
                marker_section_idx=0,
                marker_para_idx=10,
                number=5,
                blocks=[_empty_raw_para(text="endnote body")],
            )
        ]
    )
    ir = build_hwp_document(raw)
    assert len(ir.furniture.endnotes) == 1
    en = ir.furniture.endnotes[0]
    assert isinstance(en, EndnoteBlock)
    assert en.number == 5


def test_iter_blocks_furniture_order_includes_footnotes_endnotes():
    """순서: page_headers → page_footers → footnotes → endnotes (수동 주입)."""
    para_h = ParagraphBlock(text="H", prov=_prov(para_idx=1))
    para_f = ParagraphBlock(text="F", prov=_prov(para_idx=2))
    fn = FootnoteBlock(number=1, marker_prov=_prov(), prov=_prov())
    en = EndnoteBlock(number=1, marker_prov=_prov(), prov=_prov())
    ir = HwpDocument(
        furniture=Furniture(
            page_headers=[para_h],
            page_footers=[para_f],
            footnotes=[fn],
            endnotes=[en],
        )
    )
    seq = list(ir.iter_blocks(scope="furniture", recurse=False))
    assert seq == [para_h, para_f, fn, en]


def test_iter_blocks_recurse_enters_footnote_blocks():
    """recurse=True 면 FootnoteBlock.blocks 의 inner paragraph 까지 yield."""
    inner = ParagraphBlock(text="각주 텍스트", prov=_prov(para_idx=99))
    fn = FootnoteBlock(number=1, blocks=[inner], marker_prov=_prov(), prov=_prov())
    ir = HwpDocument(furniture=Furniture(footnotes=[fn]))
    recursed = list(ir.iter_blocks(scope="furniture", recurse=True))
    assert recursed == [fn, inner]
    no_rec = list(ir.iter_blocks(scope="furniture", recurse=False))
    assert no_rec == [fn]


def test_iter_blocks_recurse_enters_endnote_blocks():
    inner = ParagraphBlock(text="미주 텍스트", prov=_prov(para_idx=99))
    en = EndnoteBlock(number=1, blocks=[inner], marker_prov=_prov(), prov=_prov())
    ir = HwpDocument(furniture=Furniture(endnotes=[en]))
    recursed = list(ir.iter_blocks(scope="furniture", recurse=True))
    assert recursed == [en, inner]


# * 본문 vs furniture 분리 — body 에 footnote/endnote 가 안 나타남 (계약)


def test_footnotes_endnotes_never_appear_in_body():
    """spec § 3 body vs furniture 배치: 각주/미주 본문은 furniture 로만 라우팅.

    본문 인라인 마커는 InlineRun.text 그대로 보존되지만 FootnoteBlock 자체는
    body 에 나오지 않는다 — RAG body 검색 오염 회피.
    """
    raw = _empty_raw_doc(
        footnotes=[
            RawFootnote(
                marker_section_idx=0,
                marker_para_idx=0,
                number=1,
                blocks=[_empty_raw_para(text="x")],
            )
        ],
        endnotes=[
            RawEndnote(
                marker_section_idx=0,
                marker_para_idx=0,
                number=1,
                blocks=[_empty_raw_para(text="y")],
            )
        ],
    )
    ir = build_hwp_document(raw)
    assert ir.body == []
    for blk in ir.body:
        assert not isinstance(blk, (FootnoteBlock, EndnoteBlock))


# * 실제 샘플 — 각주가 있으면 furniture.footnotes 에 노출, 없으면 skip


def test_real_sample_footnotes_exposed_in_furniture(parsed_hwp: rhwp.Document):
    ir = parsed_hwp.to_ir()
    if not ir.furniture.footnotes:
        pytest.skip("aift.hwp 샘플에 각주 컨트롤 없음")
    for fn in ir.furniture.footnotes:
        assert isinstance(fn, FootnoteBlock)
        assert fn.number >= 1
        assert isinstance(fn.marker_prov, Provenance)


def test_real_sample_endnotes_exposed_in_furniture(parsed_hwp: rhwp.Document):
    ir = parsed_hwp.to_ir()
    if not ir.furniture.endnotes:
        pytest.skip("aift.hwp 샘플에 미주 컨트롤 없음")
    for en in ir.furniture.endnotes:
        assert isinstance(en, EndnoteBlock)
