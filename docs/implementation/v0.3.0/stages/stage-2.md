# Stage S2 — FormulaBlock + Footnote/Endnote (완료)

**Status**: Frozen · **Target**: v0.3.0 · **Last updated**: 2026-04-26

**작업일**: 2026-04-26
**계획 문서**: [roadmap/v0.3.0/ir-expansion.md](../../../roadmap/v0.3.0/ir-expansion.md) §구현 스테이지 분할
**선행 stage**: [stage-1.md](stage-1.md) (PictureBlock + Furniture page_headers/footers)

## 스코프

ir-expansion.md §S2 row 정확 매핑:

- `FormulaBlock` Pydantic 모델 + Rust `Control::Equation` walker
- `FootnoteBlock` / `EndnoteBlock` Pydantic 모델 + Rust `Control::Footnote`/`Endnote` walker
- 본문 마커 위치는 그대로 `InlineRun.text` (수정 없음). 각주/미주 본문은 `furniture.footnotes` / `furniture.endnotes` 로 라우팅
- `Furniture.footnotes` 타입 강화 (`list[Block]` → `list[FootnoteBlock]`)
- `Furniture.endnotes` 신규 필드 (`list[EndnoteBlock]`)
- `Provenance.marker_prov` 패턴 — 본문 인용 마커 위치를 각주 본문 자체 위치 (`prov`) 와 별도 필드로 보존

