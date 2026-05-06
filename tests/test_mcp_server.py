"""rhwp.mcp fastmcp 서버 단위 테스트 (S1 + S2 + S3 + S4).

``fastmcp`` (``[mcp]`` extras) 미설치 환경에서는 file-level ``importorskip`` 로
전체 skip — CI ``test-without-extras`` 잡이 카운트 검증 (AC-1).

``chunks`` 도구의 smoke 테스트는 메서드 레벨 ``importorskip("langchain_text_splitters")``
로 게이트 — 본 파일은 fastmcp 만 file-level gate, langchain 미설치 환경에서는
chunks smoke 만 개별 skip (file-level skip 카운트 영향 없음).

인수조건 매핑:

- AC-2  (도구 7 개 노출 — S1 코어 4 + S2 view 2 + S3 chunks 1) → ``TestToolRegistry``
- AC-3  (잘못된 enum → isError=True)                          → ``TestErrorHandling``
- AC-4  (FileNotFound → isError=True)                         → ``TestErrorHandling``
- AC-5  (모든 handler sync 함수)                              → ``TestSyncHandler``
- AC-6  (view 도구가 v0.4.0 view API thin wrapper)            → ``TestToMarkdown`` / ``TestToHtml``
- AC-7  (chunks extras-gate 런타임 + 다른 도구 영향 없음)     → ``TestChunks``
- AC-8  (--transport streamable-http --port N CLI 기동)       → ``TestTransportCli``
- AC-9  (pyproject 등록)                                      → ``TestPackagingSurface``
- AC-10 (모듈 위치)                                           → ``TestPackagingSurface``
"""

from pathlib import Path

import pytest

# ^ extras 미설치 환경에서 file 전체 skip — CI test-without-extras 가 카운트 검증
pytest.importorskip("fastmcp")

import asyncio  # noqa: E402
import importlib  # noqa: E402
import inspect  # noqa: E402

import rhwp  # noqa: E402
from fastmcp.exceptions import NotFoundError, ToolError  # noqa: E402
from fastmcp.tools.function_tool import FunctionTool  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from rhwp.mcp import tools  # noqa: E402
from rhwp.mcp.server import build_server  # noqa: E402

pytestmark = pytest.mark.spec("v0.5.0/mcp")


# ------------------------------------------------------------------ AC-2
class TestToolRegistry:
    """도구 등록 (S1 코어 4 + S2 view 2 + S3 chunks 1 = 7 개, GA 기준)."""

    @pytest.mark.spec("v0.5.0/mcp#AC-2")
    def test_lists_exactly_seven_tools(self) -> None:
        server = build_server()
        names = {t.name for t in asyncio.run(server.list_tools())}
        assert names == {
            "parse_hwp_summary",
            "extract_text",
            "get_ir",
            "iter_blocks",
            "to_markdown",
            "to_html",
            "chunks",
        }

    def test_each_tool_has_description(self) -> None:
        server = build_server()
        for tool in asyncio.run(server.list_tools()):
            assert tool.description and tool.description.strip(), (
                f"{tool.name} has empty description"
            )

    def test_iter_blocks_kind_schema_is_enum(self) -> None:
        """LLM 이 enum 어휘를 정확히 사용하도록 ``kind`` 는 JSON Schema enum 으로 노출.

        IR ``Block.kind`` Literal 과 1:1 — "all" sentinel 제외 (filter 미적용은
        ``kind=null`` / 미지정으로 표현).
        """
        server = build_server()
        iter_blocks_tool = next(
            t for t in asyncio.run(server.list_tools()) if t.name == "iter_blocks"
        )
        # ^ fastmcp v3 는 input schema 를 ``Tool.parameters`` 로 노출 (공식 mcp SDK 의
        #   ``inputSchema`` 와 다른 attribute 명).
        kind_field = iter_blocks_tool.parameters["properties"]["kind"]
        # ^ ``kind: BlockKind | None = None`` → JSON Schema 는 anyOf [enum, null]
        kind_enum = next(sub["enum"] for sub in kind_field["anyOf"] if sub.get("type") == "string")
        assert set(kind_enum) == {
            "paragraph",
            "table",
            "picture",
            "formula",
            "footnote",
            "endnote",
            "list_item",
            "caption",
            "toc",
            "field",
        }
        assert "all" not in kind_enum, "kind enum must not include 'all' sentinel"

    def test_iter_blocks_scope_schema_is_enum(self) -> None:
        server = build_server()
        iter_blocks_tool = next(
            t for t in asyncio.run(server.list_tools()) if t.name == "iter_blocks"
        )
        scope_field = iter_blocks_tool.parameters["properties"]["scope"]
        assert "enum" in scope_field
        assert set(scope_field["enum"]) == {"body", "furniture", "all"}


