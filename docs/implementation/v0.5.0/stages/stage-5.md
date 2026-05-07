---
status: Frozen
description: "v0.5.0 S5 작업 로그 — 문서화·검증. README MCP 섹션 / Claude Desktop 등록 예제 / examples/06_mcp_server.py / AC-1~AC-11 sweep. v0.5.0 GA 직전 마지막 stage"
ga: v0.5.0
last_updated: 2026-05-06
---

# Stage S5 — 문서화·검증 (완료)

**작업일**: 2026-05-06
**계획 문서**: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md) §구현 스테이지 분할 S5
**선행 stages**: [stage-1.md](stage-1.md) (서버 스켈레톤) / [stage-2.md](stage-2.md) (view 도구) / [stage-3.md](stage-3.md) (chunks) / [stage-4.md](stage-4.md) (streamable-http transport)

## 스코프

mcp.md §구현 스테이지 분할 S5 행 정확 매핑:

- `README.md` 신설 § "MCP server (`rhwp-mcp`)" — 도구 7 종 표 + 설치 / Claude Desktop 등록 JSON / 클라이언트 호환성 표 + streamable-http 사용 예
- `examples/06_mcp_server.py` 신설 — fastmcp `Client` in-process round-trip 데모, 7 도구 차례로 호출
- `examples/README.md` § 6 추가 + 사전 준비의 `[examples]` extras 한 줄 설명 갱신
- `pyproject.toml` `[examples]` extras 에 `fastmcp>=3,<4` 합집합 추가 — `pip install rhwp-python[examples]` 한 줄로 06 까지 실행 가능
- AC-1 ~ AC-11 모두 충족 sweep — 코드 / 테스트 grep 으로 evidence 수집, stage-1~stage-4 의 검증 누적

`v0.5.0 GA 시점` 의 `mcp.md` / `mcp-research.md` `Draft → Frozen` flip 은 본 stage 범위 밖 — release 절차 (CONVENTIONS § GA 절차) 의 일부.

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `README.md` | +60 / -0 | § "MCP server (`rhwp-mcp`)" 신설 — 짧은 소개 + 설치 (`pip install rhwp-python[mcp]` / `[mcp-chunks]`) + 도구 7 종 표 + Claude Desktop `claude_desktop_config.json` 예 + 클라이언트 호환성 표 (Claude Desktop / Cline / Cursor / Continue.dev / Goose / 자체 에이전트) + streamable-http 예제 |
| `examples/06_mcp_server.py` | +138 (신규) | fastmcp `Client` in-process 데모 — `build_server()` → `Client(server)` 패턴, 7 도구 (parse_hwp_summary / extract_text / get_ir / iter_blocks / to_markdown / to_html / chunks) 차례 호출하며 출력 미리보기. typer 기반 (`--skip-chunks` 옵션) — `[mcp-chunks]` 미설치 환경 호환 |
| `examples/README.md` | +14 / -3 | § 6 신규 row + 사전 준비의 `[examples]` extras 가 v0.5.0+ 에서 fastmcp 합집합이 됨을 명시. § 릴리스 전 검증의 "다섯 → 여섯 스크립트" 갱신 |
| `pyproject.toml` | +2 / -1 | `[examples]` extras 에 `fastmcp>=3,<4` 추가 — examples 우산 의존성 일관 |

`python/rhwp/mcp/` / `tests/test_mcp_server.py` / `docs/roadmap/v0.5.0/mcp.md` / `docs/design/v0.5.0/mcp-research.md` / `docs/CONVENTIONS.md` / `scripts/_doc_lint.py` / `.github/workflows/ci.yml` — **변경 없음** (S5 는 문서 / 예제 신설 only).

