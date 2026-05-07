---
status: Frozen
description: "v0.5.1 구현 로그 — MCP tool 출력 schema 강타입화 (`get_ir` / `iter_blocks` / `chunks`). wire format byte-equal. `UnknownBlock.kind` JSON Schema not.enum 추가로 fastmcp strict oneOf 호환"
target: v0.5.1
last_updated: 2026-05-07
---

# v0.5.1 — MCP tool 출력 schema 강타입화 (구현 로그)

[v0.5.1/mcp-typed-output](../../roadmap/v0.5.1/mcp-typed-output.md) (spec) +
[design/v0.5.1/mcp-typed-output-research](../../design/v0.5.1/mcp-typed-output-research.md)
(ADR) 의 구현 결과 로그. 결정의 근거·옵션 비교는 ADR 가 보유 — 본 문서는
*산출물 / 검증 결과 / 호환성 / 이월 사항* 만 기록한다 (CONVENTIONS § CHANGELOG
↔ implementation log 역할 분리).

PATCH release. 단일 세션 규모 (3 함수 시그니처 강화 + 신규 모델 1 + IR
JSON Schema constraint 1 + 테스트 5 클래스) 로 단일 `migration.md` 채택. v0.5.0
의 stages 분할이 후속 polish PR 의 cross-cutting 변경 (Rust 4 + Python 6 +
docs 4) 을 5 stage 로 흩었던 이유와 대조 — 본 PATCH 는 단일 PR 안에 끝.

## 1. 산출물

### Python 신규 모델

| 파일 | 신규 | 책임 |
|---|---|---|
| [python/rhwp/mcp/tools.py](../../../python/rhwp/mcp/tools.py) | `ChunkRecord(BaseModel)` | RAG 청크의 직렬화 표면 — `page_content: str` + `metadata: dict[str, Any]`. `model_config = ConfigDict(extra="forbid", frozen=True)`. mode × block kind 분기 거부 결정 (spec § 결정 5) 의 grep-friendly evidence 는 AC-7 회귀 가드 |

### Python 시그니처 강화

| 파일 / 함수 | v0.5.0 | v0.5.1 |
|---|---|---|
| `python/rhwp/mcp/tools.py::get_ir` | `(path) -> dict[str, Any]` | `(path) -> HwpDocument` |
| `python/rhwp/mcp/tools.py::iter_blocks` | `(path, kind?, scope, limit?) -> list[dict[str, Any]]` | `(path, kind?, scope, limit?) -> list[Block]` |
| `python/rhwp/mcp/tools.py::chunks` | `(path, mode, size, overlap, include_furniture) -> list[dict[str, Any]]` | `(path, mode, size, overlap, include_furniture) -> list[ChunkRecord]` |

3 함수 모두 `model_dump(mode="json")` 호출 / 수동 dict 평탄화 제거 — `fastmcp` 가
자동 직렬화에 위임 (spec § 결정 6). 호출 시그니처 / 입력 schema / 외부 wire
format 은 v0.5.0 그대로 (PATCH SemVer 의무 — § 호환성 절).

### IR JSON Schema constraint (spec § 결정 8)

| 파일 / 위치 | 변경 |
|---|---|
| [python/rhwp/ir/nodes.py](../../../python/rhwp/ir/nodes.py) | `UnknownBlock.kind` 의 `Field(json_schema_extra=_unknown_kind_schema_extra)` callable 추가. callable 이 `not.enum: sorted(_KNOWN_KINDS)` 를 schema dict 에 in-place 삽입. `_KNOWN_KINDS` 가 모듈 정의 순서상 `UnknownBlock` 뒤에 위치하므로 lambda/함수의 lazy 평가로 NameError 회피 |
| [python/rhwp/ir/schema/hwp_ir_v1.json](../../../python/rhwp/ir/schema/hwp_ir_v1.json) | packaged JSON Schema 자동 재생성 (`uv run python -m rhwp.ir.schema > python/rhwp/ir/schema/hwp_ir_v1.json`). 본 PATCH 의 자동 산출물 — `UnknownBlock.kind` 의 `not.enum` 반영. 기존 `additionalProperties: false` invariant 그대로 |

