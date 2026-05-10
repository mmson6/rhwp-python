---
status: Draft
description: "v0.6.0 — 페이지 PNG 렌더링 표면. 상류 'native-skia' 백엔드를 'Document.render_png' / 'export_png' 로 default 노출 + MCP 'render_page_png' 도구로 VLM 입력 시나리오 지원"
target: v0.6.0
last_updated: 2026-05-10
---

# v0.6.0 — 페이지 PNG 렌더링 (VLM 입력)

VLM (Vision Language Model — Claude / GPT-4V / Gemini 등) 이 1차 입력으로 받는 raster 이미지를 HWP/HWPX 페이지로부터 직접 생성하는 표면을 추가한다. 상류 `edwardkim/rhwp` v0.7.10 (현 submodule pin `62a458a`) 의 `SkiaLayerRenderer::render_raster_with_options` 를 노출하여 `Document.render_png(page) -> bytes` / `render_all_png()` / `export_png(out_dir)` 를 새로 추가하고, MCP 도구 `render_page_png` 를 통해 LLM 에이전트가 페이지 단위 시각 입력을 획득할 수 있게 한다. 추가만 있고 v0.5.x 의 SVG / PDF / IR / MCP 표면은 모두 보존 (additive only) — SchemaVersion `"1.1"` 그대로. PNG 표면은 default wheel 에 통합 (별도 extras 없음) — Cargo `native-skia` feature 가 항상 켜져 wheel 에 포함되므로 `pip install rhwp-python` 만으로 즉시 사용 가능.

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [png-vlm-render-research.md](../../design/v0.6.0/png-vlm-render-research.md).

## 배경 — 왜 v0.6.0 인가

v0.4.0 view 렌더러 (Markdown / HTML) 와 v0.5.0 MCP server 는 *텍스트* 표면을 LLM 에 노출했지만, 표 / 수식 / 그림 / 복잡 레이아웃의 시각 의미는 IR 평탄화 과정에서 소실된다. Vision-capable LLM (Claude 3.5+ Sonnet / GPT-4V / Gemini Pro Vision 등) 이 이미지 입력을 1차 시민으로 다루기 시작한 2024-2026 환경에서, 페이지를 raster image 로 렌더해 함께 보내면 텍스트 표면이 못 살리는 시각 정보를 보완 (예: 수식의 공간 배치, 표의 셀 병합, 레이아웃 박스 — 이미 IR 의 `TableCell.role="layout"` 표시가 같은 동기) 할 수 있다.

