---
status: Frozen
last_updated: 2026-04-29
---

> **RESOLVED 2026-04-28** — 옵션 A 채택, [edwardkim/rhwp#390](https://github.com/edwardkim/rhwp/issues/390) closed by cherry-pick into `devel` (commits `2a69fe1` / `b855e2a` / `a59ce71`, [PR #405](https://github.com/edwardkim/rhwp/pull/405)). 상류 main 미반영 — 다음 `external/rhwp` pin bump 시 흡수 예정. 본 파일은 historical record 로 in-place Frozen (다른 v0.3.0 Frozen spec 이 본 파일 참조 → 삭제 대신 보존).

# 업스트림 제안 — `find_control_text_positions` 외부 노출

> 외부 binding (`rhwp-python`) 구현 중 업스트림에서 수정이 필요해 보이는 부분을 발견하여, Claude 로 조사를 진행한 결과입니다. 업스트림 머지 시 본 파일은 archive (또는 삭제) 처리.

## Summary

`document_core::find_control_text_positions(&Paragraph) -> Vec<usize>` 가 외부 crate 에서 호출 불가합니다. 알고리즘과 contract 는 prod-stable 이며 WASM 측에는 이미 노출되어 있어, `pub(crate) mod helpers` → `pub mod helpers` 또는 `Paragraph` 메서드 캡슐화로 해결 가능해 보입니다.

## 문제 상황

paragraph 안의 inline 컨트롤 (각주·미주 마커, 그림, 표, 수식) 이 `paragraph.text` 의 어느 character 인덱스에 위치하는지 외부 binding 에서 알 수 없습니다.

외부 binding (third-party PyO3 / napi / JNI 등) 이 RAG / IR 매핑 작업에서 다음 정보를 필요로 합니다:

- **각주·미주 마커 역추적**: 본문 paragraph 의 어느 character 위치에 각주 마커가 있는지 식별. 각주 본문은 별도 furniture 로 라우팅하더라도 마커의 정확한 character offset 이 RAG Provenance 에 보존되어야 검색 컨텍스트가 정확해집니다.
- **그림·수식의 paragraph 내 위치**: 단락 단위 (`para_idx`) 만으로는 텍스트 흐름 안의 정확한 위치 정보가 부족합니다.
- **InlineRun ↔ 컨트롤 매핑 검증**: 서식 런과 컨트롤이 같은 character 위치를 공유하는지 확인.

각 binding 이 알고리즘을 자체 복사하는 방식은 상류 변경 시 silent drift 위험이 있어, 이미 검증된 단일 source-of-truth 를 외부 노출하는 방향이 안전해 보입니다.

## 현재 상태

`src/document_core/helpers.rs:106` 에 함수가 존재합니다:

```rust
/// 반환: positions[i] = para.controls[i]가 삽입되어야 할 텍스트 문자 인덱스
pub(crate) fn find_control_text_positions(para: &Paragraph) -> Vec<usize> {
    // 본문 생략 — char_offsets 갭 분석 알고리즘 (~60 줄)
}
```

`src/document_core/mod.rs:6` 의 `pub(crate) mod helpers;` 때문에 외부 crate 에서는 접근 불가합니다.

이 함수는 `v0.5.0` initial commit 부터 존재해 온 helper 로, 현재 cursor / navigation / 렌더러 / 책갈피 쿼리 / 명령 (text editing, object ops) / WASM API 등 다양한 내부 경로에서 prod 사용 중이라 contract 가 안정된 상태로 보입니다.

## WASM 측 노출 선례

`src/wasm_api.rs:966` 에 동일 helper 가 이미 `#[wasm_bindgen]` 으로 노출되어 있습니다:

```rust
#[wasm_bindgen(js_name = getControlTextPositions)]
pub fn get_control_text_positions(&self, section_idx: u32, para_idx: u32) -> String {
    let sections = &self.document.sections;
    if let Some(sec) = sections.get(section_idx as usize) {
        if let Some(para) = sec.paragraphs.get(para_idx as usize) {
            let positions = crate::document_core::find_control_text_positions(para);
            return format!("[{}]", positions.iter().map(|p| p.to_string()).collect::<Vec<_>>().join(","));
        }
    }
    "[]".to_string()
}
```

WASM binding 사용 사례에서는 외부 노출이 이미 진행된 상태라, 다른 외부 crate 에서도 같은 정보가 필요한 경우 일관된 방식으로 노출이 가능하지 않을까 싶습니다.

같은 crate 내 호출이라 `pub(crate)` 면 충분한 상황이라, 외부 crate 까지의 visibility 는 자연스럽게 누락된 것으로 추정됩니다 (현재 `v0.7.7` 시점에서도 변경 없음).

## 제안

다음 중 하나를 검토 부탁드립니다:

**옵션 A** — `Paragraph` 인스턴스 메서드로 캡슐화:

```rust
// src/model/paragraph.rs (impl Paragraph 안)

/// `controls[i]` 가 `text` 의 어느 character 인덱스에 위치하는지 반환.
/// `char_offsets` 의 갭 (컨트롤당 8 UTF-16 코드 유닛) 으로 위치 복원.
pub fn control_text_positions(&self) -> Vec<usize> {
    // helpers::find_control_text_positions 와 동일 로직
}
```

장점은 외부 API surface 를 좁게 유지하면서 `Paragraph` 에 의미가 응집되고, helpers 모듈은 내부 구현 세부 사항으로 자유롭게 진화 가능하다는 점입니다.

**옵션 B** — `helpers` 모듈을 `pub` 으로 + 함수도 `pub`:

```rust
// src/document_core/mod.rs
pub mod helpers;  // pub(crate) → pub

// src/document_core/helpers.rs
pub fn find_control_text_positions(para: &Paragraph) -> Vec<usize> { ... }
```

변경 범위가 작은 대신, helpers 모듈의 다른 함수들 (`logical_to_text_offset` 등) 도 함께 외부에 노출되어 향후 helpers 진화 시 외부 contract 부담이 생길 수 있습니다.

옵션 A 가 외부 API 안정성 측면에서 좀 더 깔끔해 보이긴 합니다만, 메인테이너님 의견 듣고 싶습니다.

## 영향

- 알고리즘 변경 없음 (visibility 또는 메서드 캡슐화만) — semver MINOR
- 기존 내부 사용처 (`logical_to_text_offset`, 직접 호출들) 영향 없음
- 외부 binding 이 inline 컨트롤 마커의 character 위치를 IR Provenance 등에 활용 가능

## 관련 이슈

외부 binding API 노출 관련 이슈 시리즈와 같은 결로 보입니다:

- #269 `[api] insert_paragraph(paraIdx=paragraphCount) rejected — no path to append at section end`
- #270 `[bug] set_field value is lost after save → reopen (in-memory OK, not persisted)`
- #271 `[api] No delete_paragraph WASM function — text-blanking only, structure cannot be removed`
- #272 `[api] Expose HwpCtrl / 312 Action registry via WASM (run_action or flattened methods)`

위는 모두 WASM binding 측 누락 사례이고, 본 이슈는 같은 결의 외부 Rust crate 측 누락 사례에 해당합니다.

## 참고 위치

- `src/document_core/helpers.rs:106` (현재 구현, `pub(crate)`)
- `src/document_core/mod.rs:6-7` (`pub(crate) mod helpers; pub(crate) use helpers::*;`)
- `src/wasm_api.rs:966` (WASM 측 노출 선례)
- `src/model/paragraph.rs:185` (옵션 A 시 메서드 추가 위치)
