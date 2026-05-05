"""rhwp.ir._view — IR → Markdown / HTML 렌더링 SSOT.

``HwpDocument.to_markdown()`` / ``to_html()`` 본체. ``nodes.py`` 에 직접 두지
않은 이유: (1) 모듈 책임 분리 — ``nodes`` 는 모델 선언, 본 모듈은 view 변환,
(2) cycle 회피 — 본 모듈은 ``nodes`` 의 BaseModel 들을 import 하므로 ``nodes``
가 본 모듈을 직접 import 하면 사이클. ``HwpDocument`` 메서드는 deferred import
(함수 본문 안 import) 로 위임.

결정 사항 출처: ``docs/roadmap/v0.4.0/view-renderer.md`` §결정 사항 표 9 항목.
GFM (결정 2), 완전 HTML5 (결정 3), CSS opt-in (결정 4), 표 병합 폴백 (결정 5),
이미지 placeholder (결정 6), 수식 (결정 7), 각주/미주만 (결정 8), additive only
(결정 9). API placement (결정 1) 은 ``nodes.HwpDocument`` 메서드 본문에서 위임.
"""

from html import escape

from rhwp.ir.nodes import (
    Block,
    CaptionBlock,
    EndnoteBlock,
    FieldBlock,
    FootnoteBlock,
    FormulaBlock,
    HwpDocument,
    ListItemBlock,
    ParagraphBlock,
    PictureBlock,
    TableBlock,
    TocBlock,
)

# * Footnote / Endnote 인덱스 — 본문 paragraph 위치 → 인용 마커 매핑


class _FootnoteIndex:
    """본문 paragraph 위치별 footnote/endnote 마커 인덱스.

    paragraph 단위 매핑 — char offset 미사용 (ADR §5: 본 spec 은 paragraph 단위
    동작, 인용은 paragraph 끝에 append best-approximation).

    각 entry 는 ``(label_prefix, number)`` — Markdown ref/def 의 label 영역에
    그대로 들어가는 prefix (``""`` for footnote → ``[^1]``, ``"en"`` for endnote
    → ``[^en1]``). HTML id namespace 는 별도 ``"fn"``/``"en"`` 매핑 (AC-7 의
    Markdown ``[^N]`` syntax 와 HTML ``id="fn-N"`` 어휘 차이를 흡수).
    """

    def __init__(self, doc: HwpDocument) -> None:
        self._by_para: dict[tuple[int, int], list[tuple[str, int]]] = {}
        for fn in doc.furniture.footnotes:
            key = (fn.marker_prov.section_idx, fn.marker_prov.para_idx)
            self._by_para.setdefault(key, []).append(("", fn.number))
        for en in doc.furniture.endnotes:
            key = (en.marker_prov.section_idx, en.marker_prov.para_idx)
            self._by_para.setdefault(key, []).append(("en", en.number))

    def markers_for(self, section_idx: int, para_idx: int) -> list[tuple[str, int]]:
        return self._by_para.get((section_idx, para_idx), [])


# * Markdown 렌더 (결정 2 GFM, 결정 8 furniture)


def render_markdown(doc: HwpDocument) -> str:
    """``HwpDocument`` → GFM 문자열.

    결정 2 (GFM 방언) + 결정 8 (각주/미주만 footnote 형식, 헤더/푸터 제외).
    AC-1 / AC-7 / AC-8 / AC-10 충족.
    """
    fn_index = _FootnoteIndex(doc)
    body_parts = _md_blocks(doc.body, fn_index)

    fn_defs: list[str] = []
    for fn in doc.furniture.footnotes:
        fn_defs.append(_md_footnote_def(fn, prefix=""))
    for en in doc.furniture.endnotes:
        fn_defs.append(_md_footnote_def(en, prefix="en"))

    sections: list[str] = []
    if body_parts:
        sections.append("\n\n".join(body_parts))
    if fn_defs:
        sections.append("\n\n".join(fn_defs))
    return "\n\n".join(sections) + ("\n" if sections else "")


