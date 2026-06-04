---
status: Frozen
description: "v0.7.0 구현 로그 — HWPX writeback baseline (`to_hwpx_bytes` / `export_hwpx`). 상류 `serialize_hwpx` 위임 + 텍스트·문단 round-trip. 상류 pin `1899ef9 → ce45231c` 재동기화 후 회귀 0 재검증"
ga: v0.7.0
last_updated: 2026-06-04
---

# v0.7.0 — HWPX writeback baseline (구현 로그)

[v0.7.0/hwpx-writeback-baseline](../../roadmap/v0.7.0/hwpx-writeback-baseline.md) (spec) +
[design/v0.7.0/hwpx-writeback-baseline-research](../../design/v0.7.0/hwpx-writeback-baseline-research.md)
(ADR) 의 구현 결과 로그. 결정의 근거·옵션 비교는 ADR 가 보유 — 본 문서는
*산출물 / 검증 결과 / 호환성 / 이월 사항* + *상류 재동기화 영향 분석* 만 기록한다.

MINOR release. 단일 세션 규모 (Rust 2 메서드 + Python wrapper 2 + 테스트 7) 로
단일 `migration.md` 채택.

본 release 의 특수성: spec·feat 는 상류 pin `1899ef9` (v0.7.12) 기준으로 작성됐고
(2026-05-20), GA 직전 상류 pin 을 `ce45231c` (v0.7.12 + 394 commit) 로 재동기화한
뒤 그 위에서 회귀를 재검증했다. § 3 이 그 분석을 보유한다.

## 1. 산출물

### Rust 신규

| 파일 / 위치 | 변경 |
|---|---|
| [src/document.rs](../../../src/document.rs) | `PyDocument::to_hwpx_bytes(&self) -> PyBytes` / `export_hwpx(&self, output_path) -> usize` 2 #[pymethods] 신규. 본체는 `rhwp::serializer::serialize_hwpx(self.inner.document())` 위임 + `SerializeError → PyValueError`, 파일 쓰기 실패 → `PyIOError`. GIL 보유 (§ 2 결정 3) |

### Python 신규

| 파일 / 위치 | 변경 |
|---|---|
| [python/rhwp/document.py](../../../python/rhwp/document.py) | `Document.to_hwpx_bytes()` / `export_hwpx(output_path)` wrapper 메서드 — Rust getter 위임. § "HWPX writeback" docstring 에 보존 범위 / 에러 계약 명시 |
| [python/rhwp/_rhwp.pyi](../../../python/rhwp/_rhwp.pyi) | `_Document.to_hwpx_bytes` / `export_hwpx` 2 stub |

### 테스트

| 파일 | 변동 | 책임 |
|---|---|---|
| [tests/test_hwpx_writeback.py](../../../tests/test_hwpx_writeback.py) | 신규 (+119 lines) | 4 테스트 클래스 7 테스트 — `TestRoundtripPreservation` (AC-1) / `TestContainerShape` (AC-2~4) / `TestExportHwpx` (AC-5) / `TestAdditiveNoSideEffects` (AC-6). per-test `pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-N")` 마커. 상류 `serialize_hwpx` 위임이라 extra 의존 없음 — 항상 실행 (test-without-extras skip count 무관) |

### 문서

| 파일 | 변경 |
|---|---|
| [README.md](../../../README.md) | § "HWPX 저장 (writeback)" 신설 — `to_hwpx_bytes` / `export_hwpx` 사용 예 + HWP5 → HWPX 변환 + 보존 범위 / 에러 계약. PNG 렌더 섹션과 LangChain 통합 섹션 사이 배치 |
| [CHANGELOG.md](../../../CHANGELOG.md) | `[0.7.0]` 섹션 신설 — Added (2 메서드) / Build (상류 pin `1899ef9 → ce45231c` + sync disclosure) |
| [docs/roadmap/v0.7.0/hwpx-writeback-baseline.md](../../roadmap/v0.7.0/hwpx-writeback-baseline.md) (spec) | frontmatter `Draft → Frozen`, `target → ga: v0.7.0` |
| [docs/design/v0.7.0/hwpx-writeback-baseline-research.md](../../design/v0.7.0/hwpx-writeback-baseline-research.md) (ADR) | frontmatter 동일 전환 |
| [docs/traces/coverage.md](../../traces/coverage.md) | spec_trace 자동 갱신 — 7 새 v0.7.0/hwpx-writeback-baseline#AC-N row |
| [docs/roadmap/README.md](../../roadmap/README.md) | 활성 spec 인덱스 v0.7.0 row 를 Frozen 으로 표시 + 구현 / 검증 로그 표에 v0.7.0 row 추가 + 현재 상태 / v0.8.0 narrative 갱신 |

### Build

