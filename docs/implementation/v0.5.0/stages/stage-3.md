---
status: Frozen
description: "v0.5.0 S3 작업 로그 — chunks 도구 추가 (RAG 청킹). langchain-text-splitters 런타임 extras gate (AC-7), 도구 카운트 6 → 7 (mcp.md AC-2 GA 기준 충족)"
target: v0.5.0
last_updated: 2026-05-06
---

# Stage S3 — chunks 도구 + 런타임 extras gate (완료)

**작업일**: 2026-05-06
**계획 문서**: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md) §구현 스테이지 분할 S3
**선행 stage**: [stage-2.md](stage-2.md) (view 도구 추가)

## 스코프

mcp.md §구현 스테이지 분할 S3 행 정확 매핑:

- `python/rhwp/mcp/tools.py` 에 `chunks(path, mode, size, overlap)` 추가 — `langchain-text-splitters` 런타임 lazy import
- `python/rhwp/mcp/server.py` `build_server()` 가 7 도구 등록 (AC-2 GA 기준 충족)
- `tests/test_mcp_server.py` 의 `test_lists_exactly_six_tools` → `test_lists_exactly_seven_tools` rename + `TestChunks` 클래스 추가 (5 테스트 — smoke 3 / AC-7 missing-extras 2)
- AC-7 검증: `langchain-text-splitters` 미설치 시 chunks 호출만 ToolError → MCP isError=True, 다른 6 도구 / 서버 기동은 정상

S4 (streamable-http transport), S5 (문서화·검증) 는 본 stage 범위 밖.

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/mcp/tools.py` | +52 / -1 | `chunks(path, mode, size, overlap) -> list[dict]` 추가 — 함수 본체 안에서 ``from langchain_text_splitters import RecursiveCharacterTextSplitter`` lazy import + ImportError 시 친절 메시지로 re-raise. `ChunksMode` Literal 추가 (`"single"` / `"paragraph"` / `"ir-blocks"` — `HwpLoader.LoadMode` 와 1:1). 모듈 docstring 의 stage 분할 갱신 |
| `python/rhwp/mcp/server.py` | +5 / -2 | `build_server()` 가 `tools.chunks` 등록 — 코어 4 + view 2 + chunks 1 = 7. 주석에 등록은 무조건 / 호출 시점 lazy import 가 AC-7 의 일관 패턴 명시 |
| `tests/test_mcp_server.py` | +75 / -8 | 모듈 docstring AC 매핑 갱신 (AC-7 추가), `test_lists_exactly_seven_tools` 로 rename + 도구 set 7 개로 확장, `TestChunks` (5 테스트 — `test_default_paragraph_mode` / `test_modes_all_supported` / `test_size_overlap_pass_through` / `test_missing_extras_raises_tool_error` / `test_missing_extras_does_not_break_other_tools`) 신설 — AC-7 spec 매핑 |
| `docs/traces/coverage.md` | +7 | auto-regen — `v0.5.0/mcp#AC-7` 매핑 2 개 추가 |