런타임 동작 0 변경 — Pydantic V2 의 `json_schema_extra=callable` 은 schema
export 시점에만 호출, `model_validate` (런타임 검증) 무관. callable Discriminator
(`_block_discriminator`) 가 SSOT 으로 known/unknown 분기 — UnknownBlock 인스턴스가
known kind 를 가질 수 없는 invariant 보존.

### 테스트

| 파일 | 변동 | 책임 |
|---|---|---|
| [tests/test_mcp_server.py](../../../tests/test_mcp_server.py) | +320 / -8 | v0.5.1 신규 5 테스트 클래스 (`TestTypedSignatures` AC-1~AC-3, AC-7 / `TestTypedOutputSchema` AC-4 / `TestBackwardsCompat` AC-5 / `TestTypedClientData` AC-6 / `TestTypedModelRoundTrip` Pydantic 결정성). 기존 `TestGetIr` / `TestIterBlocks` / `TestChunks` 의 dict access 검증을 typed model 검증으로 전환 |

기존 IR 테스트 (`tests/test_ir_schema_export.py`, `tests/test_ir_schema.py`,
`tests/test_ir_iter_blocks.py`, `tests/test_ir_roundtrip.py`, `tests/test_ir_toc.py`,
`tests/test_ir_plain_text.py`) — 변경 없음. 모두 회귀 0 (in-process 확인).

### 문서

| 파일 | 변경 |
|---|---|
| [README.md](../../../README.md) | § "MCP server (`rhwp-mcp`)" 의 도구 표 출력 컬럼을 강타입 (`HwpDocument` / `list[Block]` / `list[ChunkRecord]`) 으로 갱신. v0.5.1 마이그 노트 한 단락 추가 — `result.structured_content` byte-equal + `result.data` access 패턴 변경 (dict→typed) + `iter_blocks` list element 의 dict 폴백 안내 |
| [docs/roadmap/v0.5.1/mcp-typed-output.md](../../roadmap/v0.5.1/mcp-typed-output.md) (spec) | Draft body 보강 — § wire format byte-equal 의 wrap 분기 표 (BaseModel = inline / `list[T]` = `{"result": ...}`), § 결정 8 (`UnknownBlock.kind` not.enum), AC-5 wrap 분기 명시, AC-6 fastmcp 한계 명시, § 다른 산출물 파급에 nodes.py / hwp_ir_v1.json 추가 |
| [docs/design/v0.5.1/mcp-typed-output-research.md](../../design/v0.5.1/mcp-typed-output-research.md) (ADR) | Draft body 보강 — 결정 매트릭스 row 5 (UnknownBlock not.enum) 추가, § 5 신규 (옵션 비교 + 검증자 반박 + 1차 소스), § 2 검증자 반박에 fastmcp client deserialization 한계 추가 |
| [docs/traces/coverage.md](../../traces/coverage.md) | spec_trace 자동 갱신 — 16 새 v0.5.1/mcp-typed-output#AC-N row 추가 (총 48 spec / 622 test mappings) |
| [docs/roadmap/README.md](../../roadmap/README.md) | 활성 spec 인덱스에 v0.5.1 (Draft) row 추가 — spec 시작 시 작성됨 |

### CI / 메타 (의도된 보류)

다음 항목은 spec § 다른 산출물의 파급에 명시되어 있으나 **본 step 의 범위 밖**
— 사용자 GA 절차 (별도 commit) 에서 진행:

- `Cargo.toml` 0.5.0 → 0.5.1 bump
- `CHANGELOG.md` `[0.5.1]` 섹션 추가
- spec / ADR `Draft → Frozen` flip
- git tag `v0.5.1` + GitHub Release

## 2. 결정 사항 (spec 결정 8 항목 ↔ 구현 매핑)