S3 (ListItem + Caption + Toc + Field) 와 S4 (Schema GA + CLI/LangChain 정식 매핑) 는 본 스테이지 범위 밖.

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/ir/nodes.py` | +75 / -8 | `FormulaBlock`, `FootnoteBlock`, `EndnoteBlock` 추가, `_KNOWN_KINDS` `{paragraph, table, picture}` → 6 종 확장, `Block` 유니온 3 변형 추가, `Furniture.footnotes` 타입 `list[FootnoteBlock]` 강화 + `endnotes: list[EndnoteBlock]` 신규, `iter_blocks(scope="furniture")` 가 endnotes 포함 끝에 yield, `_walk_blocks` 가 `FootnoteBlock.blocks` / `EndnoteBlock.blocks` 재귀 진입, `Sequence[Block]` 시그니처로 invariant list 호환 |
| `python/rhwp/ir/__init__.pyi` | +9 | `EndnoteBlock` / `FootnoteBlock` / `FormulaBlock` re-export |
| `python/rhwp/ir/_raw_types.py` | +35 | `RawFormula`, `RawFootnote`, `RawEndnote` TypedDict; `RawParagraph.formulas`, `RawDocument.footnotes`/`endnotes` 신규 |
| `python/rhwp/ir/_mapper.py` | +75 | `_build_formula_block`, `_build_footnote_block`, `_build_endnote_block`. `build_hwp_document` 가 furniture footnotes/endnotes 채움. `_flatten_paragraph` 가 formulas 도 emit |
| `src/ir.rs` | +130 / -12 | `RawFormula`/`RawFootnote`/`RawEndnote` struct, `RawParagraph.formulas`, `RawDocument.footnotes`/`endnotes`. `build_raw_paragraph` 가 `Control::Equation` 도 추출. `build_raw_formula` + `simple_eq_text_alt` (over → /, sqrt → √, `{}` → `()`). `build_raw_footnote` / `build_raw_endnote`. `collect_furniture_from_paragraph` 확장 (Footnote/Endnote arm 추가). `FurnitureAcc` 누적 struct 도입 (clippy::too_many_arguments 회피) |
| `python/rhwp/integrations/langchain.py` | +27 | `_block_to_content_and_meta` 가 `FormulaBlock` (text_alt or script as content; script_kind/inline meta) 분기 + `FootnoteBlock`/`EndnoteBlock` 통합 분기 (paragraph 본문 평문 합쳐 content; number/marker 메타) |
| `python/rhwp/ir/schema/hwp_ir_v1.json` | +197 / -6 | 재생성 — 15 `$defs` (S1 12 + Formula/Footnote/Endnote 3), Furniture 가 endnotes 포함, footnotes type narrowing |
| `tests/test_ir_formula.py` | +280 (신규) | 19 테스트 — 모델 왕복/frozen/extra=forbid + script_kind 닫힌 Literal + model_copy 패턴 + mapper coverage + Formula in TableCell + Formula in FootnoteBlock + naive limit fix + 실제 샘플 lookup |
| `tests/test_ir_footnote.py` | +332 (신규) | 25 테스트 — Footnote/Endnote 분리된 두 타입 + frozen/extra=forbid + 재귀 (셀 안 표) + mapper preserve number/marker + furniture 라우팅 + iter_blocks 순서 (page_headers→footers→footnotes→endnotes) + recurse=True 진입 + body 분리 계약 |
| `tests/test_ir_schema_export.py` | +3 | `expected_nodes` 12 → 15 (FormulaBlock/FootnoteBlock/EndnoteBlock 추가) |
| `tests/test_ir_schema.py` | -3 / +5 | unknown-kind 픽스처 "footnote" → "list_item" (S2 에서 known 승격) / parametrize fixture 갱신 |
| `tests/test_ir_iter_blocks.py` | -7 / +25 | furniture order 테스트가 FootnoteBlock/EndnoteBlock 인스턴스 사용, known-kinds 검사 확장 |
| `tests/test_ir_roundtrip.py` | -7 / +21 | body kinds 검사 FormulaBlock 추가, furniture lists 검사 footnotes/endnotes 별도 타입 검증 |
| `tests/test_ir_furniture.py` | -10 / +33 | endnotes 수용 테스트로 전환 (S1 의 reject 테스트 flip), `_empty_raw_doc` 헬퍼 footnotes/endnotes 추가, raw paragraph 가 formulas 채움 |
| `tests/test_ir_tables.py` | +4 / -2 | TableCell.blocks 검사에 FormulaBlock 허용 |
| `tests/test_ir_mapper.py` | +6 / -1 | `_paragraph` helper 가 formulas=[] 채움 |
| `.github/workflows/ci.yml` | +1 | scoped pyright 목록에 `test_ir_formula.py` + `test_ir_footnote.py` 추가 |

## S2 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **`script_kind` 닫힌 Literal** | `Literal["hwp_eq", "latex", "mathml"]` | spec § 2. `model_copy(update={"script": tex, "script_kind": "latex"})` 패턴이 Pydantic frozen 모델과 자연스럽게 호환 |
| **HWP equation script → LaTeX 자동 변환 미제공** | raw `"hwp_eq"` 출고 + 사용자 책임 | spec § 비목표. 공개 변환기 부재 (조사 결과). `text_alt` 는 단순 정규화만 (RAG 폴백) — 정확 변환 사용자가 외부 도구로 |
| **각주/미주 분리된 두 타입** | `FootnoteBlock` ≠ `EndnoteBlock` | 상류 rhwp 가 분리, HWP 사용자 의도 다름 (페이지 하단 vs 문서 끝). Pandoc 통합 패턴 거부 |
| **각주 본문 위치** | `furniture.footnotes` / `endnotes` (body 와 분리) | spec § 3. RAG body 검색 오염 회피. 본문 마커 텍스트는 InlineRun.text 그대로 보존 — 마커만 보고 싶으면 body 만, 본문이 필요하면 furniture 명시 요청 |
| **`marker_prov` 별도 필드** | spec § 3 그대로 | 본문 인용 위치 ↔ 각주 본문 위치 분리. 현 시점은 둘 다 parent paragraph (section_idx, para_idx) 공유 — char_offset 까지의 marker precision 은 v0.4.0+ |
| **`marker_prov.char_start/char_end` = None** | parent paragraph 단위만 | 상류 rhwp 가 paragraph 안 control 의 character 위치를 직접 노출하지 않음 (field_ranges 매핑 필요). v0.4.0+ 검토. nodes.py FootnoteBlock docstring 에 명시 |
| **`Furniture.footnotes` 타입 강화** | `list[Block]` → `list[FootnoteBlock]` | spec § 8. v0.3.0 개발 중 단계 변경 — S1 의 `list[Block]` 은 placeholder 였고 실제 채움 시점에 강화 |
| **`Furniture.endnotes` 신규** | spec § 8 그대로 | v0.2.0 ↔ v0.3.0 호환 충돌 (extra="forbid") 가 endnotes 추가로 의도적 trigger — schema_version 1.0 ≠ 1.1 분기를 강제 |
| **`_walk_blocks` Sequence 시그니처** | `list[Block]` → `Sequence[Block]` | `furniture.footnotes: list[FootnoteBlock]` 같은 협소 타입 list 가 invariant 충돌 없이 수용. pyright Sequence 공변성 활용 |
| **`FurnitureAcc` 누적 struct** | 인자 4개 → struct 1개 | clippy::too_many_arguments (8/7 한계) 회피. 누적 vec 4개 묶음이 의미상 응집 — `#[allow]` 보다 cleaner |
| **`simple_eq_text_alt` naive replace** | 토큰 경계 무시 (e.g. `"sqrtish"` → `"√ish"`) | spec § 2 "단순 정규화" 약속의 의도적 한계. `text_alt` 는 None 폴백 가능, 정확 변환은 사용자 책임. 한계는 docstring + naive_limit_fix 테스트 로 픽스 |

