---
status: Frozen
description: "v0.4.0 구현 로그 — IR view 렌더러 (Markdown / HTML). 'HwpDocument.to_markdown()' / 'to_html()' 메서드 추가, schema / 파싱 경로 변경 0"
ga: v0.4.0
last_updated: 2026-05-05
---

# v0.4.0 — IR view 렌더러 (Markdown / HTML) 구현 로그

[v0.4.0/view-renderer](../../roadmap/v0.4.0/view-renderer.md) (spec) +
[design/v0.4.0/view-renderer-research](../../design/v0.4.0/view-renderer-research.md)
(ADR) 의 구현 결과 로그. 결정의 근거·옵션 비교는 ADR 가 보유 — 본 문서는
*산출물 / 검증 결과 / 호환성 / 이월 사항* 만 기록한다 (CONVENTIONS § CHANGELOG
↔ implementation log 역할 분리).

MINOR release. 단일 세션 규모 (1 모듈 신설 + 메서드 위임 2개 + 테스트 3 파일)
로 단일 `migration.md` 채택 — Rust 변경 0 / schema 변경 0 / mapper 변경 0 인
순수 view 변환 layer 라 v0.3.0 식 stage 분할 (4 단계) 이 과합. 단일 PR 안에서
A→B→C→D 인터널 segment 로 진행했으나 stage 파일 분할은 안 함.

## 1. 산출물

### Python 신규 모듈

| 파일 | LOC | 책임 |
|---|---|---|
| [python/rhwp/ir/_view.py](../../../python/rhwp/ir/_view.py) | ~310 | `render_markdown(doc)` / `render_html(doc, *, include_css)` SSOT — block-type 별 dispatch (paragraph / list / table / picture / formula / caption / toc / field), `_FootnoteIndex` 본문 paragraph ↔ 인용 마커 매핑 헬퍼 |

### Python 기존 모듈 편집

| 파일 | 변경 |
|---|---|
| [python/rhwp/ir/nodes.py](../../../python/rhwp/ir/nodes.py) | `HwpDocument.to_markdown(self) -> str` / `to_html(self, *, include_css: bool = False) -> str` 메서드 추가. 본체는 `from rhwp.ir._view import render_markdown` deferred import 위임 (cycle 회피). schema / 기존 필드 / `iter_blocks` / 모델 정의 변경 0 — 메서드 추가는 Pydantic JSON serialization 무관, `schema_version "1.1"` 유지 |

