"""rhwp-py chunks 서브커맨드 — LangChain ``RecursiveCharacterTextSplitter`` 결과 출고.

cli.md §S3. ``langchain-text-splitters`` 미설치 시 exit 2 — typer (``cli``)
만 설치한 사용자에게 langchain 의존성을 강요하지 않도록 별도 extras
(``cli-chunks`` 또는 ``cli,langchain`` 조합) 게이팅.
"""

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Literal, cast

import typer


class ChunksMode(str, Enum):
    single = "single"
    paragraph = "paragraph"
    ir_blocks = "ir-blocks"


class ChunksFormat(str, Enum):
    json = "json"
    ndjson = "ndjson"
    text = "text"


def register_chunks_command(app: typer.Typer) -> None:
    @app.command(
        "chunks",
        # ^ Typer Rich help 가 [bracket] 을 markup tag 로 해석 — backtick 으로 escape
        help="LangChain Document 청크 스트림 — `cli-chunks` 또는 `cli,langchain` extras 필요.",
    )
    def chunks_cmd(
        path: Path = typer.Argument(..., help="HWP / HWPX 파일 경로.", exists=False),
        mode: ChunksMode = typer.Option(
            ChunksMode.paragraph,
            "--mode",
            help="LangChain 매핑 모드 (single / paragraph / ir-blocks).",
        ),
        size: int = typer.Option(
            500, "--size", help="청크 최대 문자 수 (RecursiveCharacterTextSplitter)."
        ),
        overlap: int = typer.Option(50, "--overlap", help="청크 간 오버랩."),
        fmt: ChunksFormat = typer.Option(
            ChunksFormat.ndjson, "--format", help="출력 포맷 (ndjson/json/text)."
        ),
        include_furniture: bool = typer.Option(
            False,
            "--include-furniture/--no-include-furniture",
            help=(
                "ir-blocks 모드에서 furniture (footnote/endnote/header/footer) 도 포함. "
                "다른 모드에선 무시."
            ),
        ),
    ) -> None:
        # * extras 가드 — langchain-text-splitters 미설치 시 exit 2 (cli.md §exit code)
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            typer.echo(
                "rhwp-py chunks requires `langchain-text-splitters`. Install with:\n"
                '    pip install "rhwp-python[cli-chunks]"',
                err=True,
            )
            raise typer.Exit(code=2) from None

        if not path.exists():
            typer.echo(f"file not found: {path}", err=True)
            raise typer.Exit(code=1)

        # ^ HwpLoader 의 LoadMode Literal 어휘로 cast — Enum.value 가 1:1 매핑
        from rhwp.integrations.langchain import HwpLoader

        load_mode = cast(Literal["single", "paragraph", "ir-blocks"], mode.value)
        loader = HwpLoader(str(path), mode=load_mode, include_furniture=include_furniture)
        try:
            docs = loader.load()
        except (ValueError, OSError) as e:
            typer.echo(f"load error: {e}", err=True)
            raise typer.Exit(code=1) from e

        splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
        split_docs = splitter.split_documents(docs)

        if fmt == ChunksFormat.ndjson:
            for d in split_docs:
                sys.stdout.write(
                    json.dumps(
                        {"page_content": d.page_content, "metadata": d.metadata},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            return
        if fmt == ChunksFormat.json:
            data = [{"page_content": d.page_content, "metadata": d.metadata} for d in split_docs]
            sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
            return
        # text — 청크 사이를 빈 줄로 구분
        for d in split_docs:
            sys.stdout.write(d.page_content + "\n\n")
