---
status: Draft
description: "v0.5.0 — 'rhwp-mcp' MCP 서버. LLM 에이전트가 HWP/HWPX 직접 파싱·요약·청크화 가능한 표준 프로토콜 표면"
target: v0.5.0
last_updated: 2026-05-06
---

# v0.5.0 — MCP server (`rhwp-mcp`)

[Model Context Protocol](https://modelcontextprotocol.io/) (Anthropic, 2024) 기반의 MCP 서버를 새 entry point `rhwp-mcp` 로 노출한다. LLM 에이전트 (Claude Desktop / IDE 통합 / 자체 에이전트) 가 HWP/HWPX 파일을 직접 파싱·요약·청크화할 수 있도록 표준 프로토콜 표면을 제공한다.

주요 결정 (SDK 채택 / transport 우선순위 / 동시성 모델 / 도구 분할 / 인증·sandboxing 정책) 의 업계 선례·대안·실패 시나리오는 짝 페어: [mcp-research.md](../../design/v0.5.0/mcp-research.md).

## 배경 — phase 무관 단발 통합

MCP 는 RAG 프레임워크 (LangChain 등) 가 아니라 **LLM 에이전트 프로토콜** — Phase 3 의 "RAG 프레임워크 통합" 카테고리와는 도메인이 다르다. Phase 4 (IR → HWP 역생성) 와도 무관 (readonly). 따라서 **phase 소속 없이 독립 spec** 으로 진행한다 — 활성 spec 인덱스 ([roadmap/README.md](../README.md)) 가 SSOT.

v0.5.0 시점이 sweet spot 인 이유:

- **노출할 도구가 풍부**: parse + IR (v0.2~0.3 GA) + view (v0.4 GA) + LangChain chunks (v0.3 GA) — IR / view / chunks 표면이 모두 안정화되어 MCP tool surface 가 유의미한 기능을 묶어낼 수 있음
- **외부 의존성 0**: HWP writer API 안정에 좌우되는 작업 (IR → HWP 역생성, [roadmap/README.md § v0.8.0 ~ v1.0.0](../README.md)) 은 rhwp Rust 코어 일정에 좌우되어 유동적 — "시작 전 업스트림 상태 재평가" 명시. MCP 는 readonly 라 외부 의존 없어 v0.5.0 슬롯의 안정 채움 역할
- **통합 패턴 정착**: v0.3.0 LangChain integration 으로 `python/rhwp/integrations/<framework>.py` + 옵셔널 extras 패턴이 정립된 이후 — MCP 도 동일 패턴 답습. Phase 3 후속 RAG 프레임워크 통합 (LlamaIndex / Haystack 등) 은 demand-driven 으로 보류 ([roadmap/README.md § 미착수 작업 계획](../README.md)) — MCP 가 다음 surface 확장의 우선순위가 됨

## 목표와 비목표

### v0.5.0 목표

1. **표준 MCP 서버 entry point**: `rhwp-mcp` 명령으로 stdio/streamable-http transport 기동
2. **읽기 전용 도구 노출**: `parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks` / `to_markdown` / `to_html` / `chunks`
3. **LLM-friendly schema**: Pydantic 모델 기반 입력 schema — 인자 타입을 LLM 이 정확히 추론
4. **`unsendable` 안전 보장**: sync handler 안에서 parse → consume → primitive 반환 — Document 가 thread 경계를 안 넘는 패턴 강제
5. **Claude Desktop 즉시 사용 가능**: README 에 `claude_desktop_config.json` 등록 예제 포함

### 비목표 (v0.5.0)

- **쓰기 도구** (HWP/HWPX 생성·수정) — Phase 4 (역생성) 의존. Phase 4 GA 후 별도 spec
- **파일 업로드 / blob storage** — MCP `Resource` 추상에는 적합하나 file path 노출만으로 1차 충분. 업로드는 v0.8.0+ 재평가
- **인증 / 권한 모델** — stdio transport 기본 사용 시 OS 사용자 권한이 곧 권한. streamable-http 는 reverse proxy 에 위임 (rhwp-mcp 자체에는 인증 미내장)
- **Sandboxing** — 파일 path 검증 / 디렉토리 화이트리스트는 운영자 책임. rhwp-mcp 는 사용자가 지정한 path 를 그대로 신뢰
- **렌더링 도구** (`render_pdf`/`render_svg`) — 업스트림 `rhwp` 바이너리 영역. CLI § 업스트림과의 경계 정책 동일 적용
- **REPL / 대화형 클라이언트** — MCP 클라이언트는 LLM 호스트 (Claude Desktop / Cline / 자체 에이전트) 의 영역

### 영구 비범위

- MCP `Sampling` 기능 (서버가 클라이언트 LLM 에 추가 추론 요청) — 본 서버는 순수 데이터 추출 도구. LLM 호출 비용을 사용자에게 불투명하게 만들 위험

## 노출 도구

| 도구 | 입력 | 출력 | 의존 |
|---|---|---|---|
| `parse_hwp_summary(path)` | `path: str` | `{sections, paragraphs, pages, rhwp_core_version}` | core |
| `extract_text(path)` | `path: str` | `str` (단락별 `\n` 결합) | core |
| `get_ir(path)` | `path: str` | `dict` (`HwpDocument.model_dump()`) | core |
| `iter_blocks(path, kind, scope, limit)` | `path: str`, `kind: Literal["paragraph", "table", "picture", ...]`, `scope: Literal["body", "furniture", "all"]`, `limit: int \| None` | `list[dict]` | core |
| `to_markdown(path)` | `path: str` | `str` | **v0.4.0 view 의존** |
| `to_html(path, include_css: bool)` | `path: str`, `include_css: bool = False` | `str` | **v0.4.0 view 의존** |
| `chunks(path, mode, size, overlap)` | `path: str`, `mode: Literal["single", "paragraph", "ir-blocks"]`, `size: int = 500`, `overlap: int = 50` | `list[{page_content, metadata}]` | langchain-text-splitters |

**도구 명명 규칙**:

- **명사 / 동사+명사** — `extract_text`, `get_ir`, `parse_hwp_summary` (LLM 이 의도 추론 쉬움)
- **CLI `rhwp-py` 와 1:1 mapping** — `rhwp-py blocks` ↔ `iter_blocks`, `rhwp-py chunks` ↔ `chunks`, `rhwp-py ir` ↔ `get_ir`. 두 표면이 같은 정신 모델 공유 → 사용자 학습 비용 절감
- **인자 schema 는 Pydantic V2 모델로 강타입** — FastMCP 가 자동으로 JSON Schema 생성, LLM 이 enum 값 (`kind`, `scope`, `mode`) 을 정확히 사용

## `unsendable` 안전 패턴

`_Document` 는 `#[pyclass(unsendable)]` — thread 경계를 넘으면 panic. MCP handler 에서 다음 두 패턴을 강제한다:

### ✅ 허용 — sync handler

```python
@mcp.tool()
def extract_text(path: str) -> str:
    doc = rhwp.parse(path)            # ^ 이 thread 에서 생성
    text = "\n".join(b.text for b in doc.iter_blocks(kind="paragraph"))
    return text                        # ^ Document 폐기, primitive 만 반환
```

FastMCP 의 sync tool 은 event loop thread 에서 직접 호출 — Document 가 만들어진 thread 에서 소비되고 폐기. thread 경계 없음.

### ❌ 금지 — async handler + `asyncio.to_thread`

```python
# DO NOT DO THIS
@mcp.tool()
async def extract_text(path: str) -> str:
    doc = await asyncio.to_thread(rhwp.parse, path)   # ^ worker thread 에서 생성
    return "\n".join(b.text for b in doc.iter_blocks(kind="paragraph"))
    #     ^ event loop thread 에서 접근 — panic
```

CLAUDE.md § 비동기 방향 의 "Forbidden pattern" 그대로. async 가 필요하면 **handler 안에서 sync rhwp 호출만 하고, MCP 프로토콜 측 async 는 FastMCP 가 알아서 처리** 하도록 둔다.

### `aparse` 의 위치

`rhwp.aparse(path)` 는 file read 만 thread 에 보내고 `Document.from_bytes(data)` 는 event loop thread 에서 호출하는 우회 패턴 (CLAUDE.md § 비동기 방향). MCP handler 에서 **굳이 async 가 필요한 경우만** `aparse` 사용하되, 일반적으로는 sync `parse` 만으로 충분 — MCP request 1건의 latency 가 file read 한 번에 묶이는 것이 정상.

## Transport 결정

| Transport | 우선순위 | 사용처 |
|---|---|---|
| **stdio** | **기본** | Claude Desktop / Cline / 로컬 IDE 통합 — `rhwp-mcp` 단독 실행, MCP 클라이언트가 subprocess spawn |
| **streamable-http** | 옵션 (`--transport streamable-http --port N`) | 서버 배포 / 다중 클라이언트 / 컨테이너 — uvicorn 기반 ASGI |
| **SSE** | 비범위 | streamable-http 가 후속 표준 (MCP spec 2024-11). SSE 만 별도 노출하지 않음 |

stdio 가 기본인 이유:

1. **MCP 의 가장 일반적 배포 형태** — Claude Desktop 의 `claude_desktop_config.json` 이 stdio subprocess 만 지원
2. **인증 부담 없음** — OS 사용자 권한이 곧 접근 권한
3. **`unsendable` 과 자연 정합** — 단일 process / 단일 event loop / 동시 request 도 직렬화

streamable-http 는 **optional** — 서버 컨테이너 배포 / 원격 LLM 에이전트 시나리오 대응. 운영자가 reverse proxy + 인증을 책임진다.

## 의존성 / 배포

### 새 extras 축

```toml
[project.optional-dependencies]
mcp = ["fastmcp>=3,<4"]
# ^ standalone fastmcp v3 (jlowin) — MCP 서버의 약 70% 가 사용하는 현업 표준 (2026-05).
#   공식 mcp SDK 안의 FastMCP v1 은 frozen 상태 — v2/v3 의 OAuth / OpenTelemetry /
#   server composition / OpenAPI 통합 / streamable-http 우선 같은 프로덕션 기능은
#   standalone 에만 존재. ADR § 1 참조.
mcp-chunks = [
    "fastmcp>=3,<4",
    "langchain-core>=0.2",
    "langchain-text-splitters>=0.2",
]
# ^ chunks 도구는 langchain-text-splitters 도 요구. cli-chunks 와 동일 패턴.
```

`pip install "rhwp-python[mcp]"` 로 `rhwp-mcp` 활성화. `chunks` 도구 사용자는 `[mcp-chunks]` 또는 `[mcp,langchain]` 조합. extras 키 이름은 `mcp` (기능 표시) — 실제 의존성은 `fastmcp` standalone.

### Entry point

```toml
[project.scripts]
rhwp-mcp = "rhwp.mcp:run"
```

CLI 와 같은 lazy-import 패턴 — `fastmcp` 미설치 시 친절한 에러:

```
rhwp-mcp requires `fastmcp`. Install with:
    pip install "rhwp-python[mcp]"
```

### 모듈 위치

```
python/rhwp/mcp/
├── __init__.py          (빈 파일, CLAUDE.md 규칙)
├── __main__.py          python -m rhwp.mcp 진입점
├── server.py            FastMCP 인스턴스 + 도구 등록
└── tools.py             도구 함수 본체 (server.py 가 데코레이터로 wrap)
```

`integrations/` 가 아닌 **별도 top-level 모듈** — entry point 가 있고 lifecycle (서버 기동) 이 있어 통합 (passive loader/converter) 와 성격이 다름. CLI 와 같은 위계.

## 구현 스테이지 분할

| Stage | 내용 | 산출물 |
|---|---|---|
| **S1 — 서버 스켈레톤** | `python/rhwp/mcp/` 패키지, FastMCP 인스턴스, `parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks` 4개 도구, stdio transport, extras 설정, entry point | `python/rhwp/mcp/{__init__.py, __main__.py, server.py, tools.py}`, `pyproject.toml`, `tests/test_mcp_server.py` |
| **S2 — view 도구** | `to_markdown` / `to_html` 도구 추가 (v0.4.0 view API 의존) | `tools.py` 확장, 테스트 |
| **S3 — chunks 도구** | `chunks` 도구 (langchain-text-splitters extras gate) | `tools.py` 확장, extras-gated 테스트 |
| **S4 — streamable-http transport** | `--transport streamable-http --port N` CLI 옵션, uvicorn 기반 기동 | `server.py` transport 분기, smoke 테스트 |
| **S5 — 문서화·검증** | README MCP 섹션, Claude Desktop 등록 예제, 실제 LLM 클라이언트 손 검증 | 문서 전반 |

## 테스트 전략

### 단위 테스트 (`tests/test_mcp_server.py` — 신규)

- `mcp.server.fastmcp.FastMCP.list_tools()` 로 등록된 도구 7개 확인
- 각 도구를 in-process 로 호출 (`mcp.run` 없이 `await mcp._tool_manager.call_tool(...)`) — 입출력 schema 검증
- `extract_text("nonexistent.hwp")` → 친절한 에러 (`FileNotFoundError` raise → MCP `isError=True`)
- `iter_blocks` 의 `kind` enum 미허용 값 → Pydantic validation error 가 MCP error 로 변환

### 통합 테스트

- 실제 샘플 `aift.hwp` / `table-vpos-01.hwpx` 로 7개 도구 round-trip
- stdio transport 로 `rhwp-mcp` subprocess spawn → MCP `initialize` + `tools/list` + `tools/call` 시퀀스 검증

### CI

- `test-without-extras` job 에서 `rhwp-mcp` 호출 시 친절 에러 + exit 2 검증 (extras-gated 4개 → 5개로 증가, ci.yml + CLAUDE.md 동시 갱신)
- streamable-http smoke 는 별도 `slow` 마커 — 매 PR 미실행

## 결정 사항

| # | 이슈 | 결정 | 근거 |
|---|---|---|---|
| 1 | SDK | standalone `fastmcp` v3 (jlowin) | 2026-05 현업 표준 (MCP 서버 약 70% 사용) + v3 의 OAuth / OpenTelemetry / server composition / streamable-http 우선 기능. 공식 `mcp` SDK 안의 FastMCP v1 은 frozen — 상세: [mcp-research § 1](../../design/v0.5.0/mcp-research.md#1-sdk-선택) |
| 2 | Transport 우선순위 | stdio 기본 + streamable-http 옵션 | Claude Desktop 호환 + ASGI 배포 시나리오 양쪽 커버. SSE 단독은 비범위 |
| 3 | Handler sync/async | **sync 강제** | `unsendable` Document 의 thread-safety. async + to_thread 는 panic — 상세: [mcp-research § 3](../../design/v0.5.0/mcp-research.md#3-handler-동시성-모델) |
| 4 | 도구 분할 | 작은 도구 7개 (단일 통합 도구 X) | LLM 이 의도별로 명확히 호출 가능. 단일 도구 + `operation` 파라미터는 schema 가 모호 — 상세: [mcp-research § 4](../../design/v0.5.0/mcp-research.md#4-도구-분할-vs-통합) |
| 5 | 인증 / sandboxing | 미내장 (운영자 책임) | stdio = OS 권한 / streamable-http = reverse proxy. 라이브러리 레이어가 보안 책임지면 부분적 보호로 오해 유발 |
| 6 | extras 명명 | `[mcp]` / `[mcp-chunks]` (의존성은 `fastmcp`) | CLI extras (`[cli]` / `[cli-chunks]`) 와 일관 패턴. extras 키는 "MCP 서버 기능" 을 표시 — 의존성 패키지명 (`fastmcp`) 과 분리 |
| 7 | 모듈 위치 | `python/rhwp/mcp/` (top-level) | entry point + lifecycle 보유 — `integrations/` (passive) 와 성격 다름. CLI 와 같은 위계 |

## 인수조건

- **AC-1** — `[mcp]` extras (= `fastmcp`) 미설치 시 `rhwp-mcp` 호출이 친절 에러 + exit 2 (CLI extras gate 패턴 동일, 결정 6)
- **AC-2** — `rhwp-mcp` stdio 기동 후 MCP `tools/list` 응답이 7 개 도구 (`parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks` / `to_markdown` / `to_html` / `chunks`) 정확히 노출 (§ 노출 도구, 결정 4)
- **AC-3** — `iter_blocks(kind="invalid_value")` 호출 시 Pydantic validation error → MCP `CallToolResult.isError=True` 응답 (panic 아님, § 단위 테스트)
- **AC-4** — `extract_text("nonexistent.hwp")` 호출 시 `FileNotFoundError` → MCP `isError=True` 응답 (§ 단위 테스트)
- **AC-5** — 모든 7 도구 handler 가 sync 함수 (`async def` 아님) — handler 안에서 `rhwp.parse(path)` → 소비 → primitive 반환 (Document 가 thread 경계 미보유). `asyncio.to_thread(rhwp.parse, ...)` 패턴 코드 내 부재 (결정 3, § `unsendable` 안전 패턴)
- **AC-6** — `to_markdown(path)` / `to_html(path, include_css=False)` 도구가 v0.4.0 view API (`HwpDocument.to_markdown()` / `HwpDocument.to_html()`) 위 thin wrapper 로 동작 (S2)
- **AC-7** — `chunks` 도구 호출 시 `langchain-text-splitters` 미설치면 MCP `isError=True` 응답 — 서버 기동은 정상 + 다른 6 도구는 사용 가능 (런타임 extras gate, S3)
- **AC-8** — `rhwp-mcp --transport streamable-http --port N` 옵션이 uvicorn ASGI 로 기동, MCP `initialize` + `tools/list` round-trip 정상 (결정 2, S4 — endpoint path 는 SDK 기본값 추종)
- **AC-9** — `pyproject.toml` 에 `[project.optional-dependencies]` `mcp = ["fastmcp>=3,<4"]` + `mcp-chunks` extras 등록 + `[project.scripts]` `rhwp-mcp = "rhwp.mcp:run"` entry point 등록 (§ 의존성 / 배포)
- **AC-10** — `python/rhwp/mcp/` 모듈 위치 (top-level, `integrations/` 가 아님 — 결정 7). `__init__.py` 는 빈 파일 또는 docstring only (CLAUDE.md 규칙)
- **AC-11** — CI `test-without-extras` job 의 expected skip count 가 4 → 5 로 증가 (`tests/test_mcp_server.py` 가 module-level `pytest.importorskip("fastmcp")` 로 1 skip 기여). `.github/workflows/ci.yml` + `AGENTS.md` § Tests 동시 갱신 (§ 다른 산출물의 파급)

## 미확정 이슈

- **`get_ir` 의 출력 크기** — 큰 문서는 IR JSON 이 수 MB. MCP `tools/call` 응답 한도 (클라이언트 별 상이) 와 충돌 가능. **검토**: `--max-bytes` 파라미터 추가 vs `Resource` 추상으로 재노출 (`hwp://path/ir`)
- **에러 응답 형식** — `FileNotFoundError` / `ParseError` / `ExtrasNotInstalledError` 를 MCP `CallToolResult.isError=True` + `content[0].text` 로 통일할지, 또는 MCP `errors.MCPError` 표준 사용할지
- **Resource 추상 사용 여부** — MCP `Resource` 는 "URL 기반 데이터 노출" 추상. 파일 path 를 `hwp://` URI 로 노출하면 클라이언트가 도구 호출 없이 직접 fetch 가능. v0.5.0 1차는 도구 7개만 — Resource 는 차기 minor 의 MCP 확장 spec 에서 평가
- **Prompt 추상 사용 여부** — MCP `Prompt` 는 "재사용 가능한 LLM prompt template". HWP 문서를 Markdown 으로 변환 후 요약하는 prompt 템플릿 등을 노출하면 가치 있을 수 있으나 라이브러리 책임 범위 모호
- **Claude Desktop 외 호환성 검증** — Cline / Continue.dev / Cursor / Goose 등 다른 MCP 클라이언트의 stdio handshake 차이 — Stage 5 손 검증 항목

## 다른 산출물의 파급 (코드 / 데이터)

- `pyproject.toml` — `[mcp]` / `[mcp-chunks]` extras 신규, `[project.scripts] rhwp-mcp = "rhwp.mcp:run"` entry point 등록
- `CLAUDE.md` § Tests — extras-gated 테스트 파일 카운트 4 → 5로 증가 (test_mcp_server.py 추가). ci.yml `test-without-extras` 의 expected skip count 도 동시 갱신
- `README.md` — § MCP 섹션 신설, Claude Desktop 등록 예제 추가
- `examples/` — `06_mcp_server.py` (FastMCP 직접 사용 예제) 신규 검토

문서 cross-link (README 인덱스) 는 CONVENTIONS.md § Cross-link 방향성 규칙 에 따라 본 spec 본문에서 다루지 않음.

## 참조

- Model Context Protocol 공식: <https://modelcontextprotocol.io/>
- MCP Python SDK: <https://github.com/modelcontextprotocol/python-sdk>
- 활성 spec 인덱스 (phase 무관 단발 통합): [roadmap/README.md](../README.md)
- 짝 페어 (ADR): [mcp-research.md](../../design/v0.5.0/mcp-research.md)
- `unsendable` 패턴 배경: 프로젝트 [CLAUDE.md § Rust + Python 하이브리드 빌드](../../../CLAUDE.md)