| spec 결정 | 구현 위치 |
|---|---|
| 1 — `get_ir` 출력 모델 = `HwpDocument` | `python/rhwp/mcp/tools.py:get_ir` |
| 2 — `iter_blocks` 출력 모델 = `list[Block]` | `python/rhwp/mcp/tools.py:iter_blocks` |
| 3 — `chunks` 출력 모델 = `list[ChunkRecord]` | `python/rhwp/mcp/tools.py:chunks` + `ChunkRecord` 정의 |
| 4 — wire format 보존 정책 | `tests/test_mcp_server.py::TestBackwardsCompat` 3 케이스 (AC-5) |
| 5 — `metadata` 자유 dict 유지 | `ChunkRecord.metadata: dict[str, Any]` + `tests/test_mcp_server.py::TestTypedSignatures::test_chunk_record_metadata_annotation_is_free_dict` (AC-7) |
| 6 — fastmcp `output_schema=` 수동 오버라이드 미사용 | `python/rhwp/mcp/server.py` 변경 없음 — 자동 schema 생성 그대로 |
| 7 — 호출 시그니처 보존 | tools.py 함수 signature — kind / scope / limit / mode 등 v0.5.0 그대로 |
| 8 — `UnknownBlock.kind` JSON Schema not.enum | `python/rhwp/ir/nodes.py:_unknown_kind_schema_extra` callable + `UnknownBlock.kind` Annotated. `tests/test_ir_schema_export.py::test_unknown_kind_routing_pydantic_matches_schema` 가 회귀 가드 |

## 3. 호환성

| 시나리오 | 결과 |
|---|---|
| **기존 fastmcp Client 사용자 (`result.structured_content` raw dict access)** | byte-equal 보장 (`TestBackwardsCompat` × 3). 영향 0 |
| **기존 fastmcp Client 사용자 (`result.data` 인덱싱 — 예: `result.data["body"]`)** | v0.5.1 부터 `result.data` 가 typed Pydantic-like 객체 (`get_ir` / `chunks`) — dict 인덱싱 → attribute access 마이그 필요 (`result.data.body`). README 마이그 노트가 안내 |
| **`iter_blocks` 사용자 (`result.data[0]["kind"]`)** | fastmcp v3 의 `oneOf` deserialization 한계로 list element 가 dict 폴백 — v0.5.0 dict access 패턴 그대로 동작 (backwards-compat 보존) |
| **server side 사용자 (sync handler 직접 호출 — `tools.iter_blocks(path)`)** | v0.5.1 부터 `list[Block]` (typed) 반환 — `block["kind"]` → `block.kind` 마이그 필요. server side 직접 호출은 server-internal 패턴이라 외부 영향 작음 |
| **IR `UnknownBlock` 직접 생성 (Pydantic 런타임 검증)** | 변경 없음. `UnknownBlock(kind="future_kind", prov=...)` 그대로 작동. `not.enum` 은 schema export 만 |
| **IR `HwpDocument.model_dump(mode="json")` round-trip** | 변경 없음. `model_validate_json(model_dump_json())` 동등 — `TestTypedModelRoundTrip` 가 회귀 가드 |
| **Schema validator (`hwp_ir_v1.json` 또는 content-addressed alias)** | packaged schema 갱신 — `UnknownBlock.kind` 의 `not.enum` 반영. v0.3.0 부터 사용한 schema 검증 invariant (`additionalProperties: false`) 그대로 |
| **CI `test-without-extras` job (skip count = 5)** | 변경 없음. `tests/test_mcp_server.py` 의 file-level `pytest.importorskip("fastmcp")` (line 42) 위치 보존 |
| **`tests/type_check_errors.py` 의 4 intentional pyright errors** | 변경 없음 |

**SemVer**: PATCH (0.5.0 → 0.5.1). 외부 wire format 보존 + 기존 dict access 패턴
보존 (iter_blocks list element). `result.data` 에 dict 인덱싱을 직접 했던
사용자만 attribute access 마이그 필요 — README 한 단락으로 안내.

## 4. 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/ -m "not slow"` (전체) | **585 passed, 2 skipped** (aift fixture 의 미주/수식 부재 — pre-existing), 6 deselected (slow). 신규 v0.5.1 테스트 16 모두 그린 |
| `uv run pytest tests/test_mcp_server.py -m "not slow"` | **55 passed** — v0.5.0 의 39 + v0.5.1 신규 16 |
| `uv run pyright python/rhwp/ir/nodes.py python/rhwp/mcp/ tests/test_mcp_server.py` | 0 errors |
| `uv run pyright tests/type_check_errors.py` | 4 intentional errors 보존 (CI invariant) |
| `uv run ruff check python/rhwp/ir/nodes.py python/rhwp/mcp/ tests/test_mcp_server.py` | clean |
| `uv run python scripts/lint_docs.py` | exit 0 |
| `uv run python scripts/generate_spec_trace.py` | 갱신 완료 — 48 spec / 622 test mappings (v0.5.1 16 신규) |
| `cargo` 빌드 | **변경 0** — Rust 코드 변경 없음, `maturin develop` 재빌드 불필요 |
| code-reviewer (fresh-context, sub-agent) | PASS — HIGH 0 / MEDIUM 4 / LOW 2. MEDIUM-1 (측정값 stale) + MEDIUM-3 (라이브러리 이름 in comments) 즉시 처리됨. MEDIUM-2 (Cargo / CHANGELOG) 는 사용자 의도된 보류 (GA 절차로 이양). MEDIUM-4 / LOW-1 / LOW-2 는 pre-existing 또는 spec design intent — no action |