신규 메서드는 Pydantic `BaseModel` 의 method 추가가 schema 영향 없음을 활용한
[패턴 1](https://docs.pydantic.dev/latest/concepts/models/#frozen) — `frozen=True`
는 field 변경만 차단, method 정의 무관.

### 테스트 신규

| 파일 | 테스트 수 | 커버 AC |
|---|---|---|
| [tests/test_view_markdown.py](../../../tests/test_view_markdown.py) | 24 | AC-1 / AC-3 / AC-5 / AC-6 / AC-7 / AC-8 / AC-10 + level indent 회귀 |
| [tests/test_view_html.py](../../../tests/test_view_html.py) | 27 | AC-2 / AC-4 / AC-5 / AC-6 / AC-7 / AC-8 / AC-9 / AC-10 + list grouping + level data-attr |
| [tests/test_view_baseline.py](../../../tests/test_view_baseline.py) | 2 | AC-11 (회귀 가드) |
| [tests/baselines/v0_3_2_aift_ir.json](../../../tests/baselines/v0_3_2_aift_ir.json) | n/a | v0.3.2 GA `Document.to_ir()` 캡처 (`exclude={"source"}`, 4.3 MB) |
| [tests/baselines/v0_3_2_table_vpos_01_ir.json](../../../tests/baselines/v0_3_2_table_vpos_01_ir.json) | n/a | v0.3.2 GA `Document.to_ir()` 캡처 (130 KB) |

`pytest.mark.spec("v0.4.0/view-renderer#AC-N")` marker 부여 — 발효일 (2026-04-29)
이후 신규 spec 정책 (CONVENTIONS § Trace report). file-level `pytestmark` +
함수별 추가 marker 누적.

### CI

| 파일 | 변경 |
|---|---|
| [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) | scoped pyright 목록에 `tests/test_view_markdown.py` / `test_view_html.py` / `test_view_baseline.py` 3 파일 추가. `test-without-extras` 4-skip 룰은 본 PR 영향 없음 — 신규 파일 모두 stdlib 만 의존, 어떤 importorskip 도 추가하지 않음 |

## 2. 결정 사항 (spec 결정 9 항목 ↔ 구현 매핑)

| spec 결정 | 구현 위치 |
|---|---|
| 1 — API placement (`HwpDocument` 메서드) | `nodes.py:HwpDocument.to_markdown` / `.to_html` (deferred import 위임) |
| 2 — GFM 방언 | `_view.py:render_markdown` + `_md_*` dispatch helpers |
| 3 — 완전 HTML5 | `_view.py:render_html` 의 `<!DOCTYPE html>` + `<html>` + `<head>` + `<body>` 5-라인 wrapper |
| 4 — `include_css: bool = False` | `_view.py:render_html` 의 `head_parts` 분기 + `_DEFAULT_CSS` (단일 `<style>`) |
| 5 — 표 셀 병합 폴백 | `_view.py:_md_table` 의 `any(c.row_span > 1 or c.col_span > 1 ...)` 분기, 병합 셀 → `block.html` 그대로 inline |
| 6 — 이미지 placeholder | `_view.py:_md_picture` / `_html_picture` — `picture.image.uri` pass-through, alt 는 `description` |
| 7 — 수식 표현 | `_view.py:_md_formula` / `_html_formula` 의 `script_kind` × `inline` 분기 — `latex` display 는 `<div class="math">$$...$$</div>` (HTML), `hwp_eq` 는 `<pre><code class="language-hwp-eq">` (HTML) / fenced (Markdown) |
| 8 — furniture (각주/미주만) | `_FootnoteIndex` 가 `marker_prov.(section_idx, para_idx)` 로 본문 paragraph 매핑, `_md_paragraph` / `_html_paragraph` 가 paragraph-end append. `page_headers` / `page_footers` 는 양쪽 진입점에서 미참조 |
| 9 — additive only | nodes.py 메서드 추가 외 schema / 파싱 / 매퍼 / Document wrapper / extras 모두 변경 0. `tests/test_view_baseline.py` 가 AC-11 회귀 가드 |

## 3. 인터널 segment 진행 (단일 PR 안)

| Segment | 범위 | 시점 |
|---|---|---|
| A | `_view.py` skeleton + `nodes.py` 메서드 위임 + paragraph / list / field / caption / toc / unknown dispatch | 첫 commit |
| B | `TableBlock` (span 분기 → GFM vs `TableBlock.html` 인라인) + `PictureBlock` + `FormulaBlock` | 같은 commit |
| C | `FootnoteBlock` / `EndnoteBlock` (본문 ref + 끝 정의 / `<sup>` ref + `<aside>` 정의) + 헤더/푸터 제외 + `include_css=True` `<style>` 1회 | 같은 commit |
| D | baseline 캡처 + AC-11 회귀 가드 | 같은 commit |

## 4. 호환성

| 시나리오 | 결과 |
|---|---|
| 기존 `HwpDocument` consumer (Pydantic field 접근, `iter_blocks`, `model_dump`, `model_dump_json`) | 그대로 작동. 메서드 추가는 schema 영향 없음 — JSON 직렬화 / 검증 / hash 동일 |
| `Document.to_ir()` 캐시 (`OnceCell`) | 그대로. 같은 `HwpDocument` 인스턴스 재사용 — `to_markdown` / `to_html` 호출이 IR 인스턴스를 변경하지 않아 (frozen=True 정합) `model_dump_json` byte-equal |
| Schema validator (`hwp_ir_v1.json`) | 변경 없음. `schema_version "1.1"` 유지 |
| JSON serialization round-trip | 그대로. baseline diff 0 (AC-11) |
| API surface diff | additive — `to_markdown` / `to_html` 신규 2개 메서드, 기존 메서드 / 함수 / 타입 / extras 변경 0 |
| Wheel 크기 | `_view.py` 약 8 KB 추가. extras 변경 0 (pure stdlib `html.escape` 만 사용) |

**SemVer**: MINOR (0.3.2 → 0.4.0). 신규 capability 추가 + breaking change 0 +
schema 미변경. 외부 소비자 입장에서 신규 메서드 1쌍이 노출될 뿐.

## 5. 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest -m "not slow"` (전체) | **531 passed**, 2 pre-existing skipped (aift fixture 의 미주/수식 부재), 5 deselected (slow). 신규 view 테스트 53 모두 green |
| `uv run pytest tests/test_view_markdown.py tests/test_view_html.py tests/test_view_baseline.py -v` | 53 passed |
| `uv run pyright python/rhwp/ir/_view.py python/rhwp/ir/nodes.py tests/test_view_*.py tests/test_view_baseline.py` | 0 errors |
| `uv run pyright tests/type_check_errors.py` | 4 intentional errors (CI 검증 통과 — 본 PR 영향 없음) |
| `uv run ruff check python/rhwp/ir/_view.py tests/test_view_*.py tests/test_view_baseline.py` | clean |
| AC-11 baseline regression | aift / table-vpos 둘 다 byte-equal (source.uri 제외) |
| `cargo` 변경 | **0** — Rust 빌드 트리거 없음, maturin develop 재빌드 불필요 |

### AC ↔ 테스트 매핑

| AC | 테스트 (Markdown 면) | 테스트 (HTML 면) |
|---|---|---|
| AC-1 | 7 (paragraph 분리 + 빈 doc + fixture 구조 패턴 — footnote ref/def 매칭, 표 행 일관성, 코드펜스 닫힘 + picture description `[`/`]` escape 회귀) | — |
| AC-2 | — | 4 (DOCTYPE + 빈 doc + fixture well-formed + escape) |
| AC-3 | 2 (단순 표 → GFM, 병합 셀 → HTML 인라인) | — |
| AC-4 | — | 2 (synthetic + fixture `TableBlock.html` substring) |
| AC-5 | 4 (image+desc / image=None / fixture base64 부재 + bracket escape) | 3 (img+desc / img=None / fixture base64 부재) |
| AC-6 | 4 (latex display / latex inline / hwp_eq fenced / **mathml fenced**) | 4 (latex `<div class="math">` / latex inline `<span class="math">` / hwp_eq `<pre><code>` / **mathml `<pre><code>`**) |
| AC-7 | 3 (footnote `[^N]` / endnote `[^enN]` / 공존) | 3 (footnote `<aside id="fn-N">` / endnote `<aside id="en-N">` / **공존 + 출고 순서**) |
| AC-8 | 2 (synthetic + fixture 누설 없음) | 2 (synthetic + **fixture 누설 없음**) |
| AC-9 | — | 3 (default 0 `<style>` / `include_css=True` 1 `<style>` / fixture well-formed) |
| AC-10 | 2 (idempotency byte-equal + 비-mutation) | 2 (idempotency / include_css 분기 differ) |
| AC-11 | (baseline 파일에서) | (baseline 파일에서) |
| (bonus) | level indent | list grouping (`<ul>`/`<ol>` 그룹화, kind 변경 분리) + **level `data-level` attribute** |

AC-1 은 GFM round-trip parser 도입 없이 stdlib 정규식 + 구조 패턴으로 충족 —
신규 dep 0 정책 (결정 9 + spec 인트로 "신규 extras 도입 없음") 준수. AC-2 는
stdlib `html.parser.HTMLParser` 기반 stack-balance 검증으로 lxml 등 외부 dep
도입 없이 충족.

## 6. 이월 사항

다음 항목은 v0.4.0 범위 밖. spec § 영구 비목표 가 정확한 목록 — 본 절은
*v0.4.0 작업 중 후속 spec 후보로 표면화된 항목* 만 추림.

| 항목 | 후속 |
|---|---|
| 인라인 서식 (`InlineRun.bold` / `italic` / `strikethrough` / `href`) Markdown/HTML 매핑 | spec 결정 사항 미명시. 현 구현은 `ParagraphBlock.text` 평문만 사용. RAG 품질 향상 가치는 있으나 별도 spec 으로 결정 9 (additive only, 기존 결정 미변경) 분리 |
| HTML5 정식 nested list (`<ul><li><ul>...`) 재구성 | 현 v0.4.0 은 평면 `<ul>` + `data-level="N"` attribute 로 정보 보존. 정식 nesting 은 stack-based reconstruction 필요 — 별도 spec |
| `script_kind="mathml"` spec 결정 본문 명시 | 현재 `_view.py` 에 forward-compat 분기로 fenced block 출고 (Markdown ` ```mathml ` / HTML `<pre><code class="language-mathml">`). spec 결정 7 본문에 정식화 가능 |
| `marker_prov.char_start` 활용한 인라인 위치 정확 삽입 | ADR §5: paragraph 단위 best-approximation 채택. v0.3.1 부터 char_start 가 흘러오므로 기술적 가능. 별도 spec 에서 inline-position 모드 추가 검토 |
| `PictureBlock.caption` (CaptionBlock) 의 view 출력 | spec 결정 사항 미명시. 현 구현은 caption block body 단독 등장 시 평문 폴백만. picture parent 와 1:1 부착 케이스의 view 표현 (예: `<figure>` + `<figcaption>`) 은 별도 spec |
| `Document` wrapper 의 `to_markdown_with_images(image_mode=...)` | spec § 영구 비목표 (결정 6 ADR §4). embedded / external 모드는 raw bytes resolution 의존 — `Document` 책임으로 분리 |
| Pandoc / MyST 방언 옵션 | spec § 영구 비목표 (결정 2). GFM 출력을 외부 변환기로 처리 |
| HTML fragment 모드 (full document 아님) | spec § 영구 비목표 (결정 3). 사용자가 `lxml.html.fromstring(doc.to_html()).body` 또는 `TableBlock.html` 직접 합성 |

## 7. 참조

### 짝 페어

- spec: [docs/roadmap/v0.4.0/view-renderer.md](../../roadmap/v0.4.0/view-renderer.md)
- ADR: [docs/design/v0.4.0/view-renderer-research.md](../../design/v0.4.0/view-renderer-research.md)

### 외부

- HtmlRAG (구조 보존이 RAG 성능 향상에 기여, WWW 2025): <https://arxiv.org/abs/2411.02959>
- GFM spec: <https://github.github.com/gfm/>
- HTML5 spec: <https://html.spec.whatwg.org/>
- KaTeX supported syntax: <https://katex.org/docs/supported>

### 상류

본 v0.4.0 은 상류 (`edwardkim/rhwp`) 변경 0 — pure Python view layer.
`external/rhwp` submodule pin (`0fb3e67`) 그대로.
