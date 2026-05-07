"""rhwp.mcp fastmcp 서버 단위 테스트 (S1 + S2 + S3 + S4 + v0.5.1 typed-output).

``fastmcp`` (``[mcp]`` extras) 미설치 환경에서는 file-level ``importorskip`` 로
전체 skip — CI ``test-without-extras`` 잡이 카운트 검증 (AC-1).

``chunks`` 도구의 smoke 테스트는 메서드 레벨 ``importorskip("langchain_text_splitters")``
로 게이트 — 본 파일은 fastmcp 만 file-level gate, langchain 미설치 환경에서는
chunks smoke 만 개별 skip (file-level skip 카운트 영향 없음).

v0.5.0 인수조건 매핑:

- AC-2  (도구 7 개 노출 — S1 코어 4 + S2 view 2 + S3 chunks 1) → ``TestToolRegistry``
- AC-3  (잘못된 enum → isError=True)                          → ``TestErrorHandling``
- AC-4  (FileNotFound → isError=True)                         → ``TestErrorHandling``
- AC-5  (모든 handler sync 함수)                              → ``TestSyncHandler``
- AC-6  (view 도구가 v0.4.0 view API thin wrapper)            → ``TestToMarkdown`` / ``TestToHtml``
- AC-7  (chunks extras-gate 런타임 + 다른 도구 영향 없음)     → ``TestChunks``
- AC-8  (--transport streamable-http --port N CLI 기동)       → ``TestTransportCli``
- AC-9  (pyproject 등록)                                      → ``TestPackagingSurface``
- AC-10 (모듈 위치)                                           → ``TestPackagingSurface``

v0.5.1 인수조건 매핑 (mcp-typed-output PATCH):

- AC-1  (``get_ir`` 반환 타입 = ``HwpDocument``)              → ``TestTypedSignatures``
- AC-2  (``iter_blocks`` 반환 타입 = ``list[Block]``)         → ``TestTypedSignatures``
- AC-3  (``chunks`` 반환 타입 = ``list[ChunkRecord]``)        → ``TestTypedSignatures``
- AC-4  (outputSchema 강화)                                   → ``TestTypedOutputSchema``
- AC-5  (wire format byte-equal — v0.5.0 회귀 가드)           → ``TestBackwardsCompat``
- AC-6  (fastmcp Client ``result.data`` 가 typed 인스턴스)    → ``TestTypedClientData``
- AC-7  (``ChunkRecord.metadata`` = ``dict[str, Any]``)       → ``TestTypedSignatures``
- AC-8  (도구 등록 7 개 회귀 보존)                            → 기존 ``TestToolRegistry`` 가 cover
- AC-9  (extras / skip count 변동 없음)                       → 기존 CI ``test-without-extras`` job
"""

import sys
import typing
from pathlib import Path

import pytest

# ^ extras 미설치 환경에서 file 전체 skip — CI test-without-extras 가 카운트 검증
pytest.importorskip("fastmcp")

import asyncio  # noqa: E402
import importlib  # noqa: E402
import inspect  # noqa: E402
import json  # noqa: E402
from typing import Any  # noqa: E402

