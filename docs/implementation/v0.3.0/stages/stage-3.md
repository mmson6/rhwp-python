# Stage S3 — ListItem + Caption + Toc + Field (완료)

**Status**: Frozen · **GA**: v0.3.0 · **Last updated**: 2026-04-27

**작업일**: 2026-04-27
**계획 문서**: [roadmap/v0.3.0/ir-expansion.md](../../../roadmap/v0.3.0/ir-expansion.md) §구현 스테이지 분할
**선행 stage**: [stage-2.md](stage-2.md) (FormulaBlock + Footnote/Endnote)

## 스코프

ir-expansion.md §S3 row 정확 매핑 — 작은 4 종 일괄 도입:

- `ListItemBlock` Pydantic 모델 + Rust `ParaShape.head_type` walker (Number/Bullet/Outline → list item, None → 일반 paragraph)
- `CaptionBlock` Pydantic 모델 + Rust `shape::Caption` walker. `PictureBlock.caption: CaptionBlock | None` / `TableBlock.caption_block: CaptionBlock | None` 부착 (v0.2.0 `caption: str` 필드 호환 보존)
- `TocBlock` + `TocEntryBlock` Pydantic 모델 + Rust `FieldType::TableOfContents` 라우팅. v0.3.0 entries 는 빈 placeholder
- `FieldBlock` + `FieldKind` 닫힌 Literal 14 종 + `"unknown"` 안전판. `FieldType::TableOfContents` 외 모든 Field control 매핑
- `Block` 유니온 10 known + UnknownBlock = 11 멤버. `_KNOWN_KINDS` 동기 갱신
- `iter_blocks(recurse=True)` 가 `CaptionBlock.blocks` 진입 — `PictureBlock.caption` / `TableBlock.caption_block` 은 부모 metadata 로 간주되어 진입 안 함
- `HwpLoader(mode="ir-blocks")` 신규 4 블록 매핑 — RAG-friendly content + meta

