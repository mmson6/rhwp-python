---
status: Frozen
description: "v0.5.1 — 'rhwp-mcp' 도구 출력 schema 강타입화. 'get_ir' / 'iter_blocks' / 'chunks' 의 'dict[str, Any]' 반환을 Pydantic 모델로 교체. 'UnknownBlock.kind' JSON Schema not.enum 추가로 fastmcp strict 'oneOf' 호환"
ga: v0.5.1
last_updated: 2026-05-07
---

# v0.5.1 — MCP 도구 출력 schema 강타입화

v0.5.0 GA 한 `rhwp-mcp` 의 7 도구 중 약타입 (`dict[str, Any]` / `list[dict[str, Any]]`) 으로 반환하는 3 도구 (`get_ir` / `iter_blocks` / `chunks`) 를 Pydantic V2 모델 반환으로 전환한다. fastmcp v3 의 자동 outputSchema 생성이 LLM 에 노출하는 schema 가 weak (`additionalProperties: true` 만) → strong (필드별 타입 / Discriminator + Tag 11 변형 / required 명시) 으로 강화되어 LLM 의 응답 해석 / 후속 도구 호출 정확도를 높인다. PATCH 라 사용자 코드 영향 0 — 호출 시그니처 / 반환 wire format (JSON) 모두 동일.

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [mcp-typed-output-research.md](../../design/v0.5.1/mcp-typed-output-research.md).

## 배경 — 왜 v0.5.1 PATCH 인가

v0.5.0 spec ([roadmap/v0.5.0/mcp.md](../README.md) 참조) 의 §노출 도구 표에서 7 도구 중 4 도구는 이미 강타입 (`ParseSummary` Pydantic, `str` × 3) 이지만 3 도구가 약타입으로 출고된다. v0.5.0 S3 의 `code-reviewer` fresh-context 검증이 LOW-2 로 권고: "iter_blocks / get_ir / chunks 가 모두 같은 패턴 (`list[dict[str, Any]]`) 이라 본 PR 범위 밖에서 일괄 처리". S3 / S5 implementation log 가 "후속 polish 로 보류" 명시.

v0.5.0 GA (2026-05-06) 직후 후속 polish 시점이 v0.5.1 PATCH. fastmcp v3 의 outputSchema 생성을 in-process 측정하면 약타입 vs 강타입 차이가 측정 가능한 fact 로 잡힌다 — 본 spec § 측정값 참조.

`v0.5.0/mcp.md` § 미확정 이슈 5 항 (`get_ir` 응답 크기 / 에러 응답 형식 통일 / Resource 추상 / Prompt 추상 / 클라이언트 호환성 손 검증) 중 본 spec 은 어디에도 직접 매핑되지 않는다 — `code-reviewer` 후속 polish 만 다룬다. 다른 4 항은 demand-driven 또는 v0.6.0+ 별도 spec 으로 보류 그대로.

## 목표와 비목표

### v0.5.1 목표

1. **`get_ir` 반환을 `HwpDocument` 로 교체** — `model_dump(mode="json")` 호출 제거, fastmcp 가 자동 직렬화
2. **`iter_blocks` 반환을 `list[Block]` 으로 교체** — `Block` 은 v0.3.0 의 Discriminator + Tag 유니온 11 변형 그대로 재사용
3. **`chunks` 반환을 `list[ChunkRecord]` 로 교체** — `ChunkRecord` 신규 Pydantic 모델 (`page_content: str` + `metadata: dict[str, Any]`)
4. **wire format 보존** — fastmcp Client 의 `result.structured_content` 가 v0.5.0 출력과 byte-equal (Pydantic `model_dump(mode="json")` 결과 == 기존 dict). Claude Desktop / Cline / 자체 에이전트의 기존 LLM 프롬프트 / 후처리 코드 영향 0
5. **outputSchema 강화 확인** — fastmcp 자동 생성 schema 의 `additionalProperties: true` (약) 를 필드별 type + required + (Block 의 경우) `oneOf` 변형 11 종 (강) 으로 교체. 측정값으로 회귀 가드 추가