## S3 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **extras gate 위치 — 등록 시점이 아닌 호출 시점** | `build_server()` 는 무조건 `chunks` 등록, 함수 본체 진입 시 lazy import 가 ImportError | mcp.md AC-7 ("서버 기동은 정상 + 다른 6 도구는 사용 가능") 을 위해선 등록은 무조건. fastmcp 가 도구 함수의 ImportError 를 ``ToolError`` 로 wrap → MCP `CallToolResult(isError=True)` 직렬화. 등록 자체를 conditional 로 하면 LLM 이 도구 존재 자체를 모름 (사용자 메시지 빈약) |
| **`langchain_text_splitters` 만 try/except, `HwpLoader` import 는 밖** | text-splitters 의 `Requires-Dist` 가 langchain-core 를 transitive 로 강제 (pip metadata 검증) | text-splitters 단독 설치 / langchain-core 누락 시나리오는 pip 가 차단 — `HwpLoader` import 가 try/except 밖에 있어도 ImportError 발생 안 함. try/except 범위를 넓히면 메시지가 모호해짐 (사용자에게 "어느 패키지가 빠진 건지" 안 알려줌) |
| **AC-7 검증 — `sys.modules` mocking 패턴** | `monkeypatch.setitem(sys.modules, "langchain_text_splitters", None)` | CPython import sentinel 의 documented 동작 — 캐시 hit 상태에서도 `None` 박으면 `ImportError("import of langchain_text_splitters halted; None in sys.modules")` 정확히 강제. 실제 미설치 환경 시뮬레이션의 표준 pytest 패턴. 검증환경에 langchain 이 설치되어 있어도 본 테스트는 항상 실행 |
| **smoke 테스트 — 메서드별 importorskip** | `pytest.importorskip("langchain_text_splitters")` 를 메서드 안에 배치 (file-level pytestmark 가 아님) | file-level 은 fastmcp 만 게이트 (S1 결정). 본 파일이 file-level 로 langchain 까지 게이트하면 AC-7 missing-extras 테스트 자체가 langchain 없는 환경에서 skip 됨 — AC-7 의 invariant 검증을 langchain 미설치 환경에서 더 의미있게 실행해야 한다는 모순. 메서드별 게이트는 smoke 만 conditional skip / AC-7 는 항상 실행 |
| **`include_furniture` 미노출** | spec 의 `chunks(path, mode, size, overlap)` 시그니처 그대로 — 4 파라미터만 | `HwpLoader.include_furniture` 는 `mode="ir-blocks"` 에서만 의미 있고 default `False` 가 RAG body 검색 오염 회피의 합리적 기본 (HwpLoader docstring). MCP 표면에 노출 시 모드별로 무시되는 인자가 schema 에 보여 LLM 의도 파악에 방해. furniture 가 필요한 사용자는 별도 도구 (`iter_blocks(scope="furniture")`) 로 우회 |
| **에러 메시지 형식** | `"rhwp-mcp `chunks` tool requires `langchain-text-splitters`. Install with: pip install \"rhwp-python[mcp-chunks]\""` | CLI 의 `chunks_cmd` 미설치 메시지 (`'pip install "rhwp-python[cli-chunks]"'`) 와 동일 형태 — 사용자 경험 일관. ToolError 가 이 메시지를 보존해 MCP 응답 본문에 그대로 노출 |
| **`mode` 어휘** | `"single"` / `"paragraph"` / `"ir-blocks"` (CLI / `HwpLoader.LoadMode` 와 1:1) | spec § 노출 도구 명시. 사용자 학습 비용 절감 (CLI / MCP / SDK 3 표면 동일 어휘) |
| **출력 형식 — `dict[str, Any]` (Pydantic 모델 미사용)** | `[{"page_content": str, "metadata": dict}]` flat dict | iter_blocks / get_ir 와 동일 패턴. Pydantic `ChunkRecord` 모델로 강타입화하면 LLM 의 응답 schema 추론은 더 정확하나 (코드 reviewer LOW-2), iter_blocks / chunks 양쪽이 통일된 후속 polish 로 분리 — 본 stage 는 spec 표 그대로 |

## 비타협 제약 준수