## S5 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **README § MCP server 위치** | "rhwp-py CLI" 다음, "성능" 앞 | 동일 위계 (사용자-대면 entry point) — CLI 와 같은 위계로 배치. § Document IR / § LangChain 통합 보다 뒤 (구체 통합 표면이 IR / LangChain 를 전제) |
| **클라이언트 호환성 표 — 5 클라이언트 + 자체 에이전트** | Claude Desktop / Cline / Cursor / Continue.dev / Goose / Anthropic SDK MCP client | mcp-research.md § 2 의 transport 호환성 표를 그대로 README 에 노출 — 사용자가 자신의 환경에서 어느 transport 를 써야 하는지 즉시 판단 가능 |
| **`examples/06_mcp_server.py` — in-process 패턴** | `Client(server)` 직접 wrap (FastMCPTransport) | 외부 subprocess 대신 in-process 가 빠르고 확정적 — 도구 동작 학습 / 데모 목적에 최적. 실제 운영 (subprocess 통합) 가이드는 README + Claude Desktop config 참조 |
| **`--skip-chunks` 옵션** | typer 옵션으로 명시적 분기 | `[mcp]` 만 설치한 사용자 (chunks 의존성 없음) 도 06 예제 실행 가능 — `[mcp-chunks]` 미설치 환경에서 chunks 호출이 ToolError 로 실패하면 사용자가 `--skip-chunks` 로 우회 가능 |
| **`pyproject.toml [examples] extras` 에 fastmcp 합집합** | `typer + langchain-core + langchain-text-splitters + fastmcp` 일괄 | examples 는 "01~06 예제 일괄 실행" 우산 — 사용자가 `pip install rhwp-python[examples]` 한 줄로 모든 예제 실행 가능. v0.5.0+ 부터 fastmcp 추가 |
| **README MCP 도구 표 컬럼 — 도구 / 입력 / 출력 (의존 컬럼 제거)** | spec § 노출 도구 의 4 컬럼 중 "의존" 컬럼만 본문 텍스트로 분리 | README 표는 LLM 사용자 / 일반 개발자 대상 — `[mcp-chunks]` 의존성은 표 위 설치 섹션이 이미 다룸. "의존" 컬럼은 spec 의 mcp.md 가 SSOT 으로 남기고 README 는 간결화 |
| **클라이언트 호환성 표의 streamable-http "⚠️ (실험)" 표시** | Continue.dev 한 곳만 ⚠️, 나머지는 ✅/❌ 명시 | mcp-research.md § 2 표의 그대로 — Continue.dev 가 streamable-http 를 부분 지원이라 사용자 기대치 정확화 |

## 비타협 제약 준수

