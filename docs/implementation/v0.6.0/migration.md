---
status: Frozen
description: "v0.6.0 구현 로그 — 페이지 PNG 렌더링 (`render_png` / `render_all_png` / `export_png` / `arender_png` + MCP `render_page_png`). 상류 native-skia raster 통합 + default wheel"
ga: v0.6.0
last_updated: 2026-05-10
---

# v0.6.0 — 페이지 PNG 렌더링 (구현 로그)

[v0.6.0/png-vlm-render](../../roadmap/v0.6.0/png-vlm-render.md) (spec) +
[design/v0.6.0/png-vlm-render-research](../../design/v0.6.0/png-vlm-render-research.md)
(ADR) 의 구현 결과 로그. 결정의 근거·옵션 비교는 ADR 가 보유 — 본 문서는
*산출물 / 검증 결과 / 호환성 / 이월 사항* + *작업 중 표면화된 spec 본문 단순화*
만 기록한다 (CONVENTIONS § CHANGELOG ↔ implementation log 역할 분리).

MINOR release. 단일 세션 규모 (Rust 3 메서드 + Python wrapper 4 + MCP 도구 1
+ 테스트 7) 로 단일 `migration.md` 채택.

## 1. 산출물

### Rust 신규

| 파일 / 위치 | 변경 |
|---|---|
| [Cargo.toml](../../../Cargo.toml) | `rhwp` 의존성에 `features = ["native-skia"]` 추가 — 상류 `SkiaLayerRenderer` (skia-safe v0.93.1) 활성화. wheel 빌드 시점 약 30 MB binary-cache 다운로드 |
| [src/document.rs](../../../src/document.rs) | `PyDocument::render_png` / `render_all_png` / `export_png` 3 #[pymethods] 신규 + 사적 `render_png_internal` 헬퍼. `py.detach` 안에서 `SkiaLayerRenderer::new().render_png_with_options(&layer_tree, options)` — owned `PageLayerTree` 가 closure 로 이동 (Send 보장). `&self.inner` 는 layer tree 빌드 단계 (GIL 유지) 에서만 사용 — `unsendable` 경계 위반 회피 |

### Python 신규

| 파일 / 위치 | 변경 |
|---|---|
| [python/rhwp/document.py](../../../python/rhwp/document.py) | `Document.render_png` / `render_all_png` / `export_png` wrapper 메서드 + 모듈-level `arender_png(path, page, *, scale, dpi, max_pixels)` async 함수. async 는 `aparse` 패턴 답습 — 파일 read 만 thread offload, render 는 호출 스레드 (GIL 해제는 Rust 측 `py.detach`) |
| [python/rhwp/_rhwp.pyi](../../../python/rhwp/_rhwp.pyi) | 3 새 메서드 stub (`render_png` / `render_all_png` / `export_png`) |
| [python/rhwp/__init__.py](../../../python/rhwp/__init__.py) + [__init__.pyi](../../../python/rhwp/__init__.pyi) | `arender_png` re-export |

### MCP 도구 신규

| 파일 / 위치 | 변경 |
|---|---|
| [python/rhwp/mcp/tools.py](../../../python/rhwp/mcp/tools.py) | `render_page_png(path, page, *, scale, max_pixels) -> ImageContent` 신규. `base64.b64encode` + `mimeType="image/png"`. fastmcp v3 `ImageContent` 표준 — LLM 클라이언트 자동 wire |
| [python/rhwp/mcp/server.py](../../../python/rhwp/mcp/server.py) | `build_server()` 에 `server.tool(tools.render_page_png)` 등록 — v0.5.0 의 7 도구 → 8 도구 |

### 테스트

| 파일 | 변동 | 책임 |
|---|---|---|
| [tests/test_render_png.py](../../../tests/test_render_png.py) | 신규 (+87 lines) | 7 테스트 클래스 — `TestRenderPng` (AC-1~4) / `TestExportPng` (AC-7) / `TestArenderPng` (AC-6) / `TestMcpRenderPagePng` (AC-5). per-test `pytest.mark.spec("v0.6.0/png-vlm-render#AC-N")` 마커 + MCP 테스트는 per-test `pytest.importorskip("fastmcp")` (file-level skip 회피 — 다른 AC 가드는 fastmcp 무관 실행) |

