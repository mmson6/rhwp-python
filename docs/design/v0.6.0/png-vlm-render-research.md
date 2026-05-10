---
status: Frozen
description: "v0.6.0 png-vlm-render ADR — 'native-skia' feature 활성화 / API mirror / PNG-only 코덱 / MCP 'ImageContent' 채택 / max_pixels 가드 SSOT 결정 근거"
ga: v0.6.0
last_updated: 2026-05-10
---

# v0.6.0 png-vlm-render — 설계 의사결정 리서치 요약

[v0.6.0/png-vlm-render.md](../../roadmap/v0.6.0/png-vlm-render.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 5건 (`native-skia` feature 활성화 + 배포 형태 · Python API 시그니처 · PNG-only 코덱 · MCP `ImageContent` 출력 · max_pixels 가드 SSOT) 의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | native-skia 활성화 + 배포 형태 | A: default 통합 (모든 wheel 에 native-skia, extras 없음) / B: `[png]` extras 분리 (Python-side 마커 + Pillow 의존성) / C: 별도 PyPI 패키지 (`rhwp-png`) | **A** | PyPI single-package 모델은 wheel 분리를 지원하지 않아 옵션 B 의 extras 도 어차피 통합 wheel 다운로드 — 분리 신호는 cosmetic. render_png 자체는 native skia 단독으로 작동하므로 Python 런타임 의존성 0 → cli / mcp / langchain 의 *런타임 Python 의존성 분리* 패턴과 본질이 다름. 사용자 학습 비용 최소화 |
| 2 | Python API 시그니처 | A: SVG/PDF API mirror (`render_png` / `render_all_png` / `export_png`) / B: 새 `RenderOptions` dataclass 인자 통일 / C: kwargs-only 단일 `render` dispatcher | **A** | v0.1.0 부터 SVG / PDF 가 같은 3-메서드 패턴, 사용자 학습 비용 0. `RasterRenderOptions` 7 필드 중 1차 3개만 노출 — demand-driven 확장 |
| 3 | 출력 코덱 | A: PNG 만 / B: PNG + JPEG / C: 사용자 지정 format enum | **A** | 상류 skia 가 `RasterOutputFormat::Png` 만 구현, 다른 format 은 명시적 거부. VLM 1차 호환 코덱 (Claude / GPT-4V / Gemini Vision 모두 PNG 1st-tier). 추가 코덱은 상류 PR 선행 후 |
| 4 | MCP 출력 인코딩 | A: `bytes` 반환 (fastmcp 자동 처리) / B: `ImageContent(data=base64, mime="image/png")` / C: `file://path` URI 반환 | **B** | fastmcp v3 docs 가 `ImageContent` 를 LLM 시각 입력 1st-tier 패턴으로 명시. Anthropic / OpenAI MCP client 가 image content 를 LLM 메시지에 직접 wire — base64 변환을 클라이언트에 맡기지 않음 |
| 5 | max_pixels 가드 SSOT | A: 상류 `RasterRenderOptions::default()` 그대로 노출 / B: Python 측 별도 default 정의 / C: 가드 미노출 (사용자 책임) | **A** | DoS 방어 invariant 가 두 곳에 있으면 drift 위험. 상류 가드를 그대로 wire-through 하고 사용자 override 만 허용 — invariant SSOT 단일화 |

---

## 1. native-skia 활성화 + 배포 형태

### 팩트

- 상류 `external/rhwp/Cargo.toml` 의 `[features]` 에 `native-skia = ["dep:skia-safe"]` 정의 — opt-in feature flag (default 미포함)
- `skia-safe` v0.93.1 이 `binary-cache` + `embed-icudtl` features 로 빌드되며 약 30 MB pre-built binary 다운로드 + `pdf` + `textlayout` features 활성화 (상류 Cargo.toml line 53)
- 상류 SVG / PDF 렌더 경로는 native-skia 무관 (`svg2pdf` + `usvg` + `pdf-writer` + `subsetter` + `ttf-parser` 만 사용 — line 49-52). SVG / PDF 만 사용하는 사용자에겐 skia 불필요
- abi3-py310 single wheel 정책 (`Cargo.toml` line 45 `pyo3 = { ..., features = ["abi3-py310"] }`) — 모든 Python 3.10+ 버전을 한 wheel 로 커버
- 본 프로젝트 기존 extras 패턴: `[langchain]` / `[cli]` / `[cli-chunks]` / `[mcp]` / `[mcp-chunks]` / `[examples]` — Python-side runtime 의존성만 분리, native 코드는 통합 wheel
- PyPI 의 single project 당 wheel 크기 제약: 소프트 한계 100 MB / 파일, 1 GB / 릴리즈 (PyPI Trusted Publisher 가 강제)

### 검증자 반박

- "extras 분리 (옵션 B) 가 cli / mcp / langchain 패턴과 정합 아닌가?" → 본질이 다름. cli / mcp / langchain 은 *런타임 Python 패키지* (typer / fastmcp / langchain-core) 의존성 분리 — extras 미선택 시 진짜 의존성 그래프에서 빠지고 친절 ImportError 가 *진짜* 발동한다. 반면 PNG 표면은 native skia binary 만으로 작동하므로 Python 런타임 의존성이 0 — extras 가 추가할 것이 없다. Pillow 를 끼워 넣어 *인위적* 으로 의존성을 만들 수는 있으나 (옵션 B 의 시도) , render_png 자체는 Pillow 없이도 PNG bytes 반환이 가능 → 가드는 사실 *과도한 강제*
- "별도 PyPI 패키지 `rhwp-png` 분리 (옵션 C) 가 wheel 크기 회피에 진짜 유리하지 않나?" → 두 패키지 동시 유지보수 부담 + version sync 의무 (`rhwp-python==0.6.0` ↔ `rhwp-png==0.6.0` 정합) + 사용자가 `pip install rhwp-png` 시 `rhwp-python` 도 같이 가져가야 하는 의존 그래프. PNG 가 미래 진짜 분리할 가치가 생기면 (skia-safe 빌드 비용이 임계 초과 시) 그때 옵션 C 로 마이그레이션 — 본 spec 시점은 단순화가 더 큰 가치
- "skia-safe 빌드가 모든 wheel 에 강제되면 (1) wheel 크기 50-100 MB 까지 증가 가능, (2) 빌드 시간 분 단위 증가, (3) PNG 미사용자 가 불필요한 코드 다운로드 — 부담 아닌가?" → 인정. 다만 옵션 B 도 동일 비용 (wheel 통합 빌드라 어차피 모든 사용자가 다운로드). 진짜로 비용을 회피하려면 옵션 C (별도 PyPI 패키지) 필요. 본 spec 시점은 비용을 받아들이고 단순함을 택함 — 임계 (wheel > 100 MB) 도달 시 옵션 C 로 재평가
- "사용자가 PNG 사용 의도를 명시 시그널 (`pip install rhwp-python[png]`) 로 표현하는 것이 자연스럽지 않나?" → 시그널 자체는 가치가 있으나 *비용 (학습 부담)* 이 *효익* 보다 큼. 사용자가 `[png]` extras 의 의미를 학습 → "왜 필요한가?" → "어차피 wheel 에 들어 있는데 왜 별도 install?" → "Pillow 가 들어옴" → 그러나 render_png 자체엔 Pillow 불필요 → 시그널 효익이 cosmetic 으로 축소. extras 없는 직관적 install path 가 더 좋은 UX

### 최종 결정

**A 채택** — `Cargo.toml` 의 `rhwp` dependency 에 `features = ["native-skia"]` 추가 (default 통합). Python 측 별도 extras / marker 없음. `pip install rhwp-python` 만으로 render_png 사용 가능. testing dependency-group 에는 Pillow 추가 — AC-3 (스케일 후 dimension 검증) 회귀 테스트가 디코드 라이브러리 필요. 옵션 C (별도 PyPI 패키지) 는 wheel 크기 임계 (>100 MB) 도달 시 재평가.

### 1차 소스

- 상류 `external/rhwp/Cargo.toml:35-44` (image / native-skia features)
- 상류 `external/rhwp/Cargo.toml:51-53` (skia-safe binary-cache + embed-icudtl)
- 본 프로젝트 `Cargo.toml:45-46` (pyo3 abi3-py310 + rhwp dependency)
- 본 프로젝트 `pyproject.toml` extras 정책 (langchain / cli / mcp 분리 패턴)
- PyPI wheel 크기 제약 정책: <https://pypi.org/help/#file-size-limit>
- skia-safe v0.93.1: <https://github.com/rust-skia/rust-skia>

---

## 2. Python API 시그니처

### 팩트

- 본 프로젝트 v0.1.0 부터 렌더 메서드는 3-메서드 패턴: `render_<format>(page) -> str|bytes` (페이지 단위) / `render_all_<format>() -> list[str|bytes]` (전체 메모리) / `export_<format>(out_dir, prefix=None) -> list[str]` (디스크). SVG / PDF 모두 동일 (`render_svg` / `render_all_svg` / `export_svg` 와 `render_pdf` / `export_pdf` — `render_pdf` 가 단일 호출로 전체 PDF 반환이라 `render_all_pdf` 는 미존재)
- 상류 `RasterRenderOptions` 의 7 필드: `dpi: Option<f64>` / `scale: f64` / `max_dimension: u32` / `max_pixels: u64` / `format: RasterOutputFormat` / `background_color: Option<ColorRef>` / `transparent: bool` / `color_space: Option<ColorSpace>`
- VLM use case 의 1차 옵션 — `dpi` (해상도, Anthropic Vision 권장 96-300 DPI), `scale` (배율), `max_pixels` (DoS 방어 + LLM context 비용 가드)
- 사용자 학습 비용 분석: SVG / PDF 사용자가 PNG 로 자연스럽게 확장하는 cognitive path — `render_png` / `render_all_png` / `export_png` 가 가장 작은 차이
- 옵션 dataclass 패턴 (B) 의 선례: matplotlib `savefig(fname, *, dpi, format, ...)` 가 kwargs-only, Pillow `Image.save(fp, format, **kwargs)` 가 kwargs + format 분리

### 검증자 반박

- "RenderOptions dataclass 가 7 필드 모두 한 번에 노출 — 미래 확장도 쉬움. 왜 거부?" → 1차 use case (VLM 입력) 는 dpi / scale / max_pixels 만 필요 — `background_color` / `transparent` / `color_space` 는 demand 신호 부재. 노출하면 사용자가 *왜 이게 있는지* 문서로 설명 의무 발생, 명시 안 하면 silent default. YAGNI 원칙
- "SVG/PDF mirror 가 너무 좁지 않나? `render_png(page, **kwargs)` 만 노출하면 미래 옵션 추가가 backward-compatible" → kwargs-only 도 valid, 다만 `render_png(page, scale=2.0, dpi=300, max_pixels=4_000_000)` 처럼 키워드 전달이 readable. positional 인자는 `page` 만 — 그 외는 키워드 강제 (시그니처 `def render_png(self, page, *, scale=1.0, dpi=None, max_pixels=None) -> bytes`). 옵션 A 안에서 이미 키워드 강제 패턴이라 옵션 C 와 사실상 동일
- "`export_png` 가 디스크 IO — async 도 필요한가?" → demand-driven. v0.6.0 1차는 sync `export_png` 만, async 는 사용자 측 `asyncio.to_thread(doc.export_png, ...)` 로 충분 (export 는 owned bytes 반환 후 디스크 쓰기 — `_Document` thread 경계 무관)
- "`render_all_png` 가 메모리 폭발 위험 (페이지 100 개 × 500 KB = 50 MB)" → 사용자 책임 — 페이지 수 알고 있으니 (`page_count`). 큰 문서면 `for i in range(doc.page_count): doc.render_png(i)` 루프 권장. SVG / PDF 도 같은 메모리 모델
- "`Document.arender_png()` 인스턴스 메서드는 왜 미제공?" → unsendable `_Document` 가 thread 경계 위반 시 panic ([CLAUDE.md](../../../CLAUDE.md) § "Async direction"). 모듈-level `arender_png(path, page)` 가 매번 parse + render 안에서 `_Document` 를 생성/소비하는 단일 스레드 패턴 강제. 인스턴스 재사용 async 는 본 spec 비목표

### 최종 결정

**A 채택** — SVG / PDF API 1:1 mirror. `Document.render_png(page, *, scale=1.0, dpi=None, max_pixels=None) -> bytes` / `Document.render_all_png() -> list[bytes]` / `Document.export_png(out_dir, *, prefix=None) -> list[str]` + 모듈-level `arender_png(path, page, *, ...)` async. 1차 노출 옵션 3개 (dpi / scale / max_pixels), 나머지 4 필드는 demand-driven 확장. spec § 인수조건 AC-2 ~ AC-7 이 회귀 가드.

### 1차 소스

- 본 프로젝트 `python/rhwp/document.py:200-254` (render_svg / render_pdf 패턴)
- 본 프로젝트 `src/document.rs:115-169` (Rust 측 render_pdf py.detach 패턴)
- 상류 `external/rhwp/src/renderer/skia/renderer.rs:66` (render_raster_with_options)
- 상류 `external/rhwp/src/renderer/layer_renderer.rs` (RasterRenderOptions struct)
- matplotlib savefig API: <https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html>
- Pillow Image.save API: <https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.save>

---

## 3. 출력 코덱

### 팩트

- 상류 `SkiaLayerRenderer::render_raster_with_options` (line 66-152) 는 `options.format != RasterOutputFormat::Png` 시 명시적 에러: `"Skia raster renderer currently supports PNG output"` (line 78). PNG 외 format 거부
- skia-safe `EncodedImageFormat` enum 은 PNG / JPEG / WebP / KTX 등 지원하나 본 프로젝트의 상류는 PNG 만 wire-through — `image.encode(None, EncodedImageFormat::PNG, None)` (line 142) 가 hardcoded
- VLM image input 1차 코덱 호환성 (2026-05 기준):
  - Anthropic Claude Vision: PNG / JPEG / WebP / GIF (1st-tier 모두)
  - OpenAI GPT-4V: PNG / JPEG / WebP / GIF (1st-tier)
  - Google Gemini Vision: PNG / JPEG / WebP / HEIC / HEIF
  - 즉 PNG 단독으로 3대 VLM 모두 호환
- PNG vs JPEG 비교 (HWP 페이지 렌더 use case):
  - PNG: 무손실, 텍스트 / 라인아트 압축률 우수, 파일 크기 100-500 KB / A4 페이지
  - JPEG: 손실, 사진 / 그라디언트 우수, 텍스트 영역 ringing artifact 가능
  - HWP 페이지는 텍스트 위주 → PNG 가 시각 품질 + 압축률 양 측면에서 우수

### 검증자 반박

- "JPEG 옵션 추가 시 페이지가 사진/이미지 위주면 5-10x 압축. MCP 페이로드 줄이는 데 유리" → 상류가 PNG only 라 우리 측 추가는 (1) 우리 코드에서 PNG → JPEG 재인코딩 (Pillow / image lib 의존성 + 손실), (2) 상류에 JPEG 지원 PR. (1) 은 별도 코덱 chain 으로 복잡도 ↑, (2) 는 상류 작업이라 본 spec 범위 밖. 본 spec 은 옵션 A
- "WebP / AVIF 가 PNG 보다 30-50% 작은 파일 — 미래 표준 호환" → 동일 이유 (상류 미지원 + VLM 1차 코덱이 이미 PNG). WebP 는 OpenAI / Anthropic / Google 셋 다 지원하나 PNG 는 universal. 보수적 시작 후 demand-driven 확장
- "사용자가 `format` 인자를 노출하지 않으면 미래 추가 시 breaking 인가?" → No. `format: Literal["png"] = "png"` 키워드 인자 추가 시 backward-compat. 본 spec 은 미노출, 미래 추가 시 default `"png"` 로 도입 가능
- "PNG 매직 바이트 검증 (AC-2) 가 회귀 가드로 충분한가?" → PNG 매직 (`\x89PNG\r\n\x1a\n`) 은 byte-equal 검증으로 codec 결정성을 100% 보장. 추가로 image lib (Pillow) 디코드 후 dimension 검증 (AC-4) 으로 페이지 크기 invariant 도 가드 — 두 layer 검증

### 최종 결정

**A 채택** — PNG 단독 출력. `format` 인자 미노출 (default "png" 로 미래 추가 가능). spec § 인수조건 AC-2 (PNG magic byte) + AC-4 (dimension scale) 이 회귀 가드. JPEG / WebP / AVIF 등 대안 코덱은 본 spec § 영구 비목표 — 상류 PR 선행 후 demand-driven.

### 1차 소스

- 상류 `external/rhwp/src/renderer/skia/renderer.rs:76-80` (PNG-only 거부 분기)
- 상류 `external/rhwp/src/renderer/skia/renderer.rs:142` (PNG hardcoded encode)
- Anthropic Claude Vision codec 호환성: <https://docs.anthropic.com/en/docs/build-with-claude/vision>
- OpenAI GPT-4V vision input: <https://platform.openai.com/docs/guides/vision>
- Google Gemini Vision: <https://ai.google.dev/gemini-api/docs/vision>
- W3C PNG Specification 3.0: <https://www.w3.org/TR/png-3/>

---

## 4. MCP 출력 인코딩

### 팩트

- fastmcp v3 의 `ImageContent` 클래스 (`mcp.types.ImageContent`): `data: str` (base64) + `mime: str` + `annotations: ...`. MCP 표준 `tools/call` response 의 content array 의 `image` type 1:1 매핑
- fastmcp v3.2.4 docs § Tool Result Types 가 image / audio / file content 를 LLM-aware tool 출력의 1st-tier 패턴으로 명시
- LLM 클라이언트 (Claude Desktop / Cline / Cursor) 의 ImageContent 처리 — MCP response 의 image content 를 LLM 메시지의 `image` content block 으로 변환 → LLM 이 시각 입력으로 인식. base64 변환은 클라이언트 책임 외 — fastmcp 가 server 출고 시점에 base64 wrap
- 옵션 A (`bytes` 반환): fastmcp 가 raw bytes 를 `BlobResourceContents` 로 wrap → LLM 이 이미지로 인식 못 함 (raw blob 으로 전달, mime 정보 손실)
- 옵션 C (`file://path` URI): MCP `FileContent` resource link. 클라이언트가 파일 시스템 접근 후 base64 변환 — stdio transport 에서는 클라이언트와 서버가 같은 파일 시스템일 때만 작동, streamable-http 에서는 fail
- v0.5.0 MCP 도구의 `outputSchema` 패턴 — Pydantic 모델 자동 wire-through (v0.5.1 의 typed-output 결정 정합)

### 검증자 반박

- "fastmcp v3 가 `bytes` 반환을 자동 ImageContent 로 wrap 하지 않나?" → No (1차 소스 검증 필요 — 미확정 이슈). fastmcp v3.2.4 docs 는 *return type 어노테이션* 이 `bytes` 면 `BlobResourceContents`, `ImageContent` 면 image content 로 명시 분기. server 가 의도적으로 `ImageContent` 를 명시해야 LLM 이 image 로 인식. 명시적 옵션 B 선택이 안전
- "`file://path` URI (옵션 C) 가 페이로드 작아 stdio 에 유리한가?" → stdio transport 가 동일 머신 가정이라 `file://` 가 작동하나 (1) Claude Desktop / Cline 등 클라이언트의 file 권한 처리 비결정, (2) streamable-http 에서는 server / client 가 다른 머신 → fail, (3) 임시 파일 lifecycle 관리 (export 후 삭제 시점) 책임 분산. 옵션 B 가 transport 무관 일관 동작
- "base64 페이로드 크기 (130-660 KB / A4 페이지) 가 LLM context cost 에 영향?" → 영향 — 사용자 책임 (page 수 / scale 조정). MCP 도구의 `description` 에 "한 페이지 base64 PNG 가 ~500 KB" 명시하여 사용자가 비용 인식. 페이로드 크기 자체는 옵션 A / B / C 모두 동일 (transport 가 base64 인코딩하므로) — 옵션 차이는 *LLM 이 이미지로 인식하느냐* 만
- "stdio JSON-RPC 메시지 크기 제한 (예: Claude Desktop 의 약 1 MB 제한 추정) 충돌?" → spec § 미확정 이슈. 임계 초과 시 streamable-http transport 권장 + max_pixels 강제 가이드. 본 spec 은 transport 별 한계 측정 후 README 안내

### 최종 결정

**B 채택** — MCP `render_page_png(path, page, *, ...)` 도구가 `ImageContent(data=base64.b64encode(png_bytes).decode("ascii"), mime="image/png")` 반환. fastmcp v3 자동 outputSchema 가 `ImageContent` 의 `$ref` 를 노출 → LLM 클라이언트가 image input 으로 wire. spec § 인수조건 AC-6 이 회귀 가드 (mime 검증 + base64 디코드 후 PNG magic 검증).

### 1차 소스

- fastmcp v3.2.4 docs § Tool Result Types: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- MCP Specification (`tools/call` response content types): <https://modelcontextprotocol.io/specification/2025-03-26/server/tools>
- `mcp.types.ImageContent` Python SDK: <https://github.com/modelcontextprotocol/python-sdk>
- 본 프로젝트 `python/rhwp/mcp/tools.py` (v0.5.0 도구 등록 SSOT)
- 본 프로젝트 v0.5.1 typed-output 결정: [roadmap/README.md](../../roadmap/README.md) 활성 spec 인덱스

---

## 5. max_pixels 가드 SSOT

### 팩트

- 상류 `RasterRenderOptions::default()` 의 `max_pixels` 값 — `external/rhwp/src/renderer/layer_renderer.rs` 가 SSOT (정확한 default 는 spec § 미확정 이슈로 위임)
- 상류 `render_raster_with_options` 내부 가드 (line 110-122):
  - `options.max_pixels == 0` → 에러 (`"invalid raster max pixel count: 0"`)
  - `width × height > options.max_pixels` → 에러 (`"raster pixel count out of range: {pixel_count}"`)
  - `width × height` overflow → 에러 (`"raster pixel count overflow"`)
- DoS 방어 동기 — 사용자가 `scale=1000.0` 같은 거대한 값을 넘겨 surface allocation panic / OOM 회피
- 본 프로젝트 v0.1.0 ~ v0.5.x 의 모든 가드 (`section_count` / `paragraph_count` / IR `pages` 등) 는 상류 SSOT 그대로 wire-through — Python-side 별도 가드 없음

### 검증자 반박

- "Python 측 별도 default 정의 (옵션 B) — 상류와 다른 정책 적용 가능한 유연성" → drift 위험. 두 SSOT 가 분기 (예: 상류 4_000_000, Python 8_000_000) 시 어느 것이 진짜 invariant 인가 모호. 사용자가 원본 상류 가드를 인지 못 하고 Python default 만 신뢰 시 상류 변경 후 bug
- "옵션 C (가드 미노출) — 사용자가 max_pixels 전달 안 하면 *원하는 만큼* 큰 이미지 가능" → 자체 DoS 위험. `Document.render_png(page, scale=1000.0)` 가 surface allocation panic 으로 process 죽임. 가드는 default 라도 있어야 안전
- "상류 가드의 정확한 default 값 모르는 상태에서 옵션 A 결정 적절한가?" → spec § 미확정 이슈로 명시 — 결정 *방향* 은 상류 wire-through, 구체 값은 implementation 시점 확인. RasterRenderOptions::default 가 상류 변경 시 본 binding 도 자동 호응 — SSOT 단일화의 의도된 효과
- "상류 가드 메시지가 Rust panic 메시지로 그대로 노출 — Python 사용자에게 친절한가?" → ValueError 로 wrap 하되 상류 메시지 그대로 포함 (예: `ValueError: raster pixel count out of range: 16000000000`). 상류 메시지 변경 시 본 binding 메시지 표면 자동 갱신 — 별도 번역 표 유지 부담 제거. spec § 인수조건 AC-5 가 메시지에 `"pixel count out of range"` substring 검증 (상류 변경에 강한 회귀 가드)
- "사용자가 max_pixels 명시 override — 가드 무력화 가능?" → 사용자 의도된 override 는 정상 (예: 대형 포스터 PDF 의 고해상도 PNG). 가드는 default 가 안전 + 사용자가 책임 인지 후 override — Python 일반 패턴 (예: `pickle.loads` 의 `safe=True` default)

### 최종 결정

**A 채택** — `RasterRenderOptions::default()` 의 `max_pixels` 그대로 wire-through. 사용자 명시 override 만 허용. 상류 메시지 그대로 ValueError 로 wrap. spec § 인수조건 AC-5 (`max_pixels=1` → ValueError + `"pixel count out of range"` 메시지 substring 검증) 가 회귀 가드.

### 1차 소스

- 상류 `external/rhwp/src/renderer/skia/renderer.rs:110-122` (max_pixels 가드 분기)
- 상류 `external/rhwp/src/renderer/layer_renderer.rs` (RasterRenderOptions::default — 정확한 값은 implementation 시점 확인)
- 본 프로젝트 `src/document.rs:115-169` (기존 render_pdf wire-through 패턴)
- Python ValueError 표준: <https://docs.python.org/3/library/exceptions.html#ValueError>
- DoS 방어 패턴 (image library): <https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#decompression-bomb>

---

## 참조

- 짝 페어: [png-vlm-render.md](../../roadmap/v0.6.0/png-vlm-render.md)
- 상류 `edwardkim/rhwp` v0.7.10 (PR #599 PNG 게이트웨이): <https://github.com/edwardkim/rhwp/pull/599>
- 상류 `examples/pr599_png_gateway.rs`: `external/rhwp/examples/pr599_png_gateway.rs`
- skia-safe (rust-skia bindings): <https://github.com/rust-skia/rust-skia>
- fastmcp v3 (jlowin / PrefectHQ): <https://github.com/jlowin/fastmcp>
- Anthropic Claude Vision: <https://docs.anthropic.com/en/docs/build-with-claude/vision>
- MCP Specification (image content types): <https://modelcontextprotocol.io/specification/2025-03-26/server/tools>
- 본 프로젝트 `Cargo.toml` (rhwp dependency 정책)
- 본 프로젝트 `python/rhwp/document.py` (Document wrapper)
- 본 프로젝트 `python/rhwp/mcp/tools.py` (MCP 도구 SSOT)