import rhwp  # noqa: E402
from fastmcp.client import Client  # noqa: E402
from fastmcp.exceptions import NotFoundError, ToolError  # noqa: E402
from fastmcp.tools.function_tool import FunctionTool  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from rhwp.ir.nodes import Block, HwpDocument  # noqa: E402
from rhwp.mcp import tools  # noqa: E402
from rhwp.mcp.server import build_server  # noqa: E402
from rhwp.mcp.tools import ChunkRecord  # noqa: E402

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
    def test_returns_typed_hwp_document(self, hwp_sample: Path) -> None:
        """v0.5.1 부터 typed ``HwpDocument`` 인스턴스 반환 (v0.5.0 의 dict 출력 대체).

        wire format byte-equal 회귀 가드는 ``TestBackwardsCompat`` 가 보유.
        """
        result = tools.get_ir(str(hwp_sample))
        assert isinstance(result, HwpDocument)
        # ^ schema_name 은 Literal-constrained — Pydantic validator 가 강제
        assert result.schema_name == "HwpDocument"
        assert result.schema_version
        # ^ body 는 list[Block] — 빈 리스트도 허용 (빈 문서 회귀 회피)
        assert isinstance(result.body, list)


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
    def test_default_returns_typed_blocks(self, hwp_sample: Path) -> None:
        """v0.5.1 부터 typed Block 유니온 인스턴스 리스트 반환."""
        result = tools.iter_blocks(str(hwp_sample))
        assert isinstance(result, list)
        # ^ Block 유니온의 모든 변형이 ``kind`` attribute 를 보유 (Discriminator key)
        assert all(hasattr(b, "kind") for b in result)
        assert all(isinstance(b.kind, str) for b in result)

    def test_kind_filter_paragraph(self, hwp_sample: Path) -> None:
        # ^ kind=None (또는 미지정) 이면 필터 미적용 — IR 의 모든 종류 yield
        all_blocks = tools.iter_blocks(str(hwp_sample), kind=None)
        para_blocks = tools.iter_blocks(str(hwp_sample), kind="paragraph")
        assert all(b.kind == "paragraph" for b in para_blocks)
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
            # ^ v0.5.1 부터 typed ChunkRecord 인스턴스 — wire format byte-equal 은
            #   ``TestBackwardsCompat`` 회귀 가드.
            assert isinstance(d, ChunkRecord)
            assert isinstance(d.page_content, str)
            assert isinstance(d.metadata, dict)

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
        furniture_chunks = [c for c in with_furniture if c.metadata.get("scope") == "furniture"]
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
        # ^ ``sys.version_info`` guard 로 pyright 가 Python 3.10 / 3.11+ 를 정확히 분기.
        #   try/except ModuleNotFoundError 는 런타임 동작은 옳지만 pyright 의 statically-
        #   resolved 모듈 검증을 통과 못 함 (3.10 venv 에선 ``tomllib`` 가 stdlib 부재).
        #   ``tomli`` 는 pytest>=8 / langchain 등의 transitive 로 testing extras 에 가용.
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[no-redef]

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


# ====================================================================
#                      v0.5.1 — MCP typed output PATCH
# ====================================================================
# get_ir / iter_blocks / chunks 의 출력 시그니처를 dict[str, Any] 에서
# Pydantic 모델 (HwpDocument / list[Block] / list[ChunkRecord]) 로 강화.
# wire format (result.structured_content) 은 v0.5.0 과 byte-equal —
# 외부 클라이언트 영향 0. spec: docs/roadmap/v0.5.1/mcp-typed-output.md.


# ------------------------------------------------------------------ AC-1 / AC-2 / AC-3 / AC-7
class TestTypedSignatures:
    """v0.5.1 도구 출력 어노테이션 — fastmcp 자동 outputSchema 의 입력원."""

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-1")
    def test_get_ir_return_annotation_is_hwp_document(self) -> None:
        """``get_ir`` 의 정적 반환 타입 = ``HwpDocument`` (fastmcp v3 자동 schema 진입점)."""
        sig = inspect.signature(tools.get_ir)
        assert sig.return_annotation is HwpDocument

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-2")
    def test_iter_blocks_return_annotation_is_list_of_block(self) -> None:
        """``iter_blocks`` 의 정적 반환 타입 = ``list[Block]`` (Discriminator + Tag 11 변형)."""
        hints = typing.get_type_hints(tools.iter_blocks, include_extras=True)
        assert hints["return"] == list[Block]

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-3")
    def test_chunks_return_annotation_is_list_of_chunk_record(self) -> None:
        """``chunks`` 의 정적 반환 타입 = ``list[ChunkRecord]``."""
        hints = typing.get_type_hints(tools.chunks)
        assert hints["return"] == list[ChunkRecord]

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-3")
    def test_chunk_record_is_exposed_on_tools_module(self) -> None:
        """``ChunkRecord`` 가 ``rhwp.mcp.tools`` 모듈에서 import 가능 (외부 코드 사용 가능)."""
        assert hasattr(tools, "ChunkRecord")
        assert tools.ChunkRecord is ChunkRecord

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-7")
    def test_chunk_record_metadata_annotation_is_free_dict(self) -> None:
        """``ChunkRecord.metadata`` 어노테이션 = ``dict[str, Any]``.

        결정 5 (mode × kind 분기 거부) 의 grep-friendly evidence — 새 metadata 키
        추가 시 모델 갱신 강제 회피. 분기 모델 도입 PR 회귀 가드.
        """
        anno = ChunkRecord.model_fields["metadata"].annotation
        assert anno == dict[str, Any]


