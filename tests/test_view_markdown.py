"""tests/test_view_markdown.py — v0.4.0 view-renderer Markdown 면.

spec: docs/roadmap/v0.4.0/view-renderer.md (AC-1 / AC-3 / AC-5 / AC-6 / AC-7 /
AC-8 / AC-10).
ADR : docs/design/v0.4.0/view-renderer-research.md.

GFM round-trip parser 가용성에 의존하지 않도록 구조 패턴 검증으로 AC-1 충족 —
``[^N]`` ref ↔ ``[^N]:`` def 매칭, GFM 표 행 일관성, 코드펜스 닫힘.
"""

import re
from pathlib import Path

import pytest
import rhwp
from rhwp.ir.nodes import (
    EndnoteBlock,
    FootnoteBlock,
    FormulaBlock,
    Furniture,
    HwpDocument,
    ImageRef,
    ListItemBlock,
    ParagraphBlock,
    PictureBlock,
    Provenance,
    TableBlock,
    TableCell,
)

pytestmark = pytest.mark.spec("v0.4.0/view-renderer")


def _prov(section_idx: int = 0, para_idx: int = 0) -> Provenance:
    return Provenance(section_idx=section_idx, para_idx=para_idx)


def _doc(blocks: list, **kwargs) -> HwpDocument:
    return HwpDocument(body=blocks, **kwargs)


# * AC-1 — valid GFM 구조 패턴


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
def test_to_markdown_returns_string_ending_in_newline():
    doc = _doc([ParagraphBlock(text="첫 단락", prov=_prov())])
    md = doc.to_markdown()
    assert isinstance(md, str)
    assert md.endswith("\n")


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
def test_to_markdown_empty_document_returns_empty_string():
    """빈 IR 은 빈 문자열 — 빈 문서도 valid GFM."""
    md = _doc([]).to_markdown()
    assert md == ""


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
def test_to_markdown_paragraphs_separated_by_blank_line():
    """GFM 단락 구분은 빈 줄 — ``\\n\\n`` 으로 분리 (CommonMark §4.8)."""
    doc = _doc(
        [
            ParagraphBlock(text="단락 A", prov=_prov(0, 0)),
            ParagraphBlock(text="단락 B", prov=_prov(0, 1)),
        ]
    )
    md = doc.to_markdown()
    assert "단락 A\n\n단락 B" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
def test_to_markdown_real_fixture_footnote_refs_match_defs(hwp_sample: Path):
    """fixture 출력의 ``[^N]`` ref 와 ``[^N]:`` def 가 정확히 매칭."""
    md = rhwp.parse(str(hwp_sample)).to_ir().to_markdown()
    refs = set(re.findall(r"\[\^[a-z]*\d+\](?!:)", md))
    defs = set(m.group(1) for m in re.finditer(r"(\[\^[a-z]*\d+\]):", md))
    # ref / def set 가 동일 — 모든 reference 에 정의가 존재
    assert refs == defs, f"orphan refs={refs - defs}, orphan defs={defs - refs}"


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
def test_to_markdown_real_fixture_gfm_tables_are_consistent(hwpx_sample: Path):
    """GFM 표 행: 같은 표 안 행들의 cell 수 일치 (separator + data rows)."""
    md = rhwp.parse(str(hwpx_sample)).to_ir().to_markdown()
    lines = md.splitlines()
    i = 0
    table_count = 0
    while i < len(lines):
        if (
            lines[i].startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[\s|-]+\|$", lines[i + 1])
        ):
            # GFM 표 시작 (header + separator)
            n_cells = lines[i].count("|") - 1
            sep_cells = lines[i + 1].count("|") - 1
            assert n_cells == sep_cells, f"line {i}: {lines[i]!r}"
            j = i + 2
            # ^ startswith("|") 분기 시점에 startswith("<") 는 mutually exclusive — 단일 조건
            while j < len(lines) and lines[j].startswith("|"):
                row_cells = lines[j].count("|") - lines[j].count(r"\|") - 1
                assert row_cells == n_cells, (
                    f"line {j}: cells={row_cells} != header={n_cells}: {lines[j]!r}"
                )
                j += 1
            table_count += 1
            i = j
        else:
            i += 1
    # 적어도 1 GFM 표 등장 — sample 에 단순 표 존재 가정
    assert table_count >= 1


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
def test_to_markdown_real_fixture_code_fences_balanced(hwp_sample: Path):
    """``` ``` ``` 펜스 시작/종료 회수 동일 (열린 채로 끝나지 않음)."""
    md = rhwp.parse(str(hwp_sample)).to_ir().to_markdown()
    fence_count = sum(1 for line in md.splitlines() if line.startswith("```"))
    assert fence_count % 2 == 0, f"unmatched fences: {fence_count}"


