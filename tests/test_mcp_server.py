"""rhwp.mcp fastmcp 서버 단위 테스트 (S1).

``fastmcp`` (``[mcp]`` extras) 미설치 환경에서는 file-level ``importorskip`` 로
전체 skip — CI ``test-without-extras`` 잡이 카운트 검증 (AC-1).

S1 시점 인수조건 매핑:

- AC-2  (도구 4 개 노출)               → ``TestToolRegistry``
- AC-3  (잘못된 enum → isError=True)   → ``TestErrorHandling::test_iter_blocks_invalid_kind``
- AC-4  (FileNotFound → isError=True) → ``TestErrorHandling::test_extract_text_missing_file``
- AC-5  (모든 handler sync 함수)        → ``TestSyncHandler``
- AC-9  (pyproject 등록)                → ``TestPackagingSurface`` (entry point + extras 키 verify)
- AC-10 (모듈 위치)                     → ``TestPackagingSurface``
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
    """도구 등록 (S1: 4 개)."""

    @pytest.mark.spec("v0.5.0/mcp#AC-2")
    def test_lists_exactly_four_tools(self) -> None:
        server = build_server()
        names = {t.name for t in asyncio.run(server.list_tools())}
        assert names == {"parse_hwp_summary", "extract_text", "get_ir", "iter_blocks"}

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
