---
status: Frozen
description: "v0.4.0 view-renderer ADR — API placement / Markdown 방언 / 표 병합 폴백 / 이미지 처리 범위 / furniture 처리 5 결정의 근거"
ga: v0.4.0
last_updated: 2026-05-05
---

# v0.4.0 view-renderer — 설계 의사결정 리서치 요약

[v0.4.0/view-renderer.md](../../roadmap/v0.4.0/view-renderer.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 5건의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | API placement | A: free function `rhwp.view.markdown(doc)` / B: `HwpDocument` 인스턴스 메서드 / C: `Document` wrapper 메서드 | **B** | IR 모델 자기-기술 + Pydantic / Docling 동등 패턴 일치 |
| 2 | Markdown 방언 | A: CommonMark / B: GFM / C: Pandoc Markdown / D: MyST | **B** | 표·각주·코드펜스로 IR 핵심 블록 모두 표현 + 가장 넓은 클라이언트 호환 분모 |
| 3 | 표 셀 병합 표현 | A: GFM 표만 (병합 시 lossy) / B: HTML `<table>` 인라인 폴백 / C: Markdown extension (`{rowspan=2}` 등) | **B** | GFM spec 자체가 raw HTML inline 허용. `TableBlock.html` 재사용으로 본 binding 내 단일 source |
| 4 | 이미지 처리 | A: placeholder 만 / B: placeholder + embedded / C: 3 모드 모두 (placeholder + embedded + external) | **A** | embedded / external 은 raw bytes resolution → `Document.bytes_for_image()` 의존, IR 메서드 위치 결정 (§1) 과 충돌 |
| 5 | furniture 처리 | A: 모두 비포함 / B: 각주/미주만 footnote 형식 / C: 헤더/푸터까지 모두 포함 | **B** | 각주/미주는 `marker_prov` 로 본문 1:1 / 헤더/푸터는 페이지 단위 → 페이지 무관 view 에서 1:N 매핑 모호 |

## 1. API placement — IR 메서드 vs free function vs Document 메서드

### 팩트

- 본 binding IR 모델: `python/rhwp/ir/nodes.py:652` (`HwpDocument` BaseModel, `frozen=True`)
- 본 binding Document wrapper: `python/rhwp/document.py:43` (`Document`, Rust `_Document` thin wrapper, `unsendable`)
- Pydantic V2 BaseModel 은 메서드 추가 가능 — `frozen=True` 는 field 변경만 차단, method 정의 무관 (<https://docs.pydantic.dev/latest/concepts/models/>)
- 동등 라이브러리 패턴:

  | 라이브러리 | 모델 | 변환 메서드 |
  |---|---|---|
  | Pydantic | `BaseModel` | `model_dump()`, `model_dump_json()` |
  | Docling | `DoclingDocument` | `export_to_markdown()`, `export_to_html()`, `export_to_text()` |
  | Marshmallow | `Schema` | `dump()`, `load()` |
  | Word docx (`python-docx`) | `Document` | (변환 없음 — IR 부재) |
- 본 binding 선례: `Document.to_ir()` / `Document.to_ir_json()` — Document 가 IR 으로 변환, IR 자체는 직렬화 메서드만 (Pydantic 기본). 즉 *Document → IR* 은 Document 책임, *IR → string* 은 IR 책임으로 분리 가능

### 검증자 반박

- "free function `rhwp.view.markdown(doc)` 가 함수형 스타일로 더 명시적 아닌가?" → 발견성 (discoverability) 낮음 — `from rhwp.view import markdown` import 부담. 인스턴스 메서드는 `doc.to_markdown()` 한 줄로 IDE autocomplete 활용. Pydantic / Docling 등 동등 라이브러리 모두 인스턴스 메서드 채택 — 사용자 학습 비용 절감
- "`Document.to_markdown()` 으로 두면 raw bytes 도 처리 가능한데?" → Document 메서드는 Rust `_Document` 영역. IR 위 변환은 IR 책임 — 책임 분리. `doc.to_ir().to_markdown()` chain 으로 두 단계 명시. 추가 image bytes 처리는 별도 spec 에서 `Document.to_markdown_with_images()` wrapper 추가 (forward compat) — v0.5.0+ 검토
- "IR 모델에 view 메서드 추가는 모델 비대화? `HwpDocument` 가 view 라이브러리도 알아야 함" → schema 변경 (Pydantic field 추가) 이 아닌 method 추가 — JSON serialization 영향 없음. 메서드 본체는 별도 모듈 (`python/rhwp/ir/_view.py`) 에 두고 `HwpDocument.to_markdown` 은 위임 — import cycle 회피 가능

### 최종 결정

**옵션 B — `HwpDocument` 인스턴스 메서드**. 동등 라이브러리 (Pydantic / Docling / Marshmallow) 의 일치 + discoverability + 책임 분리 (IR ↔ string 변환은 IR 책임).

### 1차 소스

- Pydantic `BaseModel.model_dump`: <https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_dump>
- Docling `DoclingDocument` 변환 메서드: <https://github.com/docling-project/docling-core>
- 본 binding `HwpDocument` 정의: `python/rhwp/ir/nodes.py:652`
- 본 binding `Document` 정의: `python/rhwp/document.py:43`

## 2. Markdown 방언 — GFM 채택, CommonMark / Pandoc / MyST 거부

### 팩트

- CommonMark (<https://commonmark.org/>): 표 / 각주 모두 미지원 (인용 / 헤딩 / 리스트 / 코드펜스만)
- GFM (<https://github.github.com/gfm/>): CommonMark superset + 표 (`|a|b|`) + 각주 (`[^1]`) + 코드펜스 (extended) + strikethrough + tasklist
- Pandoc Markdown (<https://pandoc.org/MANUAL.html#pandocs-markdown>): CommonMark + 4 종 표 + 각주 + 정의 리스트 + 인라인 수학 — 가장 표현력 높음
- MyST (<https://myst-parser.readthedocs.io/>): CommonMark + Sphinx-style directives + 수학 + cross-ref — 학술 / Jupyter 친화
- IR 핵심 블록 ↔ 방언 호환 매트릭스:

  | IR 블록 | 출력 패턴 | CommonMark | GFM | Pandoc | MyST |
  |---|---|---|---|---|---|
  | `ParagraphBlock` | text | ✓ | ✓ | ✓ | ✓ |
  | `TableBlock` (단순) | `|a|b|` | ❌ | ✓ | ✓ | ✓ |
  | `TableBlock` (병합) | raw HTML inline | ⚠️ | ✓ | ✓ | ⚠️ |
  | `FootnoteBlock` | `[^N]` | ❌ | ✓ | ✓ | ✓ |
  | `FormulaBlock` | `$$...$$` | ❌ | ✓ (de-facto) | ✓ | ✓ |
  | `PictureBlock` | `![alt](uri)` | ✓ | ✓ | ✓ | ✓ |
  | `ListItemBlock` | `-` / `1.` | ✓ | ✓ | ✓ | ✓ |
- 클라이언트 호환 (사실상 표준 분모):
  - GitHub / Slack / Discord / Linear / Notion: GFM 직접 렌더
  - Anthropic / OpenAI 출력: GFM 호환 syntax 가 LLM 학습 분포에 다수
  - Pandoc / MyST: 별도 toolchain 필요

### 검증자 반박

- "Pandoc 이 가장 표현력 높은데 왜 안 채택?" → Pandoc 은 `pandoc` CLI 환경 의존 + 그 toolchain 외에서 lossy. 본 spec 의 1차 사용처 (RAG / MCP / GitHub 표시) 는 GFM 호환 환경 — Pandoc-only markup 은 RAG 호환 분모를 좁힘. GFM 출력을 사용자가 `pandoc -f gfm -t myst` 등으로 변환 가능 (downstream)
- "MyST 는 Sphinx / Jupyter 환경에 특화된 가치 있지 않나?" → 본 spec 의 1차 사용처는 RAG (LLM 입력) 이라 Sphinx / Jupyter 비호환 markup 불필요. MyST directive (`{note}`, `{admonition}`) 는 LLM 학습 분포 희박 — 가독성 저하 위험
- "GFM 의 math 확장이 표준 spec 에 없는데 `$$` 사용?" → GFM spec 자체는 math 미포함이지만 GitHub (2022 deploy, MathJax 백엔드) / Slack / Discord 등 주류 클라이언트가 `$$` 수식 syntax 를 렌더 (KaTeX / MathJax 양쪽 호환) — de-facto 표준. Pandoc / MyST 와도 syntax 호환 (`$$`) — 미래 방언 추가 시 기본 호환
- "CommonMark + GFM 표/각주 확장만 픽 vs full GFM?" → GFM 자체가 CommonMark superset + 확장 정의 — 픽업 범위 모호하면 spec 표현 일관성 흔들림. full GFM 채택이 표준 호환

### 최종 결정

**옵션 B — GFM**. 표·각주·코드펜스의 IR 핵심 구조 모두 표현 가능 + 가장 넓은 클라이언트 호환 + KaTeX 사실상 호환. Pandoc / MyST 추가는 영구 비목표 — 사용자가 GFM 출력을 외부 변환기로 처리.

### 1차 소스

- GFM spec: <https://github.github.com/gfm/>
- CommonMark spec: <https://spec.commonmark.org/>
- Pandoc Markdown 매뉴얼: <https://pandoc.org/MANUAL.html#pandocs-markdown>
- MyST 문서: <https://myst-parser.readthedocs.io/>
- GitHub LaTeX math 지원 (2022): <https://github.blog/news-insights/product-news/math-support-in-markdown/>
- HtmlRAG (구조 보존이 RAG 성능 향상에 기여, WWW 2025): <https://arxiv.org/abs/2411.02959>

## 3. 표 셀 병합 (rowspan/colspan) 표현 — HTML 인라인 폴백

### 팩트

- GFM Tables extension (<https://github.github.com/gfm/#tables-extension->): 모든 셀이 단일 행/열 (rowspan/colspan 미지원). pipe 문자 `|` 가 곧 행 구분자
- CommonMark HTML blocks (<https://spec.commonmark.org/0.30/#html-blocks>): raw HTML 인라인 허용 — block-level 또는 inline-level 모두
- IR `TableBlock` 3중 표현 (`python/rhwp/ir/nodes.py:550`):
  - `cells: list[TableCell]` — 프로그래매틱 접근 (병합 정보 포함)
  - `html: str` — `<table>` 인라인 형식, rowspan/colspan 보존 (RAG 주입용)
  - `text: str` — 단순 평문 (검색 / diff 폴백)
- 대안 spec:
  - Pandoc grid table: ASCII art (`+----+`) — visual 양호, parser 의존
  - markdown-it-py custom rules (`@mditable` 등): third-party 정의, 호환성 좁음
  - Markdown extension (`{rowspan=2}`): 사실상 표준 없음
- 동등 라이브러리:
  - Docling: 단순 표는 GFM, 병합 셀은 HTML inline (Docling `MarkdownExporter._export_table`)
  - Pandoc: `--from html --to gfm` 변환 시 HTML 그대로 보존

### 검증자 반박

- "병합 셀 표만 HTML 폴백 → 같은 출력에 표 두 형태가 공존, 사용자 혼란?" → 두 형태 모두 GFM 호환 (raw HTML inline 허용). LangChain / RAG 소비자도 두 형태 처리 가능. lossy 회피가 우선 — RAG quality 가 최종 KPI
- "표를 항상 HTML 로 통일하면 일관성 확보 아닌가?" → 단순 표 (모든 span=1) 는 GFM `|a|b|` 가 사람이 읽기 좋음 — 가독성 우위. lossy 위험 없는 단순 표는 native GFM
- "TableBlock.html 재사용 → escape 정책 / class 이름 / id 등이 view 출력 표준과 어긋날 위험?" → IR Rust 코어가 생성한 html 그대로 — 본 binding 내 단일 source. drift 위험 없음. 미래 spec 에서 html 재합성이 필요해지면 그때 분기 (YAGNI)
- "병합 셀 검출 비용?" → `any(cell.row_span > 1 or cell.col_span > 1 for cell in table.cells)` — `O(n_cells)`, 표 1개당 마이크로초

### 최종 결정

**옵션 B — HTML `<table>` 인라인 폴백 (병합 셀 있는 표만)**. 단순 표는 native GFM, 병합 셀은 `TableBlock.html` 그대로 재사용. lossy 회피 + 가독성 양립 + 코드 중복 0.

### 1차 소스

- GFM Tables extension: <https://github.github.com/gfm/#tables-extension->
- CommonMark HTML blocks: <https://spec.commonmark.org/0.30/#html-blocks>
- IR `TableBlock` 3중 표현: `python/rhwp/ir/nodes.py:550`
- Pandoc grid tables: <https://pandoc.org/MANUAL.html#extension-grid_tables>
- Docling table export: <https://github.com/docling-project/docling-core>

## 4. 이미지 처리 — placeholder only for v0.4.0

### 팩트

- IR `PictureBlock.image: ImageRef | None` (`python/rhwp/ir/nodes.py:286`)
- IR `ImageRef.uri` (`python/rhwp/ir/nodes.py:234`): v0.3.0 시점 항상 `bin://<bin_data_id>` 형식 — `data:` (embedded) / `file://` (external) 은 v0.4.0+ opt-in 으로 docstring 에 예고
- raw bytes 해석 경로: `Document.bytes_for_image(picture)` (`python/rhwp/document.py:150`) → Rust `_Document` 의 `bytes_for_image_id` 호출 → `bin_data_content` lookup
- IR `HwpDocument` 단독으로는 bin_data 접근 불가 — `_Document` 가 함께 살아있어야 함 (Document 폐기 후 IR 만 남으면 raw bytes 잃음 — by design, IR 직렬화 가능성 보장)
- 동등 라이브러리 패턴:
  - Pandoc: `--extract-media=DIR` — 외부 파일 추출, CLI 호출자가 dir 지정
  - Docling: `MarkdownExportOptions(image_mode="placeholder"|"embedded"|"referenced")` — 3 모드, 호출자가 base path 지정
- 로드맵 README narrative (활성 spec 인덱스 § v0.4.0): "이미지 처리: `Picture.ref_mode` 를 따름 (`placeholder` → `<img alt>`, `embedded` → base64 `src=`, `external` → 외부 파일 + 경로 반환)" — 3 모드 의도 (작성 시점 narrative)

### 검증자 반박

- "embedded 모드는 RAG 사용처에 따라 가치가 큰데 왜 v0.4.0 미제공?" → IR 메서드 위치 결정 (§1) 과 충돌. embedded 는 raw bytes resolution → `Document.bytes_for_image()` 의존 → IR 메서드가 Document 를 알아야 함 → 의존 방향 역전 + IR 직렬화 후 (Document 폐기) 호출 시 동작 모호. 별도 spec 에서 `Document.to_markdown_with_images()` wrapper 추가 (v0.5.0+)
- "external 모드는 file I/O 라 spec 의 의도와 맞지 않은가?" → external 은 호출자가 출력 디렉토리를 지정하는 IO side-effect. 본 spec 의 view 출력 (string return) 과 의미축 다름 — 영구 비목표
- "placeholder 만 제공하면 RAG 사용자가 실제 이미지를 못 보지 않나?" → RAG 사용처는 LLM 입력 텍스트가 1차. multimodal RAG (이미지 직접 LLM 입력) 도 alt-text + binary lookup 으로 충분 (사용자가 `Document.bytes_for_image()` 별도 호출). 1차 사용처 (텍스트 RAG) 와 매칭
- "로드맵 narrative 가 3 모드 의도를 명시했는데 spec 이 1 모드로 좁혀도 되나?" → narrative 는 미정 의도. 본 spec 작성 시점에 IR 메서드 위치와 충돌 발견 → 해결책으로 범위 축소. narrative 는 결정 사항이 아니라 작성 직전 상태 — spec 이 SSOT

### 최종 결정

**옵션 A — placeholder 만 (image_mode 인자 없음)**. PictureBlock 출력은 IR `picture.image.uri` (`bin://<id>`) 그대로 + alt-text (description). embedded / external 은 영구 비목표 — `Document` wrapper 위 별도 spec.

### 1차 소스

- IR `PictureBlock` / `ImageRef`: `python/rhwp/ir/nodes.py:234,286`
- `Document.bytes_for_image`: `python/rhwp/document.py:150`
- Pandoc `--extract-media`: <https://pandoc.org/MANUAL.html#option--extract-media>
- Docling export options: <https://github.com/docling-project/docling-core>

## 5. furniture 처리 — 각주/미주만 포함, 헤더/푸터 비포함

### 팩트

- IR `Furniture` 컨테이너 (`python/rhwp/ir/nodes.py:633`):
  - `page_headers: list[Block]`, `page_footers: list[Block]` — 페이지 단위
  - `footnotes: list[FootnoteBlock]`, `endnotes: list[EndnoteBlock]` — 본문 인용 단위
- `FootnoteBlock.marker_prov: Provenance` (`python/rhwp/ir/nodes.py:373`): 본문 인용 마커 위치 (`section_idx`, `para_idx`) — RAG 가 각주가 어디서 인용됐는지 역추적 가능
- 머리글/꼬리말은 페이지 단위 — 본문 paragraph 와 1:N 매핑 모호 (모든 본문 paragraph 가 헤더/푸터 아래에 있음). view 출력은 페이지 무관 단일 string — 페이지 경계 명시 안 함
- Markdown footnote 표준:
  - GFM: `[^1]` ref + `[^1]: definition` 정의 (<https://github.github.com/gfm/#extension-footnotes->)
  - CommonMark: 비표준 (Pandoc / kramdown 확장)
  - Pandoc: 동일 syntax (`[^1]`)
- HTML5 `<aside>` (<https://html.spec.whatwg.org/multipage/sections.html#the-aside-element>): 보조 정보 컨테이너
- 동등 라이브러리:
  - Pandoc: `--include-in-header=FILE` / `--include-before-body` — 사용자 명시 추가
  - Docling: `MarkdownExportOptions.include_page_breaks` 등 — 페이지 경계 옵션화
  - Word docx: 헤더/푸터를 별도 XML 영역에 보유, 본문 변환에 미포함이 기본

### 검증자 반박

- "헤더/푸터에 중요한 메타정보 (저자 / 날짜 / 페이지번호) 가 있을 수 있는데 비포함은 정보 손실 아닌가?" → 메타정보는 IR `DocumentMetadata` (title / author / creation_time, `python/rhwp/ir/nodes.py:157`) 에 별도 노출. 헤더/푸터 본문 (예: `"p. 5"`) 은 view 단일 string 에서 의미 약함. RAG 사용자가 메타정보 필요 시 IR 직접 접근 (`doc.to_ir().metadata`)
- "각주/미주 footnote 형식이 RAG 임베딩에 노이즈?" → footnote ref `[^N]` 는 LLM 이 인식 가능한 표준 패턴 (Anthropic / OpenAI 출력에 자주 등장). 본문 의미와 분리 보유로 RAG quality 우위 — `[^N]` 가 본문 의미를 흐리지 않음
- "미주 (endnote) 와 각주 (footnote) 를 같은 footnote 형식으로 통합하면 IR 분리가 무의미?" → 출력 string 에서는 두 종류 모두 `[^N]` 로 표현하되 number 공간 분리 (각주 1,2,3.../ 미주는 별도 prefix 예: `[^en1]` 또는 같은 number 공간에 위치만 분리). HTML 은 `<aside class="footnote">` / `<aside class="endnote">` class 차이로 보존 — IR 분리 의미 유지
- "marker_prov 의 char_offset 정확도가 v0.3.0 시점에 paragraph 단위만 (char offset 미정확)? 인라인 위치 정확하지 않을 수 있음" → paragraph 끝에 `[^N]` 삽입은 best-approximation. 정확 char offset 은 v0.4.0+ marker_prov 확장 검토. 본 spec 은 paragraph 단위로 동작 — 인용 추적 가능 + RAG 임베딩에 충분

### 최종 결정

**옵션 B — 각주/미주만 footnote 형식 출력, 헤더/푸터 비포함**. 본문 의미와의 1:N 매핑 명확성 (각주 ✓ / 헤더 ✗) + footnote 표준 표현 활용. 헤더/푸터는 사용자가 `iter_blocks(scope="furniture")` 로 별도 접근.

### 1차 소스

- IR `Furniture`: `python/rhwp/ir/nodes.py:633`
- IR `FootnoteBlock` / `EndnoteBlock`: `python/rhwp/ir/nodes.py:356,379`
- IR `DocumentMetadata`: `python/rhwp/ir/nodes.py:157`
- GFM footnote extension: <https://github.github.com/gfm/#extension-footnotes->
- HTML5 `<aside>` element: <https://html.spec.whatwg.org/multipage/sections.html#the-aside-element>

## 참조

- [roadmap/v0.4.0/view-renderer.md](../../roadmap/v0.4.0/view-renderer.md) — 본 리서치의 결정 요약
- HtmlRAG paper (구조 보존이 RAG 성능 향상에 기여, WWW 2025): <https://arxiv.org/abs/2411.02959>
- GFM spec: <https://github.github.com/gfm/>
- HTML5 spec: <https://html.spec.whatwg.org/>
- KaTeX supported syntax: <https://katex.org/docs/supported>
