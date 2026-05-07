"""rhwp-mcp 도구 함수 본체 — 순수 rhwp 로직, ``fastmcp`` import 없음.

``server.py`` 가 ``FastMCP.tool`` 데코레이터로 등록한다. 본 모듈은 도구가
``unsendable`` 안전 패턴 (sync handler 안에서 ``rhwp.parse`` → primitive 반환)
을 강제하기 위해 모두 sync 함수로 정의 — Document 가 thread 경계를 절대 안
넘는다. 자세한 배경은 ``docs/design/v0.5.0/mcp-research.md`` § 3.

- S1 — `parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks` (코어 4)
- S2 — `to_markdown` / `to_html` (v0.4.0 view API thin wrapper)
- S3 — `chunks` (RAG 청킹 — langchain-text-splitters 런타임 extras gate)
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

import rhwp
from rhwp.ir.nodes import Block, HwpDocument


class ParseSummary(BaseModel):
    """``parse_hwp_summary`` 의 출력 스키마 — LLM 이 필드 의미를 정확히 추론하도록 Pydantic 모델."""

    sections: int = Field(description="문서 섹션 수.")
    paragraphs: int = Field(description="전체 섹션을 통틀어 누적된 문단 수.")
    pages: int = Field(description="페이지네이션 후 페이지 수.")
    rhwp_core_version: str = Field(description="파싱에 사용된 상류 rhwp Rust 코어 버전.")


class ChunkRecord(BaseModel):
    """RAG 청크의 직렬화 표면 — LangChain ``Document`` 의 ``page_content`` / ``metadata`` 평탄화.

    fastmcp 가 자동 생성하는 outputSchema 가 ``page_content: str`` + ``metadata: object``
    의 *상위 schema* 만 강타입화 — ``metadata`` 내부 키는 mode × block kind 조합으로
    동적이라 자유 dict 유지. 키 집합 SSOT 는 ``rhwp.integrations.langchain.HwpLoader``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_content: str = Field(
        description="Chunk text (마크다운 / 평문 / HTML — chunks mode 에 따름).",
    )
    metadata: dict[str, Any] = Field(
        description=(
            "Mode-dependent metadata. 공통 키 source / paragraph_count + mode 별 키 — "
            "paragraph: paragraph_index, ir-blocks: kind / section_idx / para_idx / "
            "char_start / char_end / image_uri / rows / cols / caption / scope. "
            "키 집합은 'rhwp.integrations.langchain.HwpLoader' 가 SSOT."
        ),
    )


# ^ Block kind enum — IR ``Block.kind`` Literal 과 1:1. "필터 미적용" 은 sentinel
#   대신 ``None`` (kind 인자 생략) 으로 표현 — JSON Schema enum 이 IR 에 실제로
#   존재하지 않는 "all" 값을 노출하지 않게 한다 (LLM 추론 정확도).
BlockKind = Literal[
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
]
# ^ scope 의 "all" 은 sentinel 이 아니라 "body + furniture" 합집합을 뜻하는
#   실제 의미 값 — IR ``HwpDocument.iter_blocks(scope=...)`` Literal 그대로.
BlockScope = Literal["body", "furniture", "all"]

# ^ HwpLoader.mode 어휘 그대로 — RAG 사용처가 CLI / MCP / 직접 SDK 사용 시
#   같은 정신 모델 공유. spec § 노출 도구 row chunks 에 명시.
ChunksMode = Literal["single", "paragraph", "ir-blocks"]


def parse_hwp_summary(path: str) -> ParseSummary:
    """HWP 또는 HWPX 파일을 파싱하여 기본 통계와 코어 버전을 반환.

    Args:
        path: HWP 또는 HWPX 파일 경로.

    Returns:
        섹션 / 문단 / 페이지 수 + ``rhwp-core`` 버전.
    """
    doc = rhwp.parse(path)
    return ParseSummary(
        sections=doc.section_count,
        paragraphs=doc.paragraph_count,
        pages=doc.page_count,
        rhwp_core_version=rhwp.rhwp_core_version(),
    )


def extract_text(path: str) -> str:
    """HWP 또는 HWPX 파일에서 단락별 평문을 ``\\n`` 으로 결합해 반환."""
    return rhwp.parse(path).extract_text()


def get_ir(path: str) -> HwpDocument:
    """HWP 또는 HWPX 파일을 파싱해 Document IR 전체를 ``HwpDocument`` 모델로 반환.

    fastmcp 가 자동으로 ``model_dump(mode="json")`` 직렬화하므로 wire format
    (``result.structured_content``) 은 v0.5.0 dict 출력과 byte-equal. ``result.data``
    는 typed BaseModel 인스턴스 (v0.5.1 신규 표면) — discriminated union block
    들의 강타입 access 가능. RAG 인덱싱 또는 LLM 후처리에 그대로 입력 가능.
    """
    return rhwp.parse(path).to_ir()


def to_markdown(path: str) -> str:
    """HWP 또는 HWPX 파일을 GFM (GitHub Flavored Markdown) 문자열로 변환.

    v0.4.0 view 렌더러 (``HwpDocument.to_markdown()``) 위 thin wrapper. 표는
    모든 셀 ``span == 1`` 일 때 GFM ``|...|`` 표, 병합 셀은 ``TableBlock.html``
    인라인 폴백. 이미지는 placeholder (``picture.image.uri`` pass-through),
    각주/미주는 본문 끝 정의 + 본문 paragraph 안 ``[^N]`` reference. 머리글 /
    꼬리말은 출력 미포함.
    """
    return rhwp.parse(path).to_ir().to_markdown()