# * AC-3 — 표 병합 폴백


@pytest.mark.spec("v0.4.0/view-renderer#AC-3")
def test_simple_table_renders_as_gfm_pipe_table():
    """모든 셀 span=1 → GFM ``|...|`` 표."""
    cells = [
        TableCell(row=0, col=0, grid_index=0, blocks=[ParagraphBlock(text="A", prov=_prov())]),
        TableCell(row=0, col=1, grid_index=1, blocks=[ParagraphBlock(text="B", prov=_prov())]),
        TableCell(row=1, col=0, grid_index=2, blocks=[ParagraphBlock(text="1", prov=_prov())]),
        TableCell(row=1, col=1, grid_index=3, blocks=[ParagraphBlock(text="2", prov=_prov())]),
    ]
    table = TableBlock(rows=2, cols=2, cells=cells, html="<table>...</table>", prov=_prov())
    md = _doc([table]).to_markdown()
    assert "| A | B |" in md
    assert "| --- | --- |" in md
    assert "| 1 | 2 |" in md
    # raw HTML 폴백이 사용되지 않음
    assert "<table>...</table>" not in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-3")
def test_merged_table_falls_back_to_html_inline():
    """rowspan/colspan > 1 인 셀이 있으면 ``TableBlock.html`` 그대로 inline."""
    raw_html = '<table><tr><td rowspan="2">M</td><td>X</td></tr><tr><td>Y</td></tr></table>'
    cells = [
        TableCell(row=0, col=0, grid_index=0, row_span=2, blocks=[]),
        TableCell(row=0, col=1, grid_index=1, blocks=[]),
        TableCell(row=1, col=1, grid_index=3, blocks=[]),
    ]
    table = TableBlock(rows=2, cols=2, cells=cells, html=raw_html, prov=_prov())
    md = _doc([table]).to_markdown()
    assert raw_html in md
    # GFM separator 없음 (raw HTML 만)
    assert "| --- |" not in md


# * AC-5 — Picture pass-through


@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_with_image_renders_as_markdown_image():
    pic = PictureBlock(
        image=ImageRef(uri="bin://7", mime_type="image/png"),
        description="회로도",
        prov=_prov(),
    )
    md = _doc([pic]).to_markdown()
    assert "![회로도](bin://7)" in md
    assert "base64" not in md
    assert "file://" not in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_without_image_renders_alt_only():
    pic = PictureBlock(image=None, description="누락", prov=_prov())
    md = _doc([pic]).to_markdown()
    assert "![누락]()" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_real_fixture_no_base64(hwp_sample: Path):
    md = rhwp.parse(str(hwp_sample)).to_ir().to_markdown()
    assert "base64" not in md
    assert "file://" not in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-1")
@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_description_with_brackets_is_backslash_escaped():
    """``description`` 안 ``[`` / ``]`` 가 GFM alt 슬롯을 종료시키지 않도록 escape."""
    pic = PictureBlock(
        image=ImageRef(uri="bin://1", mime_type="image/png"),
        description="회로[v1]도",
        prov=_prov(),
    )
    md = _doc([pic]).to_markdown()
    # escape 된 형태로 등장
    assert r"![회로\[v1\]도](bin://1)" in md
    # 미escape 형태 (broken syntax) 미등장
    assert "![회로[v1]도]" not in md


# * AC-6 — Formula


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_latex_display_uses_double_dollar():
    f = FormulaBlock(script="x^2 + y^2", script_kind="latex", inline=False, prov=_prov())
    md = _doc([f]).to_markdown()
    assert "$$x^2 + y^2$$" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_latex_inline_uses_single_dollar():
    f = FormulaBlock(script="a + b", script_kind="latex", inline=True, prov=_prov())
    md = _doc([f]).to_markdown()
    assert "$a + b$" in md
    assert "$$a + b$$" not in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_hwp_eq_uses_fenced_block():
    f = FormulaBlock(script="1 over 2", script_kind="hwp_eq", prov=_prov())
    md = _doc([f]).to_markdown()
    assert "```hwp-eq\n1 over 2\n```" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_mathml_uses_fenced_block():
    """script_kind="mathml" — spec 결정 7 본문 미명시지만 IR Literal 셋째 값.

    forward-compat fenced block 으로 raw 보존 (`_view.py` 의 mathml 분기 회귀 가드).
    """
    f = FormulaBlock(script="<math><mi>x</mi></math>", script_kind="mathml", prov=_prov())
    md = _doc([f]).to_markdown()
    assert "```mathml\n<math><mi>x</mi></math>\n```" in md


# * AC-7 — Footnote / Endnote