### 비목표 (v0.5.1)

- **`get_ir` 응답 크기 제한** (`--max-bytes` / `Resource` 추상화) — `v0.5.0/mcp.md` §미확정 이슈, 별도 spec 검토 사항. 본 PATCH 는 출력 schema 만 다룸
- **에러 응답 형식 통일** — `v0.5.0/mcp.md` §미확정 이슈, demand-driven 보류
- **MCP `Resource` / `Prompt` 추상** — `v0.5.0/mcp.md` §미확정 이슈, 차기 minor 별도 spec
- **`HwpDocument` / `Block` / `ChunkRecord` 등 새 출력 모델의 `output_schema=` 수동 오버라이드** — fastmcp v3 의 자동 schema 생성이 충분 (1차 소스: fastmcp v3.2.4 docs § Use Typed Models for Structured Output). 수동 오버라이드는 추가 유지 비용
- **`chunks` 의 mode 별 ChunkRecord 분기** (`ChunkRecord_Single` / `_Paragraph` / `_IrBlocks`) — `metadata` 의 키 집합이 mode 별로 동적이지만 (kind / section_idx / para_idx / char_start / image_uri / rows / cols / scope 등) Pydantic 분기 모델은 LLM 이 mode 별로 다른 schema 를 추론해야 해 schema 가 3 배로 비대해지고 metadata 의 forward-compat (새 mode / 새 metadata 키 추가 시 모델 갱신 강제) 도 깨짐. 본 PATCH 는 `metadata: dict[str, Any]` 단일 필드 유지 (결정 5 참조)

### 영구 비범위

- 서버 → 클라이언트 wire format 의 *breaking* 변경 — JSON 키 / 값 형식 / 의미는 v0.5.0 과 byte-equal 유지 (PATCH 의 backwards-compat 의무, SemVer)
- Pydantic V1 호환 — 프로젝트 전반이 Pydantic V2 (글로벌 [CLAUDE.md](../../../CLAUDE.md))

## 변경 도구 매트릭스

| 도구 | v0.5.0 반환 시그니처 | v0.5.1 반환 시그니처 | wire format |
|---|---|---|---|
| `parse_hwp_summary` | `ParseSummary` (이미 강타입) | (변경 없음) | byte-equal |
| `extract_text` | `str` | (변경 없음) | byte-equal |
| `to_markdown` | `str` | (변경 없음) | byte-equal |
| `to_html` | `str` | (변경 없음) | byte-equal |
| **`get_ir`** | `dict[str, Any]` (= `HwpDocument.model_dump(mode="json")`) | `HwpDocument` | byte-equal |
| **`iter_blocks`** | `list[dict[str, Any]]` (= `[Block.model_dump(mode="json"), ...]`) | `list[Block]` | byte-equal |
| **`chunks`** | `list[dict[str, Any]]` (= `[{"page_content": str, "metadata": dict}, ...]`) | `list[ChunkRecord]` | byte-equal |

`Block` 은 v0.3.0 IR 의 Discriminator + Tag 유니온 (11 변형: paragraph / table / picture / formula / footnote / endnote / list_item / caption / toc / field / unknown) — `python/rhwp/ir/nodes.py` 가 SSOT, 본 spec 은 import 하여 재사용.

## 새 Pydantic 모델 — `ChunkRecord`

`get_ir` / `iter_blocks` 는 기존 IR 모델 (`HwpDocument` / `Block`) 을 그대로 노출하므로 새 모델 불필요. `chunks` 만 신규.

```python
# python/rhwp/mcp/tools.py
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ChunkRecord(BaseModel):
    """RAG 청크의 직렬화 표면 — LangChain Document 의 page_content / metadata 평탄화."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_content: str = Field(
        description="Chunk text (마크다운 / 평문 / HTML — chunks mode 에 따름).",
    )
    metadata: dict[str, Any] = Field(
        description=(
            "Mode-dependent metadata. 공통 키 source / paragraph_count + mode 별 키 — "
            "paragraph: paragraph_index, ir-blocks: kind / section_idx / para_idx / "
            "char_start / char_end / image_uri / rows / cols / caption / scope. "
            "키 집합은 'rhwp.integrations.langchain.HwpLoader' 가 SSOT."
        ),
    )
```