| 파일 / 위치 | 변경 |
|---|---|
| [Cargo.toml](../../../Cargo.toml) | version 0.6.1 → 0.7.0 |
| [.gitmodules](../../../.gitmodules) / `external/rhwp` | submodule pin `1899ef9` (v0.7.12) → `ce45231c` (v0.7.12 + 394 commit, 2026-05-27 상류) |

## 2. 결정 사항 (spec 결정 5 항목 ↔ 구현 매핑)

| spec 결정 | 구현 위치 |
|---|---|
| 1 — 직렬화 source (상류 `serialize_hwpx` 위임) | `src/document.rs` — `rhwp::serializer::serialize_hwpx(self.inner.document())`. 자체 직렬화 구현 0 |
| 2 — API 표면·명명 (`to_hwpx_bytes` + `export_hwpx`) | `to_*` = 데이터 변환 (메모리) / `export_*` = 파일 저장. 기존 `to_ir` / `export_pdf` 패턴과 정합 |
| 3 — GIL 전략 (baseline 은 GIL 보유) | `serialize_hwpx(self.inner.document())` 가 `&self.inner` 캡처 — `DocumentCore` 가 RefCell 로 `!Sync` 라 `py.detach` 클로저 이동 불가 (`to_ir` 와 동일 제약). clone-후-detach 는 측정 후 후속 patch |
| 4 — 입력 포맷 (HWP5 / HWPX 모두) | 입력 포맷 분기 없음 — `Document` IR 포맷 독립. AC-3 (HWP5 → HWPX) 회귀 가드 |
| 5 — 보존 boundary (텍스트·문단 보장, 표·그림 위임) | AC-1 (텍스트·문단 round-trip) 가 회귀 보장. AC-4 (표·그림 실문서 crash-free) 는 상류 위임 범위. 참조 무결성 위반은 `ValueError` hard-error |

## 3. 상류 재동기화 영향 분석 (`1899ef9 → ce45231c`)

spec·feat 작성 시점 pin (`1899ef9`, v0.7.12, 2026-05-18 상류) 과 GA pin
(`ce45231c`, 2026-05-27 상류) 사이 **394 commit**. 변경 규모:

| 영역 | 변경 |
|---|---|
| `src/serializer/` | +2092 / −447 (23 파일) — 16 commit 거의 전부 **HWP5 binary writeback (hwpx2hwp) 한컴 호환** (`serialize_hwp` 성숙: Form 컨트롤 byte-perfect / 각주 contract 정합 / 표 셀 배경 / EQEDIT errata) |
| `src/model/` | +1267 / −428 — event / style / table / paragraph 구조체 확장 (직렬화·렌더 내부) |
| `src/document_core/queries/rendering.rs` | +1320 — 렌더 파이프라인 |

본 baseline 이 위임하는 표면의 안정성:

- **`serialize_hwpx` 시그니처 불변** — `1899ef9` ↔ `ce45231c` 모두 `serialize_hwpx(doc: &Document) -> Result<Vec<u8>, SerializeError>`. `SerializeError` enum 구조도 동일
- **HWPX IrDiff 검증은 Stage 0 그대로** — 상류 `serializer/hwpx/roundtrip.rs` 가 여전히 카운트만 비교 (섹션 / 문단 / doc_info 리소스 / bin_data). 문단 텍스트 내용은 미비교. 즉 본 baseline 의 "텍스트·문단 round-trip 보장" 은 상류 IrDiff 가 아니라 binding 자체 AC-1 이 책임
- **상류 자원 방향** — serializer 16 commit 이 HWPX writeback 검증 확장이 아니라 HWP5 binary writeback 한컴 호환에 집중. 표·그림 HWPX 의미 보존 (v0.8.0 선행조건) 은 아직 미성숙

재검증 (§ 4): 빌드 통과 + 회귀 599 passed + IR baseline byte-equal → **binding 관점 회귀 0**. model / rendering 대규모 변경은 직렬화·렌더 내부에 집중됐고 binding 이 소비하는 IR schema (`"1.1"`) 와 IR / 렌더 출력은 불변.

## 4. 호환성

| 시나리오 | 결과 |
|---|---|
| **기존 사용자 (`render_pdf` / `render_png` / `to_ir` 등)** | 변경 없음. v0.6.x 표면 모두 보존 (additive only) |
| **새 사용자 (`to_hwpx_bytes` / `export_hwpx`)** | extra 없이 즉시 사용 — 상류 `serialize_hwpx` 위임 |
| **IR schema** | `"1.1"` 불변 — writeback 은 read-only IR 표면과 독립 (AC-6) |
| **`tests/type_check_errors.py` 의 4 intentional pyright errors** | 변경 없음 |
| **test-without-extras CI skip count** | 6 유지 — `test_hwpx_writeback.py` 는 extra 무관, 항상 실행 |