def _md_blocks(blocks: list[Block], fn_index: _FootnoteIndex) -> list[str]:
    """Block 리스트 → Markdown chunk 리스트. 빈 출력은 skip (RAG 노이즈 회피)."""
    parts: list[str] = []
    for block in blocks:
        rendered = _md_block(block, fn_index)
        if rendered:
            parts.append(rendered)
    return parts


def _md_block(block: Block, fn_index: _FootnoteIndex) -> str:
    if isinstance(block, ParagraphBlock):
        return _md_paragraph(block, fn_index)
    if isinstance(block, ListItemBlock):
        return _md_list_item(block, fn_index)
    if isinstance(block, TableBlock):
        return _md_table(block)
    if isinstance(block, PictureBlock):
        return _md_picture(block)
    if isinstance(block, FormulaBlock):
        return _md_formula(block)
    if isinstance(block, CaptionBlock):
        return _md_caption(block, fn_index)
    if isinstance(block, TocBlock):
        return _md_toc(block)
    if isinstance(block, FieldBlock):
        return _md_field(block)
    # ^ FootnoteBlock / EndnoteBlock / UnknownBlock — body 통과 시 skip.
    #   (Footnote/Endnote 는 furniture 거주가 정상, UnknownBlock 은 forward-compat 미지 타입)
    return ""


def _md_paragraph(block: ParagraphBlock, fn_index: _FootnoteIndex) -> str:
    text = block.text
    markers = fn_index.markers_for(block.prov.section_idx, block.prov.para_idx)
    if markers:
        ref = "".join(f"[^{prefix}{n}]" for prefix, n in markers)
        text = text + ref if text else ref
    return text


def _md_list_item(block: ListItemBlock, fn_index: _FootnoteIndex) -> str:
    bullet = "1." if block.enumerated else "-"
    indent = "  " * block.level
    text = block.text
    markers = fn_index.markers_for(block.prov.section_idx, block.prov.para_idx)
    if markers:
        ref = "".join(f"[^{prefix}{n}]" for prefix, n in markers)
        text = text + ref if text else ref
    return f"{indent}{bullet} {text}".rstrip()


def _md_table(block: TableBlock) -> str:
    """결정 5 — 모든 셀 span=1 → GFM 표, 병합 셀 → ``TableBlock.html`` 인라인."""
    has_merged = any(c.row_span > 1 or c.col_span > 1 for c in block.cells)
    if has_merged:
        return block.html
    if not block.cells or block.rows == 0 or block.cols == 0:
        return block.html
    grid: list[list[str]] = [["" for _ in range(block.cols)] for _ in range(block.rows)]
    for cell in block.cells:
        if 0 <= cell.row < block.rows and 0 <= cell.col < block.cols:
            grid[cell.row][cell.col] = _md_cell_text(cell.blocks)
    lines: list[str] = []
    head = grid[0]
    lines.append("| " + " | ".join(_md_table_escape(c) for c in head) + " |")
    lines.append("| " + " | ".join("---" for _ in head) + " |")
    for row in grid[1:]:
        lines.append("| " + " | ".join(_md_table_escape(c) for c in row) + " |")
    return "\n".join(lines)


def _md_cell_text(blocks: list[Block]) -> str:
    """셀 안 평문화 — GFM 표는 한 셀에 한 줄, 다양한 블록은 평문 합성."""
    parts: list[str] = []
    for b in blocks:
        if isinstance(b, ParagraphBlock) and b.text:
            parts.append(b.text)
        elif isinstance(b, ListItemBlock) and b.text:
            parts.append(b.text)
        elif isinstance(b, FormulaBlock):
            alt = b.text_alt or b.script
            if alt:
                parts.append(alt)
        elif isinstance(b, FieldBlock) and b.cached_value:
            parts.append(b.cached_value)
    return " ".join(parts)