# ------------------------------------------------------------------ AC-4
class TestTypedOutputSchema:
    """fastmcp 자동 생성 outputSchema 가 v0.5.0 의 약타입 → 강타입으로 전환됨을 검증.

    v0.5.0 의 dict[str, Any] 출력은 ``additionalProperties: true`` 만 (LLM 이 키
    이름조차 모름). v0.5.1 부터 HwpDocument / Block / ChunkRecord 의 필드가
    schema 에 직접 노출 — LLM 의 응답 해석 정확도 향상.
    """

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-4")
    def test_get_ir_schema_exposes_hwp_document_defs(self) -> None:
        server = build_server()
        tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "get_ir")
        schema_text = json.dumps(tool.output_schema)
        # ^ HwpDocument 의 sub-model 들이 schema 에 등장 (v0.5.0 의 약타입엔 부재)
        for ref in ("HwpDocument", "ParagraphBlock", "TableBlock"):
            assert ref in schema_text, (
                f"expected {ref!r} in get_ir output schema (v0.5.1 강타입화). "
                f"v0.5.0 약타입 회귀 의심."
            )

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-4")
    def test_iter_blocks_schema_exposes_block_union_variants(self) -> None:
        """배열 item 의 ``oneOf`` (또는 inline `$defs`) 가 11 변형 모두 노출."""
        server = build_server()
        tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "iter_blocks")
        schema_text = json.dumps(tool.output_schema)
        for variant in (
            "ParagraphBlock",
            "TableBlock",
            "PictureBlock",
            "FormulaBlock",
            "FootnoteBlock",
            "EndnoteBlock",
            "ListItemBlock",
            "CaptionBlock",
            "TocBlock",
            "FieldBlock",
            "UnknownBlock",
        ):
            assert variant in schema_text, (
                f"expected {variant!r} in iter_blocks output schema "
                f"(Block 유니온 11 변형 — v0.5.1 강타입화)"
            )

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-4")
    def test_chunks_schema_exposes_chunk_record_fields(self) -> None:
        """``page_content`` + ``metadata`` 가 schema 에 노출 — metadata 자유 dict 유지."""
        server = build_server()
        tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "chunks")
        schema_text = json.dumps(tool.output_schema)
        assert "page_content" in schema_text
        assert "metadata" in schema_text


# ------------------------------------------------------------------ AC-5
class TestBackwardsCompat:
    """v0.5.0 → v0.5.1 wire format 회귀 가드 — ``result.structured_content`` byte-equal.

    v0.5.0 의 dict 출력 == v0.5.1 의 fastmcp 자동 직렬화 (Pydantic ``model_dump``).
    이 invariant 가 깨지면 외부 MCP 클라이언트 (Claude Desktop / Cline 등) 의 기존
    LLM 프롬프트 / 후처리 코드가 영향 받음 — PATCH 의 SemVer 의무 위반.
    """

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-5")
    def test_get_ir_structured_content_matches_v050_dump(self, hwp_sample: Path) -> None:
        """v0.5.0 의 ``HwpDocument.model_dump(mode="json")`` 와 v0.5.1 wire format byte-equal.

        BaseModel 반환은 fastmcp v3 가 wrap 없이 fields 직접 노출 — list / scalar
        반환의 ``{"result": ...}`` wrapper 와 다른 패턴 (fastmcp v3.2.4 docs § Use
        Typed Models for Structured Output).
        """
        expected = rhwp.parse(str(hwp_sample)).to_ir().model_dump(mode="json")
        server = build_server()

        async def _call() -> Any:
            async with Client(server) as client:
                return await client.call_tool("get_ir", {"path": str(hwp_sample)})

        result = asyncio.run(_call())
        assert result.structured_content == expected

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-5")
    def test_iter_blocks_structured_content_matches_v050_dump(self, hwp_sample: Path) -> None:
        """v0.5.0 의 ``[Block.model_dump(mode="json"), ...]`` 와 byte-equal."""
        ir_doc = rhwp.parse(str(hwp_sample)).to_ir()
        expected = [
            block.model_dump(mode="json")
            for block in ir_doc.iter_blocks(scope="body", recurse=True)
        ]
        server = build_server()

        async def _call() -> Any:
            async with Client(server) as client:
                return await client.call_tool("iter_blocks", {"path": str(hwp_sample)})

        result = asyncio.run(_call())
        assert result.structured_content == {"result": expected}

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-5")
    def test_chunks_structured_content_matches_v050_dump(self, hwp_sample: Path) -> None:
        """v0.5.0 의 dict 평탄화 결과와 v0.5.1 wire format byte-equal."""
        pytest.importorskip("langchain_text_splitters")
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from rhwp.integrations.langchain import HwpLoader

        # ^ v0.5.0 chunks 의 정확한 dict 평탄화 패턴 재현
        loader = HwpLoader(str(hwp_sample), mode="paragraph", include_furniture=False)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        split_docs = splitter.split_documents(docs)
        expected = [{"page_content": d.page_content, "metadata": d.metadata} for d in split_docs]

        server = build_server()

        async def _call() -> Any:
            async with Client(server) as client:
                return await client.call_tool("chunks", {"path": str(hwp_sample)})

        result = asyncio.run(_call())
        assert result.structured_content == {"result": expected}


