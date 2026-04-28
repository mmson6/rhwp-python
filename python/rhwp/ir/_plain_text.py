"""Block 컨테이너 → 평문 변환 헬퍼 — LangChain integration / CLI 공유 SSOT.

캡션·각주·미주 같은 컨테이너 블록의 inner blocks 를 평문으로 합칠 때 사용한다.
RAG 색인에 자연 포함되는 인라인-스러운 블록만 처리한다.

처리 대상 (각 블록의 평문 표현):

- ``ParagraphBlock`` → ``text``
- ``ListItemBlock`` → ``"{marker} {text}"`` — 목록 항목 단위 색인
- ``FormulaBlock`` → ``text_alt`` 우선, 없으면 ``script`` (RAG 폴백)
- ``FieldBlock`` → ``cached_value`` (없으면 None)

처리 안 함 (별도 블록으로 색인되어야 하는 구조 블록):

- ``TableBlock`` / ``PictureBlock`` / ``TocBlock`` / 중첩 컨테이너 등
"""

from rhwp.ir.nodes import (
    Block,
    FieldBlock,
    FormulaBlock,
    ListItemBlock,
    ParagraphBlock,
)


def block_inline_text(block: Block) -> str | None:
    """인라인-스러운 단일 Block → 평문. 빈 문자열·해당 없는 타입은 None.

    None 분기로 호출자가 ``if text:`` 로 빈 텍스트 / 비-인라인 블록을 함께 skip
    가능하다.
    """
    if isinstance(block, ParagraphBlock):
        return block.text or None
    if isinstance(block, ListItemBlock):
        return f"{block.marker} {block.text}".strip() or None
    if isinstance(block, FormulaBlock):
        return block.text_alt or block.script or None
    if isinstance(block, FieldBlock):
        return block.cached_value or None
    return None


def join_inline_blocks(blocks: list[Block]) -> str:
    r"""블록 리스트의 인라인 텍스트를 ``\n`` 로 결합.

    캡션·각주·미주 본문 평문화에 사용. ``block_inline_text`` 가 None 을 반환한
    (비-인라인 또는 빈) 블록은 skip — 빈 줄 노이즈 회피.
    """
    parts = [text for b in blocks if (text := block_inline_text(b))]
    return "\n".join(parts)