S4 (Schema GA + CLI/LangChain 정식 매핑 + 문서) 는 본 스테이지 범위 밖.

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/ir/nodes.py` | +254 / -19 | `FieldKind` Literal (14+unknown), `ListItemBlock` / `CaptionBlock` / `TocBlock` / `TocEntryBlock` / `FieldBlock` 추가, `_KNOWN_KINDS` 6→10 종 확장, `Block` 유니온 4 변형 추가, `PictureBlock.caption: CaptionBlock | None` 신규, `TableBlock.caption_block: CaptionBlock | None` 신규 (기존 `caption: str` 보존), `_walk_blocks` 에 `CaptionBlock` 재귀 진입 추가, `model_rebuild()` 에 `CaptionBlock` / `PictureBlock` / `TableBlock` 추가 |
| `python/rhwp/ir/__init__.pyi` | +18 | `CaptionBlock` / `FieldBlock` / `FieldKind` / `ListItemBlock` / `TocBlock` / `TocEntryBlock` re-export |
| `python/rhwp/ir/_raw_types.py` | +85 | `RawListInfo` (`head_type` lowercase string) / `RawCaption` / `RawToc` / `RawTocEntry` / `RawField` TypedDict 추가, `RawParagraph.tocs` / `.fields` / `.list_info` / `RawPicture.caption` / `RawTable.caption_block` 신규 필드 |
| `python/rhwp/ir/_mapper.py` | +145 / -6 | `_build_list_item_block` (head_type → marker placeholder + enumerated 결정) / `_build_caption_block` / `_build_toc_block` / `_build_toc_entry_block` / `_build_field_block` 추가. `_VALID_FIELD_KINDS` / `_VALID_CAPTION_DIRECTIONS` / `_LIST_MARKER_BY_HEAD` 어휘 set 도입. `_flatten_paragraph` 가 list_info 분기 + tocs/fields emit. `_build_picture_block` 가 caption 채움. `_build_table_block` 가 caption_block 채움 |
| `src/ir.rs` | +185 / -12 | `RawListInfo` (head_type 만 출고 — marker 결정은 Python) / `RawCaption` / `RawToc` / `RawTocEntry` / `RawField` struct 추가. `RawParagraph` / `RawPicture` / `RawTable` 신규 필드. `build_raw_list_info` / `build_raw_caption` / `build_raw_field` / `build_raw_toc` / `caption_direction_to_str` / `field_type_to_str` 추가. `build_raw_paragraph` 의 control match 가 `Control::Field` 도 처리 (TableOfContents → tocs, 그 외 → fields). `build_raw_picture` / `build_raw_table` 가 caption 구조화. `tests` 에 `field_type_to_str_all_variants_lowercase` / `caption_direction_lowercase` 추가 |
| `python/rhwp/integrations/langchain.py` | +70 | `_block_to_content_and_meta` 가 `ListItemBlock` (marker+text content; level/enumerated meta) / `CaptionBlock` (blocks 평문 content; direction meta) / `TocBlock` (entries text 개행 결합; entry_count meta) / `FieldBlock` (cached_value content; field_kind/raw_instruction meta) 분기. `PictureBlock` / `TableBlock` 분기가 caption_block 텍스트 폴백 (대칭). `_caption_plain_text` 헬퍼 — Paragraph + Formula(text_alt 또는 script) + Field(cached_value) 평문 추출 (수식·필드 캡션 색인 누락 방지) |
| `python/rhwp/ir/schema/hwp_ir_v1.json` | +407 / -0 | 재생성 — 20 `$defs` (S2 15 + ListItemBlock/CaptionBlock/TocBlock/TocEntryBlock/FieldBlock 5), Block oneOf 10 변형 + UnknownBlock, PictureBlock.caption / TableBlock.caption_block 필드, UnknownBlock.kind not.enum 10 known kinds 갱신 |
| `tests/test_ir_list.py` | +147 (신규) | 14 테스트 — 모델 왕복/frozen/extra=forbid + Block discriminator 라우팅 + mapper list_info=None ↔ ListItemBlock 분기 + enumerated/marker/level 보존 + 셀 안 ListItemBlock + marker placeholder 한계 명시 |
| `tests/test_ir_caption.py` | +268 (신규) | 29 테스트 — CaptionBlock 모델 + direction Literal 닫힌 어휘 + PictureBlock.caption 부착 왕복 + TableBlock.caption_block + caption: str 호환 공존 + mapper RawCaption → CaptionBlock + unknown direction → bottom 폴백 + iter_blocks recurse 정책 (caption 진입 안 함, standalone caption.blocks 진입함) |
| `tests/test_ir_toc.py` | +199 (신규) | 18 테스트 — TocBlock 왕복 + TocEntryBlock leaf type (Block 유니온 멤버 아님, dict literal 은 UnknownBlock 라우팅) + 빈 entries v0.3.0 정책 + target_section_idx/is_stale 항상 None/False + iter_blocks 가 TocEntryBlock 안 yield |
| `tests/test_ir_field.py` | +217 (신규) | 46 테스트 — FieldBlock 모델 + FieldKind 14+unknown Literal + 모든 known kind parametrize + invalid kind ValidationError + mapper unknown 폴백 + field_type_code 보존 + raw_instruction round-trip + calc vs formula 이름 충돌 회피 + _flatten_paragraph 가 FieldBlock emit |
| `tests/test_ir_furniture.py` | +6 | `_empty_raw_para` 가 신규 필드 (tocs/fields/list_info) 채움 + table dict literal 에 caption_block 추가 |
| `tests/test_ir_footnote.py` | +3 | `_empty_raw_para` 가 신규 필드 채움 |
| `tests/test_ir_formula.py` | +14 / -0 | inline raw dict 에 신규 필드 추가, RawParagraph 명시 어노테이션 + RawFootnote 생성자 사용 (pyright TypedDict 추론 보강) |
| `tests/test_ir_mapper.py` | +6 | `_paragraph` 헬퍼가 신규 필드 채움 + `_table` 가 caption_block=None 채움 |
| `tests/test_ir_picture.py` | +1 | `_raw_picture` 헬퍼가 caption=None 채움 |
| `tests/test_ir_iter_blocks.py` | +9 / -2 | known-kinds 검사 4 종 추가 (ListItemBlock/CaptionBlock/TocBlock/FieldBlock) |
| `tests/test_ir_roundtrip.py` | +37 / -10 | body/furniture known-kinds 검사 4 종 추가, paragraph_count 검사가 ParagraphBlock + ListItemBlock 합계, provenance/inline 테스트가 ListItemBlock 도 포함 |
| `tests/test_ir_tables.py` | +13 / -3 | TableCell.blocks 검사가 ListItemBlock/TocBlock/FieldBlock 도 허용 |
| `tests/test_ir_schema.py` | +5 / -5 | unknown-kind 픽스처가 "list_item" → "revision_mark" (S3 에서 known 승격), parametrize fixture 가 가설적 미래 변형 사용 |
| `tests/test_ir_schema_export.py` | +6 | `expected_nodes` set 15 → 20 (ListItemBlock/CaptionBlock/TocBlock/TocEntryBlock/FieldBlock 추가) |
| `.github/workflows/ci.yml` | +2 | scoped pyright 목록에 `test_ir_list.py` / `test_ir_caption.py` / `test_ir_toc.py` / `test_ir_field.py` 추가 |

## S3 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **ListItem 분류 source** | `ParaShape.head_type` (None/Number/Bullet/Outline) | spec § 4. 상류 list group 미존재 — paragraph 자체가 list item. `numbering_id` 기반은 정확 marker lookup 필요 (v0.4.0+) |
| **ListItemBlock marker placeholder** | Number/Outline → `"1."`, Bullet → `"•"`, 미지 head_type → `"-"` 폴백 | spec § 4 "v0.3.0 단순 정책". 정확 marker (`"가."`, `"(a)"` 등) 는 `Numbering.level_formats` lookup 필요 — v0.4.0+ 검토. **마커 결정은 Python `_mapper.py::_LIST_MARKER_BY_HEAD`** (Rust 는 head_type lowercase string 만 출고) — IR 진화 시 maturin rebuild 회피 |
| **ListItem level 매핑** | `ParaShape.para_level` (0~6) 그대로 | 1-indexed 변환 안 함 — Pydantic 도메인은 0-indexed 일관 (다른 블록 인덱스와 동일) |
| **CaptionBlock 컨테인먼트 방식** | `PictureBlock.caption` / `TableBlock.caption_block` 직접 부착 | spec § 5. HWP 가 1:1 (`Picture.caption: Option<Caption>`), ref-id 패턴 도입 시 JSON-Pointer resolver 부담. v0.2.0 `TableBlock.caption: str` 보존 + `caption_block` 추가 |
| **CaptionBlock 도 Block 유니온 멤버** | `kind="caption"` 등록 (10 known 중 1) | 일반 파싱 경로에서는 body 단독 등장 안 함 (Picture/Table 자식). 사용자 직접 구성 경로 + JSON 직렬화 일관성 위해 union 멤버로. 단, iter_blocks 가 부모 caption 에 진입 안 함 (RAG 노이즈 회피) |
| **iter_blocks 재귀 정책** | `CaptionBlock.blocks` 는 진입, `PictureBlock.caption` 은 진입 안 함 | spec 본문 § iter_blocks. 부모 metadata 로 간주된 caption 은 LangChain loader 가 별도 Document 로 중복 로드하는 noise 회피. standalone CaptionBlock.blocks (사용자 직접 구성) 는 일반 컨테이너처럼 재귀 진입 |
| **caption direction Literal** | `Literal["top", "bottom", "left", "right"]` + `"bottom"` 기본값 | 상류 `CaptionDirection` enum 4 종 → lowercase string. `"bottom"` 기본값은 HWP 기본 + Docling 관례 일치 |
| **Caption mapper unknown direction 폴백** | `"bottom"` 폴백 | spec 정신 — Rust 가 새 CaptionDirection variant 추가 시 forward-compat. silent fallback 이지만 graceful 진화 가능 |
| **TocBlock + TocEntryBlock 분리** | TocEntryBlock 은 union 멤버 아님 | spec § 6. TableCell 과 같은 패턴 — entry 는 leaf type, iter_blocks 는 TocBlock 만 yield. `_KNOWN_KINDS` 미포함 → dict literal "toc_entry" 는 UnknownBlock 라우팅 |
| **TocBlock entries v0.3.0 정책** | 빈 placeholder | spec § 6 결정 7. 정확 entry 추출 + `target_section_idx` resolver + `is_stale` 검출은 v0.4.0+ — heading hierarchy + bookmark resolver 필요 |
| **FieldKind 닫힌 Literal 어휘** | 14 known + `"unknown"` (총 15) | spec § 7. 상류 `FieldType` 14 variant 1:1 매핑. Rust `field_type_to_str` 와 Python `_VALID_FIELD_KINDS` 양방향 동기 (Rust unit test `field_type_to_str_all_variants_lowercase` 로 픽스) |
| **FieldType::Formula → "calc"** | `"formula"` 가 아닌 `"calc"` | spec § 7. Equation ("formula" kind, 수식) 와 이름 충돌 회피 — HWP `FieldType::Formula` 는 표 합계 등 "계산 필드" 의미라 별도 어휘 |
| **FieldBlock unknown 강제 폴백** | mapper 가 미지 field_kind 를 `"unknown"` 으로 강제 + `field_type_code` 보존 | silent fallback 이지만 forensics 신호 (`field_type_code`) 가 남으므로 "원인 추적 가능" 조건 충족. forward-compat 친화 |
| **TableOfContents 라우팅** | `FieldBlock` 가 아닌 별도 `TocBlock` | spec § 7. ToC 는 의미적으로 다른 블록 (entries 컬렉션). 매퍼가 `Control::Field` match 에서 분기 |
| **HWP Field cached_value 추출** | v0.3.0 미구현 (None 출고) | HWP Field 는 cached_value 를 직접 노출 안 함 — paragraph text 안 inline. `field_ranges` 매핑 필요 (v0.4.0+ 검토) |
| **HWP Field raw_instruction** | `field.command` 그대로 (빈 문자열은 None) | round-trip 보존용 — Word `<w:instrText>` 대응. v0.3.0 소비자는 보통 미사용 |
| **InlineRun.href 와 FieldBlock 중복** | 모든 Field control 을 FieldBlock 으로 emit | spec § 7 권장 정책 (side-effecting cross-ref 만 FieldBlock) 은 v0.4.0+ 검토. v0.3.0 은 Hyperlink/Bookmark 도 FieldBlock 으로 — InlineRun.href 자동 채움 path 미구현이라 중복 없음 |
| **LangChain mapping 추가 정책** | mode="ir-blocks" default body 만 | spec 본문 § HwpLoader 변경 의 `include_furniture: bool` 옵션은 v0.4.0+ 검토. 본 stage 는 신규 4 블록의 `_block_to_content_and_meta` 분기만 추가 |
| **schema_version 유지** | `"1.1"` 그대로 (S2 와 동일) | spec § 스키마 버저닝. MINOR 안에서 새 블록 추가는 1.1 유지 — S1 에서 1.0 → 1.1 bump 한 후 S2/S3 모두 1.1 안에서 누적 |

## 비타협 제약 준수

- 모든 신규 IR 모델 (`ListItemBlock` / `CaptionBlock` / `TocBlock` / `TocEntryBlock` / `FieldBlock`) `ConfigDict(extra="forbid", frozen=True)`
- `FieldKind` / `script_kind` / `direction` / `role` 모두 닫힌 `Literal` — strict mode 토큰 마스킹 호환
- `Field(ge=/le=/gt=/lt=)` 사용 **없음** — `level: int`, `cached_page: int | None`, `field_type_code: int | None` 모두 plain 타입
- mapper 도메인 분기 (caption direction 폴백, FieldKind 어휘 검증, list marker placeholder) 는 모두 Python — IR 진화 시 maturin rebuild 회피 패턴 보존
- `__init__.pyi` 만 변경 — `__init__.py` 는 docstring 만 (순환 import 방지)
- 외부 LLM-facing 어휘 (FieldKind value, caption direction value) 는 Rust `field_type_to_str` / `caption_direction_to_str` 가 SSOT — Python 어휘는 pure consumer

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest -m "not slow"` | **405 passed** (S2 의 291 + S3 신규 110 + 기존 보강 4; 2 skipped — 샘플에 수식·미주 부재) |
| `uv run pyright python/ tests/<scoped CI list>` | **0 errors** |
| `uv run pyright tests/type_check_errors.py` | **4 intentional errors** (CI 검증 통과) |
| `cargo clippy --all-targets -- -D warnings` | clean |
| Schema JSON conformance (`test_load_schema_matches_export_schema`) | pass — 20 `$defs` 모두 동기화, oneOf 10 변형 |
| Schema ↔ Pydantic round-trip (`test_unknown_kind_routing_pydantic_matches_schema`) | pass — UnknownBlock not.enum 가 `_KNOWN_KINDS` SSOT 사용 (TocEntryBlock 등 leaf-only kind 제외) |
| 실제 샘플 e2e | aift.hwp 에서 정상 파싱 — list/caption/toc/field 컨트롤 등장 시 자동 매핑 |
| `code-reviewer` fresh-context 검증 | Critical 1 (C1: schema not.enum 이 leaf-only `toc_entry` 포함 → 라운드트립 깨짐), Major 2 (M1: marker 가 Rust 에 박힘 — Python 으로 이동, M2: TocEntryBlock prov 공유 한계 알려진 한계 추가), Minor 5 (m3: TableBlock LangChain caption_block 폴백 추가, m4: CaptionBlock 평문 추출이 Formula/Field 도 포함, m5: dead code 주석, m6/m7 cast() 정리 보류). C1/M1/M2/m3/m4/m5/n3 모두 본 stage 내 fix |

