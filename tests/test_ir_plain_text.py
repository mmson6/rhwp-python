"""rhwp.ir._plain_text 단위 테스트 — 컨테이너 평문화 헬퍼.

캡션·각주·미주의 inner blocks 평문화에 ``ListItemBlock`` / ``FormulaBlock`` /
``FieldBlock`` 이 포함되는지 검증 (이전엔 ``ParagraphBlock`` 만 잡아 누락).
"""

from rhwp.ir._plain_text import block_inline_text, join_inline_blocks
from rhwp.ir.nodes import (
    Block,
    CaptionBlock,
    FieldBlock,
    FormulaBlock,
    ImageRef,
    ListItemBlock,
    ParagraphBlock,
    PictureBlock,
    Provenance,
    TableBlock,
    UnknownBlock,
)

_PROV = Provenance(section_idx=0, para_idx=0)


# * block_inline_text — 인라인-스러운 블록만 평문 반환


def test_paragraph_with_text() -> None:
    assert block_inline_text(ParagraphBlock(text="hello", prov=_PROV)) == "hello"


def test_paragraph_empty_returns_none() -> None:
    assert block_inline_text(ParagraphBlock(text="", prov=_PROV)) is None


def test_list_item_includes_marker() -> None:
    block = ListItemBlock(text="첫 항목", marker="1.", enumerated=True, prov=_PROV)
    assert block_inline_text(block) == "1. 첫 항목"


def test_list_item_empty_text_with_marker_returns_marker() -> None:
    # ^ marker 만 있고 본문 없으면 marker 그대로 (drop 하지 않음 — 정렬 정보 보존)
    block = ListItemBlock(text="", marker="•", enumerated=False, prov=_PROV)
    assert block_inline_text(block) == "•"


def test_list_item_fully_empty_returns_none() -> None:
    block = ListItemBlock(text="", marker="", enumerated=False, prov=_PROV)
    assert block_inline_text(block) is None


def test_formula_prefers_text_alt() -> None:
    block = FormulaBlock(script="1 over 2", text_alt="1 / 2", prov=_PROV)
    assert block_inline_text(block) == "1 / 2"


def test_formula_falls_back_to_script() -> None:
    block = FormulaBlock(script="x^2", text_alt=None, prov=_PROV)
    assert block_inline_text(block) == "x^2"


def test_formula_empty_returns_none() -> None:
    # ^ 정상적으로는 빈 script 가 출고되지 않지만 손상 입력 방어
    block = FormulaBlock(script="", text_alt=None, prov=_PROV)
    assert block_inline_text(block) is None


def test_field_with_cached_value() -> None:
    block = FieldBlock(field_kind="date", cached_value="2026-04-28", prov=_PROV)
    assert block_inline_text(block) == "2026-04-28"


def test_field_without_cached_value_returns_none() -> None:
    block = FieldBlock(field_kind="hyperlink", cached_value=None, prov=_PROV)
    assert block_inline_text(block) is None


def test_structural_blocks_return_none() -> None:
    # ^ Table / Picture 는 구조 블록 — 평문화에서 제외 (별도 색인 대상)
    assert block_inline_text(TableBlock(rows=1, cols=1, prov=_PROV)) is None
    assert (
        block_inline_text(
            PictureBlock(image=ImageRef(uri="bin://1", mime_type="image/png"), prov=_PROV)
        )
        is None
    )


def test_unknown_block_returns_none() -> None:
    assert block_inline_text(UnknownBlock(kind="future_kind", prov=_PROV)) is None


# * join_inline_blocks — 캡션·각주·미주 본문 평문화


def test_join_empty_list() -> None:
    assert join_inline_blocks([]) == ""


def test_join_skips_blocks_with_no_inline_text() -> None:
    # ^ 핵심 회귀: TableBlock / PictureBlock 등 구조 블록이 섞여도 인라인만 추출
    blocks: list[Block] = [
        ParagraphBlock(text="본문", prov=_PROV),
        TableBlock(rows=1, cols=1, prov=_PROV),
        ParagraphBlock(text="", prov=_PROV),  # ^ 빈 단락 skip
    ]
    assert join_inline_blocks(blocks) == "본문"


def test_join_includes_list_item_in_caption_or_footnote() -> None:
    """ListItemBlock 누락 회귀 테스트 — 각주/미주/캡션 안의 list 가 평문에 포함된다.

    이전 구현은 ``isinstance(b, ParagraphBlock)`` 만 체크하여 ListItemBlock 으로
    변환된 paragraph (`ParaShape.head_type` 비-None) 가 통째로 누락됐다.
    """
    blocks: list[Block] = [
        ParagraphBlock(text="머리말", prov=_PROV),
        ListItemBlock(text="첫째", marker="1.", enumerated=True, prov=_PROV),
        ListItemBlock(text="둘째", marker="2.", enumerated=True, prov=_PROV),
    ]
    assert join_inline_blocks(blocks) == "머리말\n1. 첫째\n2. 둘째"


def test_join_mixes_paragraph_listitem_formula_field() -> None:
    blocks: list[Block] = [
        ParagraphBlock(text="식:", prov=_PROV),
        FormulaBlock(script="x+y", text_alt=None, prov=_PROV),
        FieldBlock(field_kind="date", cached_value="2026-04-28", prov=_PROV),
        ListItemBlock(text="결론", marker="•", enumerated=False, prov=_PROV),
    ]
    assert join_inline_blocks(blocks) == "식:\nx+y\n2026-04-28\n• 결론"


def test_join_caption_blocks_works_via_attribute() -> None:
    """CaptionBlock 사용처 사용 패턴 — caption.blocks 를 그대로 넘긴다."""
    caption = CaptionBlock(
        blocks=[
            ParagraphBlock(text="<그림 1>", prov=_PROV),
            FormulaBlock(script="E=mc^2", text_alt=None, prov=_PROV),
        ],
        direction="bottom",
        prov=_PROV,
    )
    assert join_inline_blocks(caption.blocks) == "<그림 1>\nE=mc^2"
