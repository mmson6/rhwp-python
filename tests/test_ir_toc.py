"""tests/test_ir_toc.py — Stage S3 TocBlock + TocEntryBlock 매퍼.

ir-expansion.md §S3 + § 6 TocBlock/TocEntryBlock 검증:

- TocBlock 직렬화 왕복 + frozen + extra=forbid
- TocEntryBlock 은 Block 유니온 멤버 아님 (TocBlock.entries 안 leaf type)
- mapper RawToc → TocBlock (v0.3.0 entries 빈 리스트 placeholder)
- ``is_stale`` 항상 False / ``target_section_idx`` 항상 None (v0.3.0 정책)
- TocBlock 이 본문 평탄화에서 등장 (FieldType::TableOfContents → TocBlock)
- iter_blocks 가 TocBlock 만 yield, TocEntryBlock 은 yield 안 함
"""

import pytest
from pydantic import ValidationError
from rhwp.ir._mapper import _build_toc_block, _flatten_paragraph
from rhwp.ir._raw_types import RawParagraph, RawToc, RawTocEntry
from rhwp.ir.nodes import (
    HwpDocument,
    ParagraphBlock,
    Provenance,
    TocBlock,
    TocEntryBlock,
    UnknownBlock,
)

pytestmark = pytest.mark.spec("v0.3.0/ir-expansion")
# ^ soft retrofit — file-level spec mapping; v0.4.0+ specs add #AC-N to specific tests (CONVENTIONS § Trace report)


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


def _raw_para_with_tocs(tocs: list[RawToc]) -> RawParagraph:
    return RawParagraph(
        section_idx=0,
        para_idx=0,
        text="",
        char_runs=[],
        tables=[],
        pictures=[],
        formulas=[],
        tocs=tocs,
        fields=[],
        list_info=None,
    )


# * 모델 단독 — TocBlock


def test_toc_block_minimal_roundtrip():
    toc = TocBlock(entries=[], prov=_prov())
    reloaded = TocBlock.model_validate_json(toc.model_dump_json())
    assert reloaded == toc
    assert reloaded.kind == "toc"
    assert reloaded.entries == []


def test_toc_block_with_entries_roundtrip():
    entries = [
        TocEntryBlock(text="1장 서론", level=1, cached_page=1, prov=_prov()),
        TocEntryBlock(text="1.1 배경", level=2, cached_page=2, prov=_prov()),
    ]
    toc = TocBlock(entries=entries, prov=_prov())
    reloaded = TocBlock.model_validate_json(toc.model_dump_json())
    assert reloaded == toc
    assert len(reloaded.entries) == 2


def test_toc_block_extra_forbidden():
    with pytest.raises(ValidationError):
        TocBlock.model_validate(
            {"kind": "toc", "prov": {"section_idx": 0, "para_idx": 0}, "extra": "x"}
        )


def test_toc_block_frozen():
    toc = TocBlock(entries=[], prov=_prov())
    with pytest.raises(ValidationError):
        toc.entries = []  # type: ignore[misc]


def test_toc_block_routes_via_discriminator():
    raw = {
        "kind": "toc",
        "entries": [],
        "prov": {"section_idx": 0, "para_idx": 7},
    }
    doc = HwpDocument.model_validate({"body": [raw]})
    blk = doc.body[0]
    assert isinstance(blk, TocBlock)


# * 모델 단독 — TocEntryBlock


def test_toc_entry_block_minimal_roundtrip():
    e = TocEntryBlock(text="1장", prov=_prov())
    reloaded = TocEntryBlock.model_validate_json(e.model_dump_json())
    assert reloaded == e
    assert reloaded.kind == "toc_entry"


def test_toc_entry_block_full_fields():
    e = TocEntryBlock(
        text="1.1 절",
        level=2,
        target_bookmark_name="bookmark_1_1",
        target_section_idx=None,
        cached_page=15,
        is_stale=False,
        prov=_prov(),
    )
    reloaded = TocEntryBlock.model_validate_json(e.model_dump_json())
    assert reloaded == e


def test_toc_entry_block_default_values():
    """v0.3.0 default: level=1, target_section_idx=None, cached_page=None, is_stale=False."""
    e = TocEntryBlock(text="x", prov=_prov())
    assert e.level == 1
    assert e.target_bookmark_name is None
    assert e.target_section_idx is None
    assert e.cached_page is None
    assert e.is_stale is False


def test_toc_entry_block_extra_forbidden():
    with pytest.raises(ValidationError):
        TocEntryBlock.model_validate(
            {
                "kind": "toc_entry",
                "text": "x",
                "prov": {"section_idx": 0, "para_idx": 0},
                "extra": True,
            }
        )


