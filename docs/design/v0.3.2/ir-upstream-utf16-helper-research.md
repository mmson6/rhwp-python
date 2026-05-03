---
status: Frozen
description: "v0.3.2 ir-upstream-utf16-helper ADR — API source / 'u32::MAX' sentinel / 'fallback_end' 인자 / 단위 테스트 처리 4 결정의 근거"
ga: v0.3.2
last_updated: 2026-05-03
---

# v0.3.2 ir-upstream-utf16-helper — 설계 의사결정 리서치 요약

[v0.3.2/ir-upstream-utf16-helper.md](../../roadmap/v0.3.2/ir-upstream-utf16-helper.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 4건의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | API source | A: 자체 복사본 (`utf16_to_cp`) 보존 / B: 상류 `Paragraph::utf16_pos_to_char_idx()` (PR #494) / C: `helpers::utf16_pos_to_char_idx` (옵션 B 노출 가정) | **B** | 자체 복사본은 본 binding 운영 정책 ("상류 신뢰 + 결함 시 PR") 위반. 상류는 옵션 A 채택 — 옵션 C 는 머지 안 됨 |
| 2 | `u32::MAX` sentinel 처리 | A: 호출부 short-circuit 보존 / B: 호출부 분기 제거, 자연 처리 위임 | **B** | `iter().position(\|&off\| off >= u32::MAX)` 가 항상 `None` → `unwrap_or(char_offsets.len())` 로 자체 short-circuit 결과와 비트 단위 동일. SSOT 분산 회피 |
| 3 | `fallback_end` 인자 제거 | A: invariant 신뢰하고 인자 제거 / B: 방어적 코딩으로 인자 유지 | **A** | `paragraph.rs:22-24` doc-comment 가 `char_offsets.len() == text.chars().count()` 를 정의로 보장. 상류 contract 의 별도 매개변수 운반은 SSOT 분산 |
| 4 | 자체 단위 테스트 처리 | A: 함수 + 테스트 동시 삭제 / B: `Paragraph::utf16_pos_to_char_idx` 호출 wrapper 테스트 보존 / C: `build_char_runs` 통합 테스트 강화 | **A** | 자체 함수가 사라지면 본체 단위 테스트는 *없는 함수* 검증. 상류 자체 테스트 6건 + fixture 회귀가 이미 끝-단 가드 |

## 1. API source — 자체 복사본 vs 상류 `pub` 메서드

### 팩트

- 자체 복사본 위치: `src/ir.rs:421-436` — `fn utf16_to_cp(char_offsets: &[u32], utf16: u32, fallback_end: usize) -> usize`
- 알고리즘 본체: `iter().position(|&off| off >= utf16).unwrap_or(fallback_end)` (1줄) + `u32::MAX` short-circuit
- 상류 v0.7.7 까지: `pub(crate) fn utf16_pos_to_char_idx(char_offsets: &[u32], utf16_pos: u32) -> usize` (`helpers.rs:189-192`) — 외부 crate 접근 불가
- 본 binding 이 [docs/upstream/issue-utf16-pos-to-char-idx.md](../../upstream/issue-utf16-pos-to-char-idx.md) 로 옵션 A (Paragraph 인스턴스 메서드) / 옵션 B (helpers `pub`) 두 안 제시
- 상류는 옵션 A 채택, [Task #484](https://github.com/edwardkim/rhwp/issues/484) / [PR #494](https://github.com/edwardkim/rhwp/pull/494) 머지 (cherry-pick @DanMeon 3 commits), v0.7.9 GA
- 현재 상류 메서드: `external/rhwp/src/model/paragraph.rs:818-823` — `pub fn utf16_pos_to_char_idx(&self, utf16_pos: u32) -> usize`
- 선례: v0.3.1 가 동일 결로 [PR #405 (Task #390)](https://github.com/edwardkim/rhwp/pull/405) 의 `Paragraph::control_text_positions` 채택

### 검증자 반박

- "알고리즘이 1줄인데 SSOT 단일화의 가치가 있나? 상류 docstring 도 'silent drift 위험은 무시 가능' 으로 평가" → 상류 평가는 *상류 자체 안에서의* 동기화 비용. 본 binding 은 *외부 호출자* 입장 — `char_offsets` 의 의미축이 미묘하게 변하면 상류 자체 호출자는 컴파일 / 테스트로 즉시 드러나지만 외부 binding 은 *런타임 결과 어긋남* 으로만 드러남. silent drift 비용 비대칭이 본질
- "v0.3.1 PR #405 (`control_text_positions`) 는 알고리즘이 복잡해서 상류 활용이 자연이지만, 본 case 는 1줄이라 다르지 않나?" → 알고리즘 복잡도와 무관하게 *SSOT 단일화의 정책적 가치* 가 결정 축. cutoff 가 모호해지면 정책 자체가 약화

### 최종 결정

**옵션 B — 상류 `Paragraph::utf16_pos_to_char_idx` 사용**. v0.3.1 결정 1 과 같은 결 — 본 binding 의 "상류 신뢰 + 결함 시 PR" 정책 일관 적용.

### 1차 소스

- 상류 PR: <https://github.com/edwardkim/rhwp/pull/494>
- 상류 Task: <https://github.com/edwardkim/rhwp/issues/484>
- 상류 메서드: `external/rhwp/src/model/paragraph.rs:818-823`
- 본 binding 이 제출한 issue 초안: [docs/upstream/issue-utf16-pos-to-char-idx.md](../../upstream/issue-utf16-pos-to-char-idx.md)

## 2. `u32::MAX` sentinel 처리 — short-circuit 보존 vs 자연 처리

### 팩트

- 자체 함수의 sentinel 분기 (`src/ir.rs:427-429`):

  ```rust
  if utf16 == u32::MAX {
      return fallback_end;
  }
  ```
- 호출 패턴: 마지막 char_shape 의 `end_utf16` 를 `u32::MAX` 로 두는 sentinel (`src/ir.rs:390-394`) — "이 shape 는 paragraph 끝까지 적용" 의미
- 상류 메서드 본체:

  ```rust
  self.char_offsets.iter().position(|&off| off >= utf16_pos).unwrap_or(self.char_offsets.len())
  ```
- `utf16_pos = u32::MAX` 입력 시 동작: `char_offsets` 의 모든 entry 는 정상 코드 유닛 인덱스 (실제 텍스트 길이 한도 내) → 어떤 entry 도 `u32::MAX` 이상 불가 → `iter().position` 결과 항상 `None` → `unwrap_or(char_offsets.len())` 도달 → `char_offsets.len()` 반환
- `char_offsets.len() == text.chars().count() == total_cp == fallback_end` (호출부 invariant) — 비트 단위 동일

### 검증자 반박

- "iter().position 이 모든 entry traverse 하는데 short-circuit 이 효율 우위 아닌가?" → paragraph 당 char_shapes 마지막 1회. char_offsets.len() 보통 < 1000 → O(n) traverse 1회는 마이크로초 단위. PDF 렌더 / SVG 직렬화 / Rust→Python 타입 변환의 millisecond 비용에 비해 무시 가능
- "방어적 코딩으로 short-circuit 유지하는 게 안전하지 않나?" → 코드 두 군데에 동일 의미 분산 보유. 어느 한 쪽이 변경되면 다른 쪽이 silent stale — 방어적 코딩이 도리어 *동기화 부담*. 단일 경로가 SSOT 부합

### 최종 결정

**옵션 B — 호출부 분기 제거, 자연 처리 위임**. 두 경로 비트 단위 동일 + 효율 차이 무시 가능 + SSOT 원칙. 상류 메서드의 docstring 이 "모든 entry 가 작으면 `char_offsets.len()`" 를 명시 — 자연 처리가 *문서화된 contract*.

### 1차 소스

- 자체 sentinel 호출 패턴: `src/ir.rs:390-397` (`build_char_runs`)
- 상류 메서드 docstring: `external/rhwp/src/model/paragraph.rs:803-823`
- `Vec<u32>::iter().position` semantics: <https://doc.rust-lang.org/std/iter/trait.Iterator.html#method.position>

## 3. `fallback_end` 인자 제거 — invariant 신뢰 vs 방어적 명시

### 팩트

- 자체 함수의 fallback 인자 (`src/ir.rs:426`): `fallback_end: usize`
- 호출부 (`src/ir.rs:396-397`): `utf16_to_cp(&para.char_offsets, start_utf16, total_cp)` — `total_cp = para.text.chars().count()` 명시 전달
- 상류 메서드는 인자 없음 — 항상 `self.char_offsets.len()` 반환
- 상류 contract (`paragraph.rs:22-24` doc-comment): `char_offsets[i] = text[i] 에 해당하는 원본 UTF-16 코드 유닛 인덱스` → `char_offsets.len() == text.chars().count()` (i ↔ text codepoint 1:1)
- v0.3.1 [AC-12] 는 다른 종류의 contract (`controls.len() == positions.len()`) 에 `assert_eq!` 가드 강제

### 검증자 반박

- "v0.3.1 [AC-12] 와 정책 비대칭이다 — 둘 다 상류 contract 인데 왜 다른 정책?" → contract 종류 차이. v0.3.1 contract 는 *두 별개 컬렉션* 길이 일치 (paragraph.rs:734/765/786/796 *4 분기* 각자 보장 — 한 분기에서 push 빠지면 silent drift, 상류 자체 CI 가 4 분기 각각을 검증하는지 불확실). v0.3.2 contract 는 *한 paragraph 의 내부 정의 일관성* (`char_offsets[i] = text[i]` 의 1:1 정의) — 깨지면 cursor_nav / clipboard / 렌더 *전부 동시 깨짐* → 상류 prod 가 매일 호출 (cursor_nav 3회, clipboard 1회, 렌더 다수) 하는 invariant 라 drift 시 상류 CI 즉시 잡음. 검증 비용 비대칭이 정책 비대칭 정당화
- "그래도 invariant 명시 보유가 self-documenting 아닌가?" → 본 결정 항목 3 + 본 §3 자체 + paragraph.rs:22-24 doc-comment 가 self-documenting. 코드 인자로 contract 운반은 인자 의미를 곁가지로 만들어 *모호함* 추가

### 최종 결정

**옵션 A — invariant 신뢰하고 인자 제거**. `paragraph.rs:22-24` 가 SSOT 인 contract 를 본 binding 이 별도 매개변수로 이중 보유는 SSOT 분산. 호출부 단순화 (`para.utf16_pos_to_char_idx(start_utf16)` — 단일 인자) 가 가독성 우위.

### 1차 소스

- 상류 `char_offsets` 의미 정의: `external/rhwp/src/model/paragraph.rs:22-24`
- 자체 `total_cp` 정의: `src/ir.rs:381` (`para.text.chars().count()`)
- 상류 메서드 시그니처: `external/rhwp/src/model/paragraph.rs:818`

## 4. 자체 단위 테스트 처리 — 삭제 vs wrapper 보존 vs 통합 강화

### 팩트

- 자체 단위 테스트 위치 (`src/ir.rs:876-890`):
  - `utf16_to_cp_sentinel_returns_fallback` — `u32::MAX` 입력 시 fallback_end 반환
  - `utf16_to_cp_matches_first_ge` — SMP (2 코드 유닛) 혼용 paragraph first-greater-or-equal
- 상류 자체 단위 테스트: Task #484 Stage 2 에서 6 건 추가 (PR #494 의 일부)
- 본 binding 의 통합 테스트:
  - `tests/test_ir_mapper.py` — `_build_inline_runs` 폴백 정책
  - `tests/test_ir_*.py` (전체) — `Document.to_ir()` 출력 회귀 가드 (real HWP fixture 기반)

### 검증자 반박

- "옵션 A 면 회귀 가드 약해지는 것 아닌가?" → fixture 회귀 + 폴백 테스트가 끝-단 가드. 자체 단위 테스트는 *함수 단위* 인데 함수가 사라진 이상 통합 테스트가 직접 결과 검증
- "옵션 B (wrapper 테스트) 가 self-documenting 가치 있나?" → wrapper 테스트는 *상류 메서드 호출했더니 상류 메서드 결과* 의 토톨로지. 상류 자체 6 건이 본질 검증 — 본 binding 반복은 동어반복
- "옵션 C (통합 테스트 강화) 는?" → v0.3.1 baseline 회귀가 이미 byte-equal IR 가드. 별도 강화는 같은 검증 반복

### 최종 결정

**옵션 A — 함수 + 단위 테스트 동시 삭제**. 함수가 사라지면 단위 테스트도 자연스럽게 사라짐. 회귀 가드는 fixture 회귀 + 상류 자체 단위 테스트 6 건 이중 보유.

### 1차 소스

- 자체 단위 테스트: `src/ir.rs:876-890`
- 상류 자체 단위 테스트 추가 commit: <https://github.com/edwardkim/rhwp/commit/36631fd> (`Task #484 Stage 2: 단위 테스트 6건 추가`)

## 참조

- [roadmap/v0.3.2/ir-upstream-utf16-helper.md](../../roadmap/v0.3.2/ir-upstream-utf16-helper.md) — 본 리서치의 결정 요약
- [docs/upstream/issue-utf16-pos-to-char-idx.md](../../upstream/issue-utf16-pos-to-char-idx.md) — 본 binding 이 상류에 제출한 이슈 초안 (v0.3.2 GA 시 in-place Frozen)
