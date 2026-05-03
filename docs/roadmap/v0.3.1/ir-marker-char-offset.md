---
status: Draft
description: "v0.3.1 — inline 컨트롤 마커 character offset 출고. 상류 v0.7.8 'Paragraph::control_text_positions()' 활용 (schema 변경 없음)"
target: v0.3.1
last_updated: 2026-05-02
---

# v0.3.1 — inline 컨트롤 마커의 character offset 출고

v0.3.0 의 IR 은 inline 컨트롤 (각주·미주 마커, 그림, 수식, 필드) 의 `Provenance.char_start/char_end` 를 항상 `None` 으로 출고했다. 본문 paragraph 안의 정확한 character 위치를 외부 crate 에서 알 길이 없었기 때문 — 알고리즘은 상류 `rhwp::document_core::find_control_text_positions` 에 `pub(crate)` 로 갇혀 있었다.

v0.7.8 에서 상류가 [PR #405 (Task #390)](https://github.com/edwardkim/rhwp/pull/405) 로 `Paragraph::control_text_positions(&self) -> Vec<usize>` 를 `pub` 노출하면서 외부 crate 에서도 직접 호출 가능해졌다. 본 spec 은 이를 사용해 v0.3.0 시점에 deferred 처리했던 4 군데 `char_start=None / char_end=None` 슬롯을 채운다 — schema 변경 없음 (이미 `1.1` 에 정의된 슬롯), 추가 / 변경 / 제거된 API 없음, 기존 consumer 영향 0.

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [ir-marker-char-offset-research.md](../../design/v0.3.1/ir-marker-char-offset-research.md).

## 결정 사항

본 표의 항목 1–4 는 *결정 비교가 필요한 선택* (외부 독자가 "왜 그렇게?" 를 던질 만한 4건) — 짝 페어 ADR §결정 매트릭스 가 옵션 / 검증자 반박 / 1차 소스를 다룬다. 항목 5–8 은 *operational scope* (이미 결정되어 ADR 가 별도로 정당화하지 않음) — 적용 대상, raw 데이터 형태, 사전 조건, 안전 검증 정책.

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — API source | 상류 `Paragraph::control_text_positions()` (v0.7.8) | PR #405 가 본 binding 이 제출한 [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) 옵션 A 를 그대로 채택. 자체 알고리즘 복사는 silent drift 위험 |
| 2 — char_start / char_end 의미 | `char_end = char_start = position` (zero-width point) | 상류 docstring "positions[i] = controls[i] 가 삽입되어야 할 텍스트 character 인덱스" — 마커는 점이지 범위 아님. char_shape 의 [start, end) 와 다른 의미축 |
| 3 — `char_offsets.is_empty()` paragraph | `char_start / char_end = None` 폴백 | 상류 fallback 분기는 모든 컨트롤에 `positions.push(pos)` 후 Shape/Table/Picture/Equation 일 때만 `pos += 1` 이라 정확 character offset 의미 없음. 텍스트가 없는 paragraph 에 char index 부여 자체가 무의미 |
| 4 — Schema 버전 | `SchemaVersion 1.1` 유지 (bump 없음) | `Provenance.char_start: int \| None` / `char_end: int \| None` 은 1.1 에 이미 정의. 슬롯 채움이지 새 필드 추가가 아님. forward-compat 100% |
| 5 — 적용 대상 (Python 블록) | `FootnoteBlock.marker_prov` / `EndnoteBlock.marker_prov` / `PictureBlock.prov` (TAC + floating 양쪽) / `FormulaBlock.prov` / `FieldBlock.prov` / `TocBlock.prov` / `TableBlock.prov` 7 종 | RawParagraph.controls 로 흘러나오는 모든 inline 컨트롤. 상류 `control_text_positions()` 의 fallback 분기에서도 Shape/Table/Picture/Equation 이 동등 취급 — TableBlock 포함이 일관. Picture 의 `treat_as_char` 상태와 무관하게 부모 paragraph 안의 anchor 위치를 가지므로 양쪽 모두 적용. Header/Footer 는 furniture 라우팅 후 별도 paragraph 가 되므로 제외 |
| 6 — Rust raw 필드 | `Option<usize>` 단일 필드 (`marker_char_offset` for Footnote/Endnote, `char_offset` for Picture/Formula/Field/Toc/Table) | Python 측은 `char_start / char_end` 두 슬롯이지만 zero-width 결정 (항목 2) 으로 raw 는 한 값만 운반. mapper 가 양쪽 슬롯에 동일 값 복제 |
| 7 — 상류 핀 bump | `033617e` (v0.7.7) → `0fb3e67` (post-v0.7.8) — enabling commit `cee3c1e chore: sync rhwp upstream` (v0.7.8 / `42cf91b`) 후 `8482555 chore: sync upstream rhwp` 로 추가 sync (직교 영역 변경, 본 spec 동작에 영향 없음) | 상류 `pub fn control_text_positions` 가 v0.7.8 에 GA. 그 이전 핀에서는 컴파일 자체가 불가 — v0.7.8 commit `cee3c1e` 가 본 spec 의 enabling change. 본 v0.3.1 작업으로 남은 일은 CHANGELOG 기재 의무 (AC-13) |
| 8 — controls / positions 길이 동기화 | `assert_eq!(controls.len(), positions.len())` 후 `zip` (fail-fast) | 상류 `control_text_positions()` 는 항상 `controls.len()` 개 position 반환 (paragraph.rs:734 / 765 / 786 / 796 의 모든 분기 가드). 길이 불일치 시 상류 contract 위반 — 정상 빌드에서도 panic 으로 즉시 드러내야 silent 잘못된 offset 출고 회피. release 에서 무력화되는 `debug_assert!` 는 본 정책에 부적합 |
| 9 — `control_text_positions()` 호출 분배 | paragraph 당 1회 호출, 결과 `Vec<usize>` 를 `build_raw_paragraph` 와 `collect_furniture_from_paragraph` 양쪽에서 공유 | 두 함수가 각각 독립적으로 `para.controls` 를 iterate (body controls 추출 / furniture 라우팅). control index 가 둘이 공유하는 단일 축이라 positions 배열도 공유 가능. paragraph 당 중복 호출은 동일 결과의 재계산 — 낭비 |

## 인수조건

- **AC-1** — `FootnoteBlock.marker_prov.char_start` / `char_end` 가 부모 paragraph 의 `char_offsets` 가 비어있지 않을 때 동일한 정수값 (zero-width) 으로 채워진다
- **AC-2** — `EndnoteBlock.marker_prov.char_start` / `char_end` 가 같은 규칙으로 채워진다
- **AC-3** — `PictureBlock.prov.char_start` / `char_end` 가 같은 규칙으로 채워진다 (TAC / floating 무관)
- **AC-4** — `FormulaBlock.prov.char_start` / `char_end` 가 같은 규칙으로 채워진다
- **AC-5** — `FieldBlock.prov.char_start` / `char_end` 가 같은 규칙으로 채워진다
- **AC-6** — `TocBlock.prov.char_start` / `char_end` 가 같은 규칙으로 채워진다
- **AC-7** — `TableBlock.prov.char_start` / `char_end` 가 같은 규칙으로 채워진다
- **AC-8** — 부모 paragraph 의 `char_offsets` 가 비어있을 때 (`paragraph.char_offsets.is_empty()`) 위 모든 블록의 `prov.char_start` / `char_end` 는 `None` 으로 출고된다
- **AC-9** — `SchemaVersion` 은 `"1.1"` 로 유지. `python/rhwp/ir/schema/hwp_ir_v1.json` 본문 변경 없음
- **AC-10** — `python/rhwp/ir/schema/hwp_ir_v1.json` (또는 content-addressed alias `hwp_ir_v1-sha256-<hash>.json`) 으로 jsonschema validator 가 v0.3.1 IR JSON 을 검증할 때 통과한다 — `Provenance.char_start/char_end` 의 `anyOf [integer, null]` 정의와 호환됨을 실제 validator 호출로 확인
- **AC-11** — non-None 출고된 모든 marker 의 `prov.char_start == prov.char_end` 이며 `isinstance(prov.char_start, int)` — zero-width point 결정 (항목 2) 의 invariant. mapper 의 양쪽 슬롯 동일 값 복제 (항목 6) 가 비대칭으로 깨지지 않음을 보증
- **AC-12** — 상류 contract (`controls.len() == control_text_positions().len()`) 위반 시 Rust 빌드가 release / debug 무관 panic 한다 (항목 8 의 `assert_eq!` invariant) — 상류 silent regression 차단 가드
- **AC-13** — `external/rhwp` submodule pin 이 `0fb3e67` (post-v0.7.8) 이며 [CHANGELOG.md](../../../CHANGELOG.md) 에 v0.7.7 → 본 핀 bump 가 명시된다 (enabling commit 은 v0.7.8 의 `cee3c1e`, 후속 sync `8482555` 가 직교 영역 변경 — 본 AC 는 CHANGELOG 기재 의무)
- **AC-14** — AC-1 ~ AC-8 검증용 fixture 는 우선 기존 `external/rhwp/samples/aift.hwp` / `table-vpos-01.hwpx` 로 시도하고, 부족 (특히 AC-8 의 빈 `char_offsets` paragraph + 인라인 컨트롤 조합) 시 minimal 합성 fixture 를 `tests/fixtures/v0_3_1/` 에 추가

## 영구 비목표

- **`Block.order: int` 필드 신설** — controls 의 시각 순서 보존을 위한 별도 필드. v0.4.0+ 검토. 본 v0.3.1 에서는 IR `paragraphs` 배열 등장 순서 = controls 등장 순서로 묵시적 처리 유지
- **`ListItemBlock` 의 정확 marker (`"가."` / `"(a)"` 등) 추출** — `Numbering.level_formats` lookup 필요. v0.4.0+ 별도 spec
- **TOC entries 실제 추출** — bookmark resolver 필요. v0.4.0+ 별도 spec
- **`HwpField.cached_value` 추출** — `field_ranges` 매핑 필요. 본 spec 은 *위치* 만 채우고 *값* 은 다음 release 로 미룬다
- **`Header` / `Footer` 컨트롤의 char_offset** — 본문 paragraph 가 아니라 `Furniture.page_headers` / `page_footers` 로 라우팅되어 별도 paragraph 객체가 됨. *부모 paragraph 안의 char position* 개념이 적용되지 않음
- **char_end 의 1-width 의미 (`char_end = char_start + 1`)** — 마커가 char 한 칸을 차지한다고 보는 해석. 결정 항목 2 에서 zero-width 채택했으므로 본 spec 의 영구 비목표
- **`char_end` 슬롯 자체의 schema 제거 + `(char_start, width=0)` 모델로 전환** — 의미축은 가장 깨끗하지만 schema bump 필요 (AC-9 위반). schema 안정성 우선이라 본 spec 영구 비목표 (ADR §2 "옵션 D 비고" 참조)
- **char_offset UTF-16 → codepoint 재변환** — 상류 API 가 이미 codepoint 단위 character index 를 반환하므로 별도 변환 없음. UTF-16 노출은 영구 안 함
- **중첩 표 안 inline 컨트롤의 좌표 일관성** — `TableCell.paragraphs` 안에 들어있는 inline 컨트롤은 `(section_idx, para_idx)` 가 외부 표의 부모 paragraph 를 가리키지만 (Provenance 계약), `char_offset` 은 셀 *내부* paragraph 안 위치를 가리킨다. 두 인덱스의 의미축이 다르므로 `text[char_start:char_end]` 같은 외부 paragraph 기준 슬라이싱이 잘못된 결과를 낸다. v0.3.0 부터 존재하던 Provenance 모델의 한계 — 본 v0.3.1 은 새 컨트롤 종류 (마커) 에 *propagate* 만 하며 모델 자체의 수정은 별도 spec 사안 (v0.4.0+ Provenance 정정 검토)

## 참조

- 짝 페어 (ADR): [ir-marker-char-offset-research.md](../../design/v0.3.1/ir-marker-char-offset-research.md)
- 상류 PR: <https://github.com/edwardkim/rhwp/pull/405>
- 상류 Task: <https://github.com/edwardkim/rhwp/issues/390>
- 상류 메서드: `external/rhwp/src/model/paragraph.rs:730` — `pub fn control_text_positions`
- 자체 이슈 초안 (origin): [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) — PR #405 머지로 본 v0.3.1 GA 시점에 archive / 삭제