`metadata: dict[str, Any]` 로 두는 정당성 — `HwpLoader._block_to_content_and_meta()` 가 block kind 별로 키 집합을 동적 생성 (`paragraph` 는 char_start / char_end, `table` 은 rows / cols / caption / text, `picture` 는 image_uri / image_mime, `formula` 는 script_kind / inline 등). Pydantic 분기 모델로 강타입화하면 mode × kind 조합 (3 × 11) 에 대해 별도 모델 11 종이 필요해 schema 비대 + forward-compat (새 metadata 키 추가 시 모델 갱신 강제) 부담. 본 PATCH 는 page_content / metadata 의 *상위 schema* 만 강타입화하고 metadata 내부는 자유 dict 로 둔다.

## backwards-compat 보장 전략

PATCH 의 SemVer 의무 — 기존 사용자 코드 영향 0. 두 측면:

### 측면 1 — wire format byte-equal

fastmcp Client 의 `result.structured_content` (raw dict) 가 v0.5.0 과 동일해야 함. Pydantic `model_dump(mode="json")` 의 결정성:

- `HwpDocument` / `Block` / `ChunkRecord` 모두 `model_config = ConfigDict(extra="forbid", frozen=True)` — 동일 input 에 동일 dict 출력 보장
- v0.5.0 의 `get_ir` 가 `doc.to_ir().model_dump(mode="json")` 로 떨어뜨린 dict 와 v0.5.1 의 `get_ir` 가 반환한 `HwpDocument` 인스턴스를 fastmcp 가 직렬화한 dict 는 동일 함수 (Pydantic V2 의 `model_dump`) 를 거쳐 byte-equal — 직접 `assert get_ir_v050(path) == json.loads(json.dumps(get_ir_v051(path).model_dump(mode="json")))` 로 검증

#### `structured_content` wrap 분기 (fastmcp v3 의 결정성)

fastmcp v3 가 반환 타입에 따라 두 가지 wrap 패턴 적용 (1차 소스: fastmcp v3.2.4 docs § Structured Result Wrapping):

| 반환 시그니처 | wrap 패턴 | 회귀 가드 비교 |
|---|---|---|
| `HwpDocument` (단일 BaseModel) | wrap 없음 — `structured_content` 가 모델의 fields 를 직접 노출 | `assert result.structured_content == doc.model_dump(mode="json")` |
| `list[Block]` / `list[ChunkRecord]` (list of T) | `{"result": [...]}` wrap | `assert result.structured_content == {"result": [b.model_dump(mode="json") for b in ...]}` |

본 PATCH 의 byte-equal 회귀 가드 (AC-5) 가 두 패턴을 분리 검증.

### 측면 2 — fastmcp Client 의 두 접근 면

fastmcp Client 가 `result.data` 와 `result.structured_content` 를 둘 다 노출 (1차 소스: fastmcp v3.2.4 docs § Accessing Structured Results):

- `result.data` — typed 반환 (`HwpDocument` / `list[Block]` / `list[ChunkRecord]` 인스턴스). v0.5.1 신규 표면, 사용자가 강타입 활용 시 사용
- `result.structured_content` — raw dict (예: `{"result": [...]}`). v0.5.0 사용자가 dict-style 접근 (`result.structured_content["result"][0]["page_content"]`) 했다면 그대로 동작

따라서 fastmcp Client 사용자는 **dict-style 접근을 `result.data` 에 직접 시도하지 않는 한** 영향 없음. v0.5.0 사용자가 `for chunk in result.data: chunk["page_content"]` 패턴을 쓰고 있었다면 v0.5.1 부터 `chunk.page_content` (attr) 또는 `chunk.model_dump()["page_content"]` 로 마이그 필요 — README 의 v0.5.1 마이그 노트 한 단락으로 안내.