def test_toc_entry_block_frozen():
    e = TocEntryBlock(text="x", prov=_prov())
    with pytest.raises(ValidationError):
        e.text = "y"  # type: ignore[misc]


def test_toc_entry_block_is_not_in_block_union():
    """TocEntryBlock 은 Block 유니온 멤버 아님 — body 에 dict 로 넣으면 UnknownBlock 라우팅."""
    raw = {
        "kind": "toc_entry",
        "text": "x",
        "prov": {"section_idx": 0, "para_idx": 0},
    }
    doc = HwpDocument.model_validate({"body": [raw]})
    blk = doc.body[0]
    # ^ "toc_entry" 는 _KNOWN_KINDS 에 없으므로 UnknownBlock 으로 라우팅됨
    assert isinstance(blk, UnknownBlock)


# * mapper — RawToc → TocBlock


def _raw_toc(*, entries: list[RawTocEntry] | None = None, char_offset: int | None = None) -> RawToc:
    return RawToc(section_idx=1, para_idx=3, entries=entries or [], char_offset=char_offset)


def test_build_toc_block_empty_entries():
    """v0.3.0 일반 케이스 — Rust 가 entries 빈 Vec 출고."""
    toc = _build_toc_block(_raw_toc())
    assert toc.entries == []
    assert toc.prov.section_idx == 1
    assert toc.prov.para_idx == 3
    assert toc.prov.char_start is None
    assert toc.prov.char_end is None


def test_build_toc_block_with_entries():
    """v0.4.0+ 에서 entries 가 채워질 때 — 본 테스트는 forward-compat 검증."""
    raw_entry = RawTocEntry(
        text="1장",
        level=1,
        target_bookmark_name="bm1",
        cached_page=10,
    )
    toc = _build_toc_block(_raw_toc(entries=[raw_entry]))
    assert len(toc.entries) == 1
    assert toc.entries[0].text == "1장"
    assert toc.entries[0].level == 1
    assert toc.entries[0].target_bookmark_name == "bm1"
    assert toc.entries[0].cached_page == 10


def test_build_toc_entry_target_section_idx_always_none_v0_3_0():
    """spec § 6 결정 사항 — v0.3.0 은 bookmark resolver 미도입 → 항상 None."""
    raw_entry = RawTocEntry(text="x", level=1, target_bookmark_name="bm", cached_page=None)
    toc = _build_toc_block(_raw_toc(entries=[raw_entry]))
    assert toc.entries[0].target_section_idx is None


def test_build_toc_entry_is_stale_always_false_v0_3_0():
    """spec § 6 결정 사항 — v0.3.0 은 stale 검출 미구현 → 항상 False."""
    raw_entry = RawTocEntry(text="x", level=1, target_bookmark_name=None, cached_page=99)
    toc = _build_toc_block(_raw_toc(entries=[raw_entry]))
    assert toc.entries[0].is_stale is False


# * _flatten_paragraph 가 TocBlock 도 emit


def test_flatten_paragraph_yields_toc_block_when_tocs_present():
    raw_para = _raw_para_with_tocs([_raw_toc()])
    blocks = _flatten_paragraph(raw_para)
    # ^ paragraph_or_list_item + toc 두 블록
    assert len(blocks) == 2
    assert isinstance(blocks[0], ParagraphBlock)
    assert isinstance(blocks[1], TocBlock)


def test_flatten_paragraph_multiple_tocs():
    """한 paragraph 안에 여러 TOC field 가 (이상하지만) 있을 때 모두 emit."""
    raw_para = _raw_para_with_tocs([_raw_toc(), _raw_toc()])
    blocks = _flatten_paragraph(raw_para)
    toc_count = sum(1 for b in blocks if isinstance(b, TocBlock))
    assert toc_count == 2


# * iter_blocks — TocBlock 만 yield, TocEntryBlock 은 yield 안 함


def test_iter_blocks_yields_toc_block_only():
    """recurse=True 여도 TocEntryBlock 은 진입 안 함 (TocBlock.entries 는 leaf 컬렉션)."""
    entries = [TocEntryBlock(text="1장", prov=_prov()), TocEntryBlock(text="2장", prov=_prov())]
    toc = TocBlock(entries=entries, prov=_prov())
    ir = HwpDocument(body=[toc])
    seq = list(ir.iter_blocks(scope="body", recurse=True))
    assert seq == [toc]
    # ^ entries 는 직접 접근 (toc.entries) — iter_blocks 는 yield 안 함