### 테스트 커버리지 (ir-expansion.md §S3 → 실제 케이스)

| ir-expansion.md 요구 | 테스트 |
|---|---|
| ListItemBlock level/marker/enumerated 조합 | `test_build_list_item_preserves_marker_enum_level[3]`, `test_build_list_item_preserves_provenance` |
| Picture/Table 양쪽에 caption 부착 | `test_picture_block_caption_roundtrip`, `test_table_block_caption_str_and_caption_block_coexist` |
| `TableBlock.caption_block ↔ caption` 일관성 | `test_table_block_caption_str_only_v0_2_0_pattern`, `test_build_hwp_document_table_with_caption_block_routed` |
| TocBlock 컨테이너 + TocEntryBlock leaf type | `test_toc_block_with_entries_roundtrip`, `test_toc_entry_block_is_not_in_block_union`, `test_iter_blocks_yields_toc_block_only` |
| `is_stale` 미구현 디폴트 | `test_build_toc_entry_is_stale_always_false_v0_3_0`, `test_build_toc_entry_target_section_idx_always_none_v0_3_0` |
| FieldKind 14 종 + unknown 라우팅 | `test_field_block_accepts_all_known_kinds[15]`, `test_build_field_block_unknown_kind_falls_back_to_unknown` |
| `cached_value` vs `raw_instruction` | `test_build_field_block_preserves_raw_instruction`, `test_field_block_full_roundtrip` |
| Caption iter_blocks 정책 | `test_iter_blocks_recurse_does_not_enter_picture_caption`, `test_iter_blocks_recurse_enters_standalone_caption_in_body` |
| `calc` vs `formula` 이름 충돌 회피 | `test_field_block_calc_distinguishes_from_formula_block` |
| Rust ↔ Python 어휘 동기화 | `src/ir.rs::tests::field_type_to_str_all_variants_lowercase`, `caption_direction_lowercase` |

