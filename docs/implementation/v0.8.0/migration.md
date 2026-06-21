---
status: Frozen
description: "v0.8.0 구현 로그 — HWPX writeback round-trip 검증 (verify_hwpx_roundtrip + RoundtripReport). 보존 boundary 를 상류 diff_documents 검증 필드로 확대. 직렬화·진단 상류 위임. 구현 중 발견한 도형 shapeComment 누락은 상류 #1451 등록."
ga: v0.8.0
last_updated: 2026-06-21
---

# v0.8.0 — HWPX writeback round-trip 검증 (구현 로그)

[v0.8.0/hwpx-writeback-expansion](../../roadmap/v0.8.0/hwpx-writeback-expansion.md) (spec) +
[design/v0.8.0/hwpx-writeback-expansion-research](../../design/v0.8.0/hwpx-writeback-expansion-research.md)
(ADR) 의 구현 결과 로그. 결정의 근거·옵션 비교는 ADR 가 보유 — 본 문서는
*산출물 / 검증 결과 / 호환성 / 이월 사항* 만 기록한다.

MINOR release. 단일 세션 규모 (Rust 1 메서드 + Python wrapper·모델 + 테스트 7) 로
단일 `migration.md` 채택.

## 1. 산출물

### Rust 신규

| 파일 / 위치 | 변경 |
|---|---|
| [src/document.rs](../../../src/document.rs) | `PyDocument::verify_hwpx_roundtrip(&self) -> PyResult<(bool, Vec<String>)>` 1 #[pymethods] 신규. `serialize_hwpx` → `DocumentCore::from_bytes` 재파싱 → `serializer::hwpx::roundtrip::diff_documents` → `IrDifference` Display 문자열화. 직렬화·재파싱 실패 → `PyValueError` (`to_hwpx_bytes` 와 동일 계약). GIL 보유 (§ 2 결정 5). raw `(ok, differences)` tuple 반환 — Python wrapper 가 리포트로 감쌈 |

### Python 신규

| 파일 / 위치 | 변경 |
|---|---|
| [python/rhwp/document.py](../../../python/rhwp/document.py) | `RoundtripReport` BaseModel (`frozen=True` / `extra="forbid"`, `ok: bool` + `differences: list[str]`) + `Document.verify_hwpx_roundtrip() -> RoundtripReport` wrapper. 불변 `ok == (not differences)` 는 Rust 가 `(differences.is_empty(), differences)` 로 구조적 보장 |
| [python/rhwp/_rhwp.pyi](../../../python/rhwp/_rhwp.pyi) | `_Document.verify_hwpx_roundtrip(self) -> tuple[bool, list[str]]` stub |
| [python/rhwp/__init__.py](../../../python/rhwp/__init__.py) / [__init__.pyi](../../../python/rhwp/__init__.pyi) | `RoundtripReport` public export (`rhwp.RoundtripReport`) |

### 테스트

| 파일 | 변동 | 책임 |
|---|---|---|
| [tests/test_hwpx_writeback.py](../../../tests/test_hwpx_writeback.py) | +7 테스트 | `TestExpansionTableAndPicture` (AC-1, `aift.hwpx`) / `TestVerifyReport` (AC-2, AC-3 positive+negative) / `TestVerifyNoSideEffects` (AC-4) / `TestVerifyErrorContract` (AC-5) / `TestV070GuaranteeIntact` (AC-6). per-test `pytest.mark.spec("v0.8.0/hwpx-writeback-expansion#AC-N")`. 상류 `diff_documents` 위임이라 extra 무관 — 항상 실행 (test-without-extras skip count 무관) |

### 문서 / 상류

