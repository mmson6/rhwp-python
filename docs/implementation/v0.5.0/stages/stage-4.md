---
status: Frozen
description: "v0.5.0 S4 작업 로그 — streamable-http transport (--transport / --host / --port CLI 옵션, fastmcp v3 의 uvicorn ASGI 분기). stdio 기본 backward-compat 유지, AC-8 충족"
ga: v0.5.0
last_updated: 2026-05-06
---

# Stage S4 — streamable-http transport (완료)

**작업일**: 2026-05-06
**계획 문서**: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md) §구현 스테이지 분할 S4
**선행 stages**: [stage-1.md](stage-1.md) (서버 스켈레톤) / [stage-2.md](stage-2.md) (view 도구) / [stage-3.md](stage-3.md) (chunks 도구)

## 스코프

mcp.md §구현 스테이지 분할 S4 행 정확 매핑:

- `python/rhwp/mcp/server.py` 의 `run()` 에 argparse 추가 — `--transport stdio | streamable-http`, `--host`, `--port` CLI 옵션
- argparse choices / port range / stdio + 명시 host/port 충돌 검증 (fail-fast)
- `tests/test_mcp_server.py` 의 `TestTransportCli` 클래스 신설 (10 테스트 — argparse 7 + dispatch mock 2 + slow smoke 1)
- `pytest.mark.slow` smoke 테스트 — subprocess 로 `rhwp-mcp --transport streamable-http` 실제 기동 후 fastmcp Client 로 round-trip 검증 (3 회 retry / stderr 진단 surface)
- 코어 도구 본체 / 등록 로직 / `__init__.py` lazy-import 패턴 — **변경 없음** (transport 분기는 `run()` 내부, 도구 본체와 직교)

S5 (문서화·검증) 는 본 stage 범위 밖.

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/mcp/server.py` | +73 / -8 | `_build_arg_parser()` (argparse 정의) / `_port_type()` (TCP port [1, 65535] validator) / `run(argv=None)` 에 argparse + dispatch — stdio (인자 없음) vs streamable-http (host/port 전달). stdio + 명시 host/port 조합 시 `parser.error` (보안 사고 회피) |
| `tests/test_mcp_server.py` | +175 / -8 | `TestTransportCli` 신설 — argparse 검증 (default / streamable-http+port / custom host / invalid transport / port out-of-range / stdio+host conflict / stdio+port conflict), dispatch mock (stdio / streamable-http kwargs), `slow` smoke (subprocess + 3-retry round-trip + stderr surface). 모듈 docstring AC 매핑에 AC-8 추가 |
| `docs/traces/coverage.md` | +10 | auto-regen — `v0.5.0/mcp#AC-8` 매핑 10 추가 |

`__init__.py` / `tools.py` / `pyproject.toml` 변경 없음 — transport 추가는 stdio 기본값 보존 + 새 옵션만 더하는 backward-compat 변경.