**SemVer**: MINOR (0.6.1 → 0.7.0). additive only — 외부 wire format / wheel 의존성 / schema (`"1.1"`) / abi3-py310 정책 보존.

## 5. 검증

| 검사 | 결과 |
|---|---|
| `uv run maturin develop --release` (pin `ce45231c`) | OK — release 빌드 35.85s, abi3 wheel (Apple silicon) |
| `uv run pytest -m "not slow"` | **599 passed, 2 skipped, 6 deselected** — IR baseline byte-equal 포함 |
| `uv run pytest tests/test_hwpx_writeback.py` | 7 passed — AC-1 ~ AC-6 그린 |

2 skipped 는 fixture 한계 (`aift.hwp` 에 미주 / 수식 컨트롤 없음) — writeback 무관.

### AC ↔ 테스트 매핑

| AC | 테스트 |
|---|---|
| AC-1 (텍스트·문단 round-trip) | `TestRoundtripPreservation::test_text_paragraph_roundtrip` (`business_overview.hwpx`) |
| AC-2 (valid HWPX 컨테이너) | `TestContainerShape::test_to_hwpx_bytes_is_valid_container` |
| AC-3 (HWP5 → HWPX 변환) | `TestContainerShape::test_hwp5_input_converts_to_hwpx_container` |
| AC-4 (표·그림 실문서 crash-free) | `TestContainerShape::test_table_document_serializes_without_crash` (`table-vpos-01.hwpx`) |
| AC-5 (`export_hwpx` 파일 + 바이트 수 / 부모 부재 OSError) | `TestExportHwpx::test_export_writes_file_and_returns_byte_count` + `test_export_to_missing_parent_raises_oserror` |
| AC-6 (additive, 부작용 없음) | `TestAdditiveNoSideEffects::test_writeback_does_not_mutate_existing_surfaces` |

6/6 AC 충족.

## 6. 알려진 한계 / 이월 사항

| 항목 | 상태 | 후속 |
|---|---|---|
| HWP5 binary writeback (`to_hwp_bytes` / `export_hwp`) | 본 baseline 미노출. 상류 `serialize_hwp` 는 공개 API 이며 본 sync 에서 한컴 호환 byte-perfect 수준으로 성숙 (§ 3) | spec § 영구 비목표대로 별도 minor. 상류 성숙도 반영하여 v0.9.0 앞당김은 별도 검토 |
| 표·그림·수식 round-trip 의미 보존 | baseline 은 crash-free 만 보장 (AC-4). 상류 HWPX IrDiff Stage 0 | v0.8.0 — 상류 IrDiff 확장에 lock-step |
| GIL clone-후-detach 최적화 | baseline 은 GIL 보유 (정확성 우선) | `benches/bench_gil.py` 측정이 순이득 보이면 후속 patch (v0.7.x) |
| 순수 텍스트 HWPX fixture 부재 | AC-1 은 `business_overview.hwpx` (텍스트 풍부, 표 무) 사용 — samples 에 머리말/꼬리말 도형 없는 순수 텍스트 HWPX 없음 | 검증 대상은 최상위 문단 수·텍스트 의미 보존이라 표 컨트롤 유무와 독립 |

## 7. v0.7.0 GA 절차 (인계)

본 step 이후 GA 까지의 release 절차 (CONVENTIONS § 버전 GA 후):

1. **`Cargo.toml` version bump** — 0.6.1 → 0.7.0 (완료)
2. **spec / ADR frontmatter flip** — `Draft → Frozen`, `target → ga: v0.7.0` (완료)
3. **본 `migration.md`** — 작성 즉시 Frozen + ga: v0.7.0 (CONVENTIONS § Implementation log)
4. **`docs/roadmap/README.md` 인덱스 갱신** — v0.7.0 row Frozen + 구현 로그 표 추가 (완료)
5. **`CHANGELOG.md` [0.7.0] 섹션** — 완료
6. **git tag `v0.7.0`** + GitHub Release 생성 — `publish.yml` 트리거 (Trusted Publisher OIDC) — *사용자 진행*

## 8. 참조

### 짝 페어

- spec: [docs/roadmap/v0.7.0/hwpx-writeback-baseline.md](../../roadmap/v0.7.0/hwpx-writeback-baseline.md)
- ADR: [docs/design/v0.7.0/hwpx-writeback-baseline-research.md](../../design/v0.7.0/hwpx-writeback-baseline-research.md)

### 상류

- 상류 `serialize_hwpx`: `external/rhwp/src/serializer/hwpx/mod.rs`
- 상류 직렬화 trait / 에러: `external/rhwp/src/serializer/mod.rs` (`DocumentSerializer` / `SerializeError`)
- 상류 PR #170 (HWPX Serializer — Document IR → HWPX 저장)
- submodule pin: `1899ef9` (v0.7.12) → `ce45231c` (GA pin)