| 파일 | 변경 |
|---|---|
| [CHANGELOG.md](../../../CHANGELOG.md) | `[0.8.0]` 섹션 — Added (verify + RoundtripReport) / Build (상류 pin sync) |
| [docs/upstream/issue-hwpx-shapecomment-drawing-shapes.md](../../upstream/issue-hwpx-shapecomment-drawing-shapes.md) | 상류 [#1451](https://github.com/edwardkim/rhwp/issues/1451) 등록 — legacy 도형 (ellipse/arc/polygon/curve) shapeComment 미직렬화 보고. 구현 중 negative fixture 로 발견, 제안 패치 round-trip diff 0 실측 후 원복 |
| spec / ADR | frontmatter `Draft → Frozen`, `target → ga: v0.8.0` |
| [docs/traces/coverage.md](../../traces/coverage.md) | 7 v0.8.0/hwpx-writeback-expansion#AC-N row (테스트 marker 기반 자동 갱신) |

### Build

| 파일 / 위치 | 변경 |
|---|---|
| [Cargo.toml](../../../Cargo.toml) | version 0.7.0 → 0.8.0 (`pyproject.toml` 은 `dynamic` 자동 추종) |
| `external/rhwp` pin | `ce45231c` (v0.7.12+394) → `7d9aae7f` (v0.7.16+36) — `[Unreleased]` 에서 흡수, 본 release 에 동승 |

## 2. 결정 사항 (spec 결정 5 항목 ↔ 구현 매핑)

| spec 결정 | 구현 위치 |
|---|---|
| 1 — 보존 boundary 확대 | verify 가 `diff_documents` 위임 — 표 cell 내용·캡션·page_break, 그림 크기·캡션, char_shape·lineseg, PageDef, 리소스·BinData count. 미비교 요소 (수식 script / cell span / BinData byte / 도형 raw) 는 비목표 |
| 2 — 검증 표면 노출 | `Document.verify_hwpx_roundtrip()` 공개 + `rhwp.RoundtripReport` export |
| 3 — verify 반환 타입 | `RoundtripReport` (`ok` + `differences` str list). 상류 `IrDifference` variant 증가에 forward-compatible 한 문자열 출고 |
| 4 — round-trip 비교 기준 | `diff_documents(self.inner.document(), reparsed.document())` — 현재 Document 가 SSOT |
| 5 — GIL 전략 | 보유 — `diff_documents` 첫 인자가 `&self.inner` 캡처, `DocumentCore` 가 `!Sync` (`to_ir` / `to_hwpx_bytes` 와 동일 제약) |

## 3. 호환성

| 시나리오 | 결과 |
|---|---|
| **기존 사용자** | 변경 없음 — v0.7.x 표면 모두 보존 (additive only) |
| **새 사용자 (`verify_hwpx_roundtrip`)** | extra 없이 즉시 사용 — 상류 `diff_documents` 위임 |
| **IR schema** | `"1.1"` 불변 — verify 는 read-only IR 표면과 독립 |
| **`tests/type_check_errors.py` 의 4 intentional pyright errors** | 변경 없음 |
| **test-without-extras CI skip count** | 6 유지 — `test_hwpx_writeback.py` 는 extra 무관, 항상 실행 |

**SemVer**: MINOR (0.7.0 → 0.8.0). additive only — wire format / wheel 의존성 / schema (`"1.1"`) / abi3-py310 정책 보존.

## 4. 검증

| 검사 | 결과 |
|---|---|
| `uv run maturin develop --release` | clean (release 빌드, abi3 wheel) |
| `cargo clippy --all-targets -- -D warnings` | clean |
| `uv run pytest -m "not slow"` | **606 passed / 2 skipped / 6 deselected** (v0.7.0 599 → +7) |
| `uv run pytest tests/test_view_baseline.py` | 2/2 byte-equal 유지 |
| `lint_docs docs/` | 0 위반 |
| 별도 컨텍스트 코드 리뷰 | 정합 — critical/high/medium 0 건 |

### AC ↔ 테스트 매핑

| AC | 테스트 |
|---|---|
| AC-1 (표·그림 round-trip 동등) | `TestExpansionTableAndPicture::test_table_and_picture_roundtrip_equivalent` (`aift.hwpx` — 표·그림 카운트 보존 + verify ok) |
| AC-2 (보존 문서 ok + 불변) | `TestVerifyReport::test_preserved_document_is_ok_with_invariant` |
| AC-3 (사람 가독 differences) | `test_preserved_document_differences_are_empty_str_list` (positive) + `test_lossy_document_reports_human_readable_differences` (negative — `table-vpos-01.hwpx` 도형 shapeComment 손실) |
| AC-4 (부작용 없음) | `TestVerifyNoSideEffects::test_verify_does_not_mutate_existing_surfaces` |
| AC-5 (직렬화 실패 ValueError 계약) | `TestVerifyErrorContract::test_serializable_document_passes_verify_serialization` |
| AC-6 (v0.7.0 텍스트·문단 보장 유지) | `TestV070GuaranteeIntact::test_text_paragraph_guarantee_holds_under_verify` |

6/6 AC 충족.

## 5. 알려진 한계 / 이월 사항

| 항목 | 상태 | 후속 |
|---|---|---|
| 도형 (polygon/ellipse/arc/curve) shapeComment round-trip | 상류 serializer 가 `render_common_shape_xml` 경로에서 미직렬화. verify 가 검출 (`table-vpos-01.hwpx` negative fixture). spec 영구 비목표 (도형 보존 = 상류 진행 의존) | 상류 [#1451](https://github.com/edwardkim/rhwp/issues/1451) 등록 (제안 패치 round-trip diff 0 실측). 상류 반영 시 negative fixture 갱신 |
| 수식 script / 표 cell rowspan-colspan / BinData byte | 상류 `diff_documents` 미비교 | spec 영구 비목표 — 상류 비교 확대 의존 |
| GIL clone-후-detach 최적화 | baseline 은 GIL 보유 (정확성 우선) | `benches/bench_gil.py` 측정이 순이득 보이면 후속 patch |

## 6. v0.8.0 GA 절차 (인계)

본 step 이후 GA 까지의 release 절차 (CONVENTIONS § 버전 GA 후):

1. **`Cargo.toml` version bump** — 0.7.0 → 0.8.0 (완료, `pyproject.toml` 은 `dynamic` 추종)
2. **spec / ADR frontmatter flip** — `Draft → Frozen`, `target → ga: v0.8.0` (완료)
3. **본 `migration.md`** — 작성 즉시 Frozen + ga: v0.8.0 (완료)
4. **`docs/roadmap/README.md` 인덱스 갱신** — v0.8.0 row Frozen + 구현 로그 표 추가 (완료)
5. **`CHANGELOG.md` [0.8.0] 섹션** — 완료
6. **PR** feature/v0.8.0 → main → merge
7. **git tag `v0.8.0`** + GitHub Release 생성 (published) — `publish.yml` 트리거 (Trusted Publisher OIDC) — *사용자 진행*

## 7. 참조

### 짝 페어

- spec: [docs/roadmap/v0.8.0/hwpx-writeback-expansion.md](../../roadmap/v0.8.0/hwpx-writeback-expansion.md)
- ADR: [docs/design/v0.8.0/hwpx-writeback-expansion-research.md](../../design/v0.8.0/hwpx-writeback-expansion-research.md)

### 상류

- round-trip 진단: `external/rhwp/src/serializer/hwpx/roundtrip.rs` (`diff_documents` / `IrDiff` / `IrDifference`)
- HWPX serializer: `external/rhwp/src/serializer/hwpx/` (`serialize_hwpx`)
- 관련 이슈: [edwardkim/rhwp#1451](https://github.com/edwardkim/rhwp/issues/1451) (legacy 도형 shapeComment 미직렬화)
- submodule pin: `7d9aae7f` (v0.7.16+36)