## 측정값 — outputSchema 강화 fact

본 spec 의 본 PATCH 구현 시점에 fastmcp v3 + 본 프로젝트 v0.5.0 → v0.5.1 코드로 in-process 측정한 outputSchema 본문 길이 (`json.dumps(t.output_schema)` byte 수):

| 도구 | v0.5.0 (`dict[str, Any]`) | v0.5.1 (typed) | 비고 |
|---|---|---|---|
| `get_ir` | 48 bytes (`{"additionalProperties": true, "type": "object"}`) | 약 32 KB (`HwpDocument` schema 전개 — `$defs` 약 20 종) | LLM 에 IR 구조 정확히 노출 |
| `iter_blocks` | 177 bytes (배열의 item 이 `additionalProperties: true` only) | 약 28 KB (`list[Block]` — `oneOf` 11 변형 + `$defs` 약 16 종) | 배열 item 의 `kind` discriminator 가 schema 에 노출 |
| `chunks` | 177 bytes | 약 1.4 KB (`ChunkRecord.page_content: str` + `metadata: dict[str, Any]` 만) | metadata 자유 dict 유지로 schema 비대 회피 |

`HwpDocument` 만 단독으로 `model_json_schema()` 호출 시 약 35 KB / `$defs` 약 20 종 / `Block` 유니온이 `oneOf` 11 변형으로 펼쳐진다. fastmcp 의 outputSchema wrap (BaseModel = inline / `list[T]` = `{"result": ...}` envelope) 에서 약간 작아짐. 정확한 byte 수는 IR 모델 갱신 / Pydantic / fastmcp 버전에 따라 변동 — 회귀 가드 (AC-4) 가 *schema 가 known field 를 노출* 한다는 정성적 invariant 만 검증.

> **schema 크기 vs LLM 친화성** — 21 KB schema 는 LLM 의 컨텍스트 / tools-list 에 들어가지만 한 번만 노출 (도구 목록 listing 시점). 이후 매 호출마다 schema 가 재전송되지 않으므로 호출 비용 (input token) 은 증가하지 않는다. 호출 결과 본문 (`structured_content`) 만 매 호출 비용에 잡힌다. ADR § 4 참조.

## 테스트 전략

### 단위 테스트 (`tests/test_mcp_server.py` 확장)

- `TestToolRegistry::test_get_ir_output_schema_includes_hwp_document_defs` — outputSchema 가 `$defs` 안에 `ParagraphBlock` / `TableBlock` 등 IR 모델을 포함하는지 (회귀 가드)
- `TestToolRegistry::test_iter_blocks_output_schema_is_list_of_block_oneof` — outputSchema 의 `properties.result.items.oneOf` 가 11 변형 포함
- `TestToolRegistry::test_chunks_output_schema_includes_chunk_record_fields` — outputSchema 의 `properties.result.items.properties` 가 `page_content` + `metadata` 포함
- `TestBackwardsCompat::test_get_ir_structured_content_matches_v050` — sample fixture 로 v0.5.0 의 `model_dump(mode="json")` 결과와 v0.5.1 fastmcp Client 의 `result.structured_content["result"]` 가 byte-equal
- `TestBackwardsCompat::test_iter_blocks_structured_content_matches_v050` — 동일 byte-equal 검증
- `TestBackwardsCompat::test_chunks_structured_content_matches_v050` — 동일

### 통합 테스트

- 실제 샘플 `aift.hwp` / `table-vpos-01.hwpx` 로 3 도구 호출 → `result.data` 가 typed Pydantic 인스턴스인지 / 필드 access 가 정상인지

### CI

- 추가 파일 / extras 변동 없음 — `test_mcp_server.py` 확장만. `test-without-extras` job 의 expected skip count 5 유지

