---
status: Frozen
description: "v0.8.0 hwpx-writeback-expansion ADR — 보존 boundary 확대 / verify 표면 노출 / 반환 타입 / 비교 기준 / GIL 5개 결정의 근거"
ga: v0.8.0
last_updated: 2026-06-21
---

# v0.8.0 hwpx-writeback-expansion — 설계 의사결정 리서치 요약

[v0.8.0/hwpx-writeback-expansion.md](../../roadmap/v0.8.0/hwpx-writeback-expansion.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 **5**건의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | 보존 boundary 확대 | A: 텍스트·문단 유지 / B: `diff_documents` 검증 필드로 확대 / C: 직렬화되는 전체 요소 보장 | B | 보장 = 상류가 *실제 round-trip 비교* 하는 것. 직렬화 emit ≠ 검증 |
| 2 | 검증 표면 노출 | A: 미노출 (내부 회귀 테스트만) / B: `verify_hwpx_roundtrip()` 노출 | B | 상류 진단 공개 API — 사용자가 자기 문서 손실 검출 |
| 3 | verify 반환 타입 | A: `bool` / B: 경량 리포트 (ok + str list) / C: 전체 `IrDifference` Pydantic | B | bool 은 진단 정보 부족, C 는 상류 enum 증가에 fragile |
| 4 | round-trip 비교 기준 | A: `roundtrip_ir_diff(bytes)` / B: `diff_documents(현재, reparse)` | B | 이미 parse 된 `Document` 가 SSOT — bytes 재파싱은 자기 출력의 round-trip |
| 5 | GIL 전략 | A: GIL 보유 / B: clone 후 `py.detach` | A | `&self.inner` 캡처 (`!Sync`), v0.7.0 결정 3 일관, clone 비용 미측정 |

## 1. 보존 boundary 확대

### 팩트

- v0.7.0 spec 결정 5 / 영구 비목표: "표·그림·수식 round-trip 의미 보존 보장" 을 v0.8.0 으로 분리. 당시 사유는 상류 round-trip 비교가 카운트만 보던 점.
- 상류 `diff_documents` (`external/rhwp/src/serializer/hwpx/roundtrip.rs:427`) 가 **비교하는 것**: 문단 char_shape 시퀀스 (`ParagraphCharShapes`), 컨트롤 슬롯 타입 (`ParagraphControls`), lineseg (`ParagraphLinesegs`), 섹션 PageDef (`SectionPageDef`), 표 cell 내용 — 셀 문단 char_shape 재귀 (`roundtrip.rs:939`) + 표 캡션 (`TableCaption`, `roundtrip.rs:947`) + page_break (`roundtrip.rs:931`), 그림 크기 요소 (`diff_picture_size`, `roundtrip.rs:369`) + 그림 캡션, 리소스·BinData 엔트리 카운트 (`BinDataContentCount`, `roundtrip.rs:513`).
- 상류 `diff_documents` 가 **비교하지 않는 것**: 수식 script — `roundtrip.rs:1002` 주석 "equation 은 본문 텍스트 비교 대상이 아니므로 description 만 동승" (`ObjectComment` 만 push). 표 cell rowspan/colspan — 셀 루프가 `cea.paragraphs` 만 재귀 (`roundtrip.rs:939`), `col_span`/`row_span` 은 테스트 fixture 에만 등장. BinData byte — count 만. 도형 raw byte — `IrDiffAllow.shape_raw` 가 선언만 되고 미사용 (`roundtrip.rs:78`, `allowed()` 가 `_allow` 로 무시).
- 상류 모듈 주석의 "Stage N" (`external/rhwp/src/serializer/hwpx/mod.rs:4-9`) 은 serializer emit 단계 (Stage 3 표 / Stage 4 그림+BinData / Stage 5 도형) — round-trip 검증 수준이 아니다. 검증 범위는 `diff_documents` 코드가 정의한다.

### 검증자 반박

- "직렬화되는 표·그림을 왜 전부 보장하지 않나?" → 직렬화 emit ≠ round-trip 검증 완료. `diff_documents` 가 비교하는 것만 binding 회귀로 *실측* 가능하다. 미비교 요소 (수식 script / cell span / byte) 를 보장하면 v0.7.0 ADR 이 경계한 "거짓 약속" (`design/v0.7.0/hwpx-writeback-baseline-research.md:96`) 을 반복한다.
- "상류가 Stage 4 에 도달했다던데 표·그림 다 되는 것 아닌가?" → "Stage 4" 는 serializer 가 그림+BinData 를 *emit* 하는 단계지 round-trip 검증 범위가 아니다. 둘은 별개 — 검증은 `diff_documents` 코드가 비교하는 필드로만 정의된다.
- "수식·span 을 빼면 '의미 보존' 이라 부를 수 있나?" → 그래서 spec 제목을 "round-trip 검증 (boundary 확대)" 로 두고, 보장을 `diff_documents` 범위로 정직하게 한정한다. 과대 보장보다 검증 가능한 보장이 낫다.

### 최종 결정

B 채택. 보존 boundary 를 `diff_documents` 가 실제 비교하는 필드 집합 (표 cell 내용·캡션·page_break, 그림 크기·캡션, char_shape·lineseg, PageDef, 카운트) 으로 확대하고, 미비교 요소 (수식 script / cell rowspan-colspan / BinData byte / 도형 raw) 는 비목표로 둔다.

### 1차 소스

- 상류 비교 함수/항목: `external/rhwp/src/serializer/hwpx/roundtrip.rs:369` / `:427` / `:513` / `:931` / `:939` / `:947` / `:1002`
- 상류 stage taxonomy (emit 단계): `external/rhwp/src/serializer/hwpx/mod.rs:4-9`
- v0.7.0 거짓 약속 경계 선례: `design/v0.7.0/hwpx-writeback-baseline-research.md` §4

## 2. 검증 표면 노출

### 팩트

- 상류 `roundtrip.rs:427` `pub fn diff_documents(a: &Document, b: &Document) -> IrDiff`, `roundtrip.rs:414` `pub fn roundtrip_ir_diff(hwpx_bytes: &[u8]) -> Result<IrDiff, SerializeError>`. `IrDiff` (`:56`) / `IrDifference` (`:83`) 모두 `pub`.
- 재노출 경로: `external/rhwp/src/serializer/hwpx/mod.rs:20` 이 `pub mod roundtrip` — `serializer/mod.rs` 는 `serialize_hwp` / `serialize_hwpx` 만 re-export 하나, `roundtrip` 항목은 모듈 경로 (`rhwp::serializer::hwpx::roundtrip::*`) 로 접근 가능.
- 기존 binding 표면 (`src/document.rs`) 은 round-trip 검증 메서드가 없다 — v0.7.0 은 `to_hwpx_bytes` / `export_hwpx` 출력만 제공.

### 검증자 반박

- "보증만 하고 verify 는 안 노출해도 되지 않나?" → 보증은 우리 fixture 범위. 사용자 문서는 다양하고, 자기 문서의 저장 손실을 사용자가 검출하는 표면은 RAG / 포맷 변환 파이프라인의 안전장치로 실용적이다.
- "`diff_documents` 가 `serializer/mod.rs` 에서 re-export 안 된 API 인데 의존해도?" → `pub mod roundtrip` 이라 SemVer 상 공개 표면. 단 top re-export 인 `serialize_hwpx` 보다 변화 가능성이 높음 — 시그니처 변경 시 상류 이슈로 대응, 비목표에 fragility 명시.
- "verify 가 export 와 중복 아닌가?" → export 는 저장, verify 는 저장 가능성의 사전 검증. 직교.

### 최종 결정

B 채택. `Document.verify_hwpx_roundtrip()` 을 노출한다. 상류 `diff_documents` 를 위임 호출해 현재 `Document` 의 HWPX 저장 손실을 사용자가 검출한다.

### 1차 소스

- 상류 진단 API: `external/rhwp/src/serializer/hwpx/roundtrip.rs:414` / `:427` / `:56` / `:83`
- 재노출 경로: `external/rhwp/src/serializer/hwpx/mod.rs:20`

## 3. verify 반환 타입

### 팩트

- `IrDiff` 는 `{ differences: Vec<IrDifference> }` + `is_empty()` (`roundtrip.rs:56-68`).
- `IrDifference` 는 카운트 계열 (SectionCount / ParagraphCount / CharShapeCount / …) + 의미 계열 (ParagraphCharShapes / ParagraphControls / ParagraphLinesegs / SectionPageDef / TableCaption / ObjectComment / …) 의 다수 variant 로, 각 variant 가 서로 다른 필드 구조를 가진다.
- variant 집합은 상류 게이트 진행 (#1378 → #1387 → #1392 → …) 마다 증가해왔다 — 닫힌 집합이 아니다.

### 검증자 반박

- "강타입 Pydantic 매핑이 LLM / 프로그램 소비에 더 낫지 않나?" → variant 가 매 상류 sync 마다 증가할 수 있어 강타입 mirror 는 sync 마다 깨진다. 본 binding v0.2.0 IR 의 forward-compat 라우팅 (미지 kind → UnknownBlock) 과 같은 교훈 — 닫히지 않은 외부 enum 을 강타입 미러하면 부서진다.
- "문자열은 프로그램이 파싱하기 어렵지 않나?" → verify 의 1차 용도는 "보존되는가 (`ok`) + 안 되면 무엇이 (`differences`)". 프로그램 분기는 `ok` bool 로 충분하고, `differences` 는 사람이 읽는 진단. 구조화 access 수요가 구체화되면 후속.

### 최종 결정

B 채택. `verify_hwpx_roundtrip()` 은 `ok: bool` + `differences: list[str]` 경량 리포트를 반환한다 (불변 `ok == not differences`). 각 `IrDifference` 는 상류 `Debug` / `Display` 표현을 사람 가독 문자열로 출고.

### 1차 소스

- `IrDiff` / `IrDifference` 정의: `external/rhwp/src/serializer/hwpx/roundtrip.rs:56-160`
- forward-compat 선례: 본 binding v0.2.0 IR `UnknownBlock` 라우팅 (`python/rhwp/ir/nodes.py`)

## 4. round-trip 비교 기준

### 팩트

- `roundtrip_ir_diff(hwpx_bytes: &[u8])` 는 입력 bytes 를 parse 해 원본으로 삼고, 그것을 serialize → reparse 한 결과와 비교한다 (`roundtrip.rs:414`).
- `diff_documents(a: &Document, b: &Document)` 는 두 `Document` 를 직접 비교한다 (`roundtrip.rs:427`).
- `PyDocument` 는 `inner: DocumentCore` 를 보관하고 `self.inner.document()` 가 `&Document` 를 반환한다 (`src/document.rs:15`). 원본 입력 bytes 는 parse 후 보관하지 않는다.

### 검증자 반박

- "`roundtrip_ir_diff(bytes)` 가 인자 하나라 더 단순한데?" → 그 경로를 쓰려면 우리가 `to_hwpx_bytes()` 출력을 입력으로 줘야 하는데, 그러면 "우리 HWPX 출력의 round-trip 안정성" 을 재는 것이지 "원본 `Document` 대비 저장 보존" 이 아니다. 사용자가 알고 싶은 건 후자.
- "`diff_documents` 의 두 인자를 뭘로 채우나?" → a = `self.inner.document()` (현재 Document), b = `serialize_hwpx` → `parse_hwpx` 한 reparse Document. "현재 Document 를 HWPX 로 저장하면 보존되는가" 를 측정.

### 최종 결정

B 채택. `diff_documents(현재 Document, reparse Document)`. 이미 parse 된 `Document` 가 비교의 SSOT 이며, 원본 대비 저장 보존을 측정한다.

### 1차 소스

- 상류 비교 함수: `external/rhwp/src/serializer/hwpx/roundtrip.rs:414` / `:427`
- binding Document 보관: `src/document.rs:15`

## 5. GIL 전략

### 팩트

- `src/document.rs:240-243` `to_ir` 주석: `self.inner` (DocumentCore) 가 RefCell 캐시로 `!Sync` — closure 가 `&self` 를 캡처하면 `py.detach` 의 Ungil 바운드를 불만족. owned 값 (from_bytes 의 bytes, render_pdf 의 svgs) 만 detach 가능.
- `diff_documents(self.inner.document(), &reparsed)` 의 첫 인자가 `&self.inner` 를 캡처 — 위 제약에 해당.
- round-trip 1회는 serialize_hwpx + parse_hwpx + diff 로 ≥1 ms 가 확실. 프로젝트 GIL 정책: ≥1 ms Rust-side 작업은 detach 권장하되 불확실하면 `benches/bench_gil.py` 로 측정.

### 검증자 반박

- "round-trip 이 무거운데 GIL 보유면 멀티스레드 처리량 손해 아닌가?" → 맞다. 단 detach 하려면 `self.inner.document().clone()` 으로 owned `Document` 를 만들어 이동해야 하고, clone 비용은 문서 크기 비례 — 미측정. v0.7.0 결정 3 과 동일 trade-off.
- "verify 는 호출 빈도가 낮을 텐데 최적화가 의미 있나?" → 낮은 빈도면 더욱 GIL 보유의 단순·정확성이 이득. 측정 전 최적화는 YAGNI.

### 최종 결정

A 채택. baseline 은 GIL 보유로 정확성·단순성을 우선한다. clone-후-detach 는 `bench_gil.py` 측정이 순이득을 보이면 후속 patch.

### 1차 소스

- `src/document.rs:240-243` (`to_ir` GIL 주석), v0.7.0 결정 3 (GIL 보유)
- 프로젝트 GIL 정책: `AGENTS.md` § Rust + Python hybrid build

## 참조

- 짝 페어 (spec): [roadmap/v0.8.0/hwpx-writeback-expansion.md](../../roadmap/v0.8.0/hwpx-writeback-expansion.md)
- 상류 round-trip 모듈: `edwardkim/rhwp` `src/serializer/hwpx/roundtrip.rs` + 게이트 PR #1378 / #1387 / #1389 / #1392 / #1405
