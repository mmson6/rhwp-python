---
status: Draft
description: "v0.3.2 — UTF-16 → codepoint 변환 SSOT 단일화. 상류 'Paragraph::utf16_pos_to_char_idx' (PR #494) 활용 (schema 변경 없음)"
target: v0.3.2
last_updated: 2026-05-03
---

# v0.3.2 — UTF-16 → codepoint 변환 SSOT 단일화

v0.2.0 IR 매핑은 UTF-16 → codepoint 변환을 자체 복사본 (`utf16_to_cp`) 으로 보유해 왔다. 동일 알고리즘이 상류 `document_core::helpers` 에 `pub(crate)` 로 갇혀 있어 외부 호출이 불가했기 때문이다.

상류가 [PR #494 (Task #484)](https://github.com/edwardkim/rhwp/pull/494) 로 `Paragraph::utf16_pos_to_char_idx(&self, utf16_pos: u32) -> usize` 를 v0.7.9 에 `pub` 노출하면서 SSOT 단일화가 가능. 본 spec 은 자체 복사본을 제거해 상류 메서드로 치환한다 — schema 변경 없음, 공개 API 동일, IR 출력 byte-equal. 부수로 짝이 되는 issue draft archive 도 묶는다 (in-place Frozen 전환).

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [ir-upstream-utf16-helper-research.md](../../design/v0.3.2/ir-upstream-utf16-helper-research.md).

## 결정 사항

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — API source | 상류 `Paragraph::utf16_pos_to_char_idx` (v0.7.9 GA) | PR #494 가 본 binding 이 제출한 [docs/upstream/issue-utf16-pos-to-char-idx.md](../../upstream/issue-utf16-pos-to-char-idx.md) 옵션 A 채택. v0.3.1 의 `control_text_positions` (PR #405) 와 같은 결. 자체 복사본 보유는 본 binding 운영 정책 ("상류 신뢰 + 결함 시 PR") 위반이라 SSOT 단일화 우선. 자세한 옵션 비교는 ADR §1 |
| 2 — `u32::MAX` sentinel 분기 처리 | 호출부 분기 제거, 자연 처리에 위임 | 상류 메서드의 `iter().position` 이 `u32::MAX` 입력 시 자연 None → `unwrap_or(char_offsets.len())` 로 자체 short-circuit 결과와 비트 단위 동일. 자세한 본체 비교는 ADR §2 |
| 3 — `fallback_end` 인자 제거 | 상류 메서드는 항상 `char_offsets.len()` 반환 | `paragraph.rs:22-24` doc-comment 가 `char_offsets.len() == text.chars().count()` 를 정의 자체로 보장. v0.3.1 [AC-12] `assert_eq!` 정책과의 비대칭은 contract 종류 차이 — 정당화는 ADR §3 |
| 4 — 자체 단위 테스트 처리 | 함수 삭제와 동시에 제거 | 자체 함수가 사라지면 본체 단위 테스트는 *없는 함수* 검증. 회귀 가드는 fixture 회귀 (`tests/test_ir_*.py`) + 상류 자체 단위 테스트 6건 (Task #484 Stage 2) 이중 보유. 자세한 옵션 비교는 ADR §4 |
| 5 — 적용 범위 | `src/ir.rs::build_char_runs` 단일 호출자 | 코드베이스 grep — Python `_build_inline_runs` 는 RawCharRun 의 `start_cp/end_cp` 를 그대로 소비. 추가 변환 호출 없음 |
| 6 — 상류 핀 bump | 현재 핀 `0fb3e67` 유지 | 핀 history 에 PR #494 머지 commit `60eaa91` (2026-04-30) 포함 — `cargo build` 가 시그니처 해소로 직접 검증 (AC-1). v0.7.9 GA 흡수는 직교 영역, 본 spec 영구 비목표 |
| 7 — 외부 영향 | schema / API / IR 출력 모두 변경 없음 | 자체 복사본 = 상류 메서드 본체로 알고리즘 동일, fallback 의미축 동일. 사용자 visible 변화 0 |
| 8 — issue archive | `docs/upstream/issue-utf16-pos-to-char-idx.md` in-place Frozen 전환 | v0.3.1 GA 직전 (4/30) PR #494 머지됐으나 v0.3.1 spec 이 archive 를 명시 작업으로 안 넣어 누락. 본 spec 이 묶음 — CONVENTIONS § upstream/ 의 in-place Frozen 분기 (다른 spec 이 본 파일 참조) |

## 인수조건

- **AC-1** — `cargo build --release` 가 통과한다 (상류 `Paragraph::utf16_pos_to_char_idx` 시그니처 해소로 핀 `0fb3e67` 이 메서드를 포함함을 컴파일러가 직접 검증)
- **AC-2** — fixture (`external/rhwp/samples/aift.hwp`, `external/rhwp/samples/table-vpos-01.hwpx`) 의 `Document.to_ir()` 출력 `InlineRun.start_cp` / `end_cp` 값이 v0.3.1 GA baseline 과 byte-equal
- **AC-3** — 마지막 char_shape 의 `end_utf16 = u32::MAX` 인 paragraph 에서 출고 `InlineRun.end_cp == para.text.chars().count()` (sentinel 의 자연 처리 결과)
- **AC-4** — `SchemaVersion` 은 `"1.1"` 유지, `python/rhwp/ir/schema/hwp_ir_v1.json` 본문 변경 없음
- **AC-5** — `pytest -m "not slow"` 전체 회귀 통과 (`tests/test_ir_*.py` 포함)
- **AC-6** — `docs/upstream/issue-utf16-pos-to-char-idx.md` frontmatter `status: Active` → `Frozen`, 본문 첫 헤더 위에 `> **RESOLVED 2026-04-30** — 상류 PR #494 …` 한 줄 인용 블록 추가
- **AC-7** — `docs/upstream/README.md` 의 `issue-utf16-pos-to-char-idx.md` row `Status` → `Frozen`, `RESOLVED` 컬럼에 `2026-04-30 ([PR #494](https://github.com/edwardkim/rhwp/pull/494))` 채움
- **AC-8** — `CHANGELOG.md` `[0.3.2]` 섹션 신설, `### Build` 영역에 SSOT 단일화 명시

## 영구 비목표

- **상류 핀 추가 bump** (`0fb3e67` → v0.7.9 GA `2efba58`) — 직교 영역 변경, 별도 minor 에서 다른 enabling change 와 묶음
- **`document_core::helpers::utf16_pos_to_char_idx` visibility 변경** — 상류 옵션 A 채택으로 옵션 B 검토 가치 소멸
- **다른 PATCH 항목 묶음 (BMP fix / `[async]` extras 키 정리 등)** — 본 spec 은 단일 SSOT 정정 단위, 다른 후보는 별도 spec
- **자체 단위 테스트의 wrapper 형태 보존** — ADR §4 검증자 반박 참조
- **`InlineRun` 의 codepoint → UTF-16 환원 옵션** — UTF-16 노출은 v0.2.0 결정 시점부터 영구 안 함

## 참조

- 짝 페어 (ADR): [ir-upstream-utf16-helper-research.md](../../design/v0.3.2/ir-upstream-utf16-helper-research.md)
- 자체 이슈 초안: [docs/upstream/issue-utf16-pos-to-char-idx.md](../../upstream/issue-utf16-pos-to-char-idx.md) (v0.3.2 GA 시 in-place Frozen)
- 상류 PR: <https://github.com/edwardkim/rhwp/pull/494>
- 상류 Task: <https://github.com/edwardkim/rhwp/issues/484>
- 상류 메서드: `external/rhwp/src/model/paragraph.rs:818` — `pub fn utf16_pos_to_char_idx`