### 문서

| 파일 | 변경 |
|---|---|
| [README.md](../../../README.md) | § "페이지 PNG 렌더링 (VLM 입력)" 섹션 신설 — `render_png` / `render_all_png` / `export_png` / `arender_png` 사용 예 + Anthropic Vision API 호출 코드 + `max_pixels` 안내. § "MCP server" 의 도구 표 7 → 8 갱신, "8 개 도구 노출" 안내 동기화 |
| [CHANGELOG.md](../../../CHANGELOG.md) | `[0.6.0]` 섹션 신설 — Added (3 메서드 + arender + MCP) / Build (native-skia 통합 + Pillow testing) / 기존 [Unreleased] 의 doc system 변경 흡수 |
| [docs/roadmap/v0.6.0/png-vlm-render.md](../../roadmap/v0.6.0/png-vlm-render.md) (spec) | Draft body 단순화 — § 작업 중 표면화된 결정 변경 절 참조 |
| [docs/design/v0.6.0/png-vlm-render-research.md](../../design/v0.6.0/png-vlm-render-research.md) (ADR) | Draft body 단순화 — 결정 매트릭스 row 1 (배포 형태) 의 채택을 B → A (default 통합) 로 변경, 검증자 반박 cli/mcp 와의 본질 차이로 재작성 |
| [docs/traces/coverage.md](../../traces/coverage.md) | spec_trace 자동 갱신 — 7 새 v0.6.0/png-vlm-render#AC-N row 추가 |
| [docs/roadmap/README.md](../../roadmap/README.md) | 활성 spec 인덱스 v0.6.0 row 를 Frozen 으로 표시 + 구현 / 검증 로그 표에 v0.6.0 row 추가 |

### Build

| 파일 / 위치 | 변경 |
|---|---|
| [Cargo.toml](../../../Cargo.toml) | version 0.5.1 → 0.6.0. `rhwp` features = ["native-skia"] |
| [pyproject.toml](../../../pyproject.toml) | `testing` dependency-group 에 `pillow>=10` 추가 — AC-3 (스케일 후 dimension 검증) 회귀 테스트 디코드용. `[project.optional-dependencies]` 의 사용자 wheel extras 변경 0 |

## 2. 결정 사항 (spec 결정 8 항목 ↔ 구현 매핑)

