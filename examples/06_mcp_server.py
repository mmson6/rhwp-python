"""rhwp-mcp 도구 7 종 in-process 라운드트립 데모 — fastmcp Client 사용.

LLM 에이전트 (Claude Desktop / Cursor / Cline 등) 가 stdio subprocess 로 spawn
한 ``rhwp-mcp`` 와 주고받는 패턴을 같은 프로세스에서 재현. 실제 운영에는
``rhwp-mcp`` 명령을 외부 client (예: Claude Desktop config) 가 spawn 하지만,
도구 동작 검증 / 사용 예제 학습은 in-process 가 빠르고 확정적.

사용법:
    python examples/06_mcp_server.py path/to/your/file.hwp
    python examples/06_mcp_server.py path/to/your/file.hwp --skip-chunks

설치:
    pip install "rhwp-python[mcp]"          # 6 도구
    pip install "rhwp-python[mcp-chunks]"   # + chunks (RAG 청킹)
"""

import asyncio
import json
from pathlib import Path as PathLibPath

import typer
from fastmcp.client import Client
from rhwp.mcp.server import build_server


def main(
    path: PathLibPath = typer.Argument(
        PathLibPath("external/rhwp/samples/aift.hwp"),
        exists=False,
        help="HWP 또는 HWPX 파일 경로 (기본값은 fixture)",
    ),
    skip_chunks: bool = typer.Option(
        False,
        "--skip-chunks",
        help="chunks 도구 호출 스킵 ([mcp-chunks] extras 미설치 환경에서 사용).",
    ),
) -> None:
    """rhwp-mcp 의 7 도구를 fastmcp Client 로 직접 호출해 출력 미리본다."""
    if not path.exists():
        typer.echo(f"파일이 없습니다: {path}", err=True)
        raise typer.Exit(code=1)

    asyncio.run(_run_demo(str(path), skip_chunks=skip_chunks))


async def _run_demo(path: str, *, skip_chunks: bool) -> None:
    server = build_server()
    # ^ Client(server) — fastmcp 가 in-process FastMCPTransport 로 wrap. 실제 운영에는
    #   stdio subprocess (Claude Desktop) 또는 streamable-http URL 을 transport 로 전달.
    async with Client(server) as client:
        await _show_tools(client)
        await _call_parse_summary(client, path)
        await _call_extract_text(client, path)
        await _call_get_ir(client, path)
        await _call_iter_blocks(client, path)
        await _call_to_markdown(client, path)
        await _call_to_html(client, path)
        if skip_chunks:
            typer.echo("\n[7/7] chunks — skipped (--skip-chunks)")
        else:
            await _call_chunks(client, path)


async def _show_tools(client: Client) -> None:
    typer.echo("=" * 60)
    typer.echo("[등록된 도구]")
    typer.echo("=" * 60)
    for tool in await client.list_tools():
        # ^ description 은 docstring 첫 줄 — LLM 도구 호출 의도 추론용
        first_line = (tool.description or "").splitlines()[0] if tool.description else ""
        typer.echo(f"  - {tool.name:22s} {first_line}")


async def _call_parse_summary(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[1/7] parse_hwp_summary — 카운트 + 코어 버전")
    typer.echo("=" * 60)
    result = await client.call_tool("parse_hwp_summary", {"path": path})
    typer.echo(json.dumps(result.structured_content or result.data, indent=2, ensure_ascii=False))


async def _call_extract_text(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[2/7] extract_text — 단락별 평문 (LF 결합)")
    typer.echo("=" * 60)
    result = await client.call_tool("extract_text", {"path": path})
    text = result.data if isinstance(result.data, str) else str(result.data)
    typer.echo(f"  길이: {len(text):,} 자")
    typer.echo(f"  처음 200자: {text[:200]!r}")


async def _call_get_ir(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[3/7] get_ir — Document IR 전체 (dict)")
    typer.echo("=" * 60)
    result = await client.call_tool("get_ir", {"path": path})
    ir = result.structured_content or result.data
    if isinstance(ir, dict):
        typer.echo(f"  schema_name:    {ir.get('schema_name')}")
        typer.echo(f"  schema_version: {ir.get('schema_version')}")
        typer.echo(f"  body 블록 수:   {len(ir.get('body', []))}")


async def _call_iter_blocks(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[4/7] iter_blocks — kind=table, limit=3")
    typer.echo("=" * 60)
    result = await client.call_tool("iter_blocks", {"path": path, "kind": "table", "limit": 3})
    blocks = (result.structured_content or {}).get("result", []) or result.data or []
    typer.echo(f"  반환된 표 블록 수: {len(blocks)}")
    for i, b in enumerate(blocks):
        typer.echo(f"  [{i + 1}] kind={b.get('kind')}")


async def _call_to_markdown(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[5/7] to_markdown — GFM Markdown")
    typer.echo("=" * 60)
    result = await client.call_tool("to_markdown", {"path": path})
    md = result.data if isinstance(result.data, str) else str(result.data)
    typer.echo(f"  길이: {len(md):,} 자")
    typer.echo(f"  처음 200자: {md[:200]!r}")


async def _call_to_html(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[6/7] to_html — HTML5 (include_css=False)")
    typer.echo("=" * 60)
    result = await client.call_tool("to_html", {"path": path, "include_css": False})
    html = result.data if isinstance(result.data, str) else str(result.data)
    typer.echo(f"  길이: {len(html):,} 자")
    typer.echo(f"  처음 200자: {html[:200]!r}")


async def _call_chunks(client: Client, path: str) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("[7/7] chunks — RAG 청킹 (paragraph 모드, size=500)")
    typer.echo("=" * 60)
    try:
        result = await client.call_tool(
            "chunks", {"path": path, "mode": "paragraph", "size": 500, "overlap": 50}
        )
    except Exception as e:
        typer.echo(f"  chunks 호출 실패 (langchain-text-splitters 미설치 가능성): {e}")
        typer.echo('  설치: pip install "rhwp-python[mcp-chunks]"')
        return
    chunks_list = (result.structured_content or {}).get("result", []) or result.data or []
    typer.echo(f"  반환된 청크 수: {len(chunks_list)}")
    for i, c in enumerate(chunks_list[:2]):
        # ^ 첫 2 청크만 미리보기 — 전체는 길다
        preview = c.get("page_content", "")[:80]
        typer.echo(f"  [{i + 1}] {preview!r}")
    if len(chunks_list) > 2:
        typer.echo(f"  ... ({len(chunks_list) - 2} more)")


if __name__ == "__main__":
    typer.run(main)