def _md_table_escape(s: str) -> str:
    """GFM 표 셀 안 ``|`` / 개행 escape — 셀 한 줄 invariant 유지."""
    return s.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _md_picture(block: PictureBlock) -> str:
    """결정 6 — placeholder 만, ``picture.image.uri`` pass-through.

    ``description`` 안 ``[``/``]`` 는 GFM 이미지 alt 슬롯 종료 토큰이라 backslash
    escape — 미escape 시 ``![A]B](url)`` 같은 깨진 syntax 출고 위험 (AC-1 위배).
    URI 는 v0.3.0 시점 ``bin://<int>`` 만 출고되어 안전. forward-compat 모드
    (``data:`` / ``file://``) 도입 시 angle-bracket wrap (``<...>``) 검토.
    """
    alt = (block.description or "").replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    src = block.image.uri if block.image is not None else ""
    return f"![{alt}]({src})"


def _md_formula(block: FormulaBlock) -> str:
    """결정 7 — script_kind / inline 분기.

    ``mathml`` 은 spec 결정 7 본문 미명시 — ``FormulaBlock.script_kind`` Literal
    이 셋째 값으로 보유하므로 forward-compat fenced block 으로 출고 (raw 보존).
    spec 본문 추가 시 본 분기 행동 정식화.
    """
    if block.script_kind == "latex":
        return f"${block.script}$" if block.inline else f"$${block.script}$$"
    if block.script_kind == "mathml":
        return f"```mathml\n{block.script}\n```"
    return f"```hwp-eq\n{block.script}\n```"


def _md_caption(block: CaptionBlock, fn_index: _FootnoteIndex) -> str:
    """본 spec 은 caption 단독 표기 미명시 — 평문 paragraph 합성.

    파싱 경로에서는 ``PictureBlock.caption`` / ``TableBlock.caption_block`` 으로
    부모에 부착되므로 body 단독 등장은 사용자 직접 구성 시뿐. 그 케이스에서
    inner blocks 평문 결합으로 폴백.
    """
    inner = _md_blocks(block.blocks, fn_index)
    return "\n\n".join(inner)


def _md_toc(block: TocBlock) -> str:
    """v0.3.0 TocBlock.entries 는 보통 빈 (resolver 미도입). 비어 있으면 skip."""
    if not block.entries:
        return ""
    lines: list[str] = []
    for entry in block.entries:
        indent = "  " * (entry.level - 1) if entry.level >= 1 else ""
        lines.append(f"{indent}- {entry.text}")
    return "\n".join(lines)


def _md_field(block: FieldBlock) -> str:
    return block.cached_value or ""


def _md_footnote_def(block: FootnoteBlock | EndnoteBlock, prefix: str) -> str:
    """``[^N]: <text>`` 정의 — inner blocks 평문 결합."""
    return f"[^{prefix}{block.number}]: {_inline_text(block.blocks)}"


def _inline_text(blocks: list[Block]) -> str:
    """각주/미주 inner blocks → 한 줄 평문. 인라인-스러운 블록만 결합."""
    parts: list[str] = []
    for b in blocks:
        if isinstance(b, ParagraphBlock) and b.text:
            parts.append(b.text)
        elif isinstance(b, ListItemBlock) and b.text:
            parts.append(b.text)
        elif isinstance(b, FormulaBlock):
            alt = b.text_alt or b.script
            if alt:
                parts.append(alt)
        elif isinstance(b, FieldBlock) and b.cached_value:
            parts.append(b.cached_value)
    return " ".join(parts)


# * HTML 렌더 (결정 3 완전 문서, 결정 4 CSS opt-in, 결정 5 TableBlock.html 재사용)