# ------------------------------------------------------------------ AC-5
class TestSyncHandler:
    """모든 도구 handler 가 sync 함수 (``async def`` 아님) — ``unsendable`` 안전.

    AC-5 의 핵심 invariant. async + ``asyncio.to_thread(rhwp.parse, ...)`` 패턴은
    Document 가 thread 경계를 넘어가 panic. 향후 도구를 ``server.tool()`` 로
    추가할 때도 동일 invariant 가 유지되도록 등록된 모든 도구를 walk 한다.
    """

    @pytest.mark.spec("v0.5.0/mcp#AC-5")
    def test_all_registered_tools_are_sync(self) -> None:
        """fastmcp 가 등록한 모든 ``FunctionTool.fn`` 이 coroutine 이 아님.

        ``server.list_tools()`` 는 ``Tool`` 베이스 시퀀스를 반환하며, ``@server.tool``
        로 등록된 도구는 ``FunctionTool`` 서브타입 — ``.fn`` 속성이 원본 함수.
        새 도구 추가 시에도 자동 커버 (특정 4 함수 하드코딩이 아님). 향후
        proxied / transformed 도구 (FunctionTool 가 아닌 서브타입) 는 본 invariant
        의 대상이 아니라 isinstance 체크로 분리.
        """
        server = build_server()
        registered_tools = asyncio.run(server.list_tools())
        function_tools = [t for t in registered_tools if isinstance(t, FunctionTool)]
        assert function_tools, "expected at least one FunctionTool registered (S1: 4)"
        for tool in function_tools:
            assert not inspect.iscoroutinefunction(tool.fn), (
                f"{tool.name} must be sync — async + to_thread(rhwp.parse, ...) "
                "panics with unsendable Document"
            )


# ------------------------------------------------------------------ 정상 호출 (smoke)
class TestParseHwpSummary:
    def test_returns_counts_matching_doc(self, hwp_sample: Path) -> None:
        result = tools.parse_hwp_summary(str(hwp_sample))
        doc = rhwp.parse(str(hwp_sample))
        assert result.sections == doc.section_count
        assert result.paragraphs == doc.paragraph_count
        assert result.pages == doc.page_count
        assert result.rhwp_core_version == rhwp.rhwp_core_version()


class TestExtractText:
    def test_returns_string(self, hwp_sample: Path) -> None:
        result = tools.extract_text(str(hwp_sample))
        assert isinstance(result, str)
        assert result, "extract_text must yield non-empty text for fixture"


class TestGetIr:
    def test_returns_dict_with_schema_envelope(self, hwp_sample: Path) -> None:
        result = tools.get_ir(str(hwp_sample))
        assert isinstance(result, dict)
        assert result["schema_name"] == "HwpDocument"
        assert "schema_version" in result
        assert "body" in result


class TestToMarkdown:
    """AC-6 — to_markdown 가 v0.4.0 ``HwpDocument.to_markdown()`` 위 thin wrapper."""

    @pytest.mark.spec("v0.5.0/mcp#AC-6")
    def test_matches_view_api(self, hwp_sample: Path) -> None:
        """도구 출력이 ``HwpDocument.to_markdown()`` 직접 호출과 byte-equal."""
        tool_output = tools.to_markdown(str(hwp_sample))
        view_output = rhwp.parse(str(hwp_sample)).to_ir().to_markdown()
        assert tool_output == view_output

    def test_returns_non_empty_string(self, hwp_sample: Path) -> None:
        result = tools.to_markdown(str(hwp_sample))
        assert isinstance(result, str)
        assert result.strip(), "to_markdown must yield non-empty markdown for fixture"