## 결정 사항

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — `get_ir` 출력 모델 | `HwpDocument` 직접 노출 | IR 모델이 v0.3.0 부터 Pydantic V2 + `frozen=True` 라 그대로 fastmcp 자동 schema 가능. `model_dump(mode="json")` 호출 제거로 메모리 1 회 절감. ADR § 1 |
| 2 — `iter_blocks` 출력 모델 | `list[Block]` 직접 노출 | `Block` 의 callable Discriminator + Tag 유니온이 fastmcp v3 자동 schema 생성과 호환 — `oneOf` 11 변형이 LLM 에 노출. 별도 wrapper 모델 불필요. ADR § 2 |
| 3 — `chunks` 출력 모델 | 신규 `ChunkRecord(BaseModel)` — `page_content: str` + `metadata: dict[str, Any]` | LangChain Document 의 직렬화 표면이 정확히 두 필드. `metadata` 는 mode × kind 조합으로 동적이라 `dict[str, Any]` 유지 (mode 별 분기 모델 거부). ADR § 3 |
| 4 — wire format 보존 정책 | `result.structured_content` byte-equal 회귀 가드 | PATCH 의 SemVer 의무. fastmcp 가 Pydantic 인스턴스를 `model_dump(mode="json")` 로 직렬화하므로 v0.5.0 의 수동 dump 와 결정적으로 동일. 측정 가능한 회귀 가드 (`TestBackwardsCompat`) 로 발견 |
| 5 — `metadata` 분기 거부 | mode 별 `ChunkRecord_Single` / `_Paragraph` / `_IrBlocks` 분기 모델 거부 | mode × block kind 조합 (3 × 11) 으로 schema 가 3-11 배 비대 + 새 metadata 키 추가 (예: 미래 Provenance 확장) 시 모델 갱신 강제. 본 PATCH 는 `metadata` 자유 dict + 키 집합 SSOT 는 `HwpLoader` docstring. ADR § 3 |
| 6 — fastmcp `output_schema=` 수동 오버라이드 미사용 | 자동 schema 생성에 위임 | fastmcp v3.2.4 docs § Use Typed Models for Structured Output 가 자동 생성을 1st-tier 패턴으로 명시. 수동 오버라이드는 schema drift 위험 + 추가 유지. ADR § 4 |
| 7 — 호출 시그니처 보존 | `path: str` / `kind: BlockKind \| None` / `scope: BlockScope` / `limit: int \| None` / `mode: ChunksMode` / 기타 — 모두 v0.5.0 그대로 | PATCH 의 SemVer 의무. 출력 타입만 강화, 입력 schema 무변동 |
| 8 — `UnknownBlock.kind` JSON Schema constraint 강화 | `Field(json_schema_extra=...)` 로 `not.enum: sorted(_KNOWN_KINDS)` 노출. 런타임 동작 변경 0 (callable Discriminator 가 이미 분기) | fastmcp v3 + jsonschema 의 strict `oneOf` validation 이 ParagraphBlock 과 UnknownBlock schema 양쪽 valid 인 인스턴스 (예: 빈 ParagraphBlock) 에서 fail. callable Discriminator + Tag 유니온의 자동 schema 가 `oneOf` 11 변형으로 펼쳐지는데, UnknownBlock 의 `kind: str` 가 known kinds 도 매칭 → exactly-one 위반 → client side wire format 호환 깨짐. not.enum 추가로 schema export 만 strict 화. ADR § 5 |

## 인수조건

