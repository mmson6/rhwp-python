---
status: Draft
target: v0.3.1
last_updated: 2026-04-29
---

# v0.3.1 ir-marker-char-offset — 설계 의사결정 리서치 요약

[v0.3.1/ir-marker-char-offset.md](../../roadmap/v0.3.1/ir-marker-char-offset.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 4건의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | API source | A: 알고리즘 자체 복사 / B: 상류 `Paragraph::control_text_positions()` (PR #405) / C: `paragraph.char_offsets` 갭 직접 분석 | **B** | 자체 복사는 silent drift 위험. C 는 사실상 A 의 변형. B 는 본 binding 이 [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) 로 제안 → 상류가 옵션 A (Paragraph 메서드) 채택 → 머지 → v0.7.8 GA |
| 2 | char_start / char_end 의미 | A: zero-width (`char_end = char_start`) / B: 1-width (`char_end = char_start + 1`) / C: 컨트롤별 가변 width | **A** | 상류 docstring 이 `positions[i]` 를 "삽입 위치 인덱스" 로 정의 — 점이지 범위 아님. CommonMark footnote `[^1]` / TEI `<note place="foot">` 등도 마커는 점-위치로 모델링 |
| 3 | `char_offsets.is_empty()` paragraph | A: 폴백 position 그대로 출고 / B: `None` 폴백 | **B** | 상류 fallback 경로는 비-Shape/Table/Picture/Equation 컨트롤을 모두 position 0 에 누적 — 의미 손실. 텍스트 없는 paragraph 에 character index 부여 자체가 무의미. fail-fast 원칙 (CLAUDE.md "missing precondition → None at boundary") |
| 4 | Schema 버전 | A: `1.1` 유지 / B: `1.2` 로 bump (visible 변경) | **A** | `Provenance.char_start: int \| None` / `char_end: int \| None` 은 1.1 에 이미 정의된 슬롯. 슬롯에 값을 채우는 것은 schema 변경이 아니라 *실제 데이터 정밀도 개선*. JSON Schema 의 `nullable` 슬롯에 non-null 값이 추가되는 것은 SemVer 상 호환 |

## 1. API source — 자체 복사 vs 상류 `pub` 노출

### 팩트

- 알고리즘은 `char_offsets` 갭 (각 inline 컨트롤이 char_offsets 상에서 8 단위 폭 표시자로 인코딩되어, `gap / 8` 로 위치 카운트 복원) 을 분석하여 `controls[i]` 의 character 위치를 복원. "8 UTF-16 코드 유닛" 은 *컨트롤당 텍스트 폭* 이 아니라 *char_offsets 배열 상의 인코딩 단위 폭*
- 상류 v0.7.7 까지는 `pub(crate) fn find_control_text_positions(para: &Paragraph) -> Vec<usize>` — 외부 crate 접근 불가
- WASM binding 측은 `#[wasm_bindgen]` 으로 동일 helper 가 이미 노출 (선례 존재)
- 본 binding 이 [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) 로 옵션 A (`Paragraph` 인스턴스 메서드) 와 옵션 B (helpers 모듈 `pub` 화) 두 안 제시
- 상류는 옵션 A 채택, [Task #390](https://github.com/edwardkim/rhwp/issues/390) / [PR #405](https://github.com/edwardkim/rhwp/pull/405) 로 머지, v0.7.8 GA (2026-04-29)

### 검증자 반박

- "v0.7.8 머지 전까지 어떻게 했나?" → 안 했다. v0.3.0 은 `char_start = char_end = None` 출고로 GA. RAG provenance 정밀도 손실은 알려진 trade-off 였고, [CLAUDE.md "fail-fast, no silent fallback"](../../../CLAUDE.md) 원칙대로 fake offset 을 만들어내지 않음
- "왜 옵션 A 가 채택됐나?" → helpers 모듈 전체를 `pub` 으로 노출하면 향후 helpers 진화가 외부 contract 부담. `Paragraph` 메서드 캡슐화는 외부 surface 를 좁게 유지

### 최종 결정

**옵션 B — 상류 `Paragraph::control_text_positions()` 사용**. 자체 알고리즘 복사 (옵션 A) 는 `char_offsets` 의 8 UTF-16 코드 유닛 가정이 상류 변경 시 silent 깨짐 — 상류가 변경됐다는 사실 자체가 우리 binding 의 컴파일 / 테스트로 드러나지 않는 종류의 실패. 상류 SSOT 활용이 정답.

본 프로젝트는 `external/rhwp` 의 결함 / 누락은 상류 GitHub 이슈로 보고하고 자체 patch / wraparound / 알고리즘 복사를 금지하는 정책을 운영 — 본 결정과 정확히 부합. 알고리즘 복사 시 상류와의 **silent drift** 위험이 가장 큰 비용이고, 그 위험을 피하려면 SSOT 단일화가 필수.

### 1차 소스

- 상류 PR: <https://github.com/edwardkim/rhwp/pull/405>
- 상류 Task: <https://github.com/edwardkim/rhwp/issues/390>
- 상류 commit: <https://github.com/edwardkim/rhwp/commit/2a69fe1>
- 상류 메서드 정의: `external/rhwp/src/model/paragraph.rs:730`

## 2. char_start / char_end 의미 — zero-width vs 1-width

### 팩트

- 상류 docstring: "`positions[i]` = `controls[i]` 가 삽입되어야 할 텍스트 character 인덱스"
- HWP 의 inline 컨트롤은 paragraph 의 `text` 필드에 직접 등장하지 않는다 — `controls` 배열에 별도 저장되며 character 위치는 갭 분석으로 복원
- 따라서 마커의 "텍스트 폭" 자체가 정의되지 않음 — 0 으로 보는 것도, 1 로 보는 것도 합의 문제
- v0.3.0 의 `Provenance.char_start` / `char_end` 는 `int | None` — 두 값을 명시적으로 받음
- 비교 대상:
  - **CommonMark footnote** (`[^1]`): 본문에 마커 텍스트 (`[^1]`) 가 존재 → char_end > char_start
  - **TEI XML** (`<note place="foot">`): 인라인 element → 시작·끝 태그가 character 범위 형성
  - **DOCX `<w:footnoteReference>`**: zero-width — element 자체가 위치 마커
  - **HWP**: DOCX 와 같은 모델 (zero-width inline ref)

### 검증자 반박

- "char_start == char_end 이면 빈 range 인데 RAG 검색에 의미가 있나?" → provenance 의 본질은 "어디서 왔나" 의 점-인덱스. 검색 시 `char_start - 30 .. char_start + 30` 같은 컨텍스트 윈도우는 consumer 책임. range 보다 point 가 합성 (parent paragraph + char_offset) 에 자연
- "1-width 도 합리적 아닌가? 마커 자체가 한 글자 자리 차지하는 시각 모델" → HWP 의 inline 컨트롤은 *text* 자리 안 차지. text 와 controls 가 별도 배열 — UI 렌더 시 controls 가 자기 폭만큼 끼어들지만 그건 *render* 모델이지 *text* 모델 아님. char index 는 text 모델 기준

### 최종 결정

**옵션 A — zero-width**. `char_start = char_end = position`. HWP 도메인 모델과 일치 (text 자리 안 차지) + DOCX 선례 + 향후 1-width 가 필요해지면 별도 width 필드 (`marker_width: int` 등) 로 표현 가능 (현 결정 자체는 강한 가정 아님).

### 옵션 D 비고 — char_end 슬롯 자체 제거 + `(char_start, width=0)`

의미축이 가장 깨끗한 안. 마커가 점이라는 사실을 schema 레벨에서 표현 (`char_end` 슬롯 부재 → 마커는 무조건 폭 0). 미채택 이유: schema bump 가 강제됨 (Provenance.char_end 가 1.1 에 정의된 슬롯이라 제거는 breaking change). 본 v0.3.1 의 핵심 결정인 "schema 1.1 호환 유지" (AC-9) 와 직접 충돌. *의미 순수성* 보다 *consumer 호환성* 이 우선이라 본 spec 영구 비목표로 분류.

### 1차 소스

- DOCX `w:footnoteReference` 모델: <https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.footnotereference>
- TEI 인용 모델: <https://tei-c.org/release/doc/tei-p5-doc/en/html/ref-note.html>
- 상류 메서드 docstring: `external/rhwp/src/model/paragraph.rs:717-729`

## 3. `char_offsets.is_empty()` 폴백 — 상류 fallback 채택 vs `None` 폴백

### 팩트

- 상류 `Paragraph::control_text_positions()` 의 `char_offsets.is_empty()` 분기 (`paragraph.rs:738-756`) 는 모든 컨트롤에 `positions.push(pos)` 후 Shape / Table / Picture / Equation 일 때만 `pos += 1`. 결과: 첫 컨트롤은 항상 0, 그 이후는 직전까지의 Shape/Table/Picture/Equation 카운트를 받음. 비-Shape/Table/Picture/Equation 은 *직전 위치 그대로* 누적
- 텍스트가 없는 paragraph (= controls 만 있고 text 없음) 는 실제 문서에서 매우 드뭄 — 보통 secd / cold (SectionDef / ColumnDef) 같은 layout 컨트롤만 존재하는 경우
- v0.3.0 의 `Provenance.char_start: int | None` 은 None 을 명시적으로 허용

### 검증자 반박

- "상류가 0 으로 폴백하는데 우리도 그대로 흘리면 되지 않나?" → 0 은 "0번째 character" 라는 *유의미한 값* 으로 보일 수 있음. consumer 가 0 을 valid offset 으로 신뢰하면 misleading. None 은 "값 없음" 명시
- "그럼 상류 폴백을 그대로 신뢰 못 하는 건가?" → 신뢰의 문제가 아니라 *의미축* 차이. 상류는 *어떻게든* 위치를 부여해야 다음 단계 (렌더) 가 진행됨. 우리 IR 은 *consumer 가 신뢰 가능한 데이터만* 출고하는 것이 책임

### 최종 결정

**옵션 B — `char_start / char_end = None` 폴백**. 본 프로젝트의 fail-fast 원칙 (정확하지 않은 값을 "정확한 값" 인 척 노출하지 않음) 과 결이 같다 — 상류 폴백의 `0` 은 "valid 한 0번째 character" 로 보일 수 있어 misleading. None 은 boundary (HWP binary → IR) 의 명시적 신호.

### 1차 소스

- 상류 fallback 분기: `external/rhwp/src/model/paragraph.rs:738-756`
- global CLAUDE.md 의 Error Philosophy 섹션

## 4. Schema 버전 — 1.1 유지 vs 1.2 로 bump

### 팩트

- v0.3.0 schema (`SchemaVersion = "1.1"`) 는 `Provenance.char_start: int | None` / `char_end: int | None` 슬롯을 이미 정의
- v0.3.0 IR 출고는 inline 컨트롤 마커에 대해 두 슬롯을 항상 `null` 로 채워 출고 — schema 위반 아님
- 본 v0.3.1 작업은 *기존 슬롯에 non-null 값을 채우는 것* — 새 필드 추가도, 타입 변경도, 의미 변경도 아님
- JSON Schema in-place 업데이트 정책 (v0.3.0 release note: "in-place v1 URL — major 안의 minor 추가") 는 *새 필드 추가* 에 대한 정책

### 검증자 반박

- "consumer 가 항상 null 로 받던 값이 갑자기 int 가 되는 건 visible 변화 아닌가?" → schema 정의는 처음부터 nullable 이었으므로 consumer 는 두 케이스 모두 처리 의무가 있었음. 실제로 처리하지 않은 consumer 는 schema 위반
- "그래도 SchemaVersion 을 1.2 로 올려서 explicit 하게 알려주는 게 안전하지 않나?" → SemVer 의 minor bump 는 *호환 깨지는 추가* 일 때만. 본 변경은 schema 호환 100% — bump 가 정당화 안 됨

### 최종 결정

**옵션 A — `SchemaVersion = "1.1"` 유지**. 슬롯에 값을 채우는 것은 schema 변경이 아니다. JSON Schema 정의는 동일, validator 도 동일하게 통과. v0.3.0 IR 과 v0.3.1 IR 을 같은 validator 로 검증해도 둘 다 valid.

CHANGELOG 에서 "Fixed: inline 컨트롤 마커의 `Provenance.char_start/char_end` 가 v0.3.0 까지 항상 null 이던 문제 정정" 으로 표현 — 사용자 visible "변화" 가 있다는 사실은 schema 가 아니라 CHANGELOG 가 전달.

### 1차 소스

- v0.3.0 schema: `python/rhwp/ir/schema/hwp_ir_v1.json`
- SemVer 정의: <https://semver.org/spec/v2.0.0.html>

## 참조

- [roadmap/v0.3.1/ir-marker-char-offset.md](../../roadmap/v0.3.1/ir-marker-char-offset.md) — 본 리서치의 결정 요약
- [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) — 본 binding 이 상류에 제출한 이슈 초안 (PR #405 머지로 v0.3.1 GA 시점에 archive)
