---
status: Active
description: "업스트림 제안 — 'utf16_pos_to_char_idx' 외부 노출 (UTF-16 위치 → codepoint 인덱스 변환 helper). #390/PR #405 후속 같은 결"
last_updated: 2026-04-30
---

# 업스트림 제안 — `utf16_pos_to_char_idx` 외부 노출

> 외부 binding (`rhwp-python`) 구현 중 업스트림에서 수정이 필요해 보이는 부분을 발견하여, Claude 로 조사 및 다차례 사실 검증을 거친 결과입니다.

## Summary

`document_core::helpers::utf16_pos_to_char_idx(char_offsets: &[u32], utf16_pos: u32) -> usize` 가 외부 crate 에서 호출 불가합니다. 알고리즘은 단순한 single-pass scan 이며 상류 자체에서도 prod 사용 중 (cursor / clipboard 경로) 이라, `Paragraph` 인스턴스 메서드 캡슐화 또는 helper visibility 완화로 해결 가능해 보입니다.

본 이슈는 [#390](https://github.com/edwardkim/rhwp/issues/390) (`find_control_text_positions` 외부 노출, [PR #405](https://github.com/edwardkim/rhwp/pull/405) 가 cherry-pick 으로 v0.7.8 에 반영) 와 같은 결의 — 같은 `helpers` 모듈에 갇힌 다른 helper 의 외부 노출 사례입니다.

## 문제 상황

`Paragraph.char_shapes[i].start_pos` 는 UTF-16 코드 유닛 단위 위치이고 (`paragraph.rs:121-126` `CharShapeRef.start_pos: u32`), `Paragraph.char_offsets` 의 doc-comment 도 "원본 UTF-16 코드 유닛 인덱스" 로 명시 (`paragraph.rs:22-24`) 되어 있습니다.

외부 binding 이 IR / RAG 매핑 작업에서 character (codepoint) 단위 인덱스로 정규화된 character run 을 출고해야 하는 경우, 매 char_shape 의 `start_pos` 를 codepoint 인덱스로 변환할 helper 가 필요합니다. 알고리즘은 `char_offsets.iter().position(|&off| off >= utf16_pos)` 의 단일 라인이지만, 다음 이유로 외부 자체 구현 회피가 안전해 보입니다:

- 단순해 보여도 boundary 처리 (utf16_pos > 모든 offsets 인 sentinel 케이스의 fallback) 가 정확히 일치해야 상류 렌더링·클립보드 결과와 어긋나지 않습니다.
- 상류 자체가 3 군데 직접 호출 (cursor / clipboard 경로) + 5 군데 inline 으로 같은 본체 패턴 (`char_offsets.iter().position(|&off| off >= ...)`) 을 사용 중입니다. inline 5 군데의 fallback (`unwrap_or(...)`) 은 호출자 컨텍스트별로 상이 — `text_len` / `text_end` / `0` / `inserted_chars` — helper 의 `char_offsets.len()` 과는 의도가 다릅니다. 외부 binding 은 paragraph 레벨 정규화 케이스라 helper 와 동일 fallback 이 필요한데, 외부 자체 복사 시 boundary 미묘한 차이로 렌더링 결과와 어긋날 위험이 있습니다.
- `Paragraph.char_offsets` 의 의미 (UTF-16 코드 유닛 인덱스, `paragraph.rs:22-24` doc-comment) 는 상류가 단일 source-of-truth 로 갖는 contract 입니다.

본 binding 의 호출은 paragraph 레벨 character run 정규화 hot path 로, char_shapes 길이만큼 반복합니다 — 옵션 A 채택 시:

```rust
for cs in &para.char_shapes {
    let char_idx = para.utf16_pos_to_char_idx(cs.start_pos);
    // ... character run 의 시작 인덱스로 사용
}
```

## 현재 상태

`src/document_core/helpers.rs:189-192` 에 함수가 존재합니다:

```rust
/// UTF-16 위치를 char 인덱스로 변환한다.
pub(crate) fn utf16_pos_to_char_idx(char_offsets: &[u32], utf16_pos: u32) -> usize {
    char_offsets.iter().position(|&off| off >= utf16_pos).unwrap_or(char_offsets.len())
}
```

`src/document_core/mod.rs:6` 의 `pub(crate) mod helpers;` 때문에 외부 crate 에서는 접근 불가합니다.

이 함수는 `v0.5.0` initial commit 부터 helpers 모듈에 존재해 온 helper 로, 현재 다음 경로에서 prod 사용 중이라 contract 가 안정된 상태로 보입니다:

- `src/document_core/queries/cursor_nav.rs:8, 112, 159` (import + 2 회 호출)
- `src/document_core/commands/clipboard.rs:11, 845` (import + 1 회 호출)

(`src/document_core/queries/cursor_rect.rs:8` 에도 import 가 있으나 호출은 부재 — dead import 로 보이며, 옵션 A 채택 시 함께 제거 가능)

추가로 동일 패턴이 inline 으로 사용된 경로 (총 5 군데):

- `src/renderer/composer.rs:435, 441, 500` — `char_offsets.iter().position(|&off| off >= ...)`
- `src/document_core/commands/clipboard.rs:543, 548` — 같은 패턴

성격은 약간 다르나 같은 변환 컨텍스트의 역방향 검색 (`iter().rev().find(|cs| cs.start_pos <= utf16_pos)`) 도 `src/renderer/layout/paragraph_layout.rs:188, 323, 391` 에 있습니다.

## 선례

같은 `helpers` 모듈의 다른 함수가 [#390](https://github.com/edwardkim/rhwp/issues/390) 에서 동일한 사유로 외부 노출 검토되었고, [PR #405](https://github.com/edwardkim/rhwp/pull/405) 에서 옵션 A (`Paragraph` 인스턴스 메서드 캡슐화) 로 채택되어 `Paragraph::control_text_positions(&self) -> Vec<usize>` (`paragraph.rs:730`) 로 v0.7.8 에 반영된 사례가 있습니다. 기존 `helpers::find_control_text_positions` 는 `paragraph.rs` 메서드를 호출하는 thin wrapper 로 보존되어 (`helpers.rs:105-111`) 기존 내부 호출 경로와 호환을 유지합니다.

본 helper 도 같은 패턴이 자연스러워 보입니다 — `Paragraph` 가 `char_offsets` 를 자체 필드로 보유하므로 `&self` 로 캡슐화하면 시그니처가 더 깔끔해집니다.

## 제안

다음 중 하나를 검토 부탁드립니다:

**옵션 A** — `Paragraph` 인스턴스 메서드로 캡슐화:

```rust
// src/model/paragraph.rs (impl Paragraph 안)

/// `text` 의 codepoint 중 UTF-16 위치 `utf16_pos` 이상인 첫 번째 codepoint
/// 의 인덱스를 반환. 없으면 `text.chars().count()` (= `char_offsets.len()`).
///
/// `char_shapes[i].start_pos` 와 `line_segs[i].text_start` 같은 UTF-16 단위
/// 위치 필드를 codepoint 인덱스로 정규화할 때 사용.
pub fn utf16_pos_to_char_idx(&self, utf16_pos: u32) -> usize {
    self.char_offsets.iter().position(|&off| off >= utf16_pos)
        .unwrap_or(self.char_offsets.len())
}
```

장점은 외부 API surface 를 좁게 유지하면서 `Paragraph` 에 의미가 응집되고, helpers 모듈은 내부 구현 세부 사항으로 자유롭게 진화 가능하다는 점입니다. PR #405 와 같은 결입니다.

**옵션 B** — `helpers::utf16_pos_to_char_idx` 함수 자체를 `pub` 으로:

```rust
// src/document_core/helpers.rs
pub fn utf16_pos_to_char_idx(char_offsets: &[u32], utf16_pos: u32) -> usize { ... }
```

`pub(crate) mod helpers` 는 그대로 두되 본 함수만 외부 노출 — 변경 범위 최소. 다만 외부 호출자가 `Paragraph` 가 아닌 raw `char_offsets` 슬라이스를 직접 다뤄야 해서 호출부 ergonomics 가 살짝 불편합니다.

옵션 A 가 PR #405 의 결정과 일관되어 좀 더 자연스러워 보입니다만, 메인테이너님 의견 듣고 싶습니다.

## 영향

- 알고리즘 변경 없음 (visibility 완화 또는 메서드 캡슐화만) — semver MINOR
- 기존 내부 사용처 (cursor_nav, clipboard) 영향 없음 — 옵션 A 채택 시 기존 helper 는 thin wrapper 로 유지하거나 호출부를 `&self` 메서드로 점진 전환 가능
- 외부 binding 이 char_shape / line_seg 의 UTF-16 위치 필드를 codepoint 인덱스로 변환 가능

## 관련 이슈

- [#390](https://github.com/edwardkim/rhwp/issues/390) `[api] document_core::find_control_text_positions 외부 crate 노출 검토 부탁드립니다` — 같은 helpers 모듈, 같은 결의 외부 노출 사례 (옵션 A 채택, [PR #405](https://github.com/edwardkim/rhwp/pull/405) 가 cherry-pick 으로 v0.7.8 에 반영)

## 참고 위치

- `src/document_core/helpers.rs:189-192` (현재 구현, `pub(crate)`)
- `src/document_core/mod.rs:6` (`pub(crate) mod helpers;`)
- `src/model/paragraph.rs:22-24` (`Paragraph.char_offsets` doc-comment, UTF-16 단위 명시)
- `src/model/paragraph.rs:121-126` (`CharShapeRef.start_pos`, UTF-16 단위)
- `src/model/paragraph.rs:730` (옵션 A 시 메서드 추가 위치 — `control_text_positions` 인근)
