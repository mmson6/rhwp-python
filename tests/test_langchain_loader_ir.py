"""HwpLoader(mode="ir-blocks") pytest 스위트.

``test_langchain_loader.py`` 와 분리 — 본 파일은 ir-blocks 모드 전용.
``langchain_core`` 미설치 시 파일 레벨 importorskip 으로 auto-skip.
"""

from pathlib import Path

import pytest

pytest.importorskip("langchain_core")

import rhwp  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from rhwp.integrations.langchain import HwpLoader  # noqa: E402

pytestmark = pytest.mark.langchain


# * 생성자


def test_ir_blocks_mode_accepted(hwp_sample: Path) -> None:
    loader = HwpLoader(str(hwp_sample), mode="ir-blocks")
    assert loader.mode == "ir-blocks"


# * load / lazy_load


def test_ir_blocks_mode_returns_list_of_documents(hwpx_sample: Path) -> None:
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()
    assert isinstance(docs, list)
    assert len(docs) > 0
    assert all(isinstance(d, Document) for d in docs)


def test_ir_blocks_mode_lazy_load_yields_documents(hwpx_sample: Path) -> None:
    it = HwpLoader(str(hwpx_sample), mode="ir-blocks").lazy_load()
    first = next(it)
    assert isinstance(first, Document)


# * metadata 구조 — kind / prov


def test_ir_blocks_metadata_has_base_fields(hwpx_sample: Path) -> None:
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()
    for d in docs:
        md = d.metadata
        assert md["source"] == str(hwpx_sample)
        assert "section_count" in md
        assert "paragraph_count" in md
        assert "page_count" in md
        assert "rhwp_version" in md
        assert "kind" in md
        assert "section_idx" in md
        assert "para_idx" in md


def test_ir_blocks_includes_both_paragraph_and_table(hwpx_sample: Path) -> None:
    """HWPX 샘플은 표를 포함 — ir-blocks 로 로드 시 kind=paragraph + kind=table 혼합."""
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()
    kinds = {d.metadata["kind"] for d in docs}
    assert "paragraph" in kinds
    assert "table" in kinds


def test_ir_blocks_paragraph_content_is_text(hwpx_sample: Path) -> None:
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()
    para_docs = [d for d in docs if d.metadata["kind"] == "paragraph"]
    assert para_docs  # ^ 최소 하나는 존재
    for d in para_docs:
        # ^ paragraph page_content 는 단순 텍스트 (HTML 태그 없음)
        assert "<table>" not in d.page_content


def test_ir_blocks_table_content_is_html(hwpx_sample: Path) -> None:
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()
    table_docs = [d for d in docs if d.metadata["kind"] == "table"]
    assert table_docs
    for d in table_docs:
        # ^ 표 page_content 는 HTML — HtmlRAG 호환 (ir.md §테이블 표현)
        assert d.page_content.startswith("<table>")
        assert d.page_content.endswith("</table>")
        # ^ 메타데이터에 구조화 정보 + 평문 병기
        assert d.metadata["rows"] > 0
        assert d.metadata["cols"] > 0
        assert "text" in d.metadata


# * 빈 블록 필터링


def test_ir_blocks_skips_empty_paragraphs(hwpx_sample: Path) -> None:
    """page_content 가 빈 문단은 RAG 노이즈 — 스킵."""
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()
    for d in docs:
        assert d.page_content.strip(), f"empty doc: {d}"


# * HWP5 샘플도 같은 계약


def test_ir_blocks_mode_works_on_hwp5_sample(hwp_sample: Path) -> None:
    docs = HwpLoader(str(hwp_sample), mode="ir-blocks").load()
    assert len(docs) > 0
    kinds = {d.metadata["kind"] for d in docs}
    # ^ HWP5 샘플은 paragraph 는 반드시 있음, table 은 있을 수도 없을 수도
    assert "paragraph" in kinds


# * Provenance 일치


def test_ir_blocks_preserves_iter_blocks_order(hwpx_sample: Path) -> None:
    """loader 의 Document 순서가 ``iter_blocks`` 순서의 부분 시퀀스다.

    loader 는 빈 블록을 스킵하므로 1:1 이 아니지만, 살아남은 블록들의 상대 순서
    는 ``iter_blocks(scope="body", recurse=True)`` 와 동일해야 한다.
    """
    parsed = rhwp.parse(str(hwpx_sample))
    ir = parsed.to_ir()
    docs = HwpLoader(str(hwpx_sample), mode="ir-blocks").load()

    ir_provs = [(b.prov.section_idx, b.prov.para_idx) for b in ir.iter_blocks(scope="body")]
    loader_provs = [(d.metadata["section_idx"], d.metadata["para_idx"]) for d in docs]

    # ^ loader_provs 가 ir_provs 의 부분 시퀀스인지 검증 (순서 보존)
    cursor = 0
    for prov in loader_provs:
        while cursor < len(ir_provs) and ir_provs[cursor] != prov:
            cursor += 1
        assert cursor < len(ir_provs), (
            f"loader prov {prov} not found after position in iter_blocks order"
        )
        cursor += 1


