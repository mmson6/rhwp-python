"""rhwp-mcp 도구 함수 본체 — 순수 rhwp 로직, ``fastmcp`` import 없음.

``server.py`` 가 ``FastMCP.tool`` 데코레이터로 등록한다. 본 모듈은 도구가
``unsendable`` 안전 패턴 (sync handler 안에서 ``rhwp.parse`` → primitive 반환)
을 강제하기 위해 모두 sync 함수로 정의 — Document 가 thread 경계를 절대 안
넘는다. 자세한 배경은 ``docs/design/v0.5.0/mcp-research.md`` § 3.

- S1 — `parse_hwp_summary` / `extract_text` / `get_ir` / `iter_blocks` (코어 4)
- S2 — `to_markdown` / `to_html` (v0.4.0 view API thin wrapper)
- S3 — `chunks` (langchain-text-splitters extras gate, 후속 stage)
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
