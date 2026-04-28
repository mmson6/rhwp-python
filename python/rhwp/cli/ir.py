"""rhwp-py ir / blocks 서브커맨드.

cli.md §S2 (ir / blocks) + phase-2.md § 두 축 연동 — IR 확장 8 신규 kind 를
``--kind`` enum 에 노출하여 IR 확장 GA (S4) 와 동기. 출력 포맷은 cli.md
§기본 출력 포맷 채택: ``ir`` 은 단일 JSON, ``blocks`` 는 NDJSON 기본
(jq streaming 친화).
"""

import json
import sys
from collections.abc import Iterable, Iterator
from enum import Enum
from pathlib import Path
from typing import Literal, cast

import typer

import rhwp
from rhwp.cli._state import is_quiet
from rhwp.ir._plain_text import join_inline_blocks
from rhwp.ir.nodes import (
    Block,
    CaptionBlock,
    EndnoteBlock,
    FieldBlock,
    FootnoteBlock,
    FormulaBlock,
    ListItemBlock,
    ParagraphBlock,
    PictureBlock,
    TableBlock,
    TocBlock,
    UnknownBlock,
)


# ^ Click/Typer 는 str Enum 을 자동 매핑한다. enum member name 은 Python
#   identifier, value 는 사용자 입력 어휘 — IR ``kind`` 값과 동일 (list_item).
class BlockKindOpt(str, Enum):
    all = "all"
    paragraph = "paragraph"
    table = "table"
    picture = "picture"
    formula = "formula"
    footnote = "footnote"
    endnote = "endnote"
    list_item = "list_item"
    caption = "caption"
    toc = "toc"
    field = "field"


class BlockScopeOpt(str, Enum):
    body = "body"
    furniture = "furniture"
    all = "all"


class BlocksFormatOpt(str, Enum):
    json = "json"
    ndjson = "ndjson"
    text = "text"


def register_ir_commands(app: typer.Typer) -> None:
    """``ir`` / ``blocks`` 서브커맨드를 ``app`` 에 등록."""

    @app.command("ir", help="전체 Document IR 을 JSON 으로 출력 (stdout 또는 --out FILE).")
    def ir_cmd(
        path: Path = typer.Argument(..., help="HWP / HWPX 파일 경로.", exists=False),
        out: Path | None = typer.Option(
            None, "--out", "-o", help="출력 파일 경로 (없으면 stdout)."
        ),
        indent: int | None = typer.Option(
            None, "--indent", help="JSON 들여쓰기 (없으면 한 줄로 직렬화)."
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
        text = doc.to_ir_json(indent=indent if indent and indent > 0 else None)
        if out is None:
            sys.stdout.write(text + "\n")
            return
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        if not is_quiet():
            typer.echo(f"wrote {len(text):,} bytes to {out}", err=True)

    @app.command(
        "blocks",
        help="iter_blocks 기반 블록 스트림 (NDJSON 기본 — jq streaming 친화).",
    )
    def blocks_cmd(
        path: Path = typer.Argument(..., help="HWP / HWPX 파일 경로.", exists=False),
        scope: BlockScopeOpt = typer.Option(
            BlockScopeOpt.body, "--scope", help="순회 대상 (body/furniture/all)."
        ),
        kind: BlockKindOpt = typer.Option(
            BlockKindOpt.all,
            "--kind",
            help="블록 종류 필터 (all 이면 모든 종류 yield).",
        ),
        recurse: bool = typer.Option(
            True, "--recurse/--no-recurse", help="컨테이너 블록 재귀 진입."
        ),
        fmt: BlocksFormatOpt = typer.Option(
            BlocksFormatOpt.ndjson,
            "--format",
            help="출력 포맷 (ndjson/json/text).",
        ),
        limit: int | None = typer.Option(None, "--limit", help="최대 출고 개수 (None = 전체)."),
    ) -> None:
        if not path.exists():
            typer.echo(f"file not found: {path}", err=True)
            raise typer.Exit(code=1)
        try:
            doc = rhwp.parse(str(path))
        except (ValueError, OSError) as e:
            typer.echo(f"parse error: {e}", err=True)
            raise typer.Exit(code=1) from e
        ir_doc = doc.to_ir()
        # ^ Enum.value 는 BlockScope Literal 어휘와 1:1 — cast 로 type checker 통과
        scope_lit = cast(Literal["body", "furniture", "all"], scope.value)
        block_iter = _filter_blocks(
            ir_doc.iter_blocks(scope=scope_lit, recurse=recurse),
            kind,
            limit,
        )
        _emit_blocks(block_iter, fmt)


def _filter_blocks(
    blocks: Iterable[Block],
    kind: BlockKindOpt,
    limit: int | None,
) -> Iterator[Block]:
    """--kind / --limit 필터 적용 — limit None 이면 무제한.

    평문이 빈 블록 (UnknownBlock / 빈 ParagraphBlock / 캡션 없는 PictureBlock 등)
    은 RAG 노이즈로 간주하여 모든 포맷에서 skip — LangChain loader 의
    ``_yield_documents`` 가 동일 정책 (`if not content.strip(): continue`).
    """
    n = 0
    for block in blocks:
        if kind != BlockKindOpt.all and block.kind != kind.value:
            continue
        if not _block_to_text(block).strip():
            continue
        yield block
        n += 1
        if limit is not None and n >= limit:
            return


def _emit_blocks(blocks: Iterable[Block], fmt: BlocksFormatOpt) -> None:
    """포맷별 stdout 직렬화 — 빈 컨텐츠 블록은 _filter_blocks 가 이미 skip."""
    if fmt == BlocksFormatOpt.ndjson:
        for block in blocks:
            sys.stdout.write(block.model_dump_json() + "\n")
        return
    if fmt == BlocksFormatOpt.json:
        # ^ stream 으로 모으지 않고 list 평가 — JSON array 는 한 번에 출력해야 valid
        data = [block.model_dump(mode="json") for block in blocks]
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
        return
    # text — 평문 추출 (이미 non-empty 가 보장됨)
    for block in blocks:
        sys.stdout.write(_block_to_text(block) + "\n")


def _block_to_text(block: Block) -> str:
    """``--format text`` 용 평문 추출 — LangChain ir-blocks 매핑과 같은 우선순위.

    Picture 는 caption.blocks 평문 우선 + description 폴백, Formula 는 text_alt
    우선 + script 폴백 등. RAG fallback 텍스트와 일관 — 사용자가 CLI 결과를
    그대로 vector index 에 흘려도 의미 텍스트만 노출된다.
    """
    if isinstance(block, ParagraphBlock):
        return block.text
    if isinstance(block, TableBlock):
        return block.text
    if isinstance(block, PictureBlock):
        if block.caption is not None:
            cap = join_inline_blocks(block.caption.blocks)
            if cap:
                return cap
        return block.description or ""
    if isinstance(block, FormulaBlock):
        return block.text_alt or block.script
    if isinstance(block, (FootnoteBlock, EndnoteBlock, CaptionBlock)):
        return join_inline_blocks(block.blocks)
    if isinstance(block, ListItemBlock):
        return f"{block.marker} {block.text}".strip()
    if isinstance(block, TocBlock):
        return "\n".join(e.text for e in block.entries if e.text)
    if isinstance(block, FieldBlock):
        return block.cached_value or ""
    # ^ 새 Block variant 추가 시 위 분기를 먼저 확장 — UnknownBlock 폴백은 빈 텍스트
    assert isinstance(block, UnknownBlock)
    return ""