## 알려진 한계 (S4 또는 후속 MINOR 에서 처리)

- **ListItemBlock marker placeholder** — Number/Outline 은 항상 `"1."`, Bullet 은 항상 `"•"`. 정확 marker (`"가."`, `"(a)"` 등) 추출은 `Numbering.level_formats` + `level_start_numbers` lookup 필요. v0.4.0+ 검토. spec § 4 "v0.3.0 단순 정책" 의도적 한계
- **TocBlock entries 빈 placeholder** — TOC field 검출만 수행, 항목 추출은 v0.4.0+. heading hierarchy walk + bookmark resolver 필요. spec § 6 결정 7
- **FieldBlock cached_value 항상 None** — HWP Field 가 cached_value 를 직접 노출 안 함. paragraph text 안 inline 위치를 `field_ranges` 매핑으로 추출해야 정확 — v0.4.0+ 검토. 현 시점은 None 출고
- **InlineRun.href 자동 채움 path 미구현** — Hyperlink/Bookmark Field 는 FieldBlock 으로만 노출, InlineRun.href 는 v0.2.0 시점부터 빈 채로. spec § 7 권장 정책 (side-effecting cross-ref 만 FieldBlock) 은 v0.4.0+
- **`HwpLoader(mode="ir-blocks")` `include_furniture` 옵션 부재** — spec 본문 § HwpLoader 변경 의 옵션은 v0.4.0+. 본 stage 는 신규 블록의 content/meta 매핑만 추가
- **CaptionBlock direction unknown 폴백 silent** — Rust 가 새 CaptionDirection variant 추가 시 mapper 가 silent 하게 `"bottom"` 으로 폴백. forensics 신호 없음 (FieldBlock 의 `field_type_code` 같은 raw 보존 필드 부재). spec § 5 의도적 단순화 — direction 은 부수적 metadata 라 fallback 비용 낮음
- **TocEntryBlock 모든 entries 가 동일 Provenance 공유** — `_build_toc_entry_block` 가 부모 TOC field 의 (section_idx, para_idx) 를 모든 entry 에 복사. v0.3.0 entries 는 빈 placeholder 라 영향 없지만, v0.4.0+ 에서 entries 가 채워질 때 entry 별 위치 추출이 필요. `RawTocEntry` 에 자체 위치 필드 (`section_idx`/`para_idx` 또는 `entry_idx`) 추가 시점에 격상