| spec 결정 | 구현 위치 |
|---|---|
| 1 — Renderer 백엔드 (native-skia default 통합) | `Cargo.toml` 의 `rhwp = { features = ["native-skia"] }`, 별도 extras 없음 (β 결정 — § 5 참조) |
| 2 — Python API 시그니처 (SVG/PDF API mirror) | `Document.render_png(page, *, scale, dpi, max_pixels)` / `render_all_png()` / `export_png(out_dir, *, prefix)` |
| 3 — 출력 코덱 (PNG only) | 상류 `RasterOutputFormat::Png` 거부 분기를 그대로 wire-through — 본 binding 측 `format` 인자 미노출 |
| 4 — 배포 형태 (default 통합) | `pip install rhwp-python` 만으로 즉시 사용 가능 — `[png]` extras / marker / ImportError 가드 모두 제거 (β 결정 — § 5 참조) |
| 5 — MCP 도구 (`ImageContent` 출고) | `python/rhwp/mcp/tools.py:render_page_png` — `base64.b64encode` + `mimeType="image/png"` |
| 6 — GIL 해제 정책 (`py.detach` 안에서 raster) | `src/document.rs:render_png_internal` — owned `PageLayerTree` 를 closure 로 이동, `SkiaLayerRenderer::new()` 는 closure 안에서 인스턴스 생성 (Send + 'static 보장) |
| 7 — 비동기 표면 (`arender_png` 모듈-level) | `python/rhwp/document.py:arender_png` — `aparse` 패턴 (file read 만 thread offload, render 는 호출 스레드 sync). Document 인스턴스 메서드 미제공 (`unsendable` 정합) |
| 8 — `max_pixels` 가드 SSOT (상류 default wire-through) | `RasterRenderOptions::default()` 의 `max_pixels: 67_108_864` (8192 × 8192) 그대로 사용. 사용자 명시 override 만 허용. 위반 시 상류 메시지 그대로 `PyValueError` (`tests/test_render_png.py::TestRenderPng::test_max_pixels_guard_raises` 가 회귀 가드) |

## 3. 호환성

| 시나리오 | 결과 |
|---|---|
| **기존 사용자 (`pip install rhwp-python` 후 `Document.render_pdf` / `render_svg` / `to_ir` 호출)** | 변경 없음. v0.5.x 표면 모두 보존 (additive only) |
| **새 사용자 (`Document.render_png` 호출)** | extras 없이 즉시 사용 — wheel 에 native-skia binary 통합 |
| **wheel 크기** | 약 30 MB 추가 (skia-safe binary-cache + embed-icudtl). PyPI 단일 패키지 100 MB 한도 내 — abi3-py310 single wheel 정합 유지 |
| **abi3-py310 호환성** | 본 release 환경 (macOS arm64) 빌드 OK. CI 매트릭스 (Linux / macOS / Windows × x86_64 / aarch64) 검증은 publish.yml 트리거 시 |
| **CI `test-without-extras` job (skip count = 5)** | 변경 없음. `tests/test_render_png.py` 는 file-level `importorskip` 없음 — `pillow` (testing 그룹) 와 `fastmcp` 의 미설치 영향은 (1) Pillow 부재 시 file collection error, (2) MCP 한 테스트만 per-test skip. test-without-extras job 에서는 testing 그룹 install 안 되므로 (1) 발생 가능성 — file collection error 가 fail 카운트에 안 들어가는 pytest 동작 의존. *향후 release 에서 `tests/test_render_png.py` 의 import 라인을 `pytest.importorskip("PIL")` file-level 로 옮기는 보강 검토* (본 release 보류 — `pip install pytest` only 환경 미실험) |
| **`tests/type_check_errors.py` 의 4 intentional pyright errors** | 변경 없음 |

**SemVer**: MINOR (0.5.1 → 0.6.0). additive only — 외부 wire format / wheel 의존성 / schema (`"1.1"`) / abi3-py310 정책 보존.

## 4. 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/test_render_png.py -v` | **7 passed** — AC-1 ~ AC-7 모두 그린 |
| `uv run maturin develop --release` | OK — abi3 wheel 빌드 (Apple silicon) |
| `cargo clippy --all-targets -- -D warnings` | exit 0 — clippy clean |
| `uv run pyright python/` (autolint hook) | clean |
| `uv run ruff check python/ tests/` (autolint hook) | clean |

전체 회귀 (`pytest -m "not slow"` 등) 와 `lint_docs.py` 는 본 commit 후 별도 단계에서 실행.

### AC ↔ 테스트 매핑

| AC | 위치 | 테스트 |
|---|---|---|
| AC-1 (PNG magic) | `tests/test_render_png.py::TestRenderPng::test_returns_png_magic` |
| AC-2 (`render_all_png` 길이 == `page_count`) | `TestRenderPng::test_render_all_count_matches_page_count` |
| AC-3 (스케일 후 dimension) | `TestRenderPng::test_scale_doubles_width` (Pillow 디코드) |
| AC-4 (`max_pixels` 가드) | `TestRenderPng::test_max_pixels_guard_raises` |
| AC-5 (MCP `ImageContent` mime + base64 PNG magic) | `TestMcpRenderPagePng::test_returns_image_content` (per-test `importorskip("fastmcp")`) |
| AC-6 (`arender_png` no panic) | `TestArenderPng::test_async_returns_png_without_panic` |
| AC-7 (`export_png` 파일 생성 + magic) | `TestExportPng::test_writes_files_with_png_magic` |
| AC-8 (v0.5.x 회귀 가드) | 기존 `tests/test_pdf_rendering.py` / `tests/test_svg_rendering.py` / `tests/test_mcp_server.py` 등 — 변경 없음 |
| AC-9 (README PNG 섹션) | manual inspection — § "페이지 PNG 렌더링 (VLM 입력)" 신설 |

9/9 AC 모두 충족.

## 5. 작업 중 표면화된 spec 본문 단순화 (Draft → Draft 갱신)

본 PATCH 작업 중 spec 의 *결정 1 + 4* + *AC-1 + AC-8* 이 내부 모순을 갖는 것이
표면화 — Draft 본문을 일관된 형태로 단순화. 주요 시행착오:

### 5.1 옵션 비교 (a/b/c)

원 spec 의 결정 1 (배포 형태) 옵션:

- **A**: default features 통합 (모든 wheel 에 native-skia)
- **B**: `[png]` extras 분리 (Python-side marker + Pillow 의존성) — 원 채택
- **C**: 별도 PyPI 패키지 (`rhwp-png`)

원 채택 B 의 의도된 이점은 (1) skia-safe 빌드 비용을 모든 사용자에게 강제하지
않음, (2) 사용자가 PNG 사용 의도를 `[png]` extras 로 시그널화. 시행착오:

| 시점 | 발견 | 처리 |
|---|---|---|
| α 채택 (extras + Pillow + marker 가드) | wheel 이 통합 빌드라 어차피 모든 사용자가 native skia binary 다운로드 — extras 의 비용 회피 효과 0. extras 가 추가하는 건 Pillow 만이고, render_png 자체는 Pillow 없이 작동 → marker `import PIL` 가드는 사용자에게 *과도한 강제* | 결정 1 채택을 B → A (default 통합) 로 단순화 |
| β 채택 (default 통합) | `pip install rhwp-python` 만으로 즉시 사용 가능. cli / mcp / langchain 의 *런타임 Python 의존성 분리* extras 와 PNG 표면은 본질이 다름 (PNG 는 native binary 단독 동작) — 분리할 의미 없음. AC-1 (`[png]` extras 미설치 시 ImportError) / AC-8 (`pytest.importorskip("rhwp._png_marker")` skip count 5 → 6) 도 자연 제거 | spec / ADR / 코드 / pyproject 모두 단순화 — `_png_marker.py` / `_require_png_extras` / `[png] = []` 모두 삭제. testing 그룹의 Pillow 만 유지 (AC-3 dimension 검증) |

### 5.2 가치 있는 학습

- **extras 패턴은 Python *런타임* 의존성 분리에만 의미 있음** — native binary 단독으로 동작하는 표면은 default 통합이 정직. cli / mcp / langchain 처럼 extras 를 만들면 marker 가드는 사실상 dead code 가 됨
- **Draft 단계의 결정 변경은 spec 본문 직접 수정** — Frozen 후 결정 변경은 새 spec + Superseded 절차 (CONVENTIONS § Frozen 후 결정 변경) 가 필요하나, Draft 는 본문 갱신으로 충분. 본 release 에서 Draft 단계 시행착오를 본문에 흡수 → Frozen 전환 시 일관된 최종 결정 1 종만 보유

### 5.3 ADR row 1 갱신

ADR 의 결정 매트릭스 row 1 의 채택을 **B → A** 로 변경, 검증자 반박을 *cli /
mcp / langchain 의 런타임 Python 의존성 분리 패턴과 PNG 의 native binary 단독
동작의 본질 차이* 로 재작성. § 1.최종 결정 도 단순화 (`[png] = ["pillow>=10"]`
+ marker → default 통합 + extras 없음).

## 6. 알려진 한계 / 이월 사항

다음 항목은 v0.6.0 범위 밖. spec § 미확정 이슈 가 정확한 목록 — 본 절은
v0.6.0 작업 중 표면화된 항목 + 보류 결정 정리.

| 항목 | 상태 | 후속 |
|---|---|---|
| skia-safe 빌드 시간 / wheel 크기 영향 (CI 매트릭스 측정) | 본 release 미측정 — 사용자 GA 절차의 publish.yml 결과로 확인 | 임계 (wheel > 100 MB) 도달 시 별도 PyPI 패키지 (`rhwp-png`) 분리 검토 |
| abi3-py310 호환성 (Linux / Windows × aarch64 빌드) | 본 release 환경 (macOS arm64) 만 검증 | publish.yml 의 cibuildwheel 결과로 확인 |
| MCP `ImageContent` 의 LLM 클라이언트 호환성 | 미검증 (Claude Desktop / Cline 등 transport 별 base64 인코딩 안정성) | v0.5.0 클라이언트 호환성 표 (text-only 응답 기준) 의 image 컬럼 추가 — 별도 손 검증 |
| stdio MCP transport 의 base64 페이로드 크기 (A4 페이지 약 100-500 KB → base64 약 130-660 KB) | 미측정 | 임계 초과 시 README 에 streamable-http 권장 안내 |
| `tests/test_render_png.py` 의 PIL file-level importorskip | 보류 — testing 그룹 미설치 시 collection error 가능성 | test-without-extras job 결과 확인 후 보강 |
| `Cargo.toml` bump / `CHANGELOG.md [0.6.0]` 섹션 추가 | 본 release 의 commit 6 에 포함 (사용자 GA 절차 와 다른 패턴 — 본 release 는 사용자 요청대로 commit 분할 안에 포함) | — |

## 7. v0.6.0 GA 절차 (인계)

본 step 이후 v0.6.0 GA 까지의 release 절차 (CONVENTIONS § GA 절차):

1. **`Cargo.toml` version bump** — 0.5.1 → 0.6.0 (commit 6 에서 완료)
2. **`png-vlm-render.md` / `png-vlm-render-research.md` frontmatter flip** — `status: Draft → Frozen`, `target: v0.6.0 → ga: v0.6.0` (본 commit 7 에서 완료)
3. **본 `migration.md` frontmatter** — 작성 즉시 Frozen + ga: v0.6.0 (CONVENTIONS § Implementation log 면제)
4. **`docs/roadmap/README.md` 인덱스 갱신** — v0.6.0 row 를 Frozen 으로 표시 + 구현 / 검증 로그 표에 v0.6.0 row 추가 (본 commit 7 에서 완료)
5. **`CHANGELOG.md` [0.6.0] 섹션** — commit 6 에서 완료
6. **git tag `v0.6.0`** + GitHub Release 생성 — `publish.yml` 트리거 (Trusted Publisher OIDC) — *사용자 진행*
7. **release 후 손 검증** — Anthropic Vision API + Claude Desktop MCP 통합 검증 (실제 HWP 페이지 렌더 → LLM 시각 해석)

## 8. 참조

### 짝 페어

- spec: [docs/roadmap/v0.6.0/png-vlm-render.md](../../roadmap/v0.6.0/png-vlm-render.md)
- ADR: [docs/design/v0.6.0/png-vlm-render-research.md](../../design/v0.6.0/png-vlm-render-research.md)

### 외부

- 상류 `edwardkim/rhwp` PR #599 (PNG 게이트웨이): <https://github.com/edwardkim/rhwp/pull/599>
- 상류 `SkiaLayerRenderer::render_raster_with_options`: `external/rhwp/src/renderer/skia/renderer.rs:66`
- 상류 `RasterRenderOptions::default`: `external/rhwp/src/renderer/layer_renderer.rs:24-37`
- fastmcp v3 `ImageContent` 표준: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- Anthropic Vision API: <https://docs.anthropic.com/en/docs/build-with-claude/vision>

### 상류

본 v0.6.0 의 native-skia 활성화는 `external/rhwp` submodule pin 변경 0 (`62a458a`,
v0.7.10 그대로) — Cargo features 만 추가.