_DEFAULT_CSS = (
    "body{font-family:sans-serif;max-width:800px;margin:2em auto;padding:0 1em}"
    "table{border-collapse:collapse}"
    "table,th,td{border:1px solid #ccc;padding:4px 8px}"
    "aside.footnote,aside.endnote{font-size:0.9em;color:#555;"
    "border-top:1px solid #ccc;margin-top:1em;padding-top:0.5em}"
    "div.math{text-align:center;margin:1em 0}"
)


def render_html(doc: HwpDocument, *, include_css: bool = False) -> str:
    """``HwpDocument`` → 완전 HTML5 문서.

    결정 3 (``<!DOCTYPE html>`` + ``<html>`` + ``<head>`` + ``<body>``) +
    결정 4 (``include_css=True`` 일 때 ``<head>`` 안 단일 ``<style>``).
    AC-2 / AC-4 / AC-9 / AC-10 충족.
    """
    fn_index = _FootnoteIndex(doc)
    body_parts = _html_blocks(doc.body, fn_index)

    fn_defs: list[str] = []
    for fn in doc.furniture.footnotes:
        fn_defs.append(_html_footnote_def(fn, prefix="fn"))
    for en in doc.furniture.endnotes:
        fn_defs.append(_html_footnote_def(en, prefix="en"))

    head_parts = ['<meta charset="utf-8">']
    if doc.metadata.title:
        head_parts.append(f"<title>{escape(doc.metadata.title)}</title>")
    if include_css:
        head_parts.append(f"<style>{_DEFAULT_CSS}</style>")

    body_html = "\n".join(body_parts + fn_defs)
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>" + "".join(head_parts) + "</head>\n"
        "<body>\n" + body_html + ("\n" if body_html else "") + "</body>\n"
        "</html>\n"
    )


def _html_blocks(blocks: list[Block], fn_index: _FootnoteIndex) -> list[str]:
    """Block 리스트 → HTML chunk 리스트. 연속 ``ListItemBlock`` 은 ``<ul>``/``<ol>`` 로 그룹."""
    parts: list[str] = []
    list_buffer: list[ListItemBlock] = []
    list_enumerated: bool | None = None

    def flush_list() -> None:
        nonlocal list_buffer, list_enumerated
        if list_buffer:
            tag = "ol" if list_enumerated else "ul"
            items = "\n".join(_html_list_item(b, fn_index) for b in list_buffer)
            parts.append(f"<{tag}>\n{items}\n</{tag}>")
            list_buffer = []
            list_enumerated = None

    for block in blocks:
        if isinstance(block, ListItemBlock):
            if list_enumerated is not None and list_enumerated != block.enumerated:
                flush_list()
            list_enumerated = block.enumerated
            list_buffer.append(block)
            continue
        flush_list()
        rendered = _html_block(block, fn_index)
        if rendered:
            parts.append(rendered)
    flush_list()
    return parts


def _html_block(block: Block, fn_index: _FootnoteIndex) -> str:
    if isinstance(block, ParagraphBlock):
        return _html_paragraph(block, fn_index)
    if isinstance(block, TableBlock):
        return _html_table(block)
    if isinstance(block, PictureBlock):
        return _html_picture(block)
    if isinstance(block, FormulaBlock):
        return _html_formula(block)
    if isinstance(block, CaptionBlock):
        return _html_caption(block, fn_index)
    if isinstance(block, TocBlock):
        return _html_toc(block)
    if isinstance(block, FieldBlock):
        return _html_field(block)
    # ^ ListItemBlock 은 _html_blocks 의 그룹 핸들러가 처리, 여기 도달하지 않음.
    #   FootnoteBlock / EndnoteBlock / UnknownBlock — body 통과 시 skip.
    return ""


def _html_paragraph(block: ParagraphBlock, fn_index: _FootnoteIndex) -> str:
    inner = escape(block.text)
    markers = fn_index.markers_for(block.prov.section_idx, block.prov.para_idx)
    if markers:
        refs = "".join(_html_footnote_ref(prefix, n) for prefix, n in markers)
        inner = inner + refs if inner else refs
    if not inner:
        return ""
    return f"<p>{inner}</p>"


