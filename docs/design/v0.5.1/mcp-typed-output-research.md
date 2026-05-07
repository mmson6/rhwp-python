---
status: Frozen
description: "v0.5.1 MCP 출력 강타입화 ADR — 'HwpDocument' / 'list[Block]' / 'ChunkRecord' 채택 / 'metadata' 자유 dict 유지 / fastmcp 자동 schema 위임 결정 근거"
ga: v0.5.1
last_updated: 2026-05-07
---

# v0.5.1 mcp-typed-output — 설계 의사결정 리서치 요약

[v0.5.1/mcp-typed-output.md](../../roadmap/v0.5.1/mcp-typed-output.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 4건 (`get_ir` 모델 채택 · `iter_blocks` 의 Block 유니온 노출 · `chunks` 의 ChunkRecord + metadata 정책 · fastmcp 자동 schema 위임) 의 업계 선례·대안·실패 시나리오를 기록한다. spec 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
|---|---|---|---|---|
| 1 | `get_ir` 출력 모델 | A: dict 유지 / B: `HwpDocument` 직접 노출 / C: 새 wrapper 모델 | **B** | IR 모델이 이미 Pydantic V2 + frozen — fastmcp 자동 schema 가 그대로 작동 |
| 2 | `iter_blocks` 출력 모델 | A: dict 유지 / B: `list[Block]` (Discriminator + Tag 11 변형) / C: 새 BlockRecord wrapper | **B** | callable Discriminator 가 fastmcp 자동 `oneOf` schema 와 호환 — wrapper 가 정보 추가 없음 |
| 3 | `chunks` 출력 모델 | A: dict 유지 / B: `ChunkRecord(page_content, metadata: dict)` / C: mode×kind 분기 모델 | **B** | metadata 가 mode × block kind 동적 — 분기 모델은 schema 3-11 배 비대 + forward-compat 깨짐 |
| 4 | fastmcp `output_schema=` 수동 오버라이드 | A: 자동 위임 / B: 수동 명시 | **A** | fastmcp v3 docs 가 자동 생성을 1st-tier 패턴 — 수동은 schema drift / 추가 유지 비용 |
| 5 | `UnknownBlock.kind` JSON Schema constraint | A: `kind: str` 유지 / B: `not.enum: sorted(_KNOWN_KINDS)` 추가 | **B** | strict `oneOf` validation 에서 ParagraphBlock 과 UnknownBlock 양쪽 valid 인스턴스 충돌 → client side wire format 호환 깨짐. 런타임 동작 0 변경, schema export 만 strict 화 |

---

## 1. `get_ir` 출력 모델

### 팩트

- v0.5.0 의 `get_ir(path)` 는 `rhwp.parse(path).to_ir().model_dump(mode="json")` 을 호출하여 `dict[str, Any]` 반환 (`python/rhwp/mcp/tools.py:76-82`)
- `HwpDocument` 는 v0.2.0 (Frozen) 부터 Pydantic V2 + `model_config = ConfigDict(extra="forbid", frozen=True)` (`python/rhwp/ir/nodes.py:652-667`)
- fastmcp v3 in-process 측정 결과:
  - `dict[str, Any]` 반환 시 outputSchema = 48 bytes (`{"additionalProperties": true, "type": "object"}`)
  - `HwpDocument` 반환 시 outputSchema = 약 32 KB (`$defs` 약 20 종 — Provenance / InlineRun / DocumentSource / DocumentMetadata / Section / ParagraphBlock / TableCell / TableBlock / ImageRef / PictureBlock / FormulaBlock / FootnoteBlock / EndnoteBlock / TocEntryBlock / TocBlock / FieldBlock / UnknownBlock / ListItemBlock / CaptionBlock / Furniture)
- `HwpDocument.model_json_schema()` 단독 호출 시 약 35 KB — fastmcp wrap 에서 약간 작아짐. 정확한 byte 수는 IR 모델 갱신 / 라이브러리 버전 변경에 따라 변동
- fastmcp 가 Pydantic 인스턴스를 자동 직렬화 (1차 소스: fastmcp v3.2.4 docs § Use Typed Models for Structured Output) — `model_dump(mode="json")` 의 *수동 호출* 은 더 이상 필요하지 않음

### 검증자 반박

- "21 KB schema 가 LLM 의 컨텍스트를 잡아먹지 않나?" → schema 는 도구 목록 listing 시점에만 한 번 노출. 매 호출마다 재전송되지 않음. 호출 본문 (`structured_content`) 만 매 호출 비용에 잡히는데 본문은 v0.5.0 과 byte-equal — 비용 변동 0
- "이미 dict 로 충분한데 왜 강화하나?" → LLM 이 `result.body[0].kind == "paragraph"` 같은 참조를 정확히 추론하려면 outputSchema 의 `kind` 필드가 enum (`["paragraph", "table", ...]`) 으로 노출되어야 한다. dict 출력은 `additionalProperties: true` 만이라 LLM 이 키 이름조차 모름
- "wire format 깨지지 않나?" → fastmcp 가 Pydantic 인스턴스 → `structured_content` 직렬화 시 `model_dump(mode="json")` 사용 (1차 소스: fastmcp v3.2.4 docs § Use Typed Models 의 응답 예시). v0.5.0 의 수동 dump 와 같은 함수 — byte-equal 보장
- "frozen=True 모델을 fastmcp 가 정상 직렬화하나?" → frozen 은 입력 시점 (인스턴스 생성 후 mutation 차단) 에만 영향. `model_dump()` 는 read-only 라 frozen 무관

### 최종 결정

**B 채택** — `get_ir(path) -> HwpDocument`. `model_dump(mode="json")` 호출 제거 (메모리 1 회 절감) + outputSchema 강화 + wire format byte-equal. spec § 인수조건 AC-1 / AC-4 / AC-5 가 회귀 가드.

### 1차 소스

- fastmcp v3.2.4 docs § Use Typed Models for Structured Output: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- fastmcp v3.2.4 docs § Defining Structured Tool Return Values: <https://context7.com/prefecthq/fastmcp/llms.txt>
- 본 프로젝트 `python/rhwp/mcp/tools.py:76-82` (현재 dict dump 코드)
- 본 프로젝트 `python/rhwp/ir/nodes.py:652-667` (HwpDocument 정의)
- in-process schema 측정 (2026-05-06): `uv run python -c "from rhwp.ir.nodes import HwpDocument; ..."`

---

## 2. `iter_blocks` 의 Block 유니온 노출

### 팩트

- v0.5.0 의 `iter_blocks(path, ...)` 는 `[block.model_dump(mode="json") for block in ir_doc.iter_blocks(...)]` 패턴으로 `list[dict[str, Any]]` 반환 (`python/rhwp/mcp/tools.py:115-145`)
- `Block` 은 v0.3.0 부터 callable Discriminator + Tag 유니온 (11 변형: paragraph / table / picture / formula / footnote / endnote / list_item / caption / toc / field / unknown — `python/rhwp/ir/nodes.py:617-630`)
- callable Discriminator 의 동기: 미지의 `kind` 가 등장해도 `UnknownBlock` 으로 라우팅하는 forward-compat (`python/rhwp/ir/nodes.py:607-614` `_block_discriminator`). 구 버전 소비자가 새 spec 의 IR 을 읽을 때 read-only fail 회피
- in-process 측정 (Block 유니온의 JSON Schema):
  - `TypeAdapter(Block).json_schema()` = 약 30 KB / `$defs` 약 16 종 / `oneOf` 11 변형
  - fastmcp v3 가 `list[Block]` 반환을 wrap → outputSchema = 약 28 KB (배열 item 의 `$ref` 또는 inline `oneOf`)
- v0.5.0 dict 출력 schema 와 비교 시 schema 는 약 150 배 (177 bytes → 28 KB) 강화

### 검증자 반박

- "callable Discriminator 가 fastmcp 의 자동 schema 와 호환되나?" → Pydantic V2 의 callable Discriminator 는 `model_json_schema()` 호출 시 `oneOf` 11 변형으로 펼쳐진다 (in-process 검증 완료). fastmcp v3 가 Pydantic 의 `model_json_schema()` 에 위임하므로 호환 (1차 소스: fastmcp v3.2.4 docs § Use Typed Models 의 dataclass / Pydantic 동등 처리)
- "Block 의 재귀 구조 (`TableCell.blocks: list[Block]`, `FootnoteBlock.blocks: list[Block]` 등) 가 schema 안에서 무한 루프 안 도나?" → Pydantic 이 자동으로 `$ref` 순환 참조 사용 — JSON Schema spec 에 따라 정상 처리
- "wrapper BlockRecord 모델로 한 단계 추상화 안 하나?" → wrapper 가 추가하는 정보 0 (`Block` 자체가 이미 모든 필드 포함). 추상화 부담만 추가 — 거부
- "LLM 이 11 oneOf 변형 schema 를 정확히 해석하나?" → Anthropic / OpenAI tool calling 가이드가 discriminated union 을 1st-tier 패턴으로 권장. JSON Schema `oneOf` + discriminator 는 OpenAPI / Pydantic / TypeScript 의 표준 표현이라 LLM 학습 데이터에 흔함
- "fastmcp Client 의 `result.data` 도 typed Block 인스턴스로 deserialize 되나?" → **아니다 — fastmcp v3.2.4 의 한계**. Client 의 자동 deserialization 이 단순 BaseModel 은 dynamic Pydantic 모델로 reconstruct (예: `HwpDocument`, `ChunkRecord`) 하지만, callable Discriminator + Tag 유니온의 `oneOf` schema 는 dynamic 모델로 변환 못 해 list element 가 dict 폴백. server side 출력 자체는 typed (sync handler 가 `list[Block]` 반환), client side 만 dict — `"kind"` key 노출되어 v0.5.0 dict access 패턴 그대로 동작 (backwards-compat). 진짜 typed access 가 필요하면 server side 직접 호출 (sync handler 결과) 또는 사용자 측 `Block.model_validate(d) for d in result.data` 명시적 reconstruct
- "fastmcp + jsonschema 의 strict `oneOf` validation 이 ParagraphBlock 과 UnknownBlock schema 양쪽 valid 인스턴스에서 fail 하지 않나?" → **충돌 발생** — 빈 ParagraphBlock (`{kind: "paragraph", text: "", inlines: [], prov: {...}}`) 가 ParagraphBlock 의 `kind: const "paragraph"` 와 UnknownBlock 의 `kind: str` + `extra: allow` 양쪽 valid → exactly-one 위반 → `RuntimeError: Invalid structured content`. 결정 5 (`UnknownBlock.kind` 의 `not.enum` 추가) 로 회복

### 최종 결정

**B 채택** — `iter_blocks(...) -> list[Block]`. Block 유니온이 callable Discriminator + Tag 로 fastmcp 자동 schema 의 `oneOf` 11 변형으로 호환. wrapper 모델 거부. 결정 5 (`UnknownBlock.kind not.enum`) 로 strict `oneOf` 충돌 해결. spec § 인수조건 AC-2 / AC-4 / AC-5 가 회귀 가드.

### 1차 소스

- 본 프로젝트 `python/rhwp/ir/nodes.py:617-630` (Block 유니온 정의)
- 본 프로젝트 `python/rhwp/ir/nodes.py:607-614` (`_block_discriminator` callable)
- Pydantic V2 Discriminator + Tag 문서: <https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions-with-callable-discriminator>
- fastmcp v3.2.4 docs § Use Typed Models for Structured Output: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- in-process schema 측정 (2026-05-06): `pydantic.TypeAdapter(Block).json_schema()`

---

## 3. `chunks` 의 ChunkRecord + metadata 정책

### 팩트

- v0.5.0 의 `chunks(path, ...)` 가 LangChain Document 의 `page_content` / `metadata` 를 `[{"page_content": d.page_content, "metadata": d.metadata} for d in split_docs]` 로 평탄화 (`python/rhwp/mcp/tools.py:198-199`)
- `metadata` 의 키 집합이 mode × block kind 로 동적 (`python/rhwp/integrations/langchain.py:174-289` `_block_to_content_and_meta`):
  - mode `single`: `source` / `paragraph_count` / `pages` / `sections` (4 키)
  - mode `paragraph`: 위 + `paragraph_index` (5 키)
  - mode `ir-blocks` × block kind 11 종:
    - `paragraph`: + `kind` / `section_idx` / `para_idx` / `char_start` / `char_end`
    - `table`: + `kind` / `section_idx` / `para_idx` / `rows` / `cols` / `text` / `caption`
    - `picture`: + `kind` / `section_idx` / `para_idx` / `image_uri` / `image_mime`
    - `formula`: + `kind` / `section_idx` / `para_idx` / `script_kind` / `inline`
    - `footnote` / `endnote`: + `kind` / `section_idx` / `para_idx` / `number` / `marker_section_idx` / `marker_para_idx`
    - `list_item`: + `kind` / `section_idx` / `para_idx` / `level` / `enumerated`
    - 등 11 가지 분기
  - `include_furniture=True` 분기: 위 + `scope: "furniture"`
- 분기 모델 (`ChunkRecord_Single` / `_Paragraph` / `_IrBlocksParagraph` / `_IrBlocksTable` / ... 11 종) 로 표현 시 outputSchema 가 mode × kind = 약 13 모델 schema 의 `oneOf` — 약 50 KB+ 추정 (Block 유니온 schema 의 약 3 배)
- fastmcp v3.2.4 in-process 측정 결과: `ChunkRecord(page_content: str, metadata: dict[str, Any])` 단순 모델 = outputSchema 약 600 bytes

### 검증자 반박

- "`metadata: dict[str, Any]` 는 LLM 에 정보를 안 주는데 강화 효과 없는 것 아닌가?" → `page_content` (str) + `metadata` (object) 의 *상위 schema* 는 강타입화됨. LLM 이 "각 청크는 page_content 와 metadata 두 필드를 가진다" 는 사실을 정확히 알게 됨. metadata 내부의 동적 키는 description 에 SSOT 위치 (`HwpLoader` docstring) 로 안내
- "분기 모델 11 종은 forward-compat 가 깨지지 않나?" → 정확. 새 metadata 키 추가 시 모델 갱신 강제 + breaking change 위험. `metadata: dict[str, Any]` 는 새 키를 자유 추가 가능 — 본 프로젝트의 v0.3.0 스타일 (Provenance / TocEntry 의 forward-compat 필드 추가) 정합
- "`metadata` 키 집합 SSOT 가 `HwpLoader` docstring 에 있는데 spec 에서 어떻게 검증?" → `tests/test_langchain_loader.py` / `tests/test_langchain_loader_ir.py` (v0.3.0 GA, langchain extras-gated) 가 mode × kind 별 metadata 키 집합을 behavior-driven 검증. 본 PATCH 는 그 위에 출력 schema 만 강화 — 검증 책임 분리
- "왜 `Field(description="Mode-dependent metadata. ...")` 만으로 충분한가?" → MCP Tool 의 description 은 LLM 의 1st-class context. fastmcp 가 Pydantic Field description 을 그대로 outputSchema 에 노출 — LLM 이 mode 별 키 집합을 추론할 수 있는 텍스트가 schema 에 직접 포함

### 최종 결정

**B 채택** — `chunks(...) -> list[ChunkRecord]`, `ChunkRecord(page_content: str, metadata: dict[str, Any])`. mode × kind 분기 모델 거부 — schema 비대 + forward-compat 깨짐. spec § 인수조건 AC-3 / AC-4 / AC-7 이 회귀 가드.

### 1차 소스

- 본 프로젝트 `python/rhwp/integrations/langchain.py:174-289` (mode × kind 별 metadata 키 SSOT)
- 본 프로젝트 `python/rhwp/mcp/tools.py:198-199` (현재 dict 평탄화 패턴)
- LangChain Core `Document` 모델: <https://python.langchain.com/api_reference/core/documents/langchain_core.documents.base.Document.html> (`page_content: str` + `metadata: dict`)
- fastmcp v3.2.4 docs § Use Typed Models for Structured Output (description 노출 패턴): <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>

---

## 4. fastmcp `output_schema=` 수동 오버라이드 미사용

### 팩트

- fastmcp v3 의 `@mcp.tool` 데코레이터가 함수 반환 타입 어노테이션 (`-> HwpDocument`) 으로부터 outputSchema 자동 생성 (1차 소스: fastmcp v3.2.4 docs § Use Typed Models for Structured Output, § Defining Structured Tool Return Values)
- 자동 생성 path 는 Pydantic 의 `model_json_schema()` 호출 — Pydantic V2 의 schema 표준 (`oneOf` / `$defs` / `Discriminator` / `Field(description=...)` / `Literal` enum) 모두 지원
- fastmcp v3 가 자동 schema 와 함께 wrapping (`{"properties": {"result": ...}, "x-fastmcp-wrap-result": true}`) 도 자동 처리 — primitive / list 반환을 MCP `structured_content` 의 single-key dict 형식에 맞춤
- 수동 오버라이드 (`@mcp.tool(output_schema={...})`) 는 fastmcp 도 지원하나 (1차 소스 docs 의 `custom_schema_tool` 예시) drift 위험 (코드 변경 ↔ schema 갱신 불일치) + 추가 유지 비용

### 검증자 반박

- "Pydantic V2 의 자동 schema 가 strict mode (Anthropic Tool Use / OpenAI Structured Outputs) 와 호환되나?" → 본 프로젝트의 IR 모델이 strict mode 호환 룰 (글로벌 [CLAUDE.md](../../../CLAUDE.md) § Type Hints & Pydantic — `ge=` / `le=` 미사용, `Literal` 사용) 을 이미 따른다. 자동 schema 그대로 strict 통과 가능. 본 PATCH 의 별도 호환 작업 불필요
- "자동 schema 가 향후 Pydantic 또는 fastmcp 업데이트로 깨질 가능성?" → `pyproject.toml` 의 `fastmcp>=3,<4` ceiling 이 v3 major 안에서 schema breaking 차단. spec § 인수조건 AC-4 (outputSchema 의 fact 검증) 가 회귀 가드 — 깨지면 CI 가 발견
- "수동 오버라이드가 LLM 친화성 향상에 더 효과 있지 않나?" → fastmcp 자동 생성이 이미 `Field(description=...)` 를 schema 에 노출 + `Literal` enum + `Discriminator` `oneOf` 모두 지원. 수동 오버라이드의 추가 가치는 strict mode 의 부가 제약 (`additionalProperties: false` 명시 등) 정도인데 본 PATCH 는 strict mode 가 비목표

### 최종 결정

**A 채택** — fastmcp v3 의 자동 outputSchema 생성에 위임. 수동 오버라이드는 spec 의 비목표 (§ 비목표 4 항). spec § 인수조건 AC-4 의 회귀 가드가 자동 schema 의 정확성을 보장.

### 1차 소스

- fastmcp v3.2.4 docs § Use Typed Models for Structured Output: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- fastmcp v3.2.4 docs § Defining Structured Tool Return Values: <https://context7.com/prefecthq/fastmcp/llms.txt>
- Pydantic V2 `model_json_schema()`: <https://docs.pydantic.dev/latest/concepts/json_schema/>
- 글로벌 [CLAUDE.md](../../../CLAUDE.md) § Type Hints & Pydantic (strict mode 호환 룰)

---

## 5. `UnknownBlock.kind` JSON Schema not.enum constraint

### 팩트

- v0.3.0 부터 `UnknownBlock` 은 `kind: str` + `model_config = ConfigDict(extra="allow")` (`python/rhwp/ir/nodes.py:501-517`) — forward-compat 의 catch-all
- callable Discriminator (`_block_discriminator` — `python/rhwp/ir/nodes.py:607-614`) 가 `_KNOWN_KINDS` 에 매칭 안 되는 kind 만 UnknownBlock 으로 라우팅 — Pydantic 런타임 검증은 정확
- Pydantic V2 의 `model_json_schema()` 가 callable Discriminator + Tag 유니온을 `oneOf` 11 변형으로 펼치되, UnknownBlock 의 `kind` 는 별도 constraint 없이 그대로 `{type: "string"}` 노출
- 결과: `oneOf` 의 두 변형이 같은 인스턴스에 valid — ParagraphBlock 의 `{kind: "paragraph", text: "", inlines: [], prov: {...}}` 가 UnknownBlock schema 의 `extra: allow` + `kind: str` 에도 valid
- jsonschema lib 의 strict `oneOf` 의미는 *exactly one* — fastmcp v3.2.4 Client 의 `_validate_tool_result` (mcp.client.session 의 strict 검증) 가 `RuntimeError: Invalid structured content returned by tool iter_blocks` 로 fail
- 본 spec 의 PATCH backwards-compat 의무 (측면 1 의 wire format byte-equal) 가 client side 에서 깨짐 — v0.5.0 사용자가 v0.5.1 으로 upgrade 시 도구 호출 자체가 실패

### 검증자 반박

- "옵션 A — fastmcp Client 의 strict validation 우회?" → Client 의 `_validate_tool_result` 는 `list_tools()` 후 자동 호출. 우회는 hacky + 실제 production client (Claude Desktop / Cline 등) 에서도 같은 jsonschema lib 사용 가능성 — 근본 해결 아님
- "옵션 C — fastmcp `output_schema=` 수동 오버라이드?" → 결정 4 (자동 위임) 와 충돌. 수동 schema 가 `oneOf` 와 다르게 작성되더라도 Pydantic V2 의 자동 schema 가 SSOT 인 상태가 깨짐
- "옵션 Y — Block 유니온을 string Discriminator (`Discriminator("kind")`) 로 변경?" → forward-compat 깨짐 — string discriminator 는 정확 매칭만, 미지 kind 가 등장하면 `union_tag_invalid` 로 문서 전체 파싱 거부 (UnknownBlock 라우팅 불가). v0.3.0 의 callable Discriminator 결정과 충돌
- "런타임 동작에 영향 없나?" → Pydantic V2 의 `Field(json_schema_extra=callable)` 은 **schema export 시점에만 호출** — `model_json_schema()` 결과에 추가될 뿐, `model_validate` (런타임 검증) 에는 무관. UnknownBlock 인스턴스 생성 / 직렬화 / round-trip 모두 동일
- "기존 IR 테스트 (test_ir_schema_export / test_ir_schema) 회귀?" → 기존 테스트는 *Pydantic 라우팅* 검증 (callable Discriminator) 또는 `additionalProperties: false` 검증 만 — 본 변경은 `not.enum` 추가만이고 두 검증 모두 그대로 통과 (in-process 확인 — 제로 회귀)

### 최종 결정

**B 채택** — `UnknownBlock.kind` 에 `Field(json_schema_extra=_unknown_kind_schema_extra)` 패턴으로 `not.enum: sorted(_KNOWN_KINDS)` 노출. callable 함수로 분리한 이유는 `_KNOWN_KINDS` 가 모듈 정의 순서상 `UnknownBlock` 뒤에 위치 — class definition 시점이 아닌 schema generation 시점에 평가해야 NameError 회피 (Pydantic V2 의 `json_schema_extra=callable` 표준 패턴).

본 결정의 영향:
- 런타임: 변경 0 (callable Discriminator 가 SSOT 그대로)
- JSON Schema export: `UnknownBlock.kind` 가 `{type: "string", not: {enum: [...]}, ...}` — `_KNOWN_KINDS` 의 10 known kinds 모두 노출
- packaged schema 파일 (`python/rhwp/ir/schema/hwp_ir_v1.json`) 갱신 필요 — `uv run python -m rhwp.ir.schema > python/rhwp/ir/schema/hwp_ir_v1.json` 으로 자동 재생성
- spec § 인수조건 AC-5 의 회귀 가드 (fastmcp Client in-process round-trip 의 byte-equal) 가 본 결정의 효과를 검증 — not.enum 미적용 시 client validation 실패로 fail

### 1차 소스

- 본 프로젝트 `python/rhwp/ir/nodes.py:501-517` (UnknownBlock 정의 — 변경 전)
- 본 프로젝트 `python/rhwp/ir/nodes.py:607-614` (`_block_discriminator` — 런타임 분기 SSOT)
- jsonschema spec `oneOf` semantics: <https://json-schema.org/understanding-json-schema/reference/combining#oneOf>
- Pydantic V2 `Field(json_schema_extra=callable)`: <https://docs.pydantic.dev/latest/concepts/json_schema/#schema-customization>
- fastmcp v3.2.4 client validation (`mcp.client.session._validate_tool_result`): <https://github.com/modelcontextprotocol/python-sdk> (mcp 1.x SDK 의 jsonschema 강제 검증)

---

## 참조

- 짝 페어: [mcp-typed-output.md](../../roadmap/v0.5.1/mcp-typed-output.md)
- fastmcp v3.2.4 (jlowin / PrefectHQ): <https://github.com/jlowin/fastmcp>
- MCP Specification (`tools/list` / `outputSchema`): <https://modelcontextprotocol.io/specification/2025-03-26/server/tools>
- Anthropic Tool Use (Claude tool calling) docs: <https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview>
- 본 프로젝트 `python/rhwp/ir/nodes.py` (IR Pydantic 모델 SSOT)
- 본 프로젝트 `python/rhwp/integrations/langchain.py` (LangChain HwpLoader metadata 키 SSOT)