@pytest.mark.spec("v0.4.0/view-renderer#AC-7")
def test_footnote_reference_appears_in_paragraph_and_definition_at_end():
    para = ParagraphBlock(text="이전 연구", prov=_prov(0, 0))
    fn = FootnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="Smith 2020", prov=_prov(99, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    doc = HwpDocument(body=[para], furniture=Furniture(footnotes=[fn]))
    md = doc.to_markdown()
    assert "이전 연구[^1]" in md
    assert "[^1]: Smith 2020" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-7")
def test_endnote_uses_separate_number_space_with_en_prefix():
    para = ParagraphBlock(text="후속 논의", prov=_prov(0, 0))
    en = EndnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="별도 첨부", prov=_prov(99, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    doc = HwpDocument(body=[para], furniture=Furniture(endnotes=[en]))
    md = doc.to_markdown()
    assert "후속 논의[^en1]" in md
    assert "[^en1]: 별도 첨부" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-7")
def test_footnote_and_endnote_coexist_with_separate_prefixes():
    para = ParagraphBlock(text="공존", prov=_prov(0, 0))
    fn = FootnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="각주", prov=_prov(99, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    en = EndnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="미주", prov=_prov(0, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    doc = HwpDocument(body=[para], furniture=Furniture(footnotes=[fn], endnotes=[en]))
    md = doc.to_markdown()
    # 같은 number 1 이지만 prefix 분리
    assert "[^1]" in md
    assert "[^en1]" in md
    assert "[^1]: 각주" in md
    assert "[^en1]: 미주" in md


# * AC-8 — Furniture page_headers / page_footers 비포함


@pytest.mark.spec("v0.4.0/view-renderer#AC-8")
def test_page_header_and_footer_text_excluded_from_markdown():
    """헤더/푸터 paragraph 평문이 출력에 등장하지 않음 (페이지 단위 장식 비범위, 결정 8).

    실제 fixture (``aift.hwp`` / ``table-vpos-01.hwpx``) 의 헤더/푸터는 빈 paragraph
    또는 비어있는 list 라 spec 의 fixture 예시로 검증 불가 — synthetic IR 로 강제.
    """
    body_para = ParagraphBlock(text="본문 내용", prov=_prov(0, 0))
    header_para = ParagraphBlock(text="UNIQUE_HEADER_TOKEN_8462", prov=_prov(99, 0))
    footer_para = ParagraphBlock(text="UNIQUE_FOOTER_TOKEN_3175", prov=_prov(99, 1))
    doc = HwpDocument(
        body=[body_para],
        furniture=Furniture(page_headers=[header_para], page_footers=[footer_para]),
    )
    md = doc.to_markdown()
    assert "본문 내용" in md
    assert "UNIQUE_HEADER_TOKEN_8462" not in md
    assert "UNIQUE_FOOTER_TOKEN_3175" not in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-8")
def test_real_fixture_furniture_paragraph_text_excluded(hwp_sample: Path, hwpx_sample: Path):
    """fixture 의 헤더/푸터 paragraph 가 어떤 (빈) 내용이라도 출력에 누설되지 않음."""
    for sample in (hwp_sample, hwpx_sample):
        doc = rhwp.parse(str(sample)).to_ir()
        md = doc.to_markdown()
        for h in [*doc.furniture.page_headers, *doc.furniture.page_footers]:
            if isinstance(h, ParagraphBlock) and h.text:
                assert h.text not in md, f"{sample}: leaked {h.text!r}"


# * AC-10 — Idempotency


@pytest.mark.spec("v0.4.0/view-renderer#AC-10")
def test_to_markdown_is_byte_equal_on_repeated_calls(hwp_sample: Path):
    doc = rhwp.parse(str(hwp_sample)).to_ir()
    a = doc.to_markdown()
    b = doc.to_markdown()
    assert a == b


def test_list_item_level_indented_in_markdown():
    """``ListItemBlock.level > 0`` 은 ``"  " * level`` 들여쓰기로 표현 — HTML 측
    ``data-level`` 속성과 정보 대칭."""
    items = [
        ListItemBlock(text="L0", enumerated=False, level=0, prov=_prov(0, 0)),
        ListItemBlock(text="L1", enumerated=False, level=1, prov=_prov(0, 1)),
        ListItemBlock(text="L2", enumerated=True, level=2, prov=_prov(0, 2)),
    ]
    md = _doc(items).to_markdown()
    assert "- L0" in md
    assert "  - L1" in md
    assert "    1. L2" in md


@pytest.mark.spec("v0.4.0/view-renderer#AC-10")
def test_to_markdown_does_not_mutate_ir():
    """frozen=True IR + 호출이 수정 없이 동작."""
    para = ParagraphBlock(text="X", prov=_prov())
    doc = _doc([para])
    snapshot = doc.model_dump_json()
    doc.to_markdown()
    assert doc.model_dump_json() == snapshot
