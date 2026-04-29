"""tests/test_ir_caption.py — Stage S3 CaptionBlock + Picture/Table caption 부착.

ir-expansion.md §S3 + § 5 CaptionBlock 검증:

- CaptionBlock 직렬화 왕복 + frozen + extra=forbid + direction Literal 닫힌 어휘
- mapper RawCaption → CaptionBlock + paragraphs 평탄화
- PictureBlock.caption 부착 (S3 신규)
- TableBlock.caption_block 부착 (v0.2.0 caption: str 호환 보존)
- iter_blocks recurse=True 가 PictureBlock.caption 에 진입하지 않음 (RAG 노이즈 회피)
- iter_blocks recurse=True 가 단독 body CaptionBlock.blocks 에는 진입
"""

import pytest
from pydantic import ValidationError
from rhwp.ir._mapper import _build_caption_block, _build_picture_block, build_hwp_document
from rhwp.ir._raw_types import (
    RawCaption,
    RawDocument,
    RawImageRef,
    RawParagraph,
    RawPicture,
    RawTable,
)
from rhwp.ir.nodes import (
    CaptionBlock,
    HwpDocument,
    ParagraphBlock,
    PictureBlock,
    Provenance,
    TableBlock,
    TableCell,
)

pytestmark = pytest.mark.spec("v0.3.0/ir-expansion")
# ^ soft retrofit — file-level spec mapping; v0.4.0+ specs add #AC-N to specific tests (CONVENTIONS § Trace report)


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


def _raw_para(text: str = "", section_idx: int = 0, para_idx: int = 0) -> RawParagraph:
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
        list_info=None,
    )


# * 모델 단독


def test_caption_block_minimal_roundtrip():
    cap = CaptionBlock(
        blocks=[ParagraphBlock(text="<그림 1> 회로도", prov=_prov())],
        direction="bottom",
        prov=_prov(),
    )
    reloaded = CaptionBlock.model_validate_json(cap.model_dump_json())
    assert reloaded == cap
    assert reloaded.kind == "caption"


def test_caption_block_default_direction_is_bottom():
    cap = CaptionBlock(prov=_prov())
    assert cap.direction == "bottom"
    assert cap.blocks == []


def test_caption_block_extra_forbidden():
    with pytest.raises(ValidationError):
        CaptionBlock.model_validate(
            {"kind": "caption", "prov": {"section_idx": 0, "para_idx": 0}, "extra": "x"}
        )


def test_caption_block_frozen():
    cap = CaptionBlock(prov=_prov())
    with pytest.raises(ValidationError):
        cap.direction = "top"  # type: ignore[misc]


@pytest.mark.parametrize("direction", ["top", "bottom", "left", "right"])
def test_caption_block_accepts_valid_directions(direction: str):
    cap = CaptionBlock(direction=direction, prov=_prov())  # type: ignore[arg-type]
    assert cap.direction == direction


def test_caption_block_rejects_unknown_direction():
    with pytest.raises(ValidationError):
        CaptionBlock.model_validate(
            {
                "kind": "caption",
                "direction": "diagonal",
                "prov": {"section_idx": 0, "para_idx": 0},
            }
        )


def test_caption_block_routes_via_discriminator_in_body():
    raw = {
        "kind": "caption",
        "blocks": [],
        "direction": "top",
        "prov": {"section_idx": 0, "para_idx": 0},
    }
    doc = HwpDocument.model_validate({"body": [raw]})
    blk = doc.body[0]
    assert isinstance(blk, CaptionBlock)
    assert blk.direction == "top"


# * PictureBlock.caption 컨테인먼트


def test_picture_block_caption_field_default_none():
    pic = PictureBlock(prov=_prov())
    assert pic.caption is None


def test_picture_block_caption_roundtrip():
    cap = CaptionBlock(
        blocks=[ParagraphBlock(text="설명", prov=_prov())],
        direction="bottom",
        prov=_prov(),
    )
    pic = PictureBlock(caption=cap, description="설명", prov=_prov())
    reloaded = PictureBlock.model_validate_json(pic.model_dump_json())
    assert reloaded == pic
    assert reloaded.caption is not None
    assert reloaded.caption.direction == "bottom"