- **stage 본문의 immutability** — S1 ~ S4 stage 로그 본문 변경 없음. S3 의 "include_furniture 미노출" 결정 reversal 은 git commit + spec mcp.md (Draft) 갱신으로 이미 처리됨 — historical record 보존
- **Draft / Frozen 정책** — mcp.md / mcp-research.md 는 여전히 Draft (target: v0.5.0). v0.5.0 GA 시점 release 절차에서 일괄 Frozen flip
- **examples 디렉토리 패턴** — typer 기반 (다른 예제와 동일), `--help` 노출, `pip install rhwp-python[examples]` 한 줄 설치
- **README 한국어 컨벤션** — 기술 용어 / 식별자 / LLM-facing 만 영어, 본문은 한국어 (글로벌 CLAUDE.md § Communication)
- **모듈 위치** `python/rhwp/mcp/` (top-level) — 변경 없음
- **fastmcp 의존성 ceiling `<4`** — 변경 없음

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/ -m "not slow"` | **569 passed, 2 skipped** (S4 와 동일 — S5 는 코드 / 테스트 변경 없음) |
| `uv run pytest tests/test_mcp_server.py` (slow 포함) | **40 passed** (S4 와 동일) |
| `uv run python examples/06_mcp_server.py` (실제 fixture) | 7 도구 모두 round-trip 성공 — 출력 길이 / 청크 수 합리 |
| `uv run ruff check examples/06_mcp_server.py python/rhwp/mcp/ tests/test_mcp_server.py` | clean |
| `uv run pyright python/rhwp/mcp/ tests/test_mcp_server.py examples/06_mcp_server.py` | **0 errors** |
| `uv run python scripts/lint_docs.py` | exit 0 (README + examples/README + stage-5.md 모두 통과) |
| `uv run python scripts/generate_spec_trace.py --check` | up to date — S5 는 spec marker 추가 없음 |

## AC-1 ~ AC-11 sweep (Evidence 기반)

| AC | Evidence | 위치 |
|---|---|---|
| **AC-1** (extras gate exit 2) | `__init__.py` 의 `raise SystemExit(2) from e` + 친절 메시지 ("rhwp-mcp requires `fastmcp` ...") | [`python/rhwp/mcp/__init__.py`](../../../../python/rhwp/mcp/__init__.py) (S1) + CI `test-without-extras` job (skip count 5) |
| **AC-2** (도구 7 종 노출) | `server.tool(tools.parse_hwp_summary)` 등 7 줄 + `TestToolRegistry::test_lists_exactly_seven_tools` | [`python/rhwp/mcp/server.py`](../../../../python/rhwp/mcp/server.py) (S3) + [`tests/test_mcp_server.py`](../../../../tests/test_mcp_server.py) (S3) |
| **AC-3** (잘못된 enum → isError) | `TestErrorHandling::test_iter_blocks_invalid_kind` (`pytest.raises(ValidationError)`) | tests/test_mcp_server.py (S1) |
| **AC-4** (FileNotFound → isError) | `TestErrorHandling::test_extract_text_missing_file` (`pytest.raises(ToolError)`) | tests/test_mcp_server.py (S1) |
| **AC-5** (handler sync) | `TestSyncHandler::test_all_registered_tools_are_sync` 가 등록된 7 도구 walk + `iscoroutinefunction` | tests/test_mcp_server.py (S1, S3 에서 자동 확장) |
| **AC-6** (view 도구 thin wrapper) | `TestToMarkdown::test_matches_view_api`, `TestToHtml::test_matches_view_api_no_css` / `..._with_css` (byte-equality) | tests/test_mcp_server.py (S2) |
| **AC-7** (chunks extras gate) | `TestChunks::test_missing_extras_raises_tool_error`, `..._does_not_break_other_tools` (sys.modules None mocking) | tests/test_mcp_server.py (S3) |
| **AC-8** (streamable-http) | `TestTransportCli` 9 개 fast 테스트 + `test_streamable_http_real_round_trip` (slow, subprocess + fastmcp Client round-trip) | tests/test_mcp_server.py (S4) |
| **AC-9** (pyproject 등록) | `[project.optional-dependencies] mcp = ["fastmcp>=3,<4"]` + `mcp-chunks` + `[project.scripts] rhwp-mcp = "rhwp.mcp:run"` + `TestPackagingSurface::test_pyproject_declares_fastmcp_extras_and_script` | [`pyproject.toml`](../../../../pyproject.toml) (S1, post-S1 fastmcp migration) |
| **AC-10** (top-level 모듈) | `TestPackagingSurface::test_module_is_top_level_not_under_integrations` + `__init__.py` 가 lazy-import 패턴 (heavy import 부재, CLI 와 동일 위계) | python/rhwp/mcp/ (S1) |
| **AC-11** (skip count 4 → 5) | CI ci.yml `grep -qE '(^|[^0-9])5 skipped([^0-9]|$)'` + AGENTS.md / CLAUDE.md "exactly 5 skipped" + test_mcp_server.py file-level `pytest.importorskip("fastmcp")` | `.github/workflows/ci.yml` + `AGENTS.md` + `CLAUDE.md` (S1, post-S1 fastmcp migration) |

**11 AC 모두 충족** — 11/11. spec § 미확정 이슈 (`get_ir` 응답 크기 / 에러 응답 형식 통일 / Resource 추상 / Prompt 추상 / 클라이언트 호환성) 는 모두 v0.5.0 GA 후 별도 minor 또는 demand-driven 으로 보류 (mcp.md § 미확정 이슈 의 결정 그대로).

## v0.5.0 전체 진행 누적

| Stage | 도구 카운트 | 핵심 산출물 | git commit |
|---|---|---|---|
| S1 | 4 | 서버 스켈레톤 + 코어 도구 (parse_hwp_summary / extract_text / get_ir / iter_blocks) | `1a0111a` |
| S2 | 6 | view 도구 (to_markdown / to_html — v0.4.0 view API thin wrapper) | (S1 + S2 commit) |
| S3 | 7 | chunks 도구 (RAG 청킹, langchain-text-splitters extras gate) — AC-2 GA 기준 충족 | (S3 commit) |
| post-S3 | 7 | `chunks` 에 `include_furniture: bool = False` 추가 (HwpLoader 통과). spec mcp.md (Draft) chunks row 5 파라미터로 갱신 | (post-S3 commit) |
| S4 | 7 | streamable-http transport (`--transport` / `--host` / `--port` argparse + fastmcp v3 dispatch) | (S4 commit) |
| **S5** | **7** | **README MCP 섹션 + examples/06 + AC sweep — v0.5.0 GA 준비 완료** | **(S5 commit)** |

추가로 v0.5.0 stage 사이클에서 발생한 cross-cutting decisions:
- ADR § 1 SDK 결정 갱신 (S1 진행 중) — 공식 `mcp` SDK → standalone `fastmcp` v3 (jlowin). 2026-05 현업 표준 패턴 정합 (mcp-research.md 본문 그대로 갱신)
- docs-lint 정책 갱신 (S1 진행 중) — `Frozen + target` 조합을 `docs/implementation/vX.Y.Z/` pre-GA stage log 에 한해 허용 (옵션 A — Rust RFC / PEP / ADR 의 editorial vs release 차원 분리 패턴)

## 알려진 한계 (v0.5.0 GA 후 처리)

- **`get_ir` 응답 크기** — mcp.md §미확정 이슈. 큰 문서는 IR JSON 이 수 MB 수준이라 MCP `tools/call` 응답 한도 (클라이언트 별 상이) 와 충돌 가능. v0.6.0+ 에서 `--max-bytes` 또는 `Resource` 추상 도입 평가
- **에러 응답 형식 통일** — fastmcp v3 가 ValidationError / ToolError / NotFoundError 셋으로 분기. 통일 정책 (예: 모두 ToolError 로 wrap) 검토는 demand-driven
- **Resource / Prompt 추상 사용 여부** — mcp.md § 미확정 이슈. 차기 minor 의 MCP 확장 spec 에서 평가
- **출력 schema 강타입화 (`ChunkRecord` Pydantic 모델 등)** — code-reviewer S3 LOW-2. iter_blocks / get_ir 도 같은 패턴 (`list[dict[str, Any]]`) — 일관 polish 로 후속 처리
- **uvicorn `--workers N` 등 ASGI 운영 옵션 미노출** — production 배포는 reverse proxy / 컨테이너 / systemd 가 책임지는 가정. fastmcp 의 `uvicorn_config` kwarg 후속 노출 검토 가능
- **다른 MCP 클라이언트 호환성 손 검증** — Cline / Continue.dev / Cursor / Goose 등의 stdio handshake 차이 — README 표는 spec mcp-research § 2 의 사전 조사 기반. 실제 손 검증은 사용자 피드백 / GitHub issue 기반 demand-driven

## v0.5.0 GA 절차 (인계)

본 stage 이후 v0.5.0 GA 까지의 release 절차 (CONVENTIONS § GA 절차):

1. **`Cargo.toml` version bump** — 0.4.0 → 0.5.0 (CLAUDE.md § 버전 관리 의 SSOT)
2. **`mcp.md` / `mcp-research.md` frontmatter flip** — `status: Draft → Frozen`, `target: v0.5.0 → ga: v0.5.0` (CONVENTIONS § GA 절차)
3. **`docs/implementation/v0.5.0/stages/stage-{1..5}.md` frontmatter flip** — `target: v0.5.0 → ga: v0.5.0` 일괄 (post-S1 docs-lint 갱신 정책)
4. **`docs/roadmap/README.md` 인덱스 갱신** — v0.5.0 row 를 Frozen 으로 표시
5. **`CHANGELOG.md` 항목 추가** — v0.5.0 의 변경 요약 + external/rhwp 서브모듈 commit 핀
6. **git tag `v0.5.0`** + GitHub Release 생성 — `publish.yml` 트리거 (Trusted Publisher OIDC)
7. **release 후 손 검증** — 본인의 업무 HWP 파일 3종으로 examples/06 + Claude Desktop 통합 검증

## 참조

- 상위 설계: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md)
- 결정 사항 증거: [design/v0.5.0/mcp-research.md](../../../design/v0.5.0/mcp-research.md)
- 선행 stages: [stage-1.md](stage-1.md), [stage-2.md](stage-2.md), [stage-3.md](stage-3.md), [stage-4.md](stage-4.md)
- README MCP 섹션: [`README.md` § MCP server (`rhwp-mcp`)](../../../../README.md)
- examples: [`examples/README.md`](../../../../examples/README.md), [`examples/06_mcp_server.py`](../../../../examples/06_mcp_server.py)
- MCP 공식: <https://modelcontextprotocol.io/>
- fastmcp v3 (jlowin): <https://github.com/jlowin/fastmcp>
