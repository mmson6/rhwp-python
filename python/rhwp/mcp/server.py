"""FastMCP 인스턴스 + 도구 등록 + stdio transport 기동.

``rhwp.mcp.tools`` 의 sync 함수들을 ``FastMCP.tool`` 로 wrap 한다 — 도구
본체는 ``fastmcp`` 와 무관하게 단위 테스트 가능 (tools 모듈 import 만으로 호출).

SDK 채택 (standalone ``fastmcp`` v3) 의 근거는 ``docs/design/v0.5.0/mcp-research.md`` § 1.

S1 — stdio transport 만 노출. streamable-http 는 S4 에서 ``--transport`` 옵션
추가로 도입 (``mcp.md`` § Transport 결정).
"""

from fastmcp import FastMCP

from rhwp.mcp import tools


def build_server() -> FastMCP:
    """새 ``FastMCP`` 인스턴스를 만들고 도구 7 종을 등록해 반환.

    테스트가 ``mcp.list_tools()`` / ``mcp.call_tool(name, args)`` 를 in-process
    호출할 수 있도록 build 단계를 함수로 분리 — 모듈 import 부수 효과 없이
    fresh 인스턴스 획득.
    """
    server = FastMCP("rhwp-mcp")
    # ^ S1 코어 4 + S2 view 2 + S3 chunks 1 = 7. mcp.md AC-2 의 GA 기준 도구 수.
    #   fastmcp v3 의 ``server.tool(fn)`` 은 데코레이터 호출 형태 — 동일 인스턴스에
    #   여러 도구를 program 적으로 등록할 때 같은 클로저 충돌 없이 안전.
    server.tool(tools.parse_hwp_summary)
    server.tool(tools.extract_text)
    server.tool(tools.get_ir)
    server.tool(tools.iter_blocks)
    server.tool(tools.to_markdown)
    server.tool(tools.to_html)
    # ^ chunks 는 langchain-text-splitters 런타임 extras gate — 등록은 무조건,
    #   호출 시점에 ImportError → fastmcp ToolError → MCP isError=True (AC-7).
    server.tool(tools.chunks)
    return server


def run() -> None:
    """``rhwp-mcp`` 를 stdio transport 로 기동.

    Claude Desktop / Cline / IDE 통합 시 호출되는 경로. Process 종료까지 blocking.
    """
    build_server().run()