def to_html(path: str, *, include_css: bool = False) -> str:
    """HWP 또는 HWPX 파일을 완전 HTML5 문서로 변환.

    v0.4.0 view 렌더러 (``HwpDocument.to_html()``) 위 thin wrapper. 표는
    ``TableBlock.html`` 그대로 inline (rowspan/colspan 보존). 이미지는
    ``picture.image.uri`` pass-through, 수식 디스플레이는 ``<div class="math">``,
    각주/미주는 본문 직후 ``<aside id="...">`` 정의 블록 + 본문 안 ``<sup>``
    인용 마커. 머리글/꼬리말은 출력 미포함.

    Args:
        path: HWP 또는 HWPX 파일 경로.
        include_css: True 면 ``<head>`` 안 embedded ``<style>`` 동봉 (브라우저
            표시용). 기본 False — RAG 임베딩 / 텍스트 추출 사용처용. v0.4.0 view
            API 와 동일하게 keyword-only — 호출 의미 명확화.
    """
    return rhwp.parse(path).to_ir().to_html(include_css=include_css)


def iter_blocks(
    path: str,
    kind: BlockKind | None = None,
    scope: BlockScope = "body",
    limit: int | None = None,
) -> list[Block]:
    """IR 블록을 ``kind`` / ``scope`` 로 필터링해 ``Block`` 리스트로 반환.

    재귀 진입 (``recurse=True``) 으로 컨테이너 블록 (TableCell / Footnote /
    Endnote / Caption) 내부까지 평탄화 — 결과는 RAG 청커가 그대로 소비할 수 있다.

    fastmcp 가 자동으로 각 ``Block`` 을 ``model_dump(mode="json")`` 직렬화하므로
    wire format 은 v0.5.0 dict 리스트와 byte-equal. ``Block`` 의 callable
    Discriminator + Tag 유니온 (11 변형) 이 outputSchema 의 ``oneOf`` 로 노출 —
    LLM 이 ``kind`` 별 필드 구조를 정확히 추론.

    Args:
        path: HWP 또는 HWPX 파일 경로.
        kind: 블록 종류 필터. ``None`` 또는 미지정이면 필터 미적용 (모든 종류).
        scope: 순회 범위. 본문만 (``"body"``), 장식만 (``"furniture"``),
            또는 둘 다 (``"all"``).
        limit: 최대 출고 개수. ``None`` 이면 전체.

    Returns:
        ``Block`` 인스턴스의 리스트 (Discriminator + Tag 유니온 변형 11 종).
    """
    doc = rhwp.parse(path)
    ir_doc = doc.to_ir()
    out: list[Block] = []
    for block in ir_doc.iter_blocks(scope=scope, recurse=True):
        if kind is not None and block.kind != kind:
            continue
        out.append(block)
        if limit is not None and len(out) >= limit:
            break
    return out


def chunks(
    path: str,
    mode: ChunksMode = "paragraph",
    size: int = 500,
    overlap: int = 50,
    include_furniture: bool = False,
) -> list[ChunkRecord]:
    """HWP/HWPX 를 RAG 청크 리스트로 변환 (LangChain ``RecursiveCharacterTextSplitter``).

    런타임에 ``langchain-text-splitters`` 를 lazy import — ``[mcp]`` extras 만
    설치한 사용자에게도 서버 기동 / 다른 도구 호출은 정상 동작 (mcp.md AC-7).
    chunks 도구만 호출 시점에 ImportError → fastmcp 가 ``ToolError`` 로 wrap
    → MCP 응답 ``CallToolResult(isError=True)``.

    fastmcp 가 자동으로 각 ``ChunkRecord`` 를 ``model_dump(mode="json")``
    직렬화하므로 wire format (``result.structured_content``) 은 v0.5.0 dict
    리스트와 byte-equal.

    Args:
        path: HWP 또는 HWPX 파일 경로.
        mode: LangChain Document 매핑 전략. CLI ``rhwp-py chunks --mode`` 와
            동일 어휘:

            - ``"single"``: 전체 문서를 단일 Document
            - ``"paragraph"``: 문단 텍스트별 Document (기본)
            - ``"ir-blocks"``: IR Block 단위 (표 구조 보존 + Provenance metadata)
        size: ``RecursiveCharacterTextSplitter`` 의 ``chunk_size`` (문자 수).
        overlap: 청크 간 오버랩 문자 수.
        include_furniture: ``mode="ir-blocks"`` 에서만 의미. True 면 본문 청크
            다음에 furniture (page_headers / page_footers / footnotes / endnotes)
            도 chunked Document 로 yield 하며, 각 chunk 의 ``metadata`` 에
            ``scope="furniture"`` 가 부여돼 RAG 가 body/furniture 를 분리 색인.
            다른 mode 에서는 무시 (``HwpLoader`` 와 동일 의미). 기본 False —
            RAG body 검색 오염 회피.

    Returns:
        ``ChunkRecord`` 인스턴스의 리스트 — LangChain Document 의 ``page_content``
        / ``metadata`` 평탄화.
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as e:
        raise ImportError(
            "rhwp-mcp `chunks` tool requires `langchain-text-splitters`. "
            'Install with: pip install "rhwp-python[mcp-chunks]"'
        ) from e

    # ^ HwpLoader 는 langchain-core 도 요구 — text-splitters 가 langchain-core 를
    #   transitive 로 끌어오므로 위 try/except 이 통과하면 같이 import 가능.
    from rhwp.integrations.langchain import HwpLoader

    loader = HwpLoader(path, mode=mode, include_furniture=include_furniture)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    split_docs = splitter.split_documents(docs)
    return [ChunkRecord(page_content=d.page_content, metadata=d.metadata) for d in split_docs]