# * 기본 mode 목록 검증 — invalid mode 는 여전히 거부


def test_invalid_mode_still_rejects_after_ir_addition(hwp_sample: Path) -> None:
    with pytest.raises(ValueError, match="mode"):
        HwpLoader(str(hwp_sample), mode="page")  # type: ignore[arg-type]


# * include_furniture (v0.3.0 S4 신규)


def test_include_furniture_default_false(hwp_sample: Path) -> None:
    loader = HwpLoader(str(hwp_sample), mode="ir-blocks")
    assert loader.include_furniture is False


def test_include_furniture_yields_extra_documents(hwp_sample: Path) -> None:
    """include_furniture=True 면 body 다음에 furniture Document 가 추가 yield 된다."""
    body_only = HwpLoader(str(hwp_sample), mode="ir-blocks", include_furniture=False).load()
    with_furn = HwpLoader(str(hwp_sample), mode="ir-blocks", include_furniture=True).load()
    # ^ furniture 가 비어있는 샘플도 body_only ≤ with_furn 가 invariant
    assert len(with_furn) >= len(body_only)


def test_include_furniture_marks_scope_metadata(hwp_sample: Path) -> None:
    """furniture Document 는 metadata.scope == 'furniture', body 는 키 없음."""
    docs = HwpLoader(str(hwp_sample), mode="ir-blocks", include_furniture=True).load()
    for d in docs:
        scope = d.metadata.get("scope")
        # ^ body 는 scope 키 부재 (None), furniture 만 'furniture'
        assert scope in (None, "furniture")


def test_include_furniture_ignored_in_paragraph_mode(hwp_sample: Path) -> None:
    """paragraph 모드는 include_furniture 무관하게 동일 결과 (옵션은 ir-blocks 전용)."""
    a = HwpLoader(str(hwp_sample), mode="paragraph", include_furniture=False).load()
    b = HwpLoader(str(hwp_sample), mode="paragraph", include_furniture=True).load()
    assert len(a) == len(b)
    assert [d.page_content for d in a] == [d.page_content for d in b]


# * footnote/endnote/caption 평문화 회귀 — ListItemBlock 누락 방지
#
# 이전 구현은 inner blocks 중 ParagraphBlock 만 평문에 포함 → 각주 안의 list 가 통째로
# 누락. 헬퍼 (`rhwp.ir._plain_text.join_inline_blocks`) 로 통합되며 ListItemBlock /
# FormulaBlock / FieldBlock 도 포함. 본 회귀 테스트는 sample 의 footnote 구조에 의존
# 하지 않도록 private 헬퍼 `_block_to_content_and_meta` 를 직접 호출한다.


def test_footnote_with_list_items_includes_them_in_content() -> None:
    # ^ langchain.pyi stub 이 public class (HwpLoader) 만 노출 — module-level
    #   private helper 는 stub 누락이지만 .py 에 존재. pyright 가 stub 우선이라
    #   reportAttributeAccessIssue 발생, 본 회귀 테스트 한정으로 ignore.
    from rhwp.integrations.langchain import (
        _block_to_content_and_meta,  # pyright: ignore[reportAttributeAccessIssue]
    )
    from rhwp.ir.nodes import FootnoteBlock, ListItemBlock, ParagraphBlock, Provenance

    prov = Provenance(section_idx=0, para_idx=0)
    footnote = FootnoteBlock(
        number=1,
        marker_prov=prov,
        prov=prov,
        blocks=[
            ParagraphBlock(text="참고 문헌:", prov=prov),
            ListItemBlock(text="첫째 출처", marker="1.", enumerated=True, prov=prov),
            ListItemBlock(text="둘째 출처", marker="2.", enumerated=True, prov=prov),
        ],
    )
    content, meta = _block_to_content_and_meta(footnote)
    assert content == "참고 문헌:\n1. 첫째 출처\n2. 둘째 출처"
    assert meta["kind"] == "footnote"


def test_caption_with_formula_and_field_includes_them() -> None:
    from rhwp.integrations.langchain import (
        _block_to_content_and_meta,  # pyright: ignore[reportAttributeAccessIssue]
    )
    from rhwp.ir.nodes import (
        CaptionBlock,
        FieldBlock,
        FormulaBlock,
        ParagraphBlock,
        Provenance,
    )

    prov = Provenance(section_idx=0, para_idx=0)
    caption = CaptionBlock(
        blocks=[
            ParagraphBlock(text="<그림 1>", prov=prov),
            FormulaBlock(script="E=mc^2", text_alt=None, prov=prov),
            FieldBlock(field_kind="date", cached_value="2026-04-28", prov=prov),
        ],
        direction="bottom",
        prov=prov,
    )
    content, meta = _block_to_content_and_meta(caption)
    assert content == "<그림 1>\nE=mc^2\n2026-04-28"
    assert meta["kind"] == "caption"