class TestToHtml:
    """AC-6 — to_html 가 v0.4.0 ``HwpDocument.to_html()`` 위 thin wrapper."""

    @pytest.mark.spec("v0.5.0/mcp#AC-6")
    def test_matches_view_api_no_css(self, hwp_sample: Path) -> None:
        """기본 ``include_css=False`` 가 ``HwpDocument.to_html()`` 와 byte-equal."""
        tool_output = tools.to_html(str(hwp_sample))
        view_output = rhwp.parse(str(hwp_sample)).to_ir().to_html(include_css=False)
        assert tool_output == view_output

    @pytest.mark.spec("v0.5.0/mcp#AC-6")
    def test_matches_view_api_with_css(self, hwp_sample: Path) -> None:
        """``include_css=True`` 가 ``HwpDocument.to_html(include_css=True)`` 와 byte-equal."""
        tool_output = tools.to_html(str(hwp_sample), include_css=True)
        view_output = rhwp.parse(str(hwp_sample)).to_ir().to_html(include_css=True)
        assert tool_output == view_output

    def test_returns_html5_document(self, hwp_sample: Path) -> None:
        result = tools.to_html(str(hwp_sample))
        assert result.startswith("<!DOCTYPE html>") or result.lstrip().startswith("<!DOCTYPE")


class TestIterBlocks:
    def test_default_returns_dicts(self, hwp_sample: Path) -> None:
        result = tools.iter_blocks(str(hwp_sample))
        assert isinstance(result, list)
        assert all(isinstance(b, dict) for b in result)
        assert all("kind" in b for b in result)

    def test_kind_filter_paragraph(self, hwp_sample: Path) -> None:
        # ^ kind=None (또는 미지정) 이면 필터 미적용 — IR 의 모든 종류 yield
        all_blocks = tools.iter_blocks(str(hwp_sample), kind=None)
        para_blocks = tools.iter_blocks(str(hwp_sample), kind="paragraph")
        assert all(b["kind"] == "paragraph" for b in para_blocks)
        assert len(para_blocks) <= len(all_blocks)

    def test_limit_truncates(self, hwp_sample: Path) -> None:
        result = tools.iter_blocks(str(hwp_sample), limit=3)
        assert len(result) <= 3

    def test_scope_furniture_subset(self, hwp_sample: Path) -> None:
        body_blocks = tools.iter_blocks(str(hwp_sample), scope="body")
        all_blocks = tools.iter_blocks(str(hwp_sample), scope="all")
        # ^ scope="all" = body + furniture, scope="body" 는 부분집합
        assert len(all_blocks) >= len(body_blocks)