# ------------------------------------------------------------------ AC-6
class TestTypedClientData:
    """fastmcp Client 의 ``result.data`` 가 v0.5.1 부터 typed deserialization.

    v0.5.0 의 dict 출력에서는 ``result.data`` 가 raw dict 또는 list[dict].
    v0.5.1 부터 fastmcp 가 outputSchema 기반으로 Pydantic-like 객체로 reconstruct —
    attribute access 가 가능해 LLM 에이전트의 결과 후처리가 정확.
    """

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-6")
    def test_get_ir_client_data_has_typed_attributes(self, hwp_sample: Path) -> None:
        server = build_server()

        async def _call() -> Any:
            async with Client(server) as client:
                return await client.call_tool("get_ir", {"path": str(hwp_sample)})

        result = asyncio.run(_call())
        data = result.data
        # ^ schema_name / schema_version 이 attribute 로 access 가능 (v0.5.0 dict 와 다름)
        assert hasattr(data, "schema_name")
        assert data.schema_name == "HwpDocument"
        assert hasattr(data, "schema_version")
        assert hasattr(data, "body")

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-6")
    def test_iter_blocks_client_data_is_typed_list(self, hwp_sample: Path) -> None:
        """``list[Block]`` 의 ``result.data`` — fastmcp v3 의 oneOf 한계로 list element
        는 dict 폴백 (callable Discriminator + Tag union 을 dynamic Pydantic 모델로
        reconstruct 불가). server side 출력 자체는 typed (AC-2). client side 의
        의미 있는 검증은 ``"kind"`` key 가 노출되어 있고 v0.5.0 dict access 패턴이
        그대로 동작한다는 것 — wire format 의 byte-equality 가 더 strict 한 회귀 가드 (AC-5).
        """
        server = build_server()

        async def _call() -> Any:
            async with Client(server) as client:
                return await client.call_tool("iter_blocks", {"path": str(hwp_sample)})

        result = asyncio.run(_call())
        data = result.data
        assert isinstance(data, list)
        assert data, "iter_blocks 의 fixture 결과는 빈 리스트가 아니어야 함"
        # ^ Discriminator key 'kind' 가 모든 변형의 dict key (v0.5.0 access 호환)
        for block in data:
            assert "kind" in block
            assert isinstance(block["kind"], str)

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-6")
    def test_chunks_client_data_is_typed_list(self, hwp_sample: Path) -> None:
        pytest.importorskip("langchain_text_splitters")
        server = build_server()

        async def _call() -> Any:
            async with Client(server) as client:
                return await client.call_tool("chunks", {"path": str(hwp_sample)})

        result = asyncio.run(_call())
        data = result.data
        assert isinstance(data, list)
        assert data, "chunks fixture 결과는 빈 리스트가 아니어야 함"
        for chunk in data:
            # ^ ChunkRecord 의 두 필드가 attribute 로 access 가능
            assert hasattr(chunk, "page_content")
            assert hasattr(chunk, "metadata")
            assert isinstance(chunk.page_content, str)
            assert isinstance(chunk.metadata, dict)


# ------------------------------------------------------------------ Pydantic round-trip
class TestTypedModelRoundTrip:
    """Pydantic dump → load → equality — 모델 정의의 결정성 회귀 가드."""

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-1")
    def test_get_ir_round_trip(self, hwp_sample: Path) -> None:
        original = tools.get_ir(str(hwp_sample))
        reloaded = HwpDocument.model_validate_json(original.model_dump_json())
        assert reloaded == original

    @pytest.mark.spec("v0.5.1/mcp-typed-output#AC-3")
    def test_chunk_record_round_trip(self) -> None:
        original = ChunkRecord(
            page_content="hello",
            metadata={"kind": "paragraph", "section_idx": 0, "para_idx": 0},
        )
        reloaded = ChunkRecord.model_validate_json(original.model_dump_json())
        assert reloaded == original
