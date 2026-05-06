---
status: Draft
description: "v0.5.0 MCP ADR — SDK 채택 (FastMCP) / transport (stdio + streamable-http) / handler 동시성 (sync 전용) / 도구 분할 (7 개) 결정 근거"
target: v0.5.0
last_updated: 2026-05-06
---

# v0.5.0 MCP server — 설계 의사결정 리서치 요약

[v0.5.0/mcp.md](../../roadmap/v0.5.0/mcp.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 4건 (SDK 채택 · transport 우선순위 · handler 동시성 모델 · 도구 분할 정책) 의 업계 선례·대안·실패 시나리오를 기록한다. mcp.md 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

## 결정 매트릭스

| # | 이슈 | 결정 | 핵심 근거 |
|---|---|---|---|
| 1 | MCP SDK | **공식 `mcp` Python SDK (FastMCP)** | Anthropic 1st-party 유지 + spec 변동 흡수 비용 0 |
| 2 | Transport 우선순위 | **stdio 기본 + streamable-http 옵션** | Claude Desktop 호환 (stdio-only) + ASGI 배포 시나리오 양쪽 커버 |
| 3 | Handler 동시성 모델 | **sync 전용** | `_Document` `unsendable` 제약 — async + to_thread 는 panic |
| 4 | 도구 분할 | **작은 도구 7개** (단일 통합 도구 X) | LLM 의도 명확화 + JSON Schema 정확도 + CLI `rhwp-py` 와 1:1 정합 |

---

## 1. SDK 선택

### 조사: MCP 서버 구현 옵션

| 옵션 | 유지 주체 | 성숙도 | spec 추종 |
|---|---|---|---|
| **공식 `mcp` Python SDK** (`/modelcontextprotocol/python-sdk`) | Anthropic | v1.12.4, FastMCP API 안정 | 1st-party — spec 갱신 즉시 반영 |
| 직접 구현 (JSON-RPC over stdio) | 본 프로젝트 | — | spec drift 자체 추적 비용 |
| 3rd-party SDK (`fastmcp` standalone, `mcp-server-utils` 등) | 커뮤니티 | 변동 | wrap 위주 — 공식 SDK 의존성 그대로 발생 |

### 관찰

1. **MCP spec 은 빠르게 진화 중** — 2024-11 (initial), 2025-03 (Streamable HTTP 채택, SSE deprecation) 주기. 직접 구현은 매 spec revision 마다 수정 부담
2. **FastMCP 가 사실상 표준 사용 패턴** — `@mcp.tool()` 데코레이터 + Pydantic 자동 schema 생성. 공식 SDK 가 흡수 (`mcp.server.fastmcp.FastMCP`)
3. **동등 수준의 3rd-party 가 없음** — TypeScript / Rust 진영 (`/rust-mcp-stack/rust-mcp-sdk`) 은 활발하나, Python 은 공식 SDK 가 사실상 단독

### 대안 평가

- **직접 구현**: spec drift 부담 + JSON-RPC stdio framing 재구현 + tool schema 자동 생성 부재 → 모든 도구 schema 를 수작업. 가치 없음
- **3rd-party wrap**: 공식 SDK 위에 얇은 layer 만 — extras 차원에서 의존성 늘어날 뿐
- **공식 SDK**: ✅ 채택. 의존성 1개 (`mcp>=1.12`) 로 모든 transport · schema · lifecycle 커버

### 실패 시나리오 (선택 후에도 감시)

- **공식 SDK breaking change** — v1.x 는 안정 표명되었으나 spec 자체가 변하면 SDK 도 따라감. extras pin 을 `mcp>=1.12,<2` 로 유지하고 SDK major 업그레이드 시 별도 평가
- **FastMCP API deprecation** — `mcp.server.fastmcp` 가 더 저수준 `mcp.server.lowlevel` 로 이전 가능. spec 추종이 우선이라 따라감

### 출처

- MCP Python SDK: <https://github.com/modelcontextprotocol/python-sdk>
- MCP Streamable HTTP transport (2025-03): <https://modelcontextprotocol.io/specification/2025-03-26/basic/transports>
- 본 프로젝트 검증 (context7 query): SDK v1.12.4 가 stdio / sse / streamable-http 3종 transport 지원 확인

---

## 2. Transport 우선순위

### 조사: MCP 클라이언트별 transport 지원 현황 (2026-04 기준)

| 클라이언트 | stdio | SSE | streamable-http |
|---|---|---|---|
| Claude Desktop | ✅ (only) | ❌ | ❌ |
| Cline (VSCode) | ✅ | ✅ | ✅ |
| Continue.dev | ✅ | ❌ | ⚠️ (실험) |
| Cursor | ✅ | ❌ | ❌ |
| Goose (Block) | ✅ | ✅ | ✅ |
| 자체 에이전트 (Anthropic SDK MCP client) | ✅ | ✅ | ✅ |

### 관찰

1. **stdio 가 100% 호환 분모** — 모든 LLM 호스트 클라이언트가 지원
2. **SSE 는 deprecated 경로** — MCP spec 2025-03 이 streamable-http 로 이전. 신규 구현은 SSE 단독 노출 안 함
3. **streamable-http 는 server-side / 컨테이너 / 다중 클라이언트 시나리오 전용** — 단일 사용자 desktop 통합에는 불필요한 복잡도

### 대안 평가

- **stdio only**: ✅ 단순하지만 컨테이너 / 원격 시나리오 차단
- **streamable-http only**: Claude Desktop 등 주류 클라이언트와 비호환
- **stdio + streamable-http**: ✅ 채택. 1차 출시 stdio, optional streamable-http
- **3종 모두 (stdio + SSE + streamable-http)**: SSE 는 deprecated path — 추가 유지 부담만

### 출처

- MCP Streamable HTTP 도입 PR (spec 2025-03): <https://github.com/modelcontextprotocol/specification/pulls?q=streamable-http>
- Claude Desktop config schema: <https://modelcontextprotocol.io/quickstart/user> (stdio-only 명시)

---

## 3. Handler 동시성 모델

### 핵심 제약: `_Document` 가 `unsendable`

본 프로젝트 [`src/document.rs:13`](../../../src/document.rs#L13):

```rust
#[pyclass(name = "_Document", module = "rhwp._rhwp", unsendable)]
```

PyO3 `unsendable` = **객체가 생성된 thread 외에서 접근 시 runtime panic**. 상류 `DocumentCore` 의 `RefCell` 필드가 `!Sync` 인 데서 유래.

### 조사: FastMCP 의 handler 디스패치

| Handler 유형 | 호출 thread | unsendable Document 호환 |
|---|---|---|
| `def tool(...) -> ...` (sync) | event loop thread | ✅ — 한 thread 안에서 생성·소비 |
| `async def tool(...) -> ...` (async, 순수 async I/O) | event loop thread | ✅ — 같은 thread |
| `async def tool(...) + asyncio.to_thread(rhwp.parse, ...)` | worker thread → event loop thread 회수 | ❌ — **panic** (Document 가 thread 경계 횡단) |
| `async def tool(...) + run_in_executor` | 동일 (위와 동치) | ❌ — panic |

### 본 프로젝트 [CLAUDE.md § 비동기 방향](../../../CLAUDE.md) 의 명시 금지

> **Forbidden pattern**: `asyncio.to_thread(rhwp.parse, path)` — `_Document` is unsendable, the returned Document panics on main-thread access.

### 결정

- **sync handler 강제** — 모든 도구는 `def tool(...)` 패턴
- async handler 도 기술적으로는 가능하나 **handler 본문에서 sync `rhwp.parse()` 만 호출** 하는 경우만 허용 (의미 없음 — 그냥 sync 로 작성)
- `aparse()` 사용은 **handler 외부 / 다른 통합 시나리오** 영역. MCP 의 동시성 단위는 request 1건 = parse 1회 = file I/O 1회 — 충분히 빠르고, async 의 가치가 없음

### 실패 시나리오 (선택 후에도 감시)

- **PyO3 `unsendable` 해제 가능성** — 상류 `edwardkim/rhwp` 가 `RefCell` 을 `RwLock` 등 thread-safe 로 교체하면 `unsendable` 제약 해제 가능. 그 시점에 async handler + thread offload 재평가
- **streamable-http 다중 worker 환경** — uvicorn `--workers N` 으로 process 단위 분리하면 각 process 가 자기 event loop / 자기 Document 인스턴스 → unsendable 무관. 현재 결정에 영향 없음

### 출처

- PyO3 `unsendable` 문서: <https://pyo3.rs/v0.22.0/class.html#customizing-the-class>
- 본 프로젝트 [CLAUDE.md](../../../CLAUDE.md) § Rust + Python 하이브리드 빌드 / § 비동기 방향
- FastMCP sync/async handler 디스패치: 본 프로젝트 검증 (context7 query, 2026-04-28)

---

## 4. 도구 분할 vs 통합

### 옵션 비교

| 패턴 | 예시 | LLM 호출 시 schema |
|---|---|---|
| **도구 분할** (채택) | `extract_text(path)`, `get_ir(path)`, `iter_blocks(path, kind, ...)` | 각 도구별 명시적 schema, 의도 명확 |
| **통합 도구 + operation** | `hwp(path, operation: Literal["text", "ir", "blocks"], ...)` | 단일 schema, operation 별 인자 의미 모호 |

### 조사: 다른 MCP 서버의 도구 설계 패턴

| 서버 | 도구 수 | 패턴 |
|---|---|---|
| `@modelcontextprotocol/server-filesystem` | 11개 (`read_file`, `write_file`, `list_directory`, ...) | 분할 |
| `@modelcontextprotocol/server-github` | 26개 (`create_issue`, `get_pull_request`, `search_code`, ...) | 분할 |
| `@modelcontextprotocol/server-postgres` | 1개 (`query`) | 통합 (단, SQL 자체가 표현력 보유) |
| `@modelcontextprotocol/server-fetch` | 1개 (`fetch`) | 통합 (단, URL 만으로 의도 표현) |

### 관찰

1. **도구 분할이 다수파** — 명사+동사 형태 (`read_file`, `create_issue`) 가 LLM 의도 추론에 유리
2. **통합 도구는 입력이 표현력을 가질 때만 성립** — SQL / URL 처럼 인자 자체가 의도를 담을 수 있는 경우. HWP 도구는 그런 표현력 없음
3. **CLI `rhwp-py` 와 mapping** — `rhwp-py blocks` ↔ `iter_blocks`, `rhwp-py ir` ↔ `get_ir` 처럼 1:1 대응이 사용자 학습 비용 절감

### 결정

- **도구 분할 채택** — 7개 도구 (`parse_hwp_summary`, `extract_text`, `get_ir`, `iter_blocks`, `to_markdown`, `to_html`, `chunks`)
- **CLI 와 1:1 mapping** — 두 표면이 같은 정신 모델 공유

### 실패 시나리오 (선택 후에도 감시)

- **도구 수 폭증** — Phase 4 (역생성) 추가 시 `write_hwp` / `update_paragraph` 등 더 늘어남. MCP 클라이언트의 tool list 한도 (Claude Desktop 권고 ~50개) 와 충돌 시 카테고리별 서버 분리 (`rhwp-mcp-read` / `rhwp-mcp-write`) 검토

### 출처

- MCP 공식 servers 저장소: <https://github.com/modelcontextprotocol/servers>
- Anthropic "Building effective agents": <https://www.anthropic.com/research/building-effective-agents> (도구 분할 / schema 명확성 강조)

---

## 참조

- 짝 페어: [mcp.md](../../roadmap/v0.5.0/mcp.md)
- MCP 공식: <https://modelcontextprotocol.io/>
- MCP Python SDK: <https://github.com/modelcontextprotocol/python-sdk>
- 본 프로젝트 [CLAUDE.md](../../../CLAUDE.md) § Rust + Python 하이브리드 빌드