# ------------------------------------------------------------------ AC-7
class TestChunks:
    """RAG 청킹 도구 — 런타임 langchain-text-splitters extras gate.

    AC-7: ``langchain-text-splitters`` 미설치 시 chunks 호출만 ``ToolError``
    (= MCP isError=True), 다른 6 도구 / 서버 기동은 정상.

    smoke 테스트는 langchain 이 설치된 환경에서만 실행 (메서드별 importorskip);
    AC-7 의 missing-extras 동작은 ``sys.modules`` mocking 으로 검증해 langchain
    설치 여부와 무관하게 실행.
    """

    def test_default_paragraph_mode(self, hwp_sample: Path) -> None:
        pytest.importorskip("langchain_text_splitters")
        result = tools.chunks(str(hwp_sample))
        assert isinstance(result, list)
        assert result, "chunks must yield at least one chunk for fixture"
        for d in result:
            assert isinstance(d, dict)
            assert "page_content" in d
            assert "metadata" in d
            assert isinstance(d["page_content"], str)
            assert isinstance(d["metadata"], dict)

    def test_modes_all_supported(self, hwp_sample: Path) -> None:
        pytest.importorskip("langchain_text_splitters")
        for mode in ("single", "paragraph", "ir-blocks"):
            result = tools.chunks(str(hwp_sample), mode=mode)  # type: ignore[arg-type]
            assert isinstance(result, list)
            assert result, f"mode={mode!r} produced empty list — fixture regression"

    def test_size_overlap_pass_through(self, hwp_sample: Path) -> None:
        """``size`` / ``overlap`` 이 RecursiveCharacterTextSplitter 로 정상 전달."""
        pytest.importorskip("langchain_text_splitters")
        small = tools.chunks(str(hwp_sample), size=100, overlap=10)
        large = tools.chunks(str(hwp_sample), size=2000, overlap=100)
        # ^ 작은 청크 사이즈가 더 많은 청크를 생성 (또는 같음 — 짧은 문서 한계)
        assert len(small) >= len(large)

    def test_include_furniture_appends_furniture_chunks(self, hwp_sample: Path) -> None:
        """``mode="ir-blocks"`` + ``include_furniture=True`` 가 furniture chunked Document 추가."""
        pytest.importorskip("langchain_text_splitters")
        body_only = tools.chunks(str(hwp_sample), mode="ir-blocks", include_furniture=False)
        with_furniture = tools.chunks(str(hwp_sample), mode="ir-blocks", include_furniture=True)
        # ^ furniture 가 추가되므로 청크 수가 증가하거나 같음 (샘플에 furniture 가 없으면 같음)
        assert len(with_furniture) >= len(body_only)
        # ^ aift.hwp 샘플은 page_headers 를 보유 —
        #   한 개 이상 추가 청크가 ``scope="furniture"`` 메타로 yield
        furniture_chunks = [c for c in with_furniture if c["metadata"].get("scope") == "furniture"]
        assert furniture_chunks, (
            "aift.hwp 는 page_headers 를 보유 — include_furniture=True 가 "
            "'scope=furniture' 메타로 청크를 yield 해야 함"
        )

    def test_include_furniture_ignored_outside_ir_blocks(self, hwp_sample: Path) -> None:
        """``mode="single"`` / ``"paragraph"`` 에서 ``include_furniture`` 는 silently 무시."""
        pytest.importorskip("langchain_text_splitters")
        for mode in ("single", "paragraph"):
            without = tools.chunks(str(hwp_sample), mode=mode)  # type: ignore[arg-type]
            with_flag = tools.chunks(
                str(hwp_sample),
                mode=mode,
                include_furniture=True,  # type: ignore[arg-type]
            )
            # ^ ir-blocks 외 모드에서는 HwpLoader 가 include_furniture 를 무시 — 결과 동일
            assert len(without) == len(with_flag), (
                f"mode={mode!r} should ignore include_furniture (HwpLoader 동일 의미)"
            )

    @pytest.mark.spec("v0.5.0/mcp#AC-7")
    def test_missing_extras_raises_tool_error(
        self, hwp_sample: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """langchain-text-splitters 미설치 시 chunks 호출은 panic 아닌 ToolError."""
        import sys

        # ^ sys.modules 에 None 을 박으면 Python 이 ImportError 를 raise — 실제
        #   미설치 환경 시뮬레이션. monkeypatch 가 테스트 종료 시 자동 복원.
        monkeypatch.setitem(sys.modules, "langchain_text_splitters", None)
        server = build_server()
        with pytest.raises(ToolError):
            asyncio.run(server.call_tool("chunks", {"path": str(hwp_sample)}))

    @pytest.mark.spec("v0.5.0/mcp#AC-7")
    def test_missing_extras_does_not_break_other_tools(
        self, hwp_sample: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """langchain-text-splitters 미설치여도 다른 6 도구 + 서버 기동은 정상."""
        import sys

        monkeypatch.setitem(sys.modules, "langchain_text_splitters", None)
        server = build_server()
        # ^ 서버 build 는 등록만 (lazy import 가 아직 안 일어남) — 정상
        names = {t.name for t in asyncio.run(server.list_tools())}
        assert len(names) == 7
        # ^ 다른 도구 (extract_text) 호출이 langchain 의존성과 무관하게 동작
        result = asyncio.run(server.call_tool("extract_text", {"path": str(hwp_sample)}))
        assert result is not None


# ------------------------------------------------------------------ AC-3 / AC-4
class TestErrorHandling:
    """입력 오류 / 런타임 오류 → 예외 raise (panic 아님).

    fastmcp v3 의 in-process ``call_tool`` 은:

    - **입력 schema 위반** (Pydantic) → ``pydantic.ValidationError``
    - **도구 본체 런타임 오류** → ``fastmcp.exceptions.ToolError``
    - **알 수 없는 도구 이름** → ``fastmcp.exceptions.NotFoundError``

    셋 다 panic 이 아닌 일반 Python 예외이며, stdio transport 경로에서는 모두
    MCP ``CallToolResult(isError=True, content=[...])`` JSON 응답으로 직렬화된다.
    AC-3 / AC-4 의 invariant ("panic 아님 + isError=True 응답") 가 만족된다.
    """

    @pytest.mark.spec("v0.5.0/mcp#AC-4")
    def test_extract_text_missing_file(self) -> None:
        """존재하지 않는 path → ``ToolError`` (panic 아님)."""
        server = build_server()
        with pytest.raises(ToolError):
            asyncio.run(server.call_tool("extract_text", {"path": "nonexistent_fixture.hwp"}))

    @pytest.mark.spec("v0.5.0/mcp#AC-3")
    def test_iter_blocks_invalid_kind(self, hwp_sample: Path) -> None:
        """잘못된 enum 값 → ``pydantic.ValidationError`` (panic 아님)."""
        server = build_server()
        with pytest.raises(ValidationError):
            asyncio.run(
                server.call_tool(
                    "iter_blocks",
                    {"path": str(hwp_sample), "kind": "not_a_real_kind"},
                )
            )

    def test_unknown_tool_name(self) -> None:
        server = build_server()
        with pytest.raises(NotFoundError, match="(?i)unknown tool"):
            asyncio.run(server.call_tool("does_not_exist", {}))


# ------------------------------------------------------------------ AC-8
class TestTransportCli:
    """``rhwp-mcp`` CLI 의 transport / host / port 옵션 — argparse + dispatch.

    실제 stdio JSON-RPC 또는 uvicorn ASGI 기동은 blocking 이라 ``slow`` 마커가
    필요한 별도 통합 smoke 테스트로 분리. 본 클래스는 argparse 와 ``server.run``
    로의 dispatch 호출 인자를 mock 으로 검증해 빠르게 회귀 검출.
    """

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_argparse_default_transport_stdio(self) -> None:
        """인자 없으면 ``transport="stdio"`` 가 기본값."""
        from rhwp.mcp.server import _build_arg_parser

        args = _build_arg_parser().parse_args([])
        assert args.transport == "stdio"

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_argparse_streamable_http_with_port(self) -> None:
        from rhwp.mcp.server import _build_arg_parser

        args = _build_arg_parser().parse_args(["--transport", "streamable-http", "--port", "9000"])
        assert args.transport == "streamable-http"
        assert args.port == 9000
        assert args.host == "127.0.0.1", "기본 host 는 localhost (외부 노출 회피)"

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_argparse_custom_host(self) -> None:
        from rhwp.mcp.server import _build_arg_parser

        args = _build_arg_parser().parse_args(
            ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080"]
        )
        assert args.host == "0.0.0.0"

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_argparse_invalid_transport_exits(self) -> None:
        """argparse choices 가 미허용 transport 를 SystemExit(2) 로 차단."""
        from rhwp.mcp.server import _build_arg_parser

        with pytest.raises(SystemExit):
            _build_arg_parser().parse_args(["--transport", "websocket"])

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_argparse_port_out_of_range_exits(self) -> None:
        """port 가 [1, 65535] 범위 밖이면 argparse 단계에서 차단 (fail-fast)."""
        from rhwp.mcp.server import _build_arg_parser

        for invalid in ["0", "65536", "99999", "-1", "abc"]:
            with pytest.raises(SystemExit):
                _build_arg_parser().parse_args(
                    ["--transport", "streamable-http", "--port", invalid]
                )

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_run_stdio_with_non_default_host_exits(self) -> None:
        """stdio + 명시적 ``--host`` 는 사용자 의도 모호 — SystemExit (보안 사고 회피)."""
        from rhwp.mcp import server as server_mod

        with pytest.raises(SystemExit):
            server_mod.run(["--host", "0.0.0.0"])

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_run_stdio_with_non_default_port_exits(self) -> None:
        """stdio + 명시적 ``--port`` 도 SystemExit (silent ignore 회피)."""
        from rhwp.mcp import server as server_mod

        with pytest.raises(SystemExit):
            server_mod.run(["--port", "9000"])

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_run_dispatch_stdio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``run([])`` 가 ``server.run()`` (stdio, 인자 없음) 호출."""
        from fastmcp import FastMCP
        from rhwp.mcp import server as server_mod

        captured: dict[str, object] = {}

        def fake_run(self: FastMCP, *args: object, **kwargs: object) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

        monkeypatch.setattr(FastMCP, "run", fake_run)
        server_mod.run([])
        assert captured["args"] == ()
        assert captured["kwargs"] == {}

    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_run_dispatch_streamable_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``run(["--transport", "streamable-http", ...])`` → ``server.run(transport=...)``."""
        from fastmcp import FastMCP
        from rhwp.mcp import server as server_mod

        captured: dict[str, object] = {}

        def fake_run(self: FastMCP, *args: object, **kwargs: object) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

        monkeypatch.setattr(FastMCP, "run", fake_run)
        server_mod.run(["--transport", "streamable-http", "--host", "127.0.0.1", "--port", "9001"])
        # ^ 명시적 host / port 가 server.run kwargs 로 전달
        assert captured["kwargs"] == {
            "transport": "streamable-http",
            "host": "127.0.0.1",
            "port": 9001,
        }

    @pytest.mark.slow
    @pytest.mark.spec("v0.5.0/mcp#AC-8")
    def test_streamable_http_real_round_trip(self) -> None:
        """실제 ``rhwp-mcp --transport streamable-http`` subprocess 기동 후 MCP 핸드셰이크.

        ``slow`` 마커 — 매 PR 에는 미실행, ``test-slow`` 잡에서만 실행 (mcp.md § CI).
        uvicorn ASGI 가 실제로 listen 하고 fastmcp Client 가 streamable-http 로
        ``initialize`` + ``list_tools`` round-trip 을 성공함을 검증.

        AC-8 의 invariant 는 "round-trip 성공" 이지 "도구 카운트 정확 매칭" 이 아님 —
        7-도구 set equality 대신 sentinel 검증 (S1+ 도구 추가/제거 회귀에서 본 테스트
        깨지지 않음). 도구 카운트는 AC-2 책임 (별도 테스트).
        """
        import asyncio
        import socket
        import subprocess
        import sys
        import time

        # ^ TOCTOU port race 완화: bind 0 / close / subprocess bind 사이 race 가능 —
        #   3 회 retry 로 병렬 CI / heavy load 환경의 flake 방어.
        last_error: BaseException | None = None
        for attempt in range(3):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]

            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "rhwp.mcp",
                    "--transport",
                    "streamable-http",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                # ^ stderr capture — listen 실패 시 uvicorn 진단 메시지를 AssertionError 에 surface
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                # ^ uvicorn 기동 대기 — port listen 될 때까지 polling (max 10s)
                deadline = time.monotonic() + 10
                listening = False
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        # ^ subprocess 가 일찍 죽음 — port collision / import error 등.
                        #   stderr 캡처를 AssertionError 에 surface 후 다음 retry.
                        stderr_bytes = proc.stderr.read() if proc.stderr else b""
                        stderr_text = stderr_bytes.decode(errors="replace")
                        last_error = AssertionError(
                            f"rhwp-mcp subprocess exited early "
                            f"(returncode={proc.returncode}, port={port}, "
                            f"attempt={attempt + 1}/3). stderr:\n{stderr_text}"
                        )
                        break
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                            listening = True
                            break
                    except OSError:
                        time.sleep(0.1)
                if not listening:
                    if last_error is None:
                        last_error = AssertionError(
                            f"rhwp-mcp did not listen on port {port} "
                            f"within deadline (attempt {attempt + 1}/3)"
                        )
                    continue

                from fastmcp.client import Client

                async def round_trip(p: int = port) -> set[str]:
                    async with Client(f"http://127.0.0.1:{p}/mcp/") as client:
                        tools_list = await client.list_tools()
                        return {t.name for t in tools_list}

                names = asyncio.run(round_trip())
                # ^ AC-8 sentinel 검증 — round-trip 성공 + 핵심 도구 노출 확인.
                #   S2/S3 도구 추가 / 미래 도구 변경에서 본 테스트가 회귀 신호로 작동
                #   하지 않게 sentinel 만 본다 (도구 카운트 정확 매칭은 AC-2 책임).
                assert "extract_text" in names
                assert "iter_blocks" in names
                assert len(names) >= 7, f"expected at least 7 tools registered, got {names}"
                return  # ^ 성공 — retry 종료
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        # ^ 3 회 retry 모두 실패 — 마지막 에러 surface.
        assert last_error is not None
        raise last_error


# ------------------------------------------------------------------ AC-9 / AC-10
class TestPackagingSurface:
    """패키지 / 모듈 표면 — pyproject 와 모듈 위치."""

    @pytest.mark.spec("v0.5.0/mcp#AC-9")
    def test_entry_point_dispatches_to_run(self) -> None:
        """``rhwp-mcp = "rhwp.mcp:run"`` — ``rhwp.mcp.run`` 이 호출 가능 객체."""
        import rhwp.mcp

        assert callable(rhwp.mcp.run)

    @pytest.mark.spec("v0.5.0/mcp#AC-9")
    def test_pyproject_declares_fastmcp_extras_and_script(self) -> None:
        """``[project.optional-dependencies] mcp = ["fastmcp..."]`` + ``rhwp-mcp`` script 등록."""
        try:
            import tomllib  # py 3.11+
        except ModuleNotFoundError:  # pragma: no cover — py3.10 폴백
            import tomli as tomllib  # type: ignore[import-not-found,no-redef]

        repo_root = Path(__file__).resolve().parent.parent
        with open(repo_root / "pyproject.toml", "rb") as f:
            cfg = tomllib.load(f)

        opt_deps = cfg["project"]["optional-dependencies"]
        assert "mcp" in opt_deps, "extras key 'mcp' (기능 표시) — CLI [cli] 패턴과 일관"
        # ^ 의존성 패키지명은 fastmcp (standalone v3) — ADR § 1
        assert any("fastmcp" in dep for dep in opt_deps["mcp"])
        assert "mcp-chunks" in opt_deps
        assert cfg["project"]["scripts"]["rhwp-mcp"] == "rhwp.mcp:run"

    @pytest.mark.spec("v0.5.0/mcp#AC-10")
    def test_module_is_top_level_not_under_integrations(self) -> None:
        """``rhwp.mcp`` 가 top-level — ``rhwp.integrations.mcp`` 가 아님 (결정 7)."""
        rhwp_mcp = importlib.import_module("rhwp.mcp")
        # ^ 패키지 경로가 python/rhwp/mcp 직속
        assert rhwp_mcp.__name__ == "rhwp.mcp"
        # ^ rhwp.integrations 안에 mcp 가 들어가지 않았는지 확인
        from rhwp import integrations

        assert not hasattr(integrations, "mcp")

    # ^ "__init__.py 가 lazy import 패턴인지" 는 implementation 측면 — behavior
    #   측면 검증은 CI ``test-without-extras`` 잡 (fastmcp 미설치 환경에서 file 전체
    #   skip = 5 카운트) 이 SSOT. 본 파일에 추가 source-grep 테스트는 두지 않는다.