- **AC-1** — `get_ir(path)` 의 반환 타입 어노테이션이 `HwpDocument` (정적 타입) — `inspect.signature(rhwp.mcp.tools.get_ir).return_annotation is HwpDocument`
- **AC-2** — `iter_blocks(path, ...)` 의 반환 타입 어노테이션이 `list[Block]` (정적 타입) — `typing.get_type_hints(...)["return"]` 가 `list[Block]`
- **AC-3** — `chunks(path, ...)` 의 반환 타입 어노테이션이 `list[ChunkRecord]` (정적 타입) + `ChunkRecord` 가 `rhwp.mcp.tools` 에 노출 (test 가 import 가능)
- **AC-4** — fastmcp `Tool.output_schema["properties"]["result"]["items"]["$ref"]` 가 `get_ir` 는 `#/$defs/HwpDocument`, `iter_blocks` 는 `#/$defs/Block` (또는 `oneOf` 11 변형 inline), `chunks` 는 `ChunkRecord` 의 `properties` 인라인 — schema 가 v0.5.0 의 `additionalProperties: true` 약타입에서 강타입으로 전환됨을 in-process 검증 (회귀 가드)
- **AC-5** — `aift.hwp` 픽스처로 fastmcp Client in-process 호출 시 `result.structured_content` 가 v0.5.0 동등 함수의 `model_dump(mode="json")` 결과와 byte-equal — `get_ir` 는 wrap 없이 직접 비교, `iter_blocks` / `chunks` 는 `{"result": [...]}` wrap 안 비교 (§ wire format byte-equal 의 wrap 분기 참조)
- **AC-6** — fastmcp Client 의 `result.data` access 가 v0.5.1 부터 typed-or-dict (server side 출력에 따라):
    - `get_ir`: `result.data` 가 ``HwpDocument`` 의 fields 를 expose 하는 dynamic Pydantic 객체 — `data.schema_name == "HwpDocument"` 등 attribute access
    - `iter_blocks`: `result.data` 가 `list[dict]` (callable Discriminator + Tag 유니온의 `oneOf` schema 를 fastmcp v3 가 dynamic 모델로 reconstruct 하지 않는 한계 — 1차 소스: fastmcp v3.2.4 docs § Client Result Deserialization 의 supported types). 각 dict 의 `"kind"` key 노출 — v0.5.0 dict access 패턴 그대로 동작 (backwards-compat). 진짜 typed access 가 필요한 사용자는 server side 가 직접 반환하는 typed list (sync handler 호출 결과) 를 사용
    - `chunks`: `result.data` 가 `list[Pydantic-like]` — 각 element 가 `page_content` / `metadata` attribute access 가능 (단순 BaseModel 이라 fastmcp 가 dynamic 모델 reconstruct 가능)
- **AC-7** — `ChunkRecord` 의 `metadata` 필드 타입이 `dict[str, Any]` (mode 별 분기 모델 거부 결정 5 의 grep-friendly evidence) — `ChunkRecord.model_fields["metadata"].annotation == dict[str, Any]`
- **AC-8** — 도구 등록 변동 없음 — `len(server.list_tools()) == 7` (v0.5.0 AC-2 회귀 보존)
- **AC-9** — `tests/test_mcp_server.py` 의 extras-gated import (`pytest.importorskip("fastmcp")`) 위치 / `test-without-extras` skip count 5 / `pyproject.toml` extras 모두 v0.5.0 그대로 — PATCH 가 의존성 / extras 표면을 변경 안 함
- **AC-10** — README MCP 도구 표 (v0.5.0 S5 신설) 의 출력 컬럼이 v0.5.1 의 새 타입 (`HwpDocument` / `list[Block]` / `list[ChunkRecord]`) 으로 갱신, README 본문에 한 단락 마이그 노트 (`result.data` 가 dict 에서 typed instance 로 바뀌었다 — `result.structured_content` 는 동일) 추가

## 미확정 이슈