- **`unsendable` 안전 패턴** — `chunks` 도구가 sync 함수, `HwpLoader.load()` 가 같은 thread 에서 `rhwp.parse()` → 이터레이트 → primitive dict 반환. Document 가 thread 경계 안 넘음. `TestSyncHandler::test_all_registered_tools_are_sync` 가 등록된 7 도구 walk 로 자동 커버
- **AC-7 의 두 측면 모두 검증** — (a) chunks 호출은 `ToolError` (panic 아님), (b) 다른 6 도구 + 서버 기동은 정상. 두 테스트로 분리 (`test_missing_extras_raises_tool_error`, `test_missing_extras_does_not_break_other_tools`)
- **Pydantic V2 / Literal enum** — `ChunksMode = Literal["single", "paragraph", "ir-blocks"]` (str Enum 이 아닌 Literal — JSON Schema enum 으로 정확히 출고)
- **`__init__.py` 모듈 레벨 third-party import 금지** — 변경 없음 (S1 그대로)
- **모듈 위치** `python/rhwp/mcp/` (top-level) — 변경 없음

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/ -m "not slow"` | **558 passed, 2 skipped** (S2 553 + S3 신규 5) |
| `uv run pytest tests/test_mcp_server.py -v` | **28 passed** (S1 18 + S2 5 + S3 5) |
| `uv run ruff check python/rhwp/mcp/ tests/test_mcp_server.py` | clean |
| `uv run pyright python/rhwp/mcp/ tests/test_mcp_server.py` | **0 errors** |
| `uv run python scripts/lint_docs.py` | exit 0 |
| `uv run python scripts/generate_spec_trace.py --check` | up to date — 10 AC 매핑 (S1 의 7 + S2 의 AC-6×3 + S3 의 AC-7×2) |
| `code-reviewer` fresh-context 검증 | LOW 3 / MEDIUM 0 / HIGH 0 / BLOCKER 0 — LOW-1 (furniture docstring) / LOW-3 (empty-list guard) 반영, LOW-2 (`ChunkRecord` Pydantic 모델) 는 iter_blocks 와 일괄 후속 polish 로 보류 |

### 테스트 커버리지 (mcp.md §S3 → AC 매핑)

| mcp.md AC | 테스트 |
|---|---|
| AC-2 (도구 7 개 노출 — GA 기준 충족) | `TestToolRegistry::test_lists_exactly_seven_tools` |
| AC-7 (chunks extras-gate 런타임, 다른 도구 영향 없음) | `TestChunks::test_missing_extras_raises_tool_error`, `TestChunks::test_missing_extras_does_not_break_other_tools` |
| AC-7 보조 (chunks 정상 동작) | `TestChunks::test_default_paragraph_mode`, `TestChunks::test_modes_all_supported`, `TestChunks::test_size_overlap_pass_through` |

S1 / S2 의 AC-3 / AC-4 / AC-5 / AC-6 / AC-9 / AC-10 매핑은 그대로 유지 — `TestSyncHandler` 가 7 도구 walk, packaging 검증은 도구 카운트와 독립.

## 알려진 한계 (S4 이후 처리)

- **`mode="ir-blocks"` 의 `include_furniture` 옵션 미노출** — 본 stage 결정 사항. furniture 가 필요한 사용자는 `iter_blocks(scope="furniture")` 로 우회. 향후 사용자 피드백 시 별도 spec 으로 평가
- **출력 schema 강타입화 (`ChunkRecord` Pydantic 모델)** — `code-reviewer` LOW-2. iter_blocks / get_ir 도 같은 패턴 (`list[dict[str, Any]]`) 이라 본 stage 단독 변경은 일관성 깨짐. 후속 minor 에서 일괄 polish 검토
- **AC-7 에서 `[mcp-chunks]` extras 가 실제로 동작 가능한지의 통합 검증 부재** — 단위 테스트는 sys.modules mocking 으로 미설치 시뮬레이션. 실제 `pip install rhwp-python[mcp-chunks]` 후 chunks 호출 성공의 통합 검증은 S5 (문서화·검증) 에서 손 검증 항목

## S4 진입 조건 (인수인계)

S4 는 `--transport streamable-http --port N` CLI 옵션 추가 — uvicorn ASGI 기반 기동. S1 / S2 / S3 에서 고정한 계약:

1. **`tools.py` 의 sync-only 패턴** — S4 는 transport 변경만 — 도구 본체에 영향 없음. fastmcp v3 의 `mcp.run(transport="http", host=..., port=...)` 가 도구 등록과 독립
2. **`build_server()` factory** — 7 도구 등록 그대로 유지. S4 는 `run()` 함수가 transport 인자를 분기하는 변경
3. **`__init__.py` 의 entry point dispatch** — S4 는 `rhwp-mcp --transport streamable-http --port N` CLI argparse 추가. 현재 `__init__.py` 의 lazy-import 패턴 위에서 `argparse.ArgumentParser` (stdlib only) 로 분기 후 `server.run(transport=...)` 호출
4. **AC-8 검증** — `rhwp-mcp --transport streamable-http --port N` 가 uvicorn ASGI 로 기동하고 MCP `initialize` + `tools/list` round-trip 정상. smoke 는 `pytest.mark.slow` 마커 (mcp.md § CI 의 streamable-http smoke 정책)
5. **CI test-without-extras skip count** — S4 는 추가 변동 없음. 현재 5 유지

## 참조

- 상위 설계: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md)
- 결정 사항 증거: [design/v0.5.0/mcp-research.md](../../../design/v0.5.0/mcp-research.md)
- 선행 stages: [stage-1.md](stage-1.md), [stage-2.md](stage-2.md)
- HwpLoader (의존 대상): `python/rhwp/integrations/langchain.py`
- v0.3.0 LangChain integration spec (의존 대상): roadmap/v0.3.0/cli.md (chunks CLI 결정)