# * TableBlock.caption_block 컨테인먼트 + v0.2.0 caption 호환


def test_table_block_caption_block_field_default_none():
    tbl = TableBlock(rows=1, cols=1, prov=_prov())
    assert tbl.caption_block is None
    assert tbl.caption is None  # ^ v0.2.0 호환 필드 기본값


def test_table_block_caption_str_and_caption_block_coexist():
    """v0.2.0 호환 caption: str 와 신규 caption_block: CaptionBlock 둘 다 채울 수 있다."""
    cap = CaptionBlock(
        blocks=[ParagraphBlock(text="<표 1> 결과", prov=_prov())],
        prov=_prov(),
    )
    tbl = TableBlock(
        rows=1,
        cols=1,
        caption="<표 1> 결과",
        caption_block=cap,
        prov=_prov(),
    )
    reloaded = TableBlock.model_validate_json(tbl.model_dump_json())
    assert reloaded.caption == "<표 1> 결과"
    assert reloaded.caption_block is not None
    assert reloaded.caption_block.direction == "bottom"


def test_table_block_caption_str_only_v0_2_0_pattern():
    """v0.2.0 시대처럼 caption_block 없이 caption: str 만 채워도 호환 유지."""
    tbl = TableBlock(rows=1, cols=1, caption="단순 캡션", prov=_prov())
    reloaded = TableBlock.model_validate_json(tbl.model_dump_json())
    assert reloaded.caption == "단순 캡션"
    assert reloaded.caption_block is None


# * mapper — RawCaption → CaptionBlock


def _raw_caption(direction: str = "bottom", texts: tuple[str, ...] = ("캡션",)) -> RawCaption:
    return RawCaption(
        direction=direction,
        section_idx=0,
        para_idx=0,
        paragraphs=[_raw_para(text=t) for t in texts],
    )


def test_build_caption_block_paragraphs_flattened():
    raw = _raw_caption(direction="bottom", texts=("줄1", "줄2"))
    cap = _build_caption_block(raw)
    assert cap.direction == "bottom"
    assert len(cap.blocks) == 2
    assert all(isinstance(b, ParagraphBlock) for b in cap.blocks)
    texts = [b.text for b in cap.blocks if isinstance(b, ParagraphBlock)]
    assert texts == ["줄1", "줄2"]


def test_build_caption_block_unknown_direction_falls_back_to_bottom():
    """Rust 가 새 CaptionDirection variant 를 추가할 때 forward-compat — bottom 폴백."""
    raw = _raw_caption(direction="diagonal", texts=("x",))  # ^ Literal 어휘 외
    cap = _build_caption_block(raw)
    assert cap.direction == "bottom"


@pytest.mark.parametrize("direction", ["top", "bottom", "left", "right"])
def test_build_caption_block_preserves_known_directions(direction: str):
    raw = _raw_caption(direction=direction, texts=("x",))
    cap = _build_caption_block(raw)
    assert cap.direction == direction


# * mapper — RawPicture.caption (S3 신규)


def test_build_picture_block_with_caption_field():
    raw_pic = RawPicture(
        section_idx=0,
        para_idx=0,
        image=RawImageRef(bin_data_id=1, extension="png", has_content=True),
        description="alt-text",
        caption=_raw_caption(direction="bottom", texts=("<그림 1> 회로도",)),
    )
    pic = _build_picture_block(raw_pic)
    assert pic.caption is not None
    assert pic.caption.direction == "bottom"
    assert len(pic.caption.blocks) == 1
    blk = pic.caption.blocks[0]
    assert isinstance(blk, ParagraphBlock)
    assert blk.text == "<그림 1> 회로도"


def test_build_picture_block_caption_none_when_raw_caption_none():
    raw_pic = RawPicture(
        section_idx=0,
        para_idx=0,
        image=None,
        description=None,
        caption=None,
    )
    pic = _build_picture_block(raw_pic)
    assert pic.caption is None


