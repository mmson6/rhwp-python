"""rhwp-mcp 도구 함수 본체 — 순수 rhwp 로직, ``fastmcp`` import 없음.

``server.py`` 가 ``FastMCP.tool`` 데코레이터로 등록한다. 본 모듈은 도구가
``unsendable`` 안전 패턴 (sync handler 안에서 ``rhwp.parse`` → primitive 반환)
을 강제하기 위해 모두 sync 함수로 정의 — Document 가 thread 경계를 절대 안
넘는다. 자세한 배경은 ``docs/design/v0.5.0/mcp-research.md`` § 3.

S1 — 4 개 도구 (`parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks`).
S2 (`to_markdown` / `to_html`), S3 (`chunks`) 는 후속 stage 에서 추가.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

import rhwp


class ParseSummary(BaseModel):
    """``parse_hwp_summary`` 의 출력 스키마 — LLM 이 필드 의미를 정확히 추론하도록 Pydantic 모델."""

    sections: int = Field(description="문서 섹션 수.")
    paragraphs: int = Field(description="전체 섹션을 통틀어 누적된 문단 수.")
    pages: int = Field(description="페이지네이션 후 페이지 수.")
    rhwp_core_version: str = Field(description="파싱에 사용된 상류 rhwp Rust 코어 버전.")


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


def get_ir(path: str) -> dict[str, Any]:
    """HWP 또는 HWPX 파일을 파싱해 Document IR 전체를 JSON 직렬화 가능한 dict 로 반환.

    Pydantic ``HwpDocument.model_dump(mode="json")`` 결과 — discriminated union
    block 들이 모두 평탄화된 형태. RAG 인덱싱 또는 LLM 후처리에 그대로 입력 가능.
    """
    return rhwp.parse(path).to_ir().model_dump(mode="json")


def iter_blocks(
    path: str,
    kind: BlockKind | None = None,
    scope: BlockScope = "body",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """IR 블록을 ``kind`` / ``scope`` 로 필터링해 dict 리스트로 반환.

    재귀 진입 (``recurse=True``) 으로 컨테이너 블록 (TableCell / Footnote /
    Endnote / Caption) 내부까지 평탄화 — 결과는 RAG 청커가 그대로 소비할 수 있다.

    Args:
        path: HWP 또는 HWPX 파일 경로.
        kind: 블록 종류 필터. ``None`` 또는 미지정이면 필터 미적용 (모든 종류).
        scope: 순회 범위. 본문만 (``"body"``), 장식만 (``"furniture"``),
            또는 둘 다 (``"all"``).
        limit: 최대 출고 개수. ``None`` 이면 전체.

    Returns:
        ``Block.model_dump(mode="json")`` dict 의 리스트.
    """
    doc = rhwp.parse(path)
    ir_doc = doc.to_ir()
    out: list[dict[str, Any]] = []
    for block in ir_doc.iter_blocks(scope=scope, recurse=True):
        if kind is not None and block.kind != kind:
            continue
        out.append(block.model_dump(mode="json"))
        if limit is not None and len(out) >= limit:
            break
    return out