def _html_list_item(block: ListItemBlock, fn_index: _FootnoteIndex) -> str:
    """``ListItemBlock`` → ``<li>``. ``level > 0`` 은 ``data-level`` 속성으로 보존.

    HWP ``ParaShape.para_level`` 의 0~6 nesting 정보. Markdown 측은 들여쓰기
    (``"  " * level``) 로 자연 표현되지만 HTML 평면 ``<ul>`` 안에서는 같은 정보를
    표현할 자연 syntax 가 없음 — ``data-level`` 으로 보존해 두 출력 사이 정보 비대칭
    회피. 정식 HTML5 nested list (``<ul><li><ul>...``) 재구성은 v0.4.0 영구 비목표.
    """
    inner = escape(block.text)
    markers = fn_index.markers_for(block.prov.section_idx, block.prov.para_idx)
    if markers:
        refs = "".join(_html_footnote_ref(prefix, n) for prefix, n in markers)
        inner = inner + refs if inner else refs
    if block.level > 0:
        return f'<li data-level="{block.level}">{inner}</li>'
    return f"<li>{inner}</li>"


def _html_table(block: TableBlock) -> str:
    """결정 5 — IR ``TableBlock.html`` 그대로 inline (재합성 안 함, AC-4)."""
    return block.html


def _html_picture(block: PictureBlock) -> str:
    """결정 6 — ``image.uri`` pass-through, ``description`` → alt."""
    alt = escape(block.description or "")
    if block.image is not None:
        src = escape(block.image.uri, quote=True)
        return f'<img alt="{alt}" src="{src}">'
    return f'<img alt="{alt}">'


def _html_formula(block: FormulaBlock) -> str:
    """결정 7 — latex display 는 ``<div class="math">``, 그 외는 자연 HTML 등가."""
    if block.script_kind == "latex":
        if block.inline:
            return f'<span class="math">${escape(block.script)}$</span>'
        return f'<div class="math">$${escape(block.script)}$$</div>'
    if block.script_kind == "mathml":
        return f'<pre><code class="language-mathml">{escape(block.script)}</code></pre>'
    return f'<pre><code class="language-hwp-eq">{escape(block.script)}</code></pre>'


def _html_caption(block: CaptionBlock, fn_index: _FootnoteIndex) -> str:
    inner = "\n".join(_html_blocks(block.blocks, fn_index))
    return f"<figcaption>\n{inner}\n</figcaption>" if inner else ""


def _html_toc(block: TocBlock) -> str:
    if not block.entries:
        return ""
    items = "\n".join(f"<li>{escape(e.text)}</li>" for e in block.entries)
    return f'<nav class="toc">\n<ul>\n{items}\n</ul>\n</nav>'


def _html_field(block: FieldBlock) -> str:
    return f"<p>{escape(block.cached_value)}</p>" if block.cached_value else ""


def _html_footnote_ref(prefix: str, number: int) -> str:
    """본문 paragraph 안 인용 마커 — ``<sup><a href="#<id>">[N]</a></sup>``."""
    target = f"{prefix or 'fn'}-{number}"
    label = f"{prefix}{number}"
    return f'<sup><a href="#{target}">[{label}]</a></sup>'


def _html_footnote_def(block: FootnoteBlock | EndnoteBlock, prefix: str) -> str:
    """본문 직후 ``<aside id="<prefix>-N" class="footnote|endnote">`` 정의."""
    cls = "footnote" if prefix == "fn" else "endnote"
    label_prefix = "" if prefix == "fn" else "en"
    text = escape(_inline_text(block.blocks))
    return (
        f'<aside id="{prefix}-{block.number}" class="{cls}">'
        f"<sup>[{label_prefix}{block.number}]</sup> {text}"
        f"</aside>"
    )