def test_build_picture_preserves_description_alongside_caption():
    """description (S1 호환) 과 caption (S3 신규) 모두 채울 수 있다 — 둘은 다른 source path."""
    raw_pic = RawPicture(
        section_idx=0,
        para_idx=0,
        image=None,
        description="caption text fallback",
        caption=_raw_caption(direction="bottom", texts=("caption text fallback",)),
    )
    pic = _build_picture_block(raw_pic)
    assert pic.description == "caption text fallback"
    assert pic.caption is not None


# * mapper — RawTable.caption_block (S3 신규)


def test_build_hwp_document_table_with_caption_block_routed():
    raw_table = RawTable(
        rows=1,
        cols=1,
        cells=[],
        caption="단순 캡션",
        caption_block=_raw_caption(direction="top", texts=("단순 캡션",)),
    )
    raw_para = RawParagraph(
        section_idx=0,
        para_idx=0,
        text="",
        char_runs=[],
        tables=[raw_table],
        pictures=[],
        formulas=[],
        tocs=[],
        fields=[],
        list_info=None,
    )
    raw_doc = RawDocument(
        source_uri=None,
        section_count=1,
        paragraphs=[raw_para],
        headers=[],
        footers=[],
        footnotes=[],
        endnotes=[],
    )
    ir = build_hwp_document(raw_doc)
    tbl = next(b for b in ir.body if isinstance(b, TableBlock))
    assert tbl.caption == "단순 캡션"
    assert tbl.caption_block is not None
    assert tbl.caption_block.direction == "top"


# * iter_blocks 재귀 — CaptionBlock 정책


def test_iter_blocks_recurse_does_not_enter_picture_caption():
    """spec: PictureBlock.caption 은 부모 metadata 로 간주 — recurse 진입 안 함."""
    inner = ParagraphBlock(text="caption text", prov=_prov())
    cap = CaptionBlock(blocks=[inner], prov=_prov())
    pic = PictureBlock(caption=cap, prov=_prov())
    ir = HwpDocument(body=[pic])
    seq = list(ir.iter_blocks(scope="body", recurse=True))
    # ^ PictureBlock 자체는 yield, caption.blocks 안의 paragraph 는 yield 안 됨
    assert pic in seq
    assert inner not in seq


def test_iter_blocks_recurse_does_not_enter_table_caption_block():
    inner = ParagraphBlock(text="caption text", prov=_prov())
    cap = CaptionBlock(blocks=[inner], prov=_prov())
    tbl = TableBlock(rows=1, cols=1, caption_block=cap, prov=_prov())
    ir = HwpDocument(body=[tbl])
    seq = list(ir.iter_blocks(scope="body", recurse=True))
    assert tbl in seq
    assert inner not in seq


def test_iter_blocks_recurse_enters_standalone_caption_in_body():
    """단독 body CaptionBlock 의 blocks 는 재귀 진입 (TableCell.blocks 와 같은 패턴)."""
    inner = ParagraphBlock(text="standalone", prov=_prov())
    cap = CaptionBlock(blocks=[inner], prov=_prov())
    ir = HwpDocument(body=[cap])
    seq = list(ir.iter_blocks(scope="body", recurse=True))
    assert cap in seq
    assert inner in seq


def test_iter_blocks_recurse_enters_caption_inside_table_cell():
    """CaptionBlock 안에 표가 있어 재귀해야 하는 경우 (사용자 직접 구성 경로)."""
    leaf = ParagraphBlock(text="cell text", prov=_prov())
    inner_cell = TableCell(row=0, col=0, grid_index=0, blocks=[leaf])
    inner_table = TableBlock(rows=1, cols=1, cells=[inner_cell], prov=_prov())
    cap = CaptionBlock(blocks=[inner_table], prov=_prov())
    ir = HwpDocument(body=[cap])
    recursed = list(ir.iter_blocks(scope="body", recurse=True))
    assert recursed == [cap, inner_table, leaf]
