---
status: Draft
description: "v0.8.0 — HWPX writeback round-trip 검증 표면 'verify_hwpx_roundtrip' 추가 + 보존 boundary 를 상류 'diff_documents' 검증 범위로 확대"
target: v0.8.0
last_updated: 2026-06-21
---

# v0.8.0 — HWPX writeback round-trip 검증 (보존 boundary 확대)

v0.7.0 이 연 `export_hwpx` / `to_hwpx_bytes` 의 round-trip 보존 boundary 를 텍스트·문단에서 상류 `diff_documents` 가 실제 비교하는 필드 집합까지 확대하고, 사용자가 저장 충실도를 프로그램으로 확인하는 `Document.verify_hwpx_roundtrip()` 검증 표면을 추가한다. v0.7.0 은 상류 round-trip 비교가 카운트만 보던 시점이라 텍스트·문단만 보장했으나, 그 사이 비교가 char_shape·lineseg·표/그림 구조까지 확대되고 진단 도구 (`diff_documents`) 가 공개 API 로 노출되면서 boundary 확대 조건이 성립했다. 직렬화·진단 모두 상류 위임 — 추가만 있고 기존 표면 보존, IR schema (`"1.1"`) 변경 없음.

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [hwpx-writeback-expansion-research.md](../../design/v0.8.0/hwpx-writeback-expansion-research.md).

## 배경

v0.7.0 baseline 은 상류 `serialize_hwpx` 를 노출했으나 round-trip 의미 보존은 텍스트·문단만 회귀로 보장하고 표·그림은 "crash-free + 상류 위임" 으로 남겼다. 그 boundary 의 원인은 상류 검증 성숙도였다 — 당시 상류 round-trip 비교가 섹션·문단·리소스 카운트만 봤다. "직렬화 코드 존재 ≠ round-trip 검증 완료" 라 미검증 요소를 보장하면 거짓 약속이 된다는 것이 v0.7.0 의 보수적 판단이었다.

그 사이 상류 `diff_documents` (round-trip 비교 함수) 가 비교 대상을 확대했다. **비교하는 것**: 문단 char_shape 시퀀스, lineseg, 인라인 컨트롤 슬롯 타입, 섹션 PageDef, 표 cell 내용 (셀 문단) + 캡션 + page_break, 그림 크기 요소 (curSz/imgRect/imgDim) + 캡션, 리소스·BinData 엔트리 카운트. **비교하지 않는 것**: 수식 script (description 만 비교), 표 cell 의 rowspan/colspan, BinData 실제 byte (count 만), 도형 raw byte. 동시에 진단 도구가 공개 API 가 됐다: `diff_documents(a, b) -> IrDiff`, `pub struct IrDiff` / `pub enum IrDifference`.

주의 — 상류 모듈 주석의 "Stage N" 은 *serializer 가 무엇을 emit 하는지* 의 단계 (Stage 3 표 / Stage 4 그림+BinData) 이지 *round-trip 이 무엇을 검증하는지* 가 아니다. 본 spec 의 보장 범위는 stage 라벨이 아니라 `diff_documents` 코드가 실제 비교하는 필드 집합으로 정의한다.

따라서 v0.8.0 은 (1) 보존 boundary 를 `diff_documents` 가 실제 검증하는 필드 집합으로 확대하고, (2) `diff_documents` 를 `verify_hwpx_roundtrip()` 로 노출해 사용자가 자기 문서의 저장 손실을 검출하게 하며, (3) 그 범위의 round-trip 을 binding 회귀로 가드한다. `diff_documents` 가 비교하지 않는 요소 (수식 script / cell span / BinData byte / 도형 raw) 는 보장 범위 밖 — 상류 비교 확대에 의존하며 본 spec 비목표.

## 결정 사항

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — 보존 boundary 확대 | 텍스트·문단 → `diff_documents` 검증 필드 집합 (표 cell 내용·캡션·page_break, 그림 크기·캡션, char_shape·lineseg, PageDef, 리소스·BinData 카운트) | 보장 범위 = 상류가 *실제 round-trip 비교* 하는 것으로 한정. 직렬화 emit ≠ 검증 완료 (v0.7.0 ADR 교훈). 미비교 요소는 비목표. 자세한 본체 비교는 ADR §1 |
| 2 — 검증 표면 노출 | `verify_hwpx_roundtrip()` 추가 (상류 `diff_documents` 위임) | 상류 진단 도구 공개 API 화. 사용자가 자기 문서의 저장 손실을 실측. 노출 vs 미노출 비교는 ADR §2 |
| 3 — verify 반환 타입 | 경량 리포트 (`ok: bool` + `differences: list[str]`, 불변 `ok == not differences`) | `IrDifference` variant 가 상류 Stage 진행마다 증가 — 전체 Pydantic 매핑은 매 sync 깨짐. 사람 가독 문자열이 forward-compatible. 자세한 본체 비교는 ADR §3 |
| 4 — round-trip 비교 기준 | `diff_documents(현재 Document, reparse)` | 이미 parse 된 `Document` 가 SSOT — bytes 재파싱은 원본 대비가 아닌 자기 출력의 round-trip 측정. 자세한 본체 비교는 ADR §4 |
| 5 — GIL 전략 | baseline GIL 보유 | `diff_documents(self.inner.document(), ..)` 가 `&self.inner` 캡처 — `DocumentCore` 가 `!Sync`. v0.7.0 결정 3 일관, clone-후-detach 는 측정 후 후속 |