## S4 진입 조건 (인수인계)

S4 는 ir-expansion.md §S4 row — Schema v1.1 GA + CLI/LangChain 정식 매핑 + 문서. S3 에서 고정한 계약:

1. **`Block` 유니온 + `_KNOWN_KINDS` 10 known** — S4 는 이 set 변경 없이 schema/CLI/문서 마무리.
2. **schema_version `"1.1"` GA** — S1/S2/S3 모두 1.1 안에서 누적 진화. S4 는 in-package JSON in-place 갱신 + content-addressed alias `hwp_ir_v1-sha256-<new>.json` 발행 + `publish-schema.yml` 트리거.
3. **`HwpLoader` 신규 매핑 패턴** — S3 가 7 신규 블록 (S1 3 + S2 3 + S3 4) 의 `_block_to_content_and_meta` 분기 모두 추가했으므로 S4 는 `include_furniture: bool` 옵션 + CLI `rhwp-py blocks --kind` 만 추가.
4. **CaptionBlock 부착 패턴** — `PictureBlock.caption` / `TableBlock.caption_block` 의 forward ref + model_rebuild 패턴이 S3 에서 정착 — S4 에서 새 부모 블록 (예: ChartBlock) 에 caption 부착 시 동일 패턴 적용 가능.
5. **상류 visibility 의존성 추적** — `marker_prov.char_start/char_end` (S2 한계) 와 `cached_value` (S3 한계) 둘 다 상류 `find_control_text_positions` / `field_ranges` 매핑 필요. [docs/upstream/issue-find-control-text-positions.md](../../../upstream/issue-find-control-text-positions.md) 머지 시점에 v0.3.x patch 또는 v0.4.0 에서 격상 검토.

## 참조

- 상위 설계: [roadmap/v0.3.0/ir-expansion.md](../../../roadmap/v0.3.0/ir-expansion.md)
- 결정 사항 증거: [design/v0.3.0/ir-expansion-research.md](../../../design/v0.3.0/ir-expansion-research.md)
- 상류 타입 (S3 매핑): `external/rhwp/src/model/{control,style,shape}.rs` (FieldType / ParaShape.head_type / Caption / CaptionDirection)
- 선행 stage: [stage-1.md](stage-1.md), [stage-2.md](stage-2.md)
- 상류 제안 이슈 (S2 시점 정리): [docs/upstream/issue-find-control-text-positions.md](../../../upstream/issue-find-control-text-positions.md)
- v0.2.0 선례: [implementation/v0.2.0/stages/](../../v0.2.0/stages/) (S1~S5)
