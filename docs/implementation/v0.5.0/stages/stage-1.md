---
status: Frozen
description: "v0.5.0 S1 작업 로그 — rhwp.mcp 패키지 + FastMCP 서버 스켈레톤 + 4 도구 (parse_hwp_summary / extract_text / get_ir / iter_blocks) + ADR § 1 SDK 결정 갱신 (공식 mcp SDK → standalone fastmcp v3)"
target: v0.5.0
last_updated: 2026-05-06
---

# Stage S1 — MCP 서버 스켈레톤 (완료)

**작업일**: 2026-05-06
**계획 문서**: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md) §구현 스테이지 분할
**설계 근거**: [design/v0.5.0/mcp-research.md](../../../design/v0.5.0/mcp-research.md)

## 스코프

mcp.md §구현 스테이지 분할 S1 행 정확 매핑:

- `python/rhwp/mcp/` 패키지 신설 (`__init__.py` / `__main__.py` / `server.py` / `tools.py`)
- FastMCP 인스턴스 + 4 도구 등록 (`parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks`)
- stdio transport 만 노출 (streamable-http 는 S4 의 영역)
- `[project.optional-dependencies] mcp` / `mcp-chunks` extras + `[project.scripts] rhwp-mcp = "rhwp.mcp:run"` entry point 등록
- `tests/test_mcp_server.py` 신규 — module-level `pytest.importorskip("fastmcp")` 게이트
- CI `test-without-extras` job: 4 → 5 skip 수 bump (gated 파일 5 개)

S2 (`to_markdown` / `to_html`), S3 (`chunks`), S4 (streamable-http transport), S5 (문서화·검증) 는 본 스테이지 범위 밖.

## S1 진행 중 spec 결정 변경

