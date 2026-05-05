---
status: Frozen
description: "v0.4.0 — Document IR → Markdown / HTML view 렌더러. 'HwpDocument.to_markdown()' / 'to_html()' 인스턴스 메서드 추가, schema 유지"
ga: v0.4.0
last_updated: 2026-05-05
---

# v0.4.0 — IR view 렌더러 (Markdown / HTML)

v0.2.0/v0.3.0 의 Document IR (`HwpDocument`, schema_version `"1.1"`) 을 외부 view 포맷 (Markdown / HTML) 으로 렌더링하는 첫 변환 표면을 추가한다. 지금까지 IR 은 *프로그래매틱 접근* (LangChain loader / iter_blocks / model_dump) 만 노출해 왔으나, v0.7.0 MCP server (`to_markdown` / `to_html` 도구) 와 후속 RAG 프레임워크 통합 (v0.5 LlamaIndex / v0.6 Haystack) 이 모두 *문자열 출력* 을 1차 인터페이스로 사용한다 — IR ↔ string 변환을 한 SSOT 렌더러로 통합한다. HtmlRAG ([arXiv:2411.02959](https://arxiv.org/abs/2411.02959), WWW 2025) 등 최근 연구는 LLM 에 문서를 제공할 때 *구조를 보존하는 HTML* 이 평문화 대비 우수함을 보고하므로, view 변환 품질이 RAG 체감 성능과 직결된다.

API 는 `HwpDocument` 인스턴스 메서드로 추가 — `doc.to_markdown()` / `doc.to_html(include_css=False)`. 기존 IR schema / 파싱 API / `Document` wrapper 는 모두 변경 없음 (additive only) — `schema_version` 은 `"1.1"` 유지. 신규 extras 도입 없음 (pure stdlib).

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [view-renderer-research.md](../../design/v0.4.0/view-renderer-research.md).

## 결정 사항

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — API placement | `HwpDocument` 인스턴스 메서드 — `doc.to_markdown()` / `doc.to_html(include_css=False)` | IR 모델 자기-기술 원칙 — Pydantic `model_dump()` / Docling `DoclingDocument.export_to_markdown()` 동등 패턴. `Document` wrapper 메서드는 영구 비목표 (Rust core 책임 분리, `doc.to_ir().to_markdown()` chain). 자세한 옵션 비교는 ADR §1 |
| 2 — Markdown 방언 | GFM ([github.github.com/gfm](https://github.github.com/gfm/)) | 표 (`|a|b|`) + 각주 (`[^1]`) + 코드펜스로 IR 핵심 블록 모두 표현 가능. CommonMark 단독은 표 미지원, Pandoc/MyST 는 호환 분모 좁음. 자세한 옵션 비교는 ADR §2 |
| 3 — HTML 출력 형태 | 완전한 HTML5 문서 (`<!DOCTYPE html>` + `<html>` + `<head>` + `<body>`) | 브라우저 표시용 standalone — 사용자가 fragment 가 필요하면 IR `TableBlock.html` 을 직접 합성. `to_html()` 출력 ↔ `TableBlock.html` 출력은 책임 단위 분리 |
| 4 — CSS 동봉 | `include_css: bool = False`, `True` 일 때 `<head>` 에 embedded `<style>` 1개 | RAG 임베딩 / 텍스트 추출이 1차 사용처 — CSS 불필요. 브라우저 표시용은 opt-in. 외부 `<link rel="stylesheet">` / 외부 파일 분리는 영구 비목표 (extras 미도입 정책 일관) |
| 5 — 표 셀 병합 (rowspan/colspan) | 모든 셀 span=1 → GFM 표. `row_span` 또는 `col_span > 1` → IR `TableBlock.html` 그대로 inline (재합성 안 함) | GFM spec 자체가 raw HTML inline 허용. lossy 회피 + 단순 표 가독성 양립. `TableBlock.html` 재사용으로 본 binding 내 단일 source. 자세한 비교는 ADR §3 |
| 6 — 이미지 처리 | placeholder 만 — `picture.image.uri` (`bin://<id>`) pass-through, alt-text 는 `description` | embedded / external 모드는 raw bytes resolution → `Document.bytes_for_image()` 의존 → IR 메서드 의존 방향 역전. v0.4.0 IR 메서드 범위 밖 — 영구 비목표. 자세한 비교는 ADR §4 |
| 7 — 수식 표현 | `script_kind="latex"`: `inline=False` → `$$...$$` (Markdown) / `<div class="math">$$...$$</div>` (HTML), `inline=True` → `$...$`. `script_kind="hwp_eq"`: ` ```hwp-eq ``` ` fenced block (raw 보존, 자동 변환 없음) | `$$` 수식 syntax 사실상 호환 (GitHub / Slack / Discord 등 — MathJax / KaTeX 양쪽). HWP eq → LaTeX 자동 변환은 v0.3.0 영구 비목표 그대로 — 사용자가 `model_copy(update={"script": tex, "script_kind": "latex"})` 로 재구성 |
| 8 — furniture 처리 | 각주 (`FootnoteBlock`) / 미주 (`EndnoteBlock`) 만 footnote 형식 — Markdown `[^N]` ref + 끝 정의, HTML `<sup>` ref + `<aside id="fn-N">` 정의. 머리글 / 꼬리말은 출력 미포함 | 각주/미주는 본문 의미 + `marker_prov` 로 본문 위치 1:1. 머리글/꼬리말은 페이지 단위 장식 — 페이지 무관 단일 string view 에서 의미 약함. 자세한 비교는 ADR §5 |
| 9 — 외부 영향 | 기존 IR schema / 파싱 API / `Document` wrapper / extras 모두 변경 없음 (additive only) | `HwpDocument` 에 메서드 추가는 schema 영향 없음 (Pydantic JSON serialization 무관). 순수 stdlib 구현 — 신규 dependency 0 |

## 인수조건

- **AC-1** — `doc.to_markdown()` 호출은 valid GFM 문자열 반환 — GFM-aware parser (예: `markdown-it-py` `extensions=["table", "footnote"]`) 가 에러 없이 round-trip parse
- **AC-2** — `doc.to_html()` 호출은 well-formed HTML5 문서 반환 — `<!DOCTYPE html>` 시작 + `<html>` 루트 + `<body>` 본문, `lxml.html.fromstring` 등 strict parser 로 round-trip parse
- **AC-3** — `TableBlock.row_span` 또는 `col_span > 1` 인 셀이 있는 표는 `to_markdown()` 출력에서 HTML `<table>` 인라인 (GFM `|...|` 표가 아님). 모든 셀 `span == 1` 인 표는 GFM `|...|` 표
- **AC-4** — `to_html()` 의 표 영역은 IR `TableBlock.html` 문자열을 그대로 substring 으로 포함 (재합성하지 않음)
- **AC-5** — PictureBlock 의 출력은 IR `picture.image.uri` 를 그대로 pass-through — Markdown `![<description>](bin://<id>)` / HTML `<img alt="<description>" src="bin://<id>">`. `picture.image is None` 이면 src 없이 alt 만 — Markdown `![<description>]()` / HTML `<img alt="<description>">`. raw bytes 미포함 (출력 string 안 base64 / file path 0 회 등장)
- **AC-6** — `FormulaBlock.script_kind="latex"` + `inline=False` → 출력에 `$$<script>$$` 등장 (Markdown) / `<div class="math">$$<script>$$</div>` 등장 (HTML). `inline=True` → `$<script>$` 등장. `script_kind="hwp_eq"` → ` ```hwp-eq\n<script>\n``` ` fenced block 등장 (KaTeX 미렌더, raw 보존)
- **AC-7** — `furniture.footnotes` 의 `FootnoteBlock(number=N)` 은 두 출력 모두에 등장 — Markdown 은 본문 paragraph 안 `[^N]` reference + 출력 끝 `[^N]: <text>` 정의, HTML 은 본문 paragraph 안 `<sup><a href="#fn-N">[N]</a></sup>` reference + 본문 직후 `<aside id="fn-N">` 정의 블록. `EndnoteBlock` 도 동일 형식 (number 공간 분리 — 각주는 1,2,3.../ 미주는 별도 prefix)
- **AC-8** — `furniture.page_headers` / `page_footers` 가 비어있지 않은 fixture (예: `external/rhwp/samples/aift.hwp`) 에서도 두 출력 모두에 헤더/푸터 paragraph 의 평문 텍스트가 등장하지 않음 (페이지 단위 장식 비범위, 결정 8)
- **AC-9** — `to_html(include_css=False)` (기본) 출력은 `<style>` 태그 0 회 등장. `to_html(include_css=True)` 출력은 `<head>` 안에 `<style>` 태그 정확히 1 회 등장 (외부 `<link rel="stylesheet">` 0 회)
- **AC-10** — 동일 IR 인스턴스에 `to_markdown()` / `to_html()` 두 번 호출 결과는 byte-equal — `frozen=True` IR 정합 + 호출이 IR 인스턴스를 변경하지 않음 (idempotency)
- **AC-11** — fixture (`external/rhwp/samples/aift.hwp`, `external/rhwp/samples/table-vpos-01.hwpx`) 의 `Document.to_ir()` 출력은 v0.3.2 GA baseline 과 byte-equal (additive 변경 — schema / 파싱 경로 영향 0)

## 영구 비목표

- **머리글 / 꼬리말 view 출력 포함** — 페이지 단위 장식, 페이지 무관 단일 string view 에서 의미 약함. 사용자는 `iter_blocks(scope="furniture")` 로 별도 접근 (결정 8)
- **이미지 embedded / external 모드** — raw bytes resolution 은 `Document.bytes_for_image()` 의존 → IR 메서드 의존 방향 역전. 별도 spec 에서 `Document.to_markdown_with_images(image_mode=...)` 등 wrapper 추가 검토 (결정 6)
- **HWP equation script → LaTeX 자동 변환** — 공개 변환기 부재, v0.3.0 spec § 비목표 그대로. `script_kind="hwp_eq"` raw 출고 + 사용자 외부 변환 (결정 7)
- **Pandoc Markdown / MyST / CommonMark-only 방언 옵션** — GFM 단독 — 다른 방언은 사용자가 GFM 출력을 외부 변환기 (`pandoc -f gfm -t myst`) 로 처리 (결정 2)
- **`Document` wrapper 의 `to_markdown()` / `to_html()` 메서드** — IR 모델 자기-기술 원칙. `doc.to_ir().to_markdown()` chain (결정 1)
- **CSS 외부 파일 분리 (`<link rel="stylesheet" href="...">`)** — 외부 dependency / file I/O 도입 — 본 binding extras 미도입 정책. embedded `<style>` 만 (결정 4)
- **HTML 출력 fragment 모드** — 완전한 HTML5 문서 단독. 사용자가 fragment 필요 시 IR `TableBlock.html` 직접 합성 또는 `lxml.html.fromstring(doc.to_html()).body` 추출 (결정 3)

## 참조

- 짝 페어 (ADR): [view-renderer-research.md](../../design/v0.4.0/view-renderer-research.md)
- 활성 spec 인덱스 (Phase 3 — RAG 프레임워크 통합 wave 시작): [roadmap/README.md](../README.md)
- HtmlRAG (구조 보존이 RAG 성능 향상에 기여, WWW 2025): <https://arxiv.org/abs/2411.02959>
- GFM spec: <https://github.github.com/gfm/>
- HTML5 spec: <https://html.spec.whatwg.org/>
- KaTeX supported syntax: <https://katex.org/docs/supported>
- IR `HwpDocument`: `python/rhwp/ir/nodes.py:652`
- IR `TableBlock` (3중 표현): `python/rhwp/ir/nodes.py:550`
- `Document.bytes_for_image`: `python/rhwp/document.py:150`
