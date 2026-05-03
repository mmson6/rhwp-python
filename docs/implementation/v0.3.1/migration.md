---
status: Frozen
description: "v0.3.1 구현 로그 — inline 컨트롤 마커의 'char_start'/'char_end' null 출고 정정. 상류 v0.7.8 'Paragraph::control_text_positions()' 직접 호출"
ga: v0.3.1
last_updated: 2026-05-03
---

# v0.3.1 — inline 컨트롤 마커 char offset 출고 (구현 로그)

[v0.3.1/ir-marker-char-offset](../../roadmap/v0.3.1/ir-marker-char-offset.md) (spec) + [design/v0.3.1/ir-marker-char-offset-research](../../design/v0.3.1/ir-marker-char-offset-research.md) (ADR) 의 구현 결과 로그. 결정의 근거·옵션 비교는 ADR 가 보유 — 본 문서는 *산출물 / 검증 결과 / 호환성 / 이월 사항* 만 기록한다 (CONVENTIONS § CHANGELOG ↔ implementation log 역할 분리).

PATCH release. 단일 세션 규모로 단일 `migration.md` 채택 (CONVENTIONS § implementation log 구조 — "작은 작업 (단일 세션·수일 규모) 은 단일 migration.md").

## 1. 산출물

### Rust 코어 (`src/ir.rs`)

| 항목 | 변경 |
|---|---|
| `assert_position_invariant` 헬퍼 신규 | `controls.len() == positions.len()` 을 `assert_eq!` (release-active) 로 가드. 상류 `control_text_positions()` contract 위반 시 panic |
| `build_raw_paragraph` | paragraph 당 1회 `para.control_text_positions()` 호출 → `Vec<usize>` 결과를 controls iteration 과 `zip` |
| `collect_furniture_from_paragraph` | 동일 `Vec<usize>` 를 인자로 받아 footnote/endnote marker char offset 채움. 중복 호출 회피 |
| `RawTable` / `RawPicture` / `RawFormula` / `RawField` / `RawToc` | `char_offset: Option<usize>` 필드 추가 |
| `RawFootnote` / `RawEndnote` | `marker_char_offset: Option<usize>` 필드 추가 |
| Rust 단위 테스트 | `#[should_panic]` 테스트 + 정상 zero-width 케이스 — release/debug 무관 panic 보증의 source-level 가드 |

### Python mapper (`python/rhwp/ir/_mapper.py`)

| 함수 | 변경 |
|---|---|
| `_build_table_block` / `_build_picture_block` / `_build_formula_block` / `_build_field_block` / `_build_toc_block` | `raw.char_offset` (`int \| None`) → `Provenance.char_start = char_end = char_offset` (zero-width 복제). `None` → 양쪽 슬롯 `None` 폴백 |
| `_build_footnote_block` / `_build_endnote_block` | `raw.marker_char_offset` 을 `marker_prov.char_start/char_end` 양쪽 슬롯에 동일 복제. `prov` (블록 자체 위치) 도 marker 와 같은 위치 공유 (각주/미주는 본문 paragraph 안 마커 위치 = 블록 위치) |

### Python raw types (`python/rhwp/ir/_raw_types.py`)

7 종 raw struct (`RawTable` / `RawPicture` / `RawFormula` / `RawField` / `RawToc` / `RawFootnote` / `RawEndnote`) 의 Pydantic 모델에 `char_offset` 또는 `marker_char_offset: int | None = None` 필드 추가. PyO3 `#[pyo3(get)]` 와 1:1 mirror.

### Schema / IR 모델

변경 없음. `Provenance.char_start: int | None` / `char_end: int | None` 은 이미 v1.1 에 정의 (v0.3.0 에서 슬롯만 만들어두고 `None` 으로만 출고). v0.3.1 은 *이미 있는 슬롯에 non-null 값을 흘리는* 변경이라 schema bump 불필요. `CURRENT_SCHEMA_VERSION = "1.1"` 유지.

### Submodule pin