## 인수조건

- **AC-1** — 표 (cell 텍스트 내용·캡션) 와 그림 (크기 요소·캡션) 을 포함한 HWPX 문서를 parse → `export_hwpx(out)` → `parse(out)` 했을 때, 재파싱 결과가 원본과 상류 `diff_documents` 기준 차이 없이 동등하다
- **AC-2** — round-trip 보존되는 문서에서 `verify_hwpx_roundtrip()` 는 `ok == True` 이고 `differences == []` 를 반환하며, 반환 리포트는 `ok == (len(differences) == 0)` 불변을 만족한다
- **AC-3** — `verify_hwpx_roundtrip()` 의 `differences` 각 항목은 차이 종류·위치를 담은 사람 가독 문자열이다 (상류 `IrDifference` 의 문자열화). round-trip 차이가 없으면 빈 리스트
- **AC-4** — `verify_hwpx_roundtrip()` 호출은 부작용이 없다 — 호출 후 `to_ir()` / `to_hwpx_bytes()` / `render_*` 등 기존 메서드 결과가 변하지 않는다
- **AC-5** — `verify_hwpx_roundtrip()` 의 직렬화 실패 (참조 무결성 위반 — BinData 누락 등) 는 `ValueError` 로 전파된다 (v0.7.0 `export_hwpx` 와 동일 에러 계약)
- **AC-6** — v0.7.0 의 텍스트·문단 round-trip 보장이 회귀하지 않는다 (기존 baseline AC 유지)

AC-3 negative path 주: 현 상류 HWPX 샘플은 round-trip 차이 0 (xfail 없음) 이고 binding 은 read-only `Document` 만 노출하므로, "차이를 보고하는" negative 케이스를 자연 발생 fixture 로 강제하기 어렵다. 차이를 내는 문서가 확보되면 negative 회귀를 추가하고, 그 전까지는 `ok == not differences` 불변 + positive 보존 케이스로 검증한다.

## 영구 비목표

- **수식 script round-trip 보장** — 상류 `diff_documents` 가 equation 을 description 만 비교하고 script 는 비교하지 않는다 (ObjectComment 경로). script 보장은 상류 비교 확대 (이슈) 에 의존
- **표 cell rowspan/colspan 보존 보장** — 상류 `diff_documents` 의 cell 비교가 셀 문단 (내용) 만 재귀하고 span 구조는 비교하지 않는다. span 보장은 상류 비교 확대에 의존
- **BinData byte 단위 보존 보장** — 상류는 BinData 엔트리 *count* 만 비교. byte 동일성은 비목표
- **도형 (shape) raw byte 의미 보존 보장** — 상류 `IrDiffAllow.shape_raw` 가 선언만 되고 미사용 (Stage 5 미완). 도형·OLE·차트 보장은 상류 진행 의존
- **byte-wise 동일성** — round-trip 은 의미적 동등성 기준 (v0.7.0 비목표 계승). ZIP 압축 / 타임스탬프 / canonical default 주입으로 byte 단위 동일은 보장하지 않는다
- **HWP5 binary 출력 (`export_hwp` / `verify_hwp_roundtrip`)** — 상류 `serialize_hwp` 는 성숙했으나 본 spec 은 HWPX 만. HWP5 binary writeback 은 v0.9.0
- **IR mutable 편집 후 재저장** — `Document` 는 parse 결과 read-only. IR 편집 빌더 API 는 v1.0 API 안정 선언 시점
- **verify 표면의 CLI / MCP 노출** — SDK 표면 (`Document` 메서드) 만. `rhwp-py` 서브명령 / MCP 도구 노출은 별도 demand 시 후속

## 참조

- 짝 페어 (ADR): [hwpx-writeback-expansion-research.md](../../design/v0.8.0/hwpx-writeback-expansion-research.md)
- 상류 round-trip 진단: `external/rhwp/src/serializer/hwpx/roundtrip.rs` (`diff_documents` / `IrDiff` / `IrDifference`)
- 상류 HWPX serializer: `external/rhwp/src/serializer/hwpx/` (`serialize_hwpx`)