## S4 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **transport 어휘** | `"stdio"` / `"streamable-http"` | mcp.md §Transport 결정 + ADR § 2 그대로. fastmcp v3 가 4 종 지원 (`stdio`/`http`/`sse`/`streamable-http`) 하지만 `http` 는 `streamable-http` 의 alias 라 노출 어휘 통일, `sse` 는 mcp.md §Transport "비범위" (deprecated 경로) 라 미노출 |
| **`--host` 기본 `127.0.0.1`** | 외부 노출 안 되는 localhost 강제 default | mcp.md §비목표 "인증 / sandboxing 미내장 — 운영자 책임" 정신. 0.0.0.0 같은 와일드카드는 명시적 `--host 0.0.0.0` opt-in 필요 — 사용자가 우발적으로 외부 노출하는 사고 회피 |
| **`--port` 기본 8000** | 임의 값 (uvicorn 컨벤션) | fastmcp 자체 default 도 동일. 사용자가 충돌 회피 시 명시적 지정 — bind 시점 에러도 surface |
| **port range validator (`_port_type`)** | argparse 단계에서 [1, 65535] 강제 (fail-fast) | code-reviewer MEDIUM 1 반영. `--port 99999` / `--port -1` 같은 invalid port 를 bind 시점까지 미루지 않고 argparse 가 즉시 차단. 글로벌 CLAUDE.md "Error Philosophy — Fail-Fast" 정합 |
| **stdio + 명시 `--host` / `--port` → `parser.error`** | silently 무시 안 함 | code-reviewer MEDIUM 2 반영. 사용자가 `rhwp-mcp --host 0.0.0.0 --port 8080` 호출 시 (transport 미지정) stdio 로 기동되며 host/port 가 무시되면 보안 의도 모호 — 외부 노출했다고 믿거나 그 반대 혼란 가능. argparse 가 명시적 에러로 의도 강제 |
| **`run(argv=None)` 시그니처** | 표준 Python CLI entry-point 패턴 | `argv=None` 이면 argparse 가 `sys.argv[1:]` 사용 (default 동작). 명시 list 전달 가능 — 단위 테스트에서 sys.argv 조작 없이 dispatch 검증 |
| **slow smoke 분리** | `pytest.mark.slow` 마커 | mcp.md §CI "streamable-http smoke 는 별도 slow 마커 — 매 PR 미실행". CI `test-slow` 잡에서만 실행. 매 PR 가 부담 없이 fast 단위 테스트 실행 + slow 통합 검증은 별도 |
| **smoke retry / stderr capture** | 3 회 retry + stderr capture + early-exit 진단 | code-reviewer HIGH 1/2 반영. port bind/close 사이 TOCTOU race 가능성을 retry 로 완화, `stderr=subprocess.PIPE` 로 uvicorn import error / port collision 등을 AssertionError 메시지에 surface — CI flake 디버깅 가능성 보존 |
| **smoke sentinel 검증** | `len(names) >= 7` + `"extract_text" / "iter_blocks" in names` | code-reviewer MEDIUM 4 반영. AC-8 의 invariant 는 "round-trip 성공" 이지 "정확 7 도구" 가 아님 (도구 카운트는 AC-2 책임). 도구 set equality 매칭은 미래 도구 추가/제거 시 AC-8 smoke 가 잘못된 회귀 신호 발생 |

## 비타협 제약 준수