`external/rhwp` `033617e` (v0.7.7) → `0fb3e67` (post-v0.7.8). enabling commit 은 v0.7.8 의 `cee3c1e` (PR #405 머지) — `pub fn Paragraph::control_text_positions` GA. 후속 sync `8482555` 은 직교 영역 (Task #484 `utf16_pos_to_char_idx`) 으로 본 PATCH 동작에 영향 없음.

### 테스트

| 파일 | 변경 |
|---|---|
| [tests/test_v0_3_1_marker_char_offset.py](../../../tests/test_v0_3_1_marker_char_offset.py) | 신규. AC-1 ~ AC-14 회귀 가드 (mapper 단위 + real fixture 통합) |
| `tests/test_ir_caption.py` / `test_ir_field.py` / `test_ir_footnote.py` / `test_ir_formula.py` / `test_ir_furniture.py` / `test_ir_mapper.py` / `test_ir_picture.py` / `test_ir_schema_export.py` / `test_ir_toc.py` | 기존 v0.3.0 테스트의 raw struct 생성자에 신규 `char_offset` / `marker_char_offset` 필드 추가 (Pydantic strict — 명시 필요). 일부 파일에 `pytest.mark.spec("v0.3.1/ir-marker-char-offset")` marker 추가 (trace report 매핑) |

### 메타

| 파일 | 변경 |
|---|---|
| [Cargo.toml](../../../Cargo.toml) | `version = "0.3.0"` → `"0.3.1"` (Cargo.toml 이 SSOT — `pyproject.toml` 의 `dynamic = ["version"]` 가 여기를 읽음) |
| [CHANGELOG.md](../../../CHANGELOG.md) | `[0.3.1] — 2026-05-02` 섹션 신설 (Fixed / Build / Known limitations) |
| [.github/workflows/ci.yml](../../../.github/workflows/ci.yml) | pyright scope list 에 `tests/test_v0_3_1_marker_char_offset.py` 추가 |
| [docs/traces/coverage.md](../../../docs/traces/coverage.md) | trace report 자동 갱신 — v0.3.1 spec 의 22개 테스트 매핑 (AC-1 ~ AC-14 + 파일 레벨 marker) |

## 2. 호환성

| 시나리오 | 결과 |
|---|---|
| 기존 consumer 가 `prov.char_start is None` 분기 처리 | 그대로 작동. `None` 케이스 (`char_offsets.is_empty()` paragraph) 는 여전히 발생 — fail-safe 폴백 (spec § 결정 3) |
| 기존 consumer 가 `prov.char_start` 를 정수로 직접 사용 | v0.3.0 까지 항상 `None` 이라 사실상 사용 불가했음. v0.3.1 부터 일부 케이스에 정수 출고 — 신규 capability |
| Schema validator (`hwp_ir_v1.json` 또는 content-addressed alias) | 변경 없음. `anyOf [integer, null]` 정의가 그대로 매칭 |
| JSON serialization round-trip | `int` 값 보존 — `HwpDocument.model_validate_json(ir.model_dump_json())` 동등 (AC-10) |
| API surface diff | 없음. 슬롯 채움이 유일한 외부 가시 변경 |

**SemVer**: PATCH (0.3.0 → 0.3.1). API surface 미변경 + schema 미변경 + 기존 분기 작동 — strict backward-compat.

## 3. 검증

| 검사 | 결과 |
|---|---|
| `cargo clippy --all-targets -- -D warnings` | clean |
| `uv run pytest -m "not slow"` (전체) | 246 passed, 2 skipped (`test_ir_footnote.py:345` 의 미주 케이스 + `test_ir_formula.py:310` 의 수식 케이스 — `aift.hwp` 샘플에 해당 컨트롤 부재. 합성 fixture 미도입 결정 = AC-14) |
| `uv run pytest tests/test_v0_3_1_marker_char_offset.py -v` | 22 passed (AC-1 ~ AC-14 회귀 가드 전부 그린) |
| Real fixture e2e (`aift.hwp`) | TableBlock 96 (5 populated, 91 None) / PictureBlock 14 (1 populated, 13 None) / FieldBlock 4 (4 populated, 0 None) / FootnoteBlock 1 (1 populated, char_start=333) — 모든 populated 케이스 `char_start == char_end` invariant 준수 |
| Real fixture e2e (`table-vpos-01.hwpx`) | TableBlock 11 / PictureBlock 4 모두 `None` 폴백 (HWPX 샘플은 char_offsets 빈 paragraph 비율 더 높음). FieldBlock 1 populated. 폴백 경로 회귀 가드로서 의미 큼 |
| Cargo 빌드 | `maturin develop --release` 성공. abi3-py310 wheel 단일 산출물 (Python 3.10–3.13+ 커버) 유지 |

## 4. 이월 사항

다음 항목은 v0.3.1 범위 밖. spec § 영구 비목표 가 정확한 목록 — 본 절은 *우선순위가 높은 다음 후보* 만 추림.

| 항목 | 후속 |
|---|---|
| 중첩 표 안 inline 컨트롤의 `(section_idx, para_idx)` ↔ `char_offset` 의미축 mismatch (외부 paragraph vs 셀 내부 paragraph) | v0.3.0 부터 있던 Provenance 모델 한계. v0.4.0+ Provenance 정정 spec 별도 |
| `HwpField.cached_value` 추출 (위치는 v0.3.1 에서 채웠으나 *값* 미추출) | `field_ranges` 매핑 필요. 별도 spec |
| `Block.order: int` 필드 — controls 의 시각 순서 보존 | v0.4.0+ 검토. 현 모델은 IR `paragraphs` 배열 등장 순서 = controls 등장 순서로 묵시적 처리 |

## 5. 참조

### 짝 페어

- spec: [docs/roadmap/v0.3.1/ir-marker-char-offset.md](../../roadmap/v0.3.1/ir-marker-char-offset.md)
- ADR: [docs/design/v0.3.1/ir-marker-char-offset-research.md](../../design/v0.3.1/ir-marker-char-offset-research.md)

### 상류

- enabling PR: <https://github.com/edwardkim/rhwp/pull/405> (Task #390 — `pub fn Paragraph::control_text_positions`)
- enabling commit: `cee3c1e` (v0.7.8 GA)
- 자체 등록 이슈 초안 (옵션 A 채택의 출처): [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) — 상류 머지로 RESOLVED 전환 또는 archive 대상