- **`HwpDocument.schema_version` 필드의 frontmatter-스러운 forward-compat 처리** — `field_validator` 가 major 상향 시 `UserWarning` 발생. fastmcp 호출 시 warning 이 어떻게 클라이언트에 전달되는가? Server stderr 에만 남는지, MCP 응답에 포함되는지 — 본 PATCH 범위는 출력 schema 만 다룸, warning 흐름은 fastmcp 의 책임. 손 검증 필요 시 별도 issue
- **`HwpDocument` 본문이 큰 경우 (수 MB IR JSON) MCP 응답 한도 초과** — v0.5.0 §미확정 이슈 그대로. 본 PATCH 는 출력 schema 만 — payload 자체는 v0.5.0 과 동일 byte 수
- **JSON Schema strict mode 호환성** — fastmcp 의 자동 schema 가 글로벌 [CLAUDE.md](../../../CLAUDE.md) § Pydantic V2 의 strict mode 룰 (`ge=` / `le=` 금지 등) 과 자동 정합. `IR` 모델은 `ge=` / `le=` 미사용 (검증 완료) — strict 호환은 보존된다고 가정. 미래 다른 사용처 (Anthropic Tool Use 의 strict tool calling) 에서 검증

## 다른 산출물의 파급 (코드 / 데이터)

- `python/rhwp/mcp/tools.py` — 3 함수 시그니처 변경 (`-> HwpDocument` / `-> list[Block]` / `-> list[ChunkRecord]`), `model_dump(mode="json")` / list comprehension 의 dict 펼침 제거. `ChunkRecord` BaseModel 신규 정의
- `python/rhwp/ir/nodes.py` — `UnknownBlock.kind` 의 `Field(json_schema_extra=callable)` 로 `not.enum: sorted(_KNOWN_KINDS)` JSON Schema export. 런타임 동작 변경 0. 결정 8 의 fastmcp strict `oneOf` 호환을 위한 최소 변경
- `python/rhwp/ir/schema/hwp_ir_v1.json` — UnknownBlock.kind 의 `not.enum` 반영하여 packaged JSON Schema 재생성 (`uv run python -m rhwp.ir.schema > python/rhwp/ir/schema/hwp_ir_v1.json`). 본 PATCH 의 자동 산출물
- `tests/test_mcp_server.py` — `TestTypedSignatures` (AC-1~AC-3, AC-7), `TestTypedOutputSchema` (AC-4), `TestBackwardsCompat` (AC-5), `TestTypedClientData` (AC-6), `TestTypedModelRoundTrip` (Pydantic 결정성). 기존 `TestGetIr` / `TestIterBlocks` / `TestChunks` 의 dict access 검증을 typed model 검증으로 전환
- `README.md` § MCP server (`rhwp-mcp`) — 도구 표의 출력 컬럼 갱신 + 한 단락 마이그 노트 (`result.data` 가 typed 로 바뀐 점)
- `CHANGELOG.md` — `[0.5.1]` 섹션 신설. *what* 측면에서 "MCP 도구 3 종 (`get_ir` / `iter_blocks` / `chunks`) 의 반환 타입을 Pydantic 모델로 강화. wire format 은 byte-equal 유지" 한 줄
- `pyproject.toml` — `Cargo.toml` version bump 0.5.0 → 0.5.1 만 동반 (extras / scripts 변동 없음)
- `external/rhwp/` 서브모듈 — 변경 없음. v0.5.0 동일 commit pin 유지

문서 cross-link (`docs/roadmap/README.md` 인덱스) 는 [CONVENTIONS.md](../../CONVENTIONS.md) § Cross-link 방향성 규칙 에 따라 본 spec 본문에서 다루지 않음 — 인덱스는 `roadmap/README.md` (Living) 가 SSOT.

## 참조

- 짝 페어 (ADR): [mcp-typed-output-research.md](../../design/v0.5.1/mcp-typed-output-research.md)
- v0.5.0 MCP server (선행 spec): 활성 spec 인덱스 [roadmap/README.md](../README.md)
- fastmcp v3 출력 schema 자동 생성 (1차 소스): <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- fastmcp Client `result.data` / `result.structured_content` (1차 소스): <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/clients/tools.mdx>
- IR `HwpDocument` / `Block` SSOT: `python/rhwp/ir/nodes.py`
- LangChain `HwpLoader` metadata 키 SSOT: `python/rhwp/integrations/langchain.py`
- Pydantic V2 strict mode 호환 룰 (글로벌): [CLAUDE.md](../../../CLAUDE.md) § Type Hints & Pydantic
