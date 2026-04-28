"""rhwp-py Typer 앱 — 서브커맨드 등록.

cli.md §커맨드 트리 매핑:

- ``parse``    (본 모듈)
- ``version``  (본 모듈)
- ``schema``   (본 모듈)
- ``ir``       (``rhwp.cli.ir.register_ir_commands``)
- ``blocks``   (``rhwp.cli.ir.register_ir_commands``)
- ``chunks``   (``rhwp.cli.chunks.register_chunks_command``)

Exit code 규약 (cli.md § Exit code 규약):

- ``0`` 성공
- ``1`` 사용자 오류 (파일 없음 / 옵션 조합 / 파싱 실패)
- ``2`` extras 미설치 (``chunks`` 의 ``langchain-text-splitters`` 등)
"""

import json
import sys
from pathlib import Path

import typer

import rhwp
from rhwp.cli._state import is_quiet, set_quiet
from rhwp.cli.chunks import register_chunks_command
from rhwp.cli.ir import register_ir_commands

app = typer.Typer(
    name="rhwp-py",
    help="rhwp-python 의 얇은 CLI — IR / blocks / chunks / schema / parse / version",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _global_options(
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="stderr progress 메시지 최소화 (오류 메시지는 항상 출력).",
    ),
) -> None:
    """전역 옵션 — 서브커맨드 실행 전에 한 번 호출된다."""
    set_quiet(quiet)


@app.command("parse", help="기본 정보 (섹션/단락/페이지 수 + 버전) 한 줄 요약 출력.")
def parse_cmd(
    path: Path = typer.Argument(
        ...,
        help="HWP 또는 HWPX 파일 경로",
        # ^ exists=False — typer 의 기본 검증을 비활성화하여 cli.md exit code 규약 (1)
        #   을 직접 보장. 자동 검증은 click.UsageError 로 exit 2 라 규약 어긋남.
        exists=False,
    ),
) -> None:
    if not path.exists():
        typer.echo(f"file not found: {path}", err=True)
        raise typer.Exit(code=1)
    try:
        doc = rhwp.parse(str(path))
    except (ValueError, OSError) as e:
        typer.echo(f"parse error: {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(
        f"sections={doc.section_count}  "
        f"paragraphs={doc.paragraph_count}  "
        f"pages={doc.page_count}"
    )
    typer.echo(f"rhwp-python={rhwp.version()}  rhwp-core={rhwp.rhwp_core_version()}")


@app.command("version", help="rhwp-python 과 rhwp-core 버전 출력.")
def version_cmd() -> None:
    typer.echo(f"rhwp-python {rhwp.version()}")
    typer.echo(f"rhwp-core   {rhwp.rhwp_core_version()}")


@app.command("schema", help="in-package Document IR JSON Schema (Draft 2020-12) 출력.")
def schema_cmd(
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="출력 파일 경로 (없으면 stdout).",
    ),
    indent: int | None = typer.Option(
        2,
        "--indent",
        help="JSON 들여쓰기 칸 수 (0 또는 음수 = 한 줄로 직렬화).",
    ),
) -> None:
    # ^ schema export 는 Pydantic model_rebuild 비용이 있어 함수 안 import —
    #   다른 서브커맨드 startup 시 본 비용 회피.
    from rhwp.ir.schema import export_schema

    schema_dict = export_schema()
    indent_arg = indent if indent is not None and indent > 0 else None
    text = json.dumps(schema_dict, ensure_ascii=False, indent=indent_arg)
    if out is None:
        sys.stdout.write(text + "\n")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    if not is_quiet():
        typer.echo(f"wrote {len(text):,} bytes to {out}", err=True)


# * 서브커맨드 등록 — 본 모듈에서 직접 정의 안 한 ir / blocks / chunks
register_ir_commands(app)
register_chunks_command(app)
