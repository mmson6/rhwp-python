---
status: Draft
description: "v0.7.0 hwpx-writeback-baseline ADR — 직렬화 source(상류 위임) / API 명명 / GIL 전략 / 보존 boundary 4개 결정의 근거"
target: v0.7.0
last_updated: 2026-05-20
---

# v0.7.0 hwpx-writeback-baseline — 설계 의사결정 리서치 요약

[v0.7.0/hwpx-writeback-baseline.md](../../roadmap/v0.7.0/hwpx-writeback-baseline.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 **4**건의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | 직렬화 source | A: 자체 직렬화 구현 / B: 상류 `serialize_hwpx` 위임 | B | upstream-first — 결함은 상류 이슈, binding 은 표면만 |
| 2 | API 표면·명명 | A: `render_hwpx` / B: `to_hwpx_bytes` + `export_hwpx` / C: `save_hwpx` | B | `render_*` 는 raster 전용, `save_*` 는 mutable 시맨틱 연상 |
| 3 | GIL 전략 | A: GIL 보유 / B: `Document` clone 후 `py.detach` | A | `DocumentCore` `!Sync` — clone 비용 미측정, 정확성 우선 |
| 4 | 보존 boundary | A: 전체 요소 보존 보장 / B: 텍스트·문단만 보장 + 상류 위임 | B | 상류 IrDiff 검증이 점진 확장 중 — 미검증 요소 보장은 거짓 약속 |

## 1. 직렬화 source

### 팩트

- 상류 `external/rhwp/src/serializer/hwpx/mod.rs:40` 이 `serialize_hwpx(doc: &Document) -> Result<Vec<u8>, SerializeError>` 를 공개 API 로 export 한다.
- `PyDocument` 는 `inner: DocumentCore` 를 보관하고 (`src/document.rs:15`), `self.inner.document()` 가 `&Document` 를 반환한다 (`src/document.rs:75` 등에서 사용). 상류 시그니처에 그대로 전달 가능.
- 본 프로젝트의 운영 원칙: `external/rhwp` 는 upstream-owned, 로컬 수정 금지 — 결함/누락은 상류 GitHub 이슈로 보고 (자체 patch / 알고리즘 복사 금지).

### 검증자 반박

- "상류 serializer 에 버그가 있으면 binding 에서 못 고치나?" → 못 고친다 (의도적). 상류 이슈/PR 로 해결한다. 자체 patch 는 유지보수 부채 + 상류와 발산하는 fork 를 만든다.
- "직렬화를 위임만 하면 binding 의 가치가 없는 것 아닌가?" → binding 의 가치는 직렬화 알고리즘 재구현이 아니라 Python 표면 / 타입 스텁 / 에러 변환 (`SerializeError` → `PyValueError` / `OSError`) / GIL 관리 / round-trip 회귀 테스트다.

### 최종 결정

B 채택. 상류 `serialize_hwpx` 를 그대로 위임 호출하고 자체 직렬화 구현은 하지 않는다. HWPX writer 결함은 상류 이슈로 보고한다.

### 1차 소스

- 상류 serializer 모듈: `external/rhwp/src/serializer/hwpx/mod.rs`, `external/rhwp/src/serializer/mod.rs`
- 상류 PR #170 (HWPX Serializer 구현 — Document IR → HWPX 저장)
- HWP5-origin Document 수용 증거 (결정 사항 §4 입력 포맷 backing): 상류 test `equation_roundtrip_from_hancom_origin_hwp_sample` (`external/rhwp/src/serializer/hwpx/mod.rs`) 가 `parse_hwp` 결과를 `serialize_hwpx` 에 직접 투입. `SerializeError::UnsupportedInput` 은 enum 에 선언만 되고 `serialize_hwpx` 경로에서 생성되지 않음 (입력 포맷 게이트 부재)

## 2. API 표면·명명

### 팩트

- 기존 `Document` 표면의 동사 관용: `render_svg` / `render_pdf` / `render_png` (시각 raster·view 산출물), `export_svg` / `export_pdf` / `export_png` (파일 저장), `to_ir` / `to_ir_json` (데이터 구조 변환) — `python/rhwp/document.py`.
- 즉 `render_*` = 픽셀/뷰 렌더, `to_*` = 데이터 변환 (메모리), `export_*` = 파일 저장의 3분 패턴이 이미 확립돼 있다.

### 검증자 반박

- "`save_hwpx` 가 사용자에게 더 직관적이지 않나?" → `save` 는 "편집한 것을 저장" 하는 mutable 시맨틱을 연상시킨다. baseline 은 편집 없는 변환이라 부정확하고, v1.0 의 mutable IR 빌더 API 와 명명이 충돌한다.
- "`render_hwpx` 는?" → `render_*` 는 픽셀/뷰 산출물 전용 의미라 ZIP+XML 포맷 직렬화에 부적합. `to_hwpx_bytes` 가 `to_ir_json` 과 같은 "구조 → 직렬 형식" 결을 따른다.

### 최종 결정

B 채택. `to_hwpx_bytes() -> bytes` (메모리) + `export_hwpx(path) -> int` (파일). 기존 `to_ir` / `export_pdf` 패턴과 정합.

### 1차 소스

- 기존 API 표면: `python/rhwp/document.py` (`render_*` / `export_*` / `to_*` 메서드군)

## 3. GIL 전략

### 팩트

- `src/document.rs:240-243` `to_ir` 주석: "GIL 해제 불가: `self.inner` (DocumentCore) 가 RefCell 캐시로 `!Sync` — closure 가 `&self` 를 캡처하면 `py.detach` 의 Ungil 바운드 불만족. parse (`from_bytes` — owned bytes) 와 `render_pdf` / `export_pdf` (owned svgs) 만 GIL 해제 가능."
- `serialize_hwpx(self.inner.document())` 는 `&self.inner` 를 캡처한다 — 위 제약에 해당해 클로저 이동 불가.
- 프로젝트 GIL 가이드: ≥1 ms Rust-side 작업은 `py.detach` 권장하되, 불확실하면 `benches/bench_gil.py` 패턴으로 측정 후 결정.

### 검증자 반박

- "ZIP 압축은 ≥1 ms 일 텐데 GIL 보유면 멀티스레드 처리량 손해 아닌가?" → 맞다. 단 `detach` 하려면 `self.inner.document().clone()` 으로 owned `Document` 를 만들어 클로저로 이동해야 한다. clone 비용 vs GIL 보유 비용은 미측정.
- "clone 후 detach 가 항상 이득인가?" → 아니다. clone 비용은 `Document` 크기에 비례 — 대형 문서면 clone 이 GIL 보유보다 비쌀 수 있다. 측정 없이 단정 불가.

### 최종 결정

A 채택. baseline 은 GIL 보유로 정확성을 우선한다. clone-후-detach 최적화는 `bench_gil.py` 측정이 순이득을 보이면 후속 patch (v0.7.x) 로 분리.

### 1차 소스

- `src/document.rs` (`to_ir` GIL 주석, `render_pdf` / `export_pdf` detach 패턴)
- 프로젝트 GIL 정책 (`AGENTS.md` § Rust + Python hybrid build)

## 4. 보존 boundary

### 팩트

- 상류 `external/rhwp/src/serializer/hwpx/section.rs:292` `render_control_slot` 이 `Table` / `Picture` / `Equation` / `Shape` 컨트롤을 emit 한다 — 표 직렬화 실패 시 `eprintln!` 후 계속 진행 (graceful degradation).
- 상류 `external/rhwp/src/serializer/hwpx/roundtrip.rs:7` IrDiff 하네스 주석: "누적 확장 — Stage 0 에선 뼈대 필드 (섹션 수·문단 수·리소스 카운트) 만 비교하고, Stage 1~5 진행 시 비교 대상 필드를 누적 확장." 즉 직렬화 코드 존재와 round-trip 검증 완료는 별개.
- `serialize_hwpx` 는 per-control 만 graceful (`section.rs` 의 `eprintln!`) 하고, 참조 무결성은 hard-error 다: `BinDataContent 누락` (`hwpx/mod.rs:86-93`) / `assert_all_refs_resolved()` / `assert_bin_data_3way()` 가 `Err(SerializeError)` 를 반환 → binding 에서 `ValueError` 로 전파. 보존 boundary 는 "무조건 crash-free" 가 아니라 "per-control graceful + 무결성 hard-error" 모델.

### 검증자 반박

- "표가 직렬화되는데 왜 보존을 보장하지 않나?" → 직렬화 코드 존재 ≠ round-trip 의미 보존 검증 완료. 상류가 IrDiff 로 검증한 범위 밖을 우리가 보장하면 거짓 약속이 된다.
- "그럼 baseline 의 실용 가치가 텍스트뿐인가?" → 텍스트·문단 round-trip + HWP5 → HWPX 포맷 변환 + 표·그림 포함 실문서 crash-free 직렬화. 메타 정정 / 평문 교정 / 포맷 마이그레이션 시나리오를 커버한다.

### 최종 결정

B 채택. 텍스트·문단 round-trip 을 회귀로 보장하고, 표·그림 등은 상류 보존 범위에 위임 (crash-free 만 보장). 의미 보존 확장은 상류 IrDiff 진척에 맞춰 v0.8.0.

### 1차 소스

- 상류 직렬화/검증: `external/rhwp/src/serializer/hwpx/section.rs`, `external/rhwp/src/serializer/hwpx/roundtrip.rs`

## 참조

- 짝 페어 (spec): [roadmap/v0.7.0/hwpx-writeback-baseline.md](../../roadmap/v0.7.0/hwpx-writeback-baseline.md)
- 상류 PR #170 (HWPX Serializer) / `edwardkim/rhwp` `serializer/hwpx/` 모듈
