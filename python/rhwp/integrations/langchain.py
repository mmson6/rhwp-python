"""LangChain DocumentLoader — HWP / HWPX 를 Document 리스트로 로딩.

설치:
    pip install rhwp[langchain]

사용:
    from rhwp.integrations.langchain import HwpLoader

    # 기본 — 전체 문서 하나로
    HwpLoader("report.hwp", mode="single").load()

    # 문단 단위 — 기본 텍스트만
    HwpLoader("report.hwp", mode="paragraph").load()

    # IR 블록 단위 — 구조화 정보 포함 (표/단락 혼합, Provenance 메타데이터)
    HwpLoader("report.hwp", mode="ir-blocks").load()

async 사용은 :meth:`aload` / :meth:`alazy_load` — 내부적으로 :func:`rhwp.aparse`
(aiofiles 기반 파일 I/O) 를 호출하므로 ``pip install rhwp[async]`` 필요.
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

import rhwp
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

LoadMode = Literal["single", "paragraph", "ir-blocks"]


class HwpLoader(BaseLoader):
    """HWP / HWPX 파일을 LangChain Document 리스트로 로딩.

    Args:
        path: HWP5 또는 HWPX 파일 경로.
        mode: 로딩 전략.
            - ``"single"``   : 전체 문서를 단일 Document 로 (기본)
            - ``"paragraph"``: 문단 텍스트별 Document (RAG 청킹용)
            - ``"ir-blocks"``: Document IR 의 Block 단위 — 표 구조 보존 + Provenance 메타데이터
        include_furniture: ``mode="ir-blocks"`` 일 때만 의미. True 면 본문 블록 다음에
            furniture (page_headers / page_footers / footnotes / endnotes) 도
            LangChain Document 로 추가 yield 한다 (각 Document metadata 에
            ``scope="furniture"``). 다른 모드에서는 무시. 기본 False — RAG body
            검색 오염 회피.

    Raises:
        ValueError: ``mode`` 값이 유효하지 않거나, 파일 포맷이 유효하지 않을 때.
        FileNotFoundError: 파일이 존재하지 않을 때.
        OSError: 그 외 I/O 오류.
        ImportError: async 변형 사용 시 ``aiofiles`` 미설치.
    """

    def __init__(
        self,
        path: str,
        *,
        mode: LoadMode = "single",
        include_furniture: bool = False,
    ) -> None:
        if mode not in ("single", "paragraph", "ir-blocks"):
            raise ValueError(
                f"mode 는 'single' / 'paragraph' / 'ir-blocks' 중 하나여야 합니다: {mode!r}"
            )
        self.path = path
        self.mode: LoadMode = mode
        self.include_furniture: bool = include_furniture

    # * Sync

    def load(self) -> list[Document]:
        # ^ lazy_load 를 전량 수집 — 결과 list 제공이 필요한 호출자용
        return list(self.lazy_load())

    def lazy_load(self) -> Iterator[Document]:
        """문서를 파싱한 뒤 Document 객체를 순차 yield.

        파싱 자체는 ``rhwp.parse()`` 특성상 한 번에 완료되지만, Document 객체
        생성은 지연된다. ``paragraph`` / ``ir-blocks`` 모드에서 전체 블록 리스트를
        메모리에 쌓지 않고 벡터DB 색인 등 스트리밍 소비자에게 바로 전달 가능.
        """
        yield from self._yield_documents(rhwp.parse(self.path))

    # * Async — rhwp.aparse (aiofiles 기반) 로 파일 I/O 만 async, 이후 yield 는 sync.
    #   Rust _Document 가 unsendable 이라 threadpool 오프로드 (to_thread) 는 panic —
    #   대신 event loop 스레드에서 Document 를 생성하여 같은 스레드 에서 소비한다.

    async def aload(self) -> list[Document]:
        """:meth:`load` 의 async 변형. ``aiofiles`` 로 파일 읽기만 async 처리."""
        return [doc async for doc in self.alazy_load()]

    async def alazy_load(self) -> AsyncIterator[Document]:
        """:meth:`lazy_load` 의 async 변형.

        파일 I/O 는 ``rhwp.aparse`` 가 aiofiles 로 async 처리, 이후 블록 순회는
        event loop 스레드에서 sync 실행 — 각 yield 사이에서 event loop 에 제어
        반환 (async for 는 자동으로 checkpoint 를 제공).
        """
        rhwp_doc = await rhwp.aparse(self.path)
        for doc in self._yield_documents(rhwp_doc):
            yield doc

    # * 공통 yield 로직 — sync/async 양쪽에서 공유

    def _yield_documents(self, rhwp_doc: rhwp.Document) -> Iterator[Document]:
        """이미 파싱된 rhwp.Document 에서 mode 별 LangChain Document 를 yield."""
        base_metadata = {
            "source": self.path,
            "section_count": rhwp_doc.section_count,
            "paragraph_count": rhwp_doc.paragraph_count,
            "page_count": rhwp_doc.page_count,
            "rhwp_version": rhwp.rhwp_core_version(),
        }

        if self.mode == "single":
            yield Document(
                page_content=rhwp_doc.extract_text(),
                metadata=base_metadata,
            )
            return

        if self.mode == "paragraph":
            # * paragraph 모드 — 빈 문단 제외 + 원본 인덱스 보존
            for idx, para in enumerate(rhwp_doc.paragraphs()):
                if para.strip():
                    yield Document(
                        page_content=para,
                        metadata={**base_metadata, "paragraph_index": idx},
                    )
            return

        # * ir-blocks 모드 — Document IR Block 을 LangChain Document 로 매핑
        ir = rhwp_doc.to_ir()
        for block in ir.iter_blocks(scope="body", recurse=True):
            content, extra_meta = _block_to_content_and_meta(block)
            if not content.strip():
                # ^ 공백만 있는 블록도 RAG 노이즈이므로 제외
                continue
            yield Document(
                page_content=content,
                metadata={**base_metadata, **extra_meta},
            )

        # * include_furniture=True 면 page_headers/footers/footnotes/endnotes 도 yield.
        #   각 Document 메타에 ``scope="furniture"`` — RAG 가 body/furniture 분리 색인.
        if not self.include_furniture:
            return
        for block in ir.iter_blocks(scope="furniture", recurse=True):
            content, extra_meta = _block_to_content_and_meta(block)
            if not content.strip():
                continue
            yield Document(
                page_content=content,
                metadata={**base_metadata, **extra_meta, "scope": "furniture"},
            )


def _block_to_content_and_meta(block: Block) -> tuple[str, dict[str, Any]]:
    """Block → (page_content, block-specific metadata)."""
    if isinstance(block, ParagraphBlock):
        return block.text, {
            "kind": "paragraph",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "char_start": block.prov.char_start,
            "char_end": block.prov.char_end,
        }
    if isinstance(block, TableBlock):
        # ^ HTML 을 page_content 로 — LLM 에 구조 정보 제공. 검색 색인용 평문은 메타로 노출.
        #   caption 은 v0.2.0 호환 평문 우선, 없으면 caption_block.blocks 평문 폴백
        #   (PictureBlock 분기와 대칭 — caption 정보 손실 회피).
        caption_text = block.caption or (
            _caption_plain_text(block.caption_block) if block.caption_block is not None else None
        )
        return block.html, {
            "kind": "table",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "rows": block.rows,
            "cols": block.cols,
            "text": block.text,
            "caption": caption_text,
        }
    if isinstance(block, PictureBlock):
        # ^ caption.blocks 평문 우선 (S3 구조화), 없으면 description (S1 호환).
        #   image meta 는 RAG 가 picture 를 별도 색인할 때 활용. 빈 content 는
        #   lazy_load 상위에서 strip 후 skip.
        caption_text = _caption_plain_text(block.caption) if block.caption is not None else ""
        content = caption_text or (block.description or "")
        meta: dict[str, Any] = {
            "kind": "picture",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
        }
        if block.image is not None:
            meta["image_uri"] = block.image.uri
            meta["image_mime"] = block.image.mime_type
        return content, meta
    if isinstance(block, FormulaBlock):
        # ^ text_alt (raw script 의 평문 근사) 우선, 없으면 raw script 자체.
        #   사용자가 LaTeX/MathML 변환을 외부에서 적용한 경우 script_kind 가 갱신됨
        return block.text_alt or block.script, {
            "kind": "formula",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "script_kind": block.script_kind,
            "inline": block.inline,
        }
    if isinstance(block, (FootnoteBlock, EndnoteBlock)):
        # ^ 각주/미주 본문 paragraphs 의 평문을 합쳐 content 로. marker_prov 는 본문 인용
        #   위치를 별도 메타로 노출 — RAG 가 "이 각주는 어디 paragraph 에서 인용됐나" 역추적
        text_parts = [b.text for b in block.blocks if isinstance(b, ParagraphBlock) and b.text]
        kind_label = "footnote" if isinstance(block, FootnoteBlock) else "endnote"
        return "\n".join(text_parts), {
            "kind": kind_label,
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "number": block.number,
            "marker_section_idx": block.marker_prov.section_idx,
            "marker_para_idx": block.marker_prov.para_idx,
        }
    if isinstance(block, ListItemBlock):
        # ^ marker + " " + text 로 합쳐 content — RAG 가 항목 단위로 색인 가능.
        #   level/enumerated 는 청킹 시 hierarchy 보존 단서로 사용.
        content = f"{block.marker} {block.text}".strip()
        return content, {
            "kind": "list_item",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "level": block.level,
            "enumerated": block.enumerated,
        }
    if isinstance(block, CaptionBlock):
        # ^ 단독 CaptionBlock 은 거의 없음 (Picture/Table 자식). 명시적으로 body 에
        #   넣은 사용자 경로만 — direction 메타로 노출.
        return _caption_plain_text(block), {
            "kind": "caption",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "direction": block.direction,
        }
    if isinstance(block, TocBlock):
        # ^ entries 의 text 들을 개행 결합. v0.3.0 entries 는 빈 리스트가 일반적
        #   (TOC entry 추출은 v0.4.0+) — 빈 content 는 lazy_load 상위에서 skip.
        toc_text = "\n".join(e.text for e in block.entries if e.text)
        return toc_text, {
            "kind": "toc",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "entry_count": len(block.entries),
        }
    if isinstance(block, FieldBlock):
        # ^ cached_value 가 있으면 그것이 content (예: 자동 날짜). raw_instruction 은
        #   round-trip 보존용으로 메타에. v0.3.0 은 cached_value 가 항상 None 이므로
        #   대부분 빈 content — lazy_load 상위에서 skip 됨.
        return block.cached_value or "", {
            "kind": "field",
            "section_idx": block.prov.section_idx,
            "para_idx": block.prov.para_idx,
            "field_kind": block.field_kind,
            "raw_instruction": block.raw_instruction,
        }
    # 새 Block variant 가 추가되면 그 variant 의 elif 를 이 assert 보다 위에 먼저
    # 추가해야 한다. 그러지 않으면 AssertionError 로 fail-fast (silent fallback 방지)
    assert isinstance(block, UnknownBlock)
    return "", {
        "kind": block.kind,
        "section_idx": block.prov.section_idx,
        "para_idx": block.prov.para_idx,
    }


def _caption_plain_text(caption: CaptionBlock) -> str:
    """CaptionBlock.blocks 의 텍스트 표현을 개행 결합 (S3 신규 헬퍼).

    포함 대상: ParagraphBlock.text + FormulaBlock.text_alt|script + FieldBlock.cached_value.
    캡션 안의 수식·필드도 평문 흐름의 일부 (spec § 5 "캡션 안의 인라인 수식·필드도
    자연스럽게 표현") — RAG 색인에 자연 포함. 표/그림 등 구조 블록은 별도 색인.
    """
    parts: list[str] = []
    for b in caption.blocks:
        if isinstance(b, ParagraphBlock) and b.text:
            parts.append(b.text)
        elif isinstance(b, FormulaBlock):
            text = b.text_alt or b.script
            if text:
                parts.append(text)
        elif isinstance(b, FieldBlock) and b.cached_value:
            parts.append(b.cached_value)
    return "\n".join(parts)