**ADR § 1 SDK 선택을 in-place 갱신** ([mcp-research.md § 1](../../../design/v0.5.0/mcp-research.md#1-sdk-선택)). spec Draft 라 CONVENTIONS § Frozen 정책 미적용 — Draft 는 자유 갱신 가능.

| 항목 | 갱신 전 | 갱신 후 |
|---|---|---|
| SDK | 공식 `mcp` SDK (FastMCP v1 흡수) | standalone `fastmcp` v3 (jlowin) |
| extras 의존성 | `mcp>=1.12,<2` | `fastmcp>=3,<4` |
| 근거 | "1st-party 유지·spec 추종 보장" | "2026-05 현업 표준 — MCP 서버 약 70% 사용 + v3 의 OAuth / OpenTelemetry / server composition / OpenAPI 통합 / streamable-http 우선" |

**갱신 근거**:

- 공식 `mcp` SDK 안의 FastMCP 는 v1 만 흡수 (2024) — frozen 상태. 추가 framework 기능은 standalone (v2 → v3) 으로 분기 진화
- 2026-02 출시된 fastmcp v3 는 OAuth / OpenTelemetry tracing / server composition / OpenAPI 자동 변환 / streamable-http 우선 등 프로덕션 기능 보유 — v0.5.0 S4 (streamable-http 도입) 및 미래 인증 시나리오 (mcp.md §비목표 의 "v0.8.0+ 재평가") 에 직접 영향
- standalone 패키지가 일 100만 다운로드 / 시장 점유율 약 70% — 도구 호환성 / 문서 / 커뮤니티 ecosystem 의 분모가 더 큼
- 마이그레이션 비용: import 1개, decorator 호출 형태 1개, exception 클래스 분기 (validation → `pydantic.ValidationError`, runtime → `fastmcp.exceptions.ToolError`, unknown → `NotFoundError`), input schema attribute (`inputSchema` → `parameters`) 만 차이

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/mcp/__init__.py` | +32 (신규) | `run()` entry point dispatch — `[mcp]` extras 미설치 시 친절 에러 + exit 2. `rhwp.cli.app()` 와 동일 패턴 (CLI 와 같은 위계) |
| `python/rhwp/mcp/__main__.py` | +6 (신규) | `python -m rhwp.mcp` 폴백 |
| `python/rhwp/mcp/server.py` | +40 (신규) | `build_server()` factory + `run()` (stdio). `from fastmcp import FastMCP`. 도구 등록은 `server.tool(fn)` (decorator 호출 형태) |
| `python/rhwp/mcp/tools.py` | +110 (신규) | 4 sync 도구 함수 본체 + `ParseSummary` Pydantic 모델 + `BlockKind` / `BlockScope` Literal. `fastmcp` import 없음 — 도구는 단독으로 단위 테스트 가능 |
| `tests/test_mcp_server.py` | +258 (신규) | 18 테스트 — 5 클래스 (`TestToolRegistry` / `TestSyncHandler` / 4 smoke / `TestErrorHandling` / `TestPackagingSurface`). file-level `importorskip("fastmcp")` 로 1 skip 기여 |
| `pyproject.toml` | +15 / -0 | `[project.optional-dependencies]` `mcp = ["fastmcp>=3,<4"]` + `mcp-chunks` 추가, `[project.scripts] rhwp-mcp` 추가, `[dependency-groups] testing` 에 `fastmcp>=3,<4` |
| `.github/workflows/ci.yml` | +5 / -3 | `test-without-extras` skip count 4 → 5, pyright list 에 `tests/test_mcp_server.py` 추가 |
| `CLAUDE.md` (= AGENTS.md) | +1 / -1 | gated 파일 카운트 4 → 5 (test_mcp_server.py 추가) |
| `docs/design/v0.5.0/mcp-research.md` | +21 / -16 | § 1 SDK 결정 매트릭스 + 본문 갱신 (공식 mcp SDK → standalone fastmcp v3) |
| `docs/roadmap/v0.5.0/mcp.md` | +12 / -10 | § 의존성 / 배포 / § 결정 사항 row 1 + 6 / AC-1 / AC-9 / AC-11 갱신 |
| `scripts/_doc_lint.py` | +18 / -8 | `is_pre_ga_stage` 면제 분기 — `Frozen + target` 을 `docs/implementation/vX.Y.Z/` 경로에 한해 허용 (CONVENTIONS § 131 정합, S1 § docs-lint policy 갱신 참조) |
| `docs/CONVENTIONS.md` | +2 / -2 | § 필드 schema 의 `ga` / `target` 행에 pre-GA stage 예외 명시 |

## S1 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **SDK 패키지** | `fastmcp>=3,<4` (standalone, jlowin) | ADR § 1 갱신 — 2026-05 현업 표준 + v3 의 프로덕션 기능. 공식 mcp SDK 의 FastMCP v1 은 frozen |
| **`__init__.py` lazy-import 패턴** | `rhwp.cli.app()` 와 동일 패턴 — stdlib `sys` 만 모듈 레벨, `fastmcp` import 는 `run()` 안에서 lazy | CLAUDE.md § Module Structure "`__init__.py` MUST be empty or contain only docstrings" 의 spirit (heavy import 금지) 준수 + entry point 요구 (`rhwp-mcp = "rhwp.mcp:run"`) 양립. CLI 가 검증된 선례 |
| **도구 분리: `tools.py` vs `server.py`** | `tools.py` 는 ``fastmcp`` import 없는 순수 함수. `server.py` 가 `server.tool(fn)` 으로 등록 | 도구 본체를 단위 테스트 시 SDK 무관하게 호출 가능. fastmcp 가 v3 → v4 로 변동해도 `tools.py` 본체는 영향 없음 |
| **`build_server()` factory 분리** | 모듈 레벨 `mcp` 싱글턴 대신 함수 호출로 새 인스턴스 생성 | 테스트가 격리된 instance 로 `list_tools()` / `call_tool()` in-process 호출 가능 — 모듈 import 부수 효과 회피 |
| **`BlockKind` 의 `"all"` sentinel 제거** | `kind: BlockKind \| None = None` (None = 필터 미적용) | LLM JSON Schema enum 에 IR `Block.kind` 에 존재하지 않는 가짜 값 노출 회피. CLI 의 `BlockKindOpt.all` 과는 다른 surface — typer 는 default 가 enum 멤버여야 해서 sentinel 필요했지만 MCP 는 Optional 이 자연스러움 |
| **`server.tool(fn)` (no parens)** | fastmcp v3 권장 형태 | `@mcp.tool` decorator (no parens) 와 같은 신호. v3 가 `server.tool()(fn)` 도 backwards compat 으로 지원하나 v3-native 형태 채택 |
| **에러 surface 검증을 `pytest.raises(...)` 만으로 한정** | 메시지 텍스트 검사 생략 | OS / 로케일 의존성 회피 (Windows CI 매트릭스 매치 불가). AC-3 / AC-4 의 invariant 는 "panic 아님" + "MCP isError=True 응답" — 예외 raise 자체가 in-process 신호. 메시지 검사는 brittle |
| **AC-5 sync 검증 — 등록 시점 walk** | `server.list_tools()` 의 `FunctionTool` 인스턴스 walk + `inspect.iscoroutinefunction(tool.fn)` | 4 함수 하드코딩 대신 등록 도구 전체 자동 커버. S2 (to_markdown/to_html), S3 (chunks) 추가 시에도 동일 invariant 자동 보장 |
| **fastmcp 의존성 ceiling `<4`** | major 단위 변동 흡수 | jlowin 의 v 단위 진화 속도 (v2 → v3 가 1 년) 를 고려해 보수적 ceiling. v4 출시 시점 별도 평가 |
| **ImportError 분류** | `e.name` 이 `rhwp.*` / `rhwp` 시작이면 raise (rhwp 자체 결함), 그 외는 친절 에러 + exit 2 | rhwp 자체 모듈 결함 (예: `_rhwp` 빌드 누락) 의 진단 단서 보존. `rhwp.cli.app()` 와 동일 분기 — fastmcp 든 transitive deps (pydantic-settings / starlette) 든 같은 메시지 |

## 비타협 제약 준수

- **`unsendable` 안전 패턴** — 4 도구 모두 sync 함수, handler 안에서 `rhwp.parse(path)` → 소비 → primitive 반환. `asyncio.to_thread(rhwp.parse, ...)` 패턴 코드 내 부재 (AC-5)
- **Pydantic V2 + `BaseModel`** — `ParseSummary` 가 dataclass 가 아닌 `BaseModel`. `Field(description=...)` 만 사용 (`ge=`/`le=`/`gt=`/`lt=` 부재)
- **`Literal["..."]` enum** — `BlockKind` / `BlockScope` 가 `str` 이 아닌 `Literal` — JSON Schema enum 으로 정확히 출고 (LLM token-level 제약)
- **`from __future__ import annotations` 부재** — Pydantic 런타임 타입 해석 호환
- **`__init__.py` 가 module-level 에서 third-party import 안 함** — `import sys` (stdlib) 만, `fastmcp` 는 함수 안에서만 lazy
- **Python 3.10+ 유니온 표기** (`T | None`) — `Optional[T]` 회피
- **모듈 위치** `python/rhwp/mcp/` (top-level) — `integrations/` 가 아님 (결정 7)

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/ -m "not slow"` | **548 passed, 2 skipped** (v0.4.0 의 530 + S1 신규 18) |
| `uv run pytest tests/test_mcp_server.py -v` | **18 passed** (4 도구 × 평균 2 테스트 + 5 etc.) |
| `uv run ruff check python/rhwp/mcp/ tests/test_mcp_server.py` | clean |
| `uv run pyright python/rhwp/mcp/ tests/test_mcp_server.py` | **0 errors** |
| `uv run pyright tests/type_check_errors.py` | **4 intentional errors** (CI 검증 통과) |
| `cargo clippy --all-targets -- -D warnings` | clean (Rust 미수정) |
| `code-reviewer` fresh-context 검증 | HIGH 2 / MEDIUM 4 / LOW 3 — HIGH 둘 다 반영 (BlockKind sentinel 제거 + sync handler walk), MEDIUM 4 중 3 반영 (AC-4 메시지 검사 제거 / `mcp` ceiling 추가 / `test_init_is_lightweight` 삭제) |

### 테스트 커버리지 (mcp.md §S1 → AC 매핑)

| mcp.md AC | 테스트 |
|---|---|
| AC-1 (extras gate, exit 2) | CI `test-without-extras` job (skip count 5 검증, behavior SSOT) |
| AC-2 (도구 4개 노출) | `TestToolRegistry::test_lists_exactly_four_tools`, `test_iter_blocks_kind_schema_is_enum` (BlockKind enum 정확 매칭) |
| AC-3 (잘못된 enum → isError=True) | `TestErrorHandling::test_iter_blocks_invalid_kind` (`pytest.raises(ValidationError)`) |
| AC-4 (FileNotFound → isError=True) | `TestErrorHandling::test_extract_text_missing_file` (`pytest.raises(ToolError)`) |
| AC-5 (모든 handler sync) | `TestSyncHandler::test_all_registered_tools_are_sync` (등록 도구 walk + `iscoroutinefunction`) |
| AC-9 (pyproject 등록) | `TestPackagingSurface::test_pyproject_declares_fastmcp_extras_and_script` (extras + script tomllib 검증) |
| AC-10 (모듈 위치 top-level) | `TestPackagingSurface::test_module_is_top_level_not_under_integrations`, `test_entry_point_dispatches_to_run` |

S2 / S3 영역의 AC-6 (view 도구) / AC-7 (chunks 도구) / AC-8 (streamable-http) / AC-11 (skip count 5 — CI 측 검증) 는 본 stage 범위 밖.

## 알려진 한계 (S2 이후 처리)

- **`get_ir` 응답 크기** — mcp.md §미확정 이슈. 큰 문서는 IR JSON 이 수 MB 수준이라 MCP `tools/call` 응답 한도 (클라이언트 별 상이) 와 충돌 가능. S5 손 검증 시점에 `--max-bytes` 또는 `Resource` 추상 도입 평가
- **에러 응답 형식 통일** — mcp.md §미확정 이슈. fastmcp v3 가 ValidationError / ToolError / NotFoundError 셋으로 분기 — 통일 정책 (예: 모두 ToolError 로 wrap) 검토는 S2 이후 (도구 surface 가 늘어난 뒤 패턴 정립)
- **AC-1 의 in-process 검증 부재** — 현재 CI `test-without-extras` job 의 skip count 만이 SSOT. `subprocess` 로 fastmcp 차단 환경 시뮬레이션은 가능하나 비용 대비 가치 낮음. `code-reviewer` 가 권고했으나 S5 손 검증 + 실제 사용자 환경 (Claude Desktop 설정 가이드) 검증으로 대체

## docs-lint policy 갱신 (Living-policy migration, S1 부산물)

본 stage 작성 도중 발견된 CONVENTIONS § 131 vs `scripts/_doc_lint.py` 충돌을 옵션 A 로 봉합 — Rust RFC / PEP / ADR 의 editorial vs release 차원 분리 패턴 정합. 변경:

- `scripts/_doc_lint.py` — `is_pre_ga_stage` 면제 분기 신설. `docs/implementation/vX.Y.Z/` 경로 + `target` + `not has_ga` 시 `Frozen + target` 허용
- `docs/CONVENTIONS.md` § 필드 schema — `ga` / `target` 행에 pre-GA stage 예외 명시
- 본 파일이 첫 적용 사례 (`status: Frozen` + `target: v0.5.0`). v0.5.0 GA 시점에 일괄 `target` → `ga` 로 flip

해당 변경은 stage 본문의 immutability 의미를 보존하면서 (Rust RFC 의 RFC text frozen on acceptance 패턴) GA 라벨 부여를 release-시점 administrative metadata 로 분리.

## S2 진입 조건 (인수인계)

S2 는 mcp.md § S2 row 의 view 도구 추가 — `to_markdown` / `to_html`. S1 에서 고정한 계약:

1. **`tools.py` 의 sync-only 패턴** — S2 의 `to_markdown` / `to_html` 도 같은 형태. `HwpDocument.to_markdown()` / `to_html(include_css=...)` 직접 호출 → str 반환
2. **`server.py` 의 `build_server()` factory** — 4 → 6 도구로 늘릴 때 `server.tool(tools.to_markdown)` / `server.tool(tools.to_html)` 추가만
3. **`TestSyncHandler::test_all_registered_tools_are_sync`** — 등록 도구 walk 패턴이 자동 커버 (4 → 6 함수 변경 없음)
4. **`TestToolRegistry::test_lists_exactly_four_tools`** — S2 시점에 4 → 6 으로 카운트 갱신 + 새 도구 이름 set 에 추가. 동일 함수명 변경 (`test_lists_exactly_six_tools`) 검토
5. **mcp.md AC-2 의 도구 카운트** — S1 시점은 "4 개 노출", S2 종료 시 "6 개", S3 종료 시 "7 개". stage 마다 mcp.md AC-2 본문은 그대로 두고 (spec 은 GA 기준 = 7 개) impl-log 에서만 S1/S2/S3 별 진행 카운트를 기록

## 참조

- 상위 설계: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md)
- 결정 사항 증거 (S1 진행 중 갱신): [design/v0.5.0/mcp-research.md](../../../design/v0.5.0/mcp-research.md)
- 외부 참조: [jlowin/fastmcp](https://github.com/jlowin/fastmcp), [공식 mcp SDK](https://github.com/modelcontextprotocol/python-sdk), [MCP spec](https://modelcontextprotocol.io/)
- v0.4.0 선례 (Frozen 패턴): [implementation/v0.4.0/migration.md](../../v0.4.0/migration.md)
- 비동기 안전 패턴 배경: 프로젝트 [CLAUDE.md § Rust + Python 하이브리드 빌드](../../../../CLAUDE.md)