상류 `edwardkim/rhwp` v0.7.10 GA 가 외부 기여자 PR 머지로 `native-skia` feature 기반 raster pipeline (`SkiaLayerRenderer::render_raster_with_options` — PR #599 PNG 게이트웨이) 을 도입했고, 본 binding 의 v0.5.0 MCP server 가 이미 LLM 에이전트 분모를 확보한 상태다. v0.6.0 는 두 줄기를 잇는 minor — 상류 raster API → Python `Document.render_png` → MCP `render_page_png` 도구.

## 결정 사항

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — Renderer 백엔드 | 상류 `native-skia` Cargo feature 항상 활성화 (default 통합). `external/rhwp` submodule pin 변경 0, `Cargo.toml` 의 `rhwp` dependency 에 `features = ["native-skia"]` 추가 — 모든 wheel 에 포함 | PR #599 PNG 게이트웨이가 이 feature 게이트 안에 있어 활성화 외 선택지 없음. PyPI single-package 모델은 wheel 분리를 지원하지 않아 어차피 모든 사용자가 통합 wheel 다운로드 — extras 분리 신호는 cosmetic. skia-safe binary-cache 약 30 MB 추가 비용은 PNG 미사용자에게도 부과되지만, 이 비용을 진짜로 회피하려면 별도 PyPI 패키지 (옵션 C) 가 필요한데 영구 sync 부담이 더 큼. ADR § 1 |
| 2 — Python API 시그니처 | `Document.render_png(page, *, scale=1.0, dpi=None, max_pixels=...) -> bytes` / `render_all_png() -> list[bytes]` / `export_png(out_dir, *, prefix=None) -> list[str]` — SVG / PDF API 1:1 mirror | `render_svg` / `render_pdf` 의 호출 패턴이 사용자 학습 비용 0. `RasterRenderOptions` 의 7 필드 (dpi / scale / max_dimension / max_pixels / format / background_color / transparent / color_space) 중 1차로 dpi / scale / max_pixels 만 노출, 나머지는 demand-driven. ADR § 2 |
| 3 — 출력 코덱 | PNG 만 — JPEG / WebP / AVIF / HEIC 미노출 | 상류 skia raster 가 `RasterOutputFormat::Png` 만 구현 (다른 format 은 명시적 거부 — `"Skia raster renderer currently supports PNG output"` 에러). VLM 1차 호환 코덱 (Anthropic Vision API / OpenAI Vision / Google Gemini 모두 PNG 1st-tier) 충분. ADR § 3 |
| 4 — 배포 형태 | default 통합 (별도 extras 없음). `pip install rhwp-python` 만으로 render_png 사용 가능. Pillow 는 *사용자 측 후처리* (dimension 검증 / 픽셀 조사 / VLM 입력 전 resize) 가 필요할 때 직접 install — render_png 자체는 native skia 단독으로 PNG bytes 반환 | extras 분리는 wheel 이 통합 빌드되는 마당에 cosmetic 한 시그널만의 역할 — 사용자 학습 비용은 늘리고 진짜 비용 회피는 못 함. cli / mcp / langchain 처럼 *런타임 Python 의존성이 있는* extras 와 달리 PNG 표면은 native binary 단독으로 작동하므로 분리할 의미가 없다. ADR § 1 |
| 5 — MCP 도구 | `render_page_png(path, page, *, scale=1.0, max_pixels=...) -> ImageContent` 신규. fastmcp v3 `ImageContent` 표준 (base64-encoded data + `mime="image/png"`) — Anthropic / OpenAI MCP client 가 이미지 입력을 LLM 에 직접 전달 가능 | fastmcp v3.2.4 docs § Tool Result Types 가 `ImageContent` 를 LLM 에이전트 시각 입력 1st-tier 패턴으로 명시. `bytes` 반환 후 클라이언트 측 base64 변환 거부 — wire format 이 비결정 dict 가 됨. ADR § 4 |
| 6 — GIL 해제 정책 | `render_png` / `render_all_png` / `export_png` 모두 `py.detach` 안에서 skia raster 실행 — 평균 ≥ 50 ms / 페이지 (IO + 합성 + 인코딩) 으로 [CLAUDE.md](../../../CLAUDE.md) § "GIL release via `py.detach`" 의 ≥ 1 ms 임계 충족 | 이미 `render_pdf` / `export_pdf` 가 같은 패턴 (svgs_to_pdf 가 owned `Vec<String>` → py.detach). PNG 도 owned `Vec<u8>` 반환이라 `Send + 'static` 보장. unsendable `_Document` 는 closure 안에서 미사용 (page index 만 캡처) |
| 7 — 비동기 표면 | `arender_png(path, page, *, ...) -> bytes` 모듈-level async 함수 — `aparse` 의 패턴 (file IO 만 thread offload, render 는 호출 스레드 sync) 답습. `Document.arender_png()` 인스턴스 메서드 미제공 ([CLAUDE.md](../../../CLAUDE.md) § "Async direction" — unsendable `_Document` 는 thread 경계 위반 시 panic) | `aparse` (v0.2.0) / `aload` / `alazy_load` (v0.3.0) 와 동일 패턴 — 외부 의존성 0 (stdlib `asyncio.to_thread`). render 는 GIL 해제 구간에서 충분히 빠름. demand 가 확인된 후 async batch (`arender_all_png`) 추가 검토 |
| 8 — 기본 max_pixels 한계 | 상류 default 값 그대로 (DoS 방어용 픽셀 상한) 노출 + 사용자가 명시 지정 시 override. 초과 시 `ValueError("raster pixel count out of range")` 그대로 전파 | 상류 `RasterRenderOptions::default()` 의 max_pixels 는 약 2_000 × 2_000 = 4_000_000 (확인 필요 — ADR § 5). 본 PATCH 가 self-DoS 방어 옵션을 추가 정의하지 않고 상류 가드 그대로 노출 — 동일 invariant SSOT 단일화. ADR § 5 |

## 인수조건

- **AC-1** — `aift.hwp` (HWP5 fixture) 의 page 0 → `bytes` 반환값의 첫 8 byte 가 PNG magic (`b"\x89PNG\r\n\x1a\n"`) 일치
- **AC-2** — 동일 fixture 의 `Document.render_all_png()` 결과 길이 == `Document.page_count` (페이지 수 invariant)
- **AC-3** — `Document.render_png(0, scale=2.0)` 결과의 픽셀 너비 ≈ `Document.render_png(0, scale=1.0)` 결과의 2배 (image lib 디코드 후 검증 — 상류 raster_dimension 의 `value * scale` 산식 회귀 가드)
- **AC-4** — `Document.render_png(0, max_pixels=1)` 호출이 `ValueError` (메시지에 `"pixel count out of range"` 포함) 로 fail — 상류 raster_dimension 의 max_pixels 가드 wire-through 검증
- **AC-5** — MCP `render_page_png(path, 0)` 도구 호출이 fastmcp `ImageContent` 인스턴스 반환 (속성 `mime_type == "image/png"`, `data` 가 base64-decoded PNG magic 일치). `outputSchema` 에 `ImageContent` `$ref` 노출
- **AC-6** — `arender_png(path, 0)` async 호출이 정상 PNG bytes 반환. `_Document` 인스턴스가 thread 경계를 넘지 않음 — `aparse` + sync `render_png` 구성 검증 (panic 미발생)
- **AC-7** — `Document.export_png(out_dir)` 가 `Document.page_count` 만큼 파일 생성, 각 파일 첫 8 byte PNG magic 일치, 반환 경로 리스트 길이 == 파일 수
- **AC-8** — `Document.render_pdf` / `render_svg` / `to_ir` 등 v0.5.x 표면의 모든 기존 회귀 가드가 그대로 통과 (additive 보장)
- **AC-9** — README 에 `## 페이지 PNG 렌더링 (`render_png`)` 섹션 신설 — VLM 입력 사용 예 (Anthropic Vision API 호출 코드 1 블록), 상류 native-skia 의존성 안내. MCP 도구 표 갱신 (`render_page_png` 1행 추가)

## 영구 비목표

- **JPEG / WebP / AVIF / HEIC 출력** — 상류 skia 가 `RasterOutputFormat::Png` 만 구현 (`Skia raster renderer currently supports PNG output` 에러로 다른 format 명시 거부). 우리 측 추가 코덱은 상류 PR 선행 후에만 — demand-driven 보류
- **폰트 임베딩 / 디버그 오버레이 / 페이지 메타 옵션** — 상류 SVG CLI 에는 `--embed-fonts` / `--debug-overlay` / `--show-control-codes` 가 있으나 raster pipeline 에는 미반영. raster 출력은 픽셀 픽스 구조라 폰트 임베딩 의미 없음, 디버그 오버레이는 별도 spec 검토
- **HWP3 raster 렌더링** — 상류 HWP3 파서 미완 (`src/parser/hwp3/` 가 IR 미완성). v1.0+ writeback 트랙과 직교, 본 spec 범위 밖
- **Annotation / OCR overlay** — 본 spec 은 *원문 페이지 시각 입력* 표면. OCR / 텍스트 좌표 오버레이는 별도 도메인 (RAG 응답 정확도 검증 등 별도 spec)
- **사용자 정의 폰트 경로 (`with_font_paths`) 노출** — 상류 SkiaLayerRenderer 가 지원하나 `external/rhwp` 의 ttfs 디렉토리 + 시스템 폰트 fallback 으로 1차 충분. demand 신호 (한컴 전용 폰트 미렌더링 이슈) 시 별도 PATCH 검토
- **In-process 폰트 / 색공간 / 투명 배경 사용자 옵션** — `RasterRenderOptions` 의 7 필드 중 1차로 `dpi` / `scale` / `max_pixels` 만 노출. `background_color` / `transparent` / `color_space` 는 demand-driven (대부분 use case 가 화이트 불투명 PNG)
- **WASM target PNG 렌더링** — 상류 skia 가 native target 전용 (`#[cfg(all(not(target_arch = "wasm32"), feature = "native-skia"))]`). 본 binding 은 native wheel 만 빌드 — WASM 직교

## 다른 산출물의 파급 (코드 / 데이터)

- `Cargo.toml` — `rhwp = { path = "external/rhwp" }` → `rhwp = { path = "external/rhwp", features = ["native-skia"] }`. PNG 는 default wheel 통합이라 별도 `[features]` 마커 불필요
- `src/document.rs` — `fn render_png<'py>(&self, py, page, scale, dpi, max_pixels) -> PyResult<Bound<'py, PyBytes>>`, `fn render_all_png`, `fn export_png` 신규 (PDF API mirror). `py.detach` 패턴
- `python/rhwp/document.py` — `render_png` / `render_all_png` / `export_png` wrapper 메서드 + docstring. `arender_png` 모듈-level async 함수
- `python/rhwp/_rhwp.pyi` — 새 메서드 stub
- `python/rhwp/__init__.pyi` + `__init__.py` — `arender_png` re-export
- `python/rhwp/mcp/tools.py` — `render_page_png(path, page, *, scale, max_pixels) -> ImageContent` 신규. v0.5.0 의 7 도구 → 8 도구
- `pyproject.toml` — extras 추가 없음. `testing` dependency-group 에 Pillow 추가 (AC-3 dimension 검증). `[project.optional-dependencies]` 의 다른 extras 는 변경 0
- `external/rhwp/` 서브모듈 — pin 변경 가능성 (v0.7.10 → v0.7.11 등 — `RasterRenderOptions` API 안정성 확인 후 결정). 본 spec 시점 `62a458a` (v0.7.10) 그대로 유지 시도
- `tests/test_render_png.py` 신규 — AC-1 ~ AC-7 검증 (Pillow 디코드는 testing 그룹의 Pillow 사용)
- `README.md` § 페이지 PNG 렌더링 신설 + MCP 도구 표 1행 추가
- `CHANGELOG.md` — `[0.6.0]` 섹션 — Added (3 메서드 + 1 MCP 도구), Build (Cargo features + skia-safe 의존성), Notes (VLM 입력 시나리오 사용 예)

문서 cross-link (`docs/roadmap/README.md` 인덱스) 는 [CONVENTIONS.md](../../CONVENTIONS.md) § Cross-link 방향성 규칙 에 따라 본 spec 본문에서 다루지 않음 — 인덱스는 `roadmap/README.md` (Living) 가 SSOT.

## 미확정 이슈

- **상류 `RasterRenderOptions::default()` 의 max_pixels 값 (확정)** — `external/rhwp/src/renderer/layer_renderer.rs:28` 의 `Default::default` 확인: `max_pixels: 67_108_864` (= 8192 × 8192), `max_dimension: 16_384`. decision 8 의 fact 보강 완료
- **skia-safe 빌드 시간 / wheel 크기 영향** — CI 빌드 시간 + GitHub Actions wheel artifact 크기 측정 필요. 임계 (예: wheel 크기 > 100 MB) 초과 시 별도 PyPI 패키지 (`rhwp-png`) 분리 검토 — 본 spec 시점 default 통합 (옵션 B → β 단순화)
- **abi3-py310 호환성** — skia-safe 가 abi3 호환 가정 검증 필요. abi3 미호환 시 PNG 전용 wheel 만 Python-version-specific (`cp310-cp313`) 분리 빌드 (별도 PyPI 패키지로 위임)
- **MCP `ImageContent` 의 LLM 클라이언트 호환성** — Claude Desktop / Cline / Cursor / Continue.dev / Goose 의 ImageContent 응답 처리 검증 필요 (transport 별 base64 인코딩 안정성). v0.5.0 의 클라이언트 호환성 표 (text-only 응답 기준) 의 image 컬럼 추가
- **stdio MCP transport 의 base64 페이로드 크기** — A4 페이지 PNG 가 약 100-500 KB → base64 약 130-660 KB. stdio JSON-RPC 메시지 크기 제한 (서버별 상이) 충돌 가능성. streamable-http 권장 검토

## 참조

- 짝 페어 (ADR): [png-vlm-render-research.md](../../design/v0.6.0/png-vlm-render-research.md)
- 상류 `edwardkim/rhwp` PR #599 (PNG 게이트웨이): <https://github.com/edwardkim/rhwp/pull/599>
- 상류 `SkiaLayerRenderer::render_raster_with_options`: `external/rhwp/src/renderer/skia/renderer.rs:66`
- 상류 `RasterRenderOptions` SSOT: `external/rhwp/src/renderer/layer_renderer.rs`
- fastmcp v3 `ImageContent` 표준: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- Anthropic Vision API (이미지 입력 사양): <https://docs.anthropic.com/en/docs/build-with-claude/vision>
- v0.5.0 MCP server (선행 spec): 활성 spec 인덱스 [roadmap/README.md](../README.md)
- 글로벌 GIL release 정책: [CLAUDE.md](../../../CLAUDE.md) § "GIL release via py.detach"
- 글로벌 async direction 정책: [CLAUDE.md](../../../CLAUDE.md) § "Async direction"