## 비타협 제약 준수

- 모든 신규 IR 모델 (`FormulaBlock`, `FootnoteBlock`, `EndnoteBlock`) `ConfigDict(extra="forbid", frozen=True)`
- `script_kind: Literal[...]` — closed enum 으로 strict mode 토큰 마스킹 호환
- `Field(ge=/le=/gt=/lt=)` 사용 **없음** — `number: int`, `inline: bool` 모두 plain 타입
- mapper 도메인 분기 (text_alt 정규화는 Rust, 폴백 정책은 Python) — IR 진화 시 maturin rebuild 회피 패턴 보존
- `__init__.pyi` 만 변경 — `__init__.py` 는 docstring 만 (순환 import 방지)

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest -m "not slow"` | **291 passed** (S1 의 255 + S2 신규 36; 2 skipped — 샘플에 수식·미주 부재) |
| `uv run pyright python/ tests/<scoped CI list>` | **0 errors** |
| `uv run pyright tests/type_check_errors.py` | **4 intentional errors** (CI 검증 통과) |
| `cargo clippy --all-targets -- -D warnings` | clean |
| Schema JSON conformance (`test_load_schema_matches_export_schema`) | pass — 15 `$defs` 모두 동기화 |
| `code-reviewer` fresh-context 검증 | Critical 0 / Major 0 / Minor 5 (M1 naive_limit fix 픽스, M4 cross-container coverage 추가, M5 redundant import 제거, N6 mapper site comment 추가, M2/M3 알려진 한계로 명시) |
| 실제 샘플 e2e | aift.hwp 에서 footnote 1개 정상 추출 (`marker_prov=(2, 472)`, blocks=1) |

### 테스트 커버리지 (ir-expansion.md §S2 → 실제 케이스)

| ir-expansion.md 요구 | 테스트 |
|---|---|
| FormulaBlock script_kind 분기 / `text_alt` 폴백 | `test_formula_block_accepts_known_script_kinds[3]`, `test_formula_block_rejects_unknown_script_kind`, `test_build_formula_block_text_alt_can_be_none`, `test_simple_eq_text_alt_known_naive_limits` |
| FootnoteBlock / EndnoteBlock 의 marker_prov ↔ prov 분리 | `test_footnote_block_marker_and_prov_separately_assignable`, `test_build_footnote_block_preserves_number_and_marker` |
| 각주 안의 표 재귀 | `test_footnote_block_blocks_supports_recursion_with_table` |
| `recurse=True` 가 FootnoteBlock.blocks 진입 | `test_iter_blocks_recurse_enters_footnote_blocks`, `test_iter_blocks_recurse_enters_endnote_blocks` |
| body vs furniture 분리 | `test_footnotes_endnotes_never_appear_in_body`, `test_real_sample_body_excludes_header_footer_text` |
| furniture 순서 (page_headers→footers→footnotes→endnotes) | `test_iter_blocks_furniture_order_includes_footnotes_endnotes`, `test_build_hwp_document_preserves_header_footer_order` |
| Formula in TableCell / FootnoteBlock | `test_formula_inside_table_cell_is_flattened`, `test_formula_inside_footnote_body_is_flattened` |
| `endnotes` 신규 필드 수용 (S1 거부 → S2 수용) | `test_furniture_accepts_endnotes_field_in_s2`, `test_build_hwp_document_routes_endnotes_to_furniture` |

## 알려진 한계 (S3/S4 또는 후속 MINOR 에서 처리)

- **`marker_prov.char_start/char_end` = None** — 정확 위치 계산 알고리즘은 상류 `document_core::find_control_text_positions` 에 이미 존재하나 `pub(crate)` 라 외부 crate 에서 호출 불가. 상류 visibility 변경 요청 등록 (참조: [docs/upstream/issue-find-control-text-positions.md](../../../upstream/issue-find-control-text-positions.md)). 머지 + submodule pin 갱신 시점에 paragraph 단위 → character 단위로 격상 (v0.3.x patch 또는 v0.4.0 검토).
- **`simple_eq_text_alt` 토큰 경계 미인식** — `replace("sqrt", "√")` 가 `"sqrtish"` 같은 식별자 안 부분문자열도 치환. spec § 2 "단순 정규화" 의도적 한계, RAG 폴백용. 정확 LaTeX 가 필요하면 사용자가 외부 변환 + `model_copy` 사용.
- **Equation `inline` flag 항상 False** — 상류 `Equation.common.inline_object` 등에서 추론 가능하지만 v0.3.0 RAG 1차 사용처에서 차이 무의미. 디스플레이/인라인 구분이 필요해질 때 v0.4.0+ 활성화.
- **Footnote/Endnote 자체 안의 footnote 컨트롤은 silently dropped** — `build_raw_paragraph` 가 본문에서만 control 추출. 중첩 각주가 HWP 에서 실재 가능해질 때 walker 확장.
- **Furniture body separation 의 부정 검증은 spec 차원** — `test_furniture_accepts_endnotes_field_in_s2` 가 v0.2.0 reader 의 ValidationError 를 직접 시뮬하지 않음 (v0.2.0 schema 보존 안 함). spec § 호환성에 명시.

## S3 진입 조건 (인수인계)

S3 는 spec § 4-7 (ListItem + Caption + Toc + Field 4 종 일괄). S2 에서 고정한 계약:

1. **`Block` 유니온 + `_KNOWN_KINDS` 확장 패턴** — S3 는 `list_item`, `caption`, `toc`, `field` 추가 시 동일 패턴.
2. **`Furniture` 외 본문 컨테이너 — `CaptionBlock`** — `PictureBlock.caption: CaptionBlock | None` 필드 추가 (v0.3.0 S1 미배치). S3 에서 `_build_picture_block` 매핑 확장 + `TableBlock.caption_block: CaptionBlock | None` 추가 (기존 `caption: str | None` 호환 보존).
3. **mapper 평탄화 패턴** — `_flatten_paragraph` 가 ParagraphBlock → tables → pictures → formulas → list_items 순으로 emit. S3 에서 ListItemBlock 도 같은 위치에 추가.
4. **`Provenance.marker_prov` 패턴** — Footnote/Endnote 외에는 적용 대상 없음. ListItem/Caption/Toc/Field 는 단일 `prov` 만.
5. **`FieldKind` 닫힌 Literal 14 종 + `"unknown"`** — spec § 7. 상류 `FieldType` 이 추가될 때 `field_type_code: int | None` 으로 forward-compat.

## 참조

- 상위 설계: [roadmap/v0.3.0/ir-expansion.md](../../../roadmap/v0.3.0/ir-expansion.md)
- 결정 사항 증거: [design/v0.3.0/ir-expansion-research.md](../../../design/v0.3.0/ir-expansion-research.md)
- 상류 타입 (S2 매핑): `external/rhwp/src/model/{footnote,control}.rs`
- 선행 stage: [stage-1.md](stage-1.md)
- v0.2.0 선례: [implementation/v0.2.0/stages/](../../v0.2.0/stages/) (S1~S5)
