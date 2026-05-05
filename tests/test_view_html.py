"""tests/test_view_html.py — v0.4.0 view-renderer HTML 면.

spec: docs/roadmap/v0.4.0/view-renderer.md (AC-2 / AC-4 / AC-5 / AC-6 / AC-7 /
AC-8 / AC-9 / AC-10).
ADR : docs/design/v0.4.0/view-renderer-research.md.

AC-2 round-trip parse 는 stdlib ``html.parser.HTMLParser`` 기반 stack-balance
검증으로 충족 — lxml 등 외부 dep 도입 없음.
"""

from html.parser import HTMLParser
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


# * Helper — HTML5 well-formedness via stdlib stack-balance


_VOID_ELEMENTS = frozenset(
    {
        "meta",
        "link",
        "br",
        "hr",
        "img",
        "input",
        "area",
        "base",
        "col",
        "embed",
        "source",
        "track",
        "wbr",
    }
)


class _StackBalance(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag not in _VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            self.errors.append(f"close </{tag}> with empty stack")
            return
        if self.stack[-1] != tag:
            self.errors.append(f"close </{tag}> doesn't match open <{self.stack[-1]}>")
            return
        self.stack.pop()


def _assert_well_formed_html5(html: str) -> None:
    """``<!DOCTYPE html>`` + ``<html>`` 루트 + ``<body>`` 본문 + 모든 tag balanced."""
    assert html.startswith("<!DOCTYPE html>"), f"missing doctype: {html[:50]!r}"
    assert "<html>" in html
    assert "<head>" in html and "</head>" in html
    assert "<body>" in html and "</body>" in html
    v = _StackBalance()
    v.feed(html)
    assert not v.errors, f"malformed: {v.errors[:3]}"
    assert not v.stack, f"unclosed: {v.stack}"


# * AC-2 — well-formed HTML5


@pytest.mark.spec("v0.4.0/view-renderer#AC-2")
def test_to_html_returns_doctype_and_html5_skeleton():
    doc = _doc([ParagraphBlock(text="X", prov=_prov())])
    html = doc.to_html()
    _assert_well_formed_html5(html)


@pytest.mark.spec("v0.4.0/view-renderer#AC-2")
def test_to_html_empty_document_still_well_formed():
    html = _doc([]).to_html()
    _assert_well_formed_html5(html)


@pytest.mark.spec("v0.4.0/view-renderer#AC-2")
def test_to_html_real_fixture_well_formed(hwp_sample: Path, hwpx_sample: Path):
    for sample in (hwp_sample, hwpx_sample):
        html = rhwp.parse(str(sample)).to_ir().to_html()
        _assert_well_formed_html5(html)


@pytest.mark.spec("v0.4.0/view-renderer#AC-2")
def test_to_html_escapes_special_chars_in_paragraph():
    para = ParagraphBlock(text="<script>alert(1)</script>&\"'", prov=_prov())
    html = _doc([para]).to_html()
    _assert_well_formed_html5(html)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# * AC-4 — TableBlock.html substring (재합성 안 함)


@pytest.mark.spec("v0.4.0/view-renderer#AC-4")
def test_table_html_appears_as_substring_unchanged():
    raw = '<table><tr><td colspan="2">M</td></tr><tr><td>x</td><td>y</td></tr></table>'
    cells = [
        TableCell(row=0, col=0, grid_index=0, col_span=2, blocks=[]),
        TableCell(row=1, col=0, grid_index=2, blocks=[]),
        TableCell(row=1, col=1, grid_index=3, blocks=[]),
    ]
    table = TableBlock(rows=2, cols=2, cells=cells, html=raw, prov=_prov())
    html = _doc([table]).to_html()
    assert raw in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-4")
def test_table_html_real_fixture_appears_as_substring(hwpx_sample: Path):
    """fixture 의 모든 ``TableBlock.html`` 이 ``to_html()`` 출력 안 substring 으로 등장."""
    doc = rhwp.parse(str(hwpx_sample)).to_ir()
    html = doc.to_html()
    body_tables = [b for b in doc.body if isinstance(b, TableBlock)]
    assert body_tables, "fixture has no body TableBlock"
    for t in body_tables:
        if t.html:
            assert t.html in html, f"TableBlock.html not substring (rows={t.rows}, cols={t.cols})"


# * AC-5 — Picture pass-through


@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_renders_as_img_with_uri_passthrough():
    pic = PictureBlock(
        image=ImageRef(uri="bin://7", mime_type="image/png"),
        description="회로도",
        prov=_prov(),
    )
    html = _doc([pic]).to_html()
    assert '<img alt="회로도" src="bin://7">' in html
    assert "base64" not in html
    assert "file://" not in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_without_image_renders_alt_only_no_src():
    pic = PictureBlock(image=None, description="누락", prov=_prov())
    html = _doc([pic]).to_html()
    assert '<img alt="누락">' in html
    assert "src=" not in html.split("<img")[1].split(">")[0]


@pytest.mark.spec("v0.4.0/view-renderer#AC-5")
def test_picture_real_fixture_no_base64(hwp_sample: Path):
    html = rhwp.parse(str(hwp_sample)).to_ir().to_html()
    assert "base64" not in html
    assert "file://" not in html


# * AC-6 — Formula


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_latex_display_wraps_in_div_math():
    f = FormulaBlock(script="x^2 + y^2", script_kind="latex", inline=False, prov=_prov())
    html = _doc([f]).to_html()
    assert '<div class="math">$$x^2 + y^2$$</div>' in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_latex_inline_wraps_in_span_math():
    """inline=True → ``<span class="math">$...$</span>`` (display ``<div>`` 와 구분)."""
    f = FormulaBlock(script="a", script_kind="latex", inline=True, prov=_prov())
    html = _doc([f]).to_html()
    assert '<span class="math">$a$</span>' in html
    assert '<div class="math">' not in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_hwp_eq_preserves_script_in_pre_code():
    """``script_kind="hwp_eq"`` → raw 보존 (KaTeX 미렌더). HTML 자연 등가는 ``<pre><code>``."""
    f = FormulaBlock(script="1 over 2", script_kind="hwp_eq", prov=_prov())
    html = _doc([f]).to_html()
    assert '<pre><code class="language-hwp-eq">1 over 2</code></pre>' in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-6")
def test_formula_mathml_preserves_script_in_pre_code():
    """``script_kind="mathml"`` — spec 결정 7 본문 미명시, forward-compat 가드.

    ``script`` 안 ``<math>...</math>`` 는 HTML escape 되어 raw text 로 보존.
    """
    f = FormulaBlock(script="<math><mi>x</mi></math>", script_kind="mathml", prov=_prov())
    html = _doc([f]).to_html()
    # escape 된 raw 보존
    assert (
        '<pre><code class="language-mathml">'
        "&lt;math&gt;&lt;mi&gt;x&lt;/mi&gt;&lt;/math&gt;</code></pre>"
    ) in html
    _assert_well_formed_html5(html)


# * AC-7 — Footnote / Endnote


@pytest.mark.spec("v0.4.0/view-renderer#AC-7")
def test_footnote_renders_sup_ref_and_aside_def():
    para = ParagraphBlock(text="이전 연구", prov=_prov(0, 0))
    fn = FootnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="Smith 2020", prov=_prov(99, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    doc = HwpDocument(body=[para], furniture=Furniture(footnotes=[fn]))
    html = doc.to_html()
    assert '<sup><a href="#fn-1">[1]</a></sup>' in html
    assert '<aside id="fn-1" class="footnote">' in html
    assert "Smith 2020" in html
    _assert_well_formed_html5(html)


@pytest.mark.spec("v0.4.0/view-renderer#AC-7")
def test_endnote_uses_separate_id_namespace():
    para = ParagraphBlock(text="후속", prov=_prov(0, 0))
    en = EndnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="별첨", prov=_prov(99, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    doc = HwpDocument(body=[para], furniture=Furniture(endnotes=[en]))
    html = doc.to_html()
    assert '<aside id="en-1" class="endnote">' in html
    assert '<sup><a href="#en-1">[en1]</a></sup>' in html
    _assert_well_formed_html5(html)


@pytest.mark.spec("v0.4.0/view-renderer#AC-7")
def test_footnote_and_endnote_coexist_with_separate_id_namespaces():
    """같은 number 1 이지만 ``id="fn-1"`` / ``id="en-1"`` 분리 + 본문 직후 두 ``<aside>`` 등장."""
    para = ParagraphBlock(text="공존", prov=_prov(0, 0))
    fn = FootnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="각주본문", prov=_prov(99, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    en = EndnoteBlock(
        number=1,
        blocks=[ParagraphBlock(text="미주본문", prov=_prov(0, 0))],
        marker_prov=_prov(0, 0),
        prov=_prov(99, 0),
    )
    doc = HwpDocument(body=[para], furniture=Furniture(footnotes=[fn], endnotes=[en]))
    html = doc.to_html()
    # 두 ref 모두 본문 안 등장
    assert '<sup><a href="#fn-1">[1]</a></sup>' in html
    assert '<sup><a href="#en-1">[en1]</a></sup>' in html
    # 두 def 모두 등장
    assert '<aside id="fn-1" class="footnote">' in html
    assert '<aside id="en-1" class="endnote">' in html
    # 출고 순서: 각주 def 가 미주 def 보다 먼저 (Furniture 내부 순서 계약 — footnotes → endnotes)
    assert html.index('id="fn-1"') < html.index('id="en-1"')
    _assert_well_formed_html5(html)


# * AC-8 — Furniture page_headers / page_footers 비포함


@pytest.mark.spec("v0.4.0/view-renderer#AC-8")
def test_page_headers_and_footers_excluded_from_html():
    body_para = ParagraphBlock(text="본문", prov=_prov(0, 0))
    header_para = ParagraphBlock(text="UNIQUE_HEADER_HTML_4729", prov=_prov(99, 0))
    footer_para = ParagraphBlock(text="UNIQUE_FOOTER_HTML_8316", prov=_prov(99, 1))
    doc = HwpDocument(
        body=[body_para],
        furniture=Furniture(page_headers=[header_para], page_footers=[footer_para]),
    )
    html = doc.to_html()
    assert "본문" in html
    assert "UNIQUE_HEADER_HTML_4729" not in html
    assert "UNIQUE_FOOTER_HTML_8316" not in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-8")
def test_real_fixture_furniture_paragraph_text_excluded_from_html(
    hwp_sample: Path, hwpx_sample: Path
):
    """fixture 의 헤더/푸터 paragraph 가 HTML 출력에 누설되지 않음."""
    for sample in (hwp_sample, hwpx_sample):
        doc = rhwp.parse(str(sample)).to_ir()
        html = doc.to_html()
        for h in [*doc.furniture.page_headers, *doc.furniture.page_footers]:
            if isinstance(h, ParagraphBlock) and h.text:
                assert h.text not in html, f"{sample}: leaked {h.text!r}"


# * AC-9 — CSS opt-in


@pytest.mark.spec("v0.4.0/view-renderer#AC-9")
def test_to_html_default_has_zero_style_tags():
    doc = _doc([ParagraphBlock(text="X", prov=_prov())])
    html = doc.to_html()
    assert html.count("<style>") == 0
    assert html.count("</style>") == 0


@pytest.mark.spec("v0.4.0/view-renderer#AC-9")
def test_to_html_include_css_true_has_exactly_one_style_in_head():
    doc = _doc([ParagraphBlock(text="X", prov=_prov())])
    html = doc.to_html(include_css=True)
    assert html.count("<style>") == 1
    assert html.count("</style>") == 1
    # ``<style>`` 가 ``<head>...</head>`` 영역 안에 위치
    head_section = html.split("</head>", 1)[0]
    assert "<style>" in head_section
    # 외부 스타일시트 0
    assert '<link rel="stylesheet"' not in html


@pytest.mark.spec("v0.4.0/view-renderer#AC-9")
def test_to_html_include_css_real_fixture_well_formed(hwp_sample: Path):
    html = rhwp.parse(str(hwp_sample)).to_ir().to_html(include_css=True)
    assert html.count("<style>") == 1
    _assert_well_formed_html5(html)


# * AC-10 — Idempotency


@pytest.mark.spec("v0.4.0/view-renderer#AC-10")
def test_to_html_byte_equal_on_repeated_calls(hwp_sample: Path):
    doc = rhwp.parse(str(hwp_sample)).to_ir()
    a = doc.to_html()
    b = doc.to_html()
    assert a == b


@pytest.mark.spec("v0.4.0/view-renderer#AC-10")
def test_to_html_byte_equal_with_and_without_css_distinct(hwp_sample: Path):
    """include_css 분기는 결과 differ — 두 호출이 동일 옵션이면 byte-equal."""
    doc = rhwp.parse(str(hwp_sample)).to_ir()
    a1 = doc.to_html(include_css=True)
    a2 = doc.to_html(include_css=True)
    b = doc.to_html(include_css=False)
    assert a1 == a2
    assert a1 != b


# * Bonus — list grouping


def test_consecutive_list_items_group_into_single_ul():
    items = [
        ListItemBlock(text="A", enumerated=False, prov=_prov(0, 0)),
        ListItemBlock(text="B", enumerated=False, prov=_prov(0, 1)),
    ]
    html = _doc(items).to_html()
    # 단일 <ul> 안에 두 <li>
    assert html.count("<ul>") == 1
    assert html.count("<li>A</li>") == 1
    assert html.count("<li>B</li>") == 1


def test_enumerated_list_uses_ol():
    items = [ListItemBlock(text="첫째", enumerated=True, prov=_prov(0, 0))]
    html = _doc(items).to_html()
    assert "<ol>" in html
    assert "<ul>" not in html


def test_alternating_list_kind_creates_separate_lists():
    items = [
        ListItemBlock(text="A", enumerated=False, prov=_prov(0, 0)),
        ListItemBlock(text="1", enumerated=True, prov=_prov(0, 1)),
    ]
    html = _doc(items).to_html()
    assert html.count("<ul>") == 1
    assert html.count("<ol>") == 1


def test_list_item_level_preserved_via_data_level_attribute():
    """``ListItemBlock.level > 0`` 은 ``<li data-level="N">`` 으로 정보 보존.

    Markdown 측은 ``"  " * level`` 들여쓰기로 자연 표현 — HTML 평면 ``<ul>`` 은
    같은 정보를 표현할 자연 syntax 가 없어 attribute 로 보존 (양쪽 출력 정보
    비대칭 회피). 정식 HTML5 nested ``<ul>`` 재구성은 v0.4.0 영구 비목표.
    """
    items = [
        ListItemBlock(text="L0", enumerated=False, level=0, prov=_prov(0, 0)),
        ListItemBlock(text="L1", enumerated=False, level=1, prov=_prov(0, 1)),
        ListItemBlock(text="L2", enumerated=False, level=2, prov=_prov(0, 2)),
    ]
    html = _doc(items).to_html()
    # level=0 은 attribute 부재 (간결성)
    assert "<li>L0</li>" in html
    assert '<li data-level="1">L1</li>' in html
    assert '<li data-level="2">L2</li>' in html
    _assert_well_formed_html5(html)