- **stdio backward-compat** — 인자 없는 `rhwp-mcp` 호출은 S1~S3 와 동일하게 stdio 로 기동. Claude Desktop / Cline 등 기존 통합에 영향 없음 (`test_argparse_default_transport_stdio`, `test_run_dispatch_stdio` 검증)
- **`unsendable` 안전 패턴** — transport 변경은 `FastMCP.run()` 의 분기일 뿐 도구 본체 변경 없음. `TestSyncHandler::test_all_registered_tools_are_sync` 가 7 도구 walk 그대로
- **`__init__.py` lazy-import** — 변경 없음. argparse 는 stdlib 라 server.py 모듈 레벨 import 무방
- **모듈 위치** `python/rhwp/mcp/` (top-level) — 변경 없음
- **fastmcp v3 의존성 ceiling `<4`** — 변경 없음. `run_http_async(host, port, ...)` 시그니처는 fastmcp 3.2.4 검증

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/ -m "not slow"` | **569 passed, 2 skipped** (S3+post-S3 560 + S4 신규 9) |
| `uv run pytest tests/test_mcp_server.py -m slow` | **1 passed** (`test_streamable_http_real_round_trip` ~1.7s) |
| `uv run pytest tests/test_mcp_server.py` (slow 포함) | **40 passed** (9 fast S4 + 1 slow + 30 prior) |
| `uv run ruff check python/rhwp/mcp/ tests/test_mcp_server.py` | clean |
| `uv run pyright python/rhwp/mcp/ tests/test_mcp_server.py` | **0 errors** |
| `uv run python scripts/lint_docs.py` | exit 0 |
| `uv run python scripts/generate_spec_trace.py --check` | up to date — 18 AC 매핑 (S1 7 + S2 3 + S3 2 + post-S3 0 + S4 신규 6 spec-marked tests · 4 LOW-test 더한 총 10 in coverage) |
| `code-reviewer` fresh-context 검증 | HIGH 2 / MEDIUM 4 / LOW 3 — HIGH 둘 + MEDIUM 1/2/4 반영, MEDIUM 3 (signature drift assertion) / LOW 전부 marginal 이라 보류 |

### 테스트 커버리지 (mcp.md §S4 → AC 매핑)

| mcp.md AC | 테스트 |
|---|---|
| AC-8 (--transport streamable-http --port N round-trip) | `TestTransportCli::test_argparse_default_transport_stdio`, `..._streamable_http_with_port`, `..._custom_host`, `..._invalid_transport_exits`, `..._port_out_of_range_exits`, `test_run_stdio_with_non_default_host_exits`, `test_run_stdio_with_non_default_port_exits`, `test_run_dispatch_stdio`, `test_run_dispatch_streamable_http`, `test_streamable_http_real_round_trip` (slow) |

S1 / S2 / S3 의 AC-2 / AC-3 / AC-4 / AC-5 / AC-6 / AC-7 / AC-9 / AC-10 매핑 그대로 유지 — `TestSyncHandler` 가 7 도구 walk, packaging 검증은 transport 와 독립.

## 알려진 한계 (S5 이후 처리)

- **`mode` 어휘에 `"sse"` 미노출** — fastmcp v3 가 SSE transport 도 지원하나 mcp.md §Transport "SSE deprecated" 결정으로 비범위. 사용자 요구가 발생하면 별도 spec 으로 재평가
- **인증 / TLS / sandboxing 미내장** — mcp.md §비목표 결정 그대로. streamable-http 운영자가 reverse proxy (Caddy / Nginx) 로 책임. 라이브러리 레이어가 부분적 보호 노출 시 오해 유발
- **Windows 의 subprocess terminate 정합성** — slow smoke 가 `start_new_session=True` 미사용 — Windows / 신호 처리 환경에서 자식의 자식 (uvicorn worker) 까지 도달 안 할 수 있음. 현재 darwin / linux CI 에서만 실행이라 영향 없으나, Windows 매트릭스 추가 시 재평가
- **`signature drift assertion` 부재** — code-reviewer MEDIUM 3. fastmcp v3 → v4 가 `run` 시그니처 바꾸면 dispatch mock 이 silently 통과. 현재 `mcp>=3,<4` ceiling 으로 v3 안에서는 안전, v4 이전 시 dispatch 테스트 갱신 필수
- **uvicorn `--workers N` 등 ASGI 운영 옵션 미노출** — production 배포는 reverse proxy 위에 컨테이너 / systemd 가 책임지는 가정. fastmcp 의 `uvicorn_config` kwarg 를 `--uvicorn-config-path` 같은 파일 기반으로 후속 노출 검토 가능

## S5 진입 조건 (인수인계)

S5 는 **문서화·검증** — README MCP 섹션 / Claude Desktop 등록 예제 / 실제 LLM 클라이언트 손 검증. S1~S4 에서 고정한 계약:

1. **stdio 기동 명령** — `rhwp-mcp` (인자 없음). Claude Desktop `claude_desktop_config.json` 에 `{"command": "rhwp-mcp"}` 등록 가능
2. **streamable-http 기동 명령** — `rhwp-mcp --transport streamable-http --port 8000` (호스트는 `--host 0.0.0.0` opt-in)
3. **`pip install rhwp-python[mcp]`** — fastmcp 만 설치, chunks 외 6 도구 사용 가능. **`pip install rhwp-python[mcp-chunks]`** — chunks 까지
4. **README MCP 섹션** — 도구 7 종 표 + 사용 예제 + Claude Desktop 등록 JSON 스니펫 + Cursor / Cline 호환성 표
5. **examples/06_mcp_server.py** (선택) — fastmcp Client 로 in-process round-trip 예제 — 사용자가 도구 호출 패턴 학습용
6. **mcp.md 의 AC-1 ~ AC-11 모두 충족 검증** — S5 종료 시점에 spec 의 미확정 이슈 (get_ir 응답 크기 / 에러 응답 형식 통일 / Resource 추상 / Prompt 추상 / 클라이언트 호환성) 손 검증 결과 정리
7. **mcp.md / mcp-research.md frontmatter `Draft → Frozen` flip** — v0.5.0 GA 시점에 `target` → `ga` 일괄 전환 (CONVENTIONS § 219 ~ 223 의 GA 절차)

## 참조

- 상위 설계: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md)
- 결정 사항 증거: [design/v0.5.0/mcp-research.md](../../../design/v0.5.0/mcp-research.md)
- 선행 stages: [stage-1.md](stage-1.md), [stage-2.md](stage-2.md), [stage-3.md](stage-3.md)
- fastmcp v3 transport API: [`fastmcp.FastMCP.run`](https://github.com/jlowin/fastmcp) — `transport: stdio | http | sse | streamable-http`
- streamable-http 표준: [MCP spec 2025-03 transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
