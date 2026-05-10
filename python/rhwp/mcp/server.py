"""FastMCP 인스턴스 + 도구 등록 + transport 기동 + CLI argparse.

``rhwp.mcp.tools`` 의 sync 함수들을 ``FastMCP.tool`` 로 wrap 한다 — 도구
본체는 ``fastmcp`` 와 무관하게 단위 테스트 가능 (tools 모듈 import 만으로 호출).

SDK 채택 (standalone ``fastmcp`` v3) 의 근거는 ``docs/design/v0.5.0/mcp-research.md`` § 1.

- S1 — stdio transport 만 노출.
- S4 — ``--transport stdio | streamable-http`` + ``--host`` + ``--port`` CLI 옵션.
  mcp.md § Transport 결정 의 "stdio 기본 + streamable-http 옵션" 정합.
"""

import argparse

from fastmcp import FastMCP

from rhwp.mcp import tools


def build_server() -> FastMCP:
    """새 ``FastMCP`` 인스턴스를 만들고 도구 8 종을 등록해 반환.

    테스트가 ``mcp.list_tools()`` / ``mcp.call_tool(name, args)`` 를 in-process
    호출할 수 있도록 build 단계를 함수로 분리 — 모듈 import 부수 효과 없이
    fresh 인스턴스 획득.
    """
    server = FastMCP("rhwp-mcp")
    # ^ S1 코어 4 + S2 view 2 + S3 chunks 1 + v0.6.0 PNG 1 = 8.
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
    # ^ v0.6.0: VLM 시각 입력 — fastmcp ImageContent 반환 (base64 + image/png).
    server.tool(tools.render_page_png)
    return server


_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


def _port_type(value: str) -> int:
    """argparse type validator — TCP port 범위 [1, 65535] 강제 (fail-fast)."""
    try:
        port = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"port must be integer, got {value!r}") from e
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            f"port must be in [1, 65535], got {port} (TCP port 범위 — bind 시점 회피)"
        )
    return port


def _build_arg_parser() -> argparse.ArgumentParser:
    """``rhwp-mcp`` CLI 옵션 정의 — argparse 파서 분리해 단위 테스트 용이."""
    parser = argparse.ArgumentParser(
        prog="rhwp-mcp",
        description=(
            "rhwp-python MCP server — HWP/HWPX 를 LLM agent 표면으로 노출. "
            "기본 stdio transport (Claude Desktop / IDE 통합) 또는 "
            "streamable-http (서버 배포)."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help=(
            "Transport protocol. 'stdio' (기본) 는 Claude Desktop / Cline / IDE "
            "통합 — subprocess 로 spawn 됨. 'streamable-http' 는 서버 배포 / 다중 "
            "클라이언트 / 컨테이너 시나리오 — 인증 / sandboxing 은 운영자 책임 "
            "(mcp.md § 비목표)."
        ),
    )
    parser.add_argument(
        "--host",
        default=_DEFAULT_HOST,
        help=(
            "streamable-http bind host. 기본 '127.0.0.1' — 외부 노출 안 함. "
            "0.0.0.0 등으로 바꾸려면 명시적으로 지정 (보안 사고 회피). "
            "stdio transport 와 함께 쓰면 에러."
        ),
    )
    parser.add_argument(
        "--port",
        type=_port_type,
        default=_DEFAULT_PORT,
        help="streamable-http bind port (1-65535). 기본 8000. stdio 와 함께 쓰면 에러.",
    )
    return parser


def run(argv: list[str] | None = None) -> None:
    """``rhwp-mcp`` CLI entry point — argparse 후 transport 별 dispatch.

    Args:
        argv: 명령행 인자 리스트 (테스트 용도). ``None`` 이면 ``sys.argv[1:]``
            사용 — argparse 의 표준 동작.

    Behavior:
        - ``--transport stdio`` (기본): ``server.run()`` — fastmcp 가 stdin/stdout
          JSON-RPC framing 처리. Process 종료까지 blocking. ``--host`` / ``--port``
          를 함께 지정하면 argparse error (silent ignore 보안 혼란 회피).
        - ``--transport streamable-http``: ``server.run(transport="streamable-http",
          host=..., port=...)`` — uvicorn ASGI 기동. SDK 기본 endpoint path
          (``/mcp/``) 추종 (mcp.md AC-8).
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    if args.transport == "stdio" and (args.host != _DEFAULT_HOST or args.port != _DEFAULT_PORT):
        # ^ stdio + non-default host/port = 사용자 의도 모호 (보안 사고 회피).
        #   transport=streamable-http 명시 강제.
        parser.error(
            "--host / --port options require --transport streamable-http "
            "(stdio transport ignores network options)"
        )
    server = build_server()
    if args.transport == "stdio":
        server.run()
    else:
        # ^ args.transport == "streamable-http" — argparse choices 가 보장
        server.run(transport="streamable-http", host=args.host, port=args.port)