### AC ↔ 테스트 매핑

| AC | 위치 | 테스트 |
|---|---|---|
| AC-1 (`get_ir` return = `HwpDocument`) | `tests/test_mcp_server.py::TestTypedSignatures::test_get_ir_return_annotation_is_hwp_document`, `TestTypedModelRoundTrip::test_get_ir_round_trip` |
| AC-2 (`iter_blocks` return = `list[Block]`) | `TestTypedSignatures::test_iter_blocks_return_annotation_is_list_of_block` |
| AC-3 (`chunks` return = `list[ChunkRecord]` + module export) | `TestTypedSignatures::test_chunks_return_annotation_is_list_of_chunk_record`, `..._chunk_record_is_exposed_on_tools_module`, `TestTypedModelRoundTrip::test_chunk_record_round_trip` |
| AC-4 (outputSchema 강화) | `TestTypedOutputSchema` × 3 (`get_ir` defs / `iter_blocks` oneOf 변형 / `chunks` page_content+metadata) |
| AC-5 (wire format byte-equal) | `TestBackwardsCompat` × 3 (`get_ir` no-wrap / `iter_blocks` `{"result": ...}` wrap / `chunks` `{"result": ...}` wrap) |
| AC-6 (`result.data` typed-or-dict) | `TestTypedClientData` × 3 (`get_ir` typed / `iter_blocks` list[dict] fallback / `chunks` typed) |
| AC-7 (`ChunkRecord.metadata: dict[str, Any]`) | `TestTypedSignatures::test_chunk_record_metadata_annotation_is_free_dict` |
| AC-8 (도구 7 개 등록 회귀) | 기존 `TestToolRegistry::test_lists_exactly_seven_tools` (v0.5.0/mcp#AC-2 marker 그대로) |
| AC-9 (extras / skip count 변동 없음) | CI `test-without-extras` job (`.github/workflows/ci.yml`) — `pytest.importorskip("fastmcp")` file-level + `5 skipped` regex |
| AC-10 (README 갱신) | manual inspection — 도구 표 + 마이그 노트 |

10/10 AC 모두 충족.

## 5. fastmcp v3 한계 — 본 PATCH 작업 중 표면화

본 PATCH 작업 중 spec 의 가정과 fastmcp v3.2.4 의 실제 동작이 두 군데 차이 —
spec body 갱신으로 일관성 회복:

1. **`structured_content` wrap 분기** — BaseModel 반환 (예: `HwpDocument`) 은 wrap
   없이 fields 직접 노출, `list[T]` / scalar 반환은 `{"result": [...]}` wrap. spec
   § wire format byte-equal 의 wrap 분기 표가 정확한 검증 패턴 제공.

2. **callable Discriminator + Tag union 의 client-side deserialization 한계** —
   fastmcp Client 의 자동 reconstruct 가 단순 BaseModel 은 dynamic 모델로 변환
   하지만, callable Discriminator + Tag 유니온의 `oneOf` schema 는 변환 못 해
   list element 가 dict 폴백. server side 의 typed 출력 (sync handler 결과) 은
   AC-2 가 cover, wire format byte-equal 은 AC-5 가 cover. spec AC-6 본문에
   typed-or-dict 분기 명시.

추가 발견: **fastmcp Client + jsonschema 의 strict `oneOf` validation** 이
ParagraphBlock 과 UnknownBlock schema 양쪽 valid 인스턴스 (예: 빈 ParagraphBlock)
에서 fail → client side wire format 호환 실제 깨짐. 결정 8 (`UnknownBlock.kind`
not.enum) 으로 회복.

세 가지 모두 spec 작성 시 in-process 측정으로 발견하지 못한 fastmcp v3 +
jsonschema strict 동작과 callable Discriminator schema 한계가 검증 단계에서
표면화. 코드 fix 는 모두 표준 Pydantic V2 / fastmcp 패턴.

## 6. 알려진 한계 / 이월 사항

다음 항목은 v0.5.1 범위 밖. spec § 미확정 이슈 가 정확한 목록 — 본 절은
v0.5.1 작업 중 표면화된 항목 + 보류 결정 정리.

| 항목 | 상태 | 후속 |
|---|---|---|
| `HwpDocument.schema_version` UserWarning 의 fastmcp 응답 흐름 | 본 PATCH 범위 밖 (spec § 미확정) | 별도 손 검증 (fastmcp Client 의 stderr 캡처) |
| `HwpDocument` 본문 (수 MB IR JSON) 의 MCP 응답 한도 | 본 PATCH 범위 밖 (v0.5.0 § 미확정 그대로 — 본 PATCH 의 wire format byte-equal 의무가 payload 자체를 변경 못함) | v0.6.0+ `--max-bytes` / `Resource` 추상 spec |
| Anthropic Tool Use strict mode 호환 (Field `ge=`/`le=` 금지 등) | IR 모델 미사용 — 보존됨 (gloval CLAUDE.md § Type Hints & Pydantic) | 미래 strict tool calling 사용처에서 검증 |
| fastmcp Client 의 `iter_blocks` typed list (oneOf union dynamic 모델 reconstruct) | fastmcp v3.2.4 한계 — spec AC-6 본문에 명시. dict fallback 으로 backwards-compat 보존 | fastmcp 후속 버전이 oneOf 처리 추가하면 자동 갱신 |
| `Cargo.toml` bump / `CHANGELOG.md [0.5.1]` 섹션 추가 | 본 PATCH step 의 의도된 보류 — 사용자 GA 절차로 이양 | 별도 `chore: v0.5.1 release marker` commit |

## 7. v0.5.1 GA 절차 (인계)

본 step 이후 v0.5.1 GA 까지의 release 절차 (CONVENTIONS § GA 절차):

1. **`Cargo.toml` version bump** — 0.5.0 → 0.5.1 (CLAUDE.md § 버전 관리 의 SSOT)
2. **`mcp-typed-output.md` / `mcp-typed-output-research.md` frontmatter flip** — `status: Draft → Frozen`, `target: v0.5.1 → ga: v0.5.1` (CONVENTIONS § GA 절차)
3. **본 `migration.md` frontmatter** — 이미 Frozen + target: v0.5.1 (post-S1 docs-lint 정책의 pre-GA stage 면제 그대로 적용)
4. **`docs/roadmap/README.md` 인덱스 갱신** — v0.5.1 row 를 Frozen 으로 표시 + 구현 / 검증 로그 표에 v0.5.1 row 추가
5. **`CHANGELOG.md` 항목 추가** — v0.5.1 의 변경 요약 + external/rhwp 서브모듈 commit 핀 (v0.5.0 동일 — 변경 없음)
6. **git tag `v0.5.1`** + GitHub Release 생성 — `publish.yml` 트리거 (Trusted Publisher OIDC)
7. **release 후 손 검증** — 본인 업무 HWP 파일로 examples/06 + Claude Desktop 통합 검증 (typed `result.data` 의 attribute access)

## 8. 참조

### 짝 페어

- spec: [docs/roadmap/v0.5.1/mcp-typed-output.md](../../roadmap/v0.5.1/mcp-typed-output.md)
- ADR: [docs/design/v0.5.1/mcp-typed-output-research.md](../../design/v0.5.1/mcp-typed-output-research.md)

### 외부

- fastmcp v3.2.4 docs § Use Typed Models for Structured Output: <https://github.com/jlowin/fastmcp/blob/v3.2.4/docs/servers/tools.mdx>
- jsonschema spec `oneOf` semantics: <https://json-schema.org/understanding-json-schema/reference/combining#oneOf>
- Pydantic V2 `Field(json_schema_extra=callable)`: <https://docs.pydantic.dev/latest/concepts/json_schema/#schema-customization>
- LangChain Core `Document` 모델 (ChunkRecord 의 source-of-truth): <https://python.langchain.com/api_reference/core/documents/langchain_core.documents.base.Document.html>

### 상류

본 v0.5.1 은 상류 (`edwardkim/rhwp`) 변경 0 — pure Python schema 강화.
`external/rhwp` submodule pin (v0.5.0 그대로) 보존.
