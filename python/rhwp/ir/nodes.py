"""rhwp.ir.nodes — Document IR Pydantic 모델 (schema_version "1.1").

재귀 구조 (``TableCell.blocks`` → ``Block`` → ``TableBlock.cells`` → ``TableCell``,
``FootnoteBlock.blocks`` / ``EndnoteBlock.blocks`` / ``CaptionBlock.blocks`` →
``Block``) 는 문자열 전방 참조 + 파일 하단 ``model_rebuild()`` 로 해소한다.

스키마 버전 1.1 (v0.3.0) — v1.0 의 paragraph/table 위에 picture (S1), formula /
footnote / endnote (S2), list_item / caption / toc / field (S3) 가 차례로 추가된다.
"""

import warnings
from collections.abc import Iterator, Sequence
from typing import Annotated, Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    StringConstraints,
    Tag,
    field_validator,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "Block",
    "CaptionBlock",
    "DocumentMetadata",
    "DocumentSource",
    "EndnoteBlock",
    "FieldBlock",
    "FieldKind",
    "FootnoteBlock",
    "FormulaBlock",
    "Furniture",
    "HwpDocument",
    "ImageRef",
    "InlineRun",
    "ListItemBlock",
    "ParagraphBlock",
    "PictureBlock",
    "Provenance",
    "SchemaVersion",
    "Section",
    "TableBlock",
    "TableCell",
    "TocBlock",
    "TocEntryBlock",
    "UnknownBlock",
]


CURRENT_SCHEMA_VERSION: Final = "1.1"
_SCHEMA_VERSION_PATTERN: Final = r"^\d+\.\d+(\.\d+)?$"

SchemaVersion = Annotated[
    str,
    StringConstraints(pattern=_SCHEMA_VERSION_PATTERN, strict=True),
]


# ^ 상류 ``FieldType`` 14 종 + ``"unknown"`` 안전판. ``"calc"`` 는 상류
#   ``FieldType::Formula`` 매핑 — "수식 (eqed)" 와 이름 충돌 회피용 별도 어휘.
#   미래에 상류가 새 FieldType 을 추가하면 매퍼는 일단 ``field_kind="unknown"``
#   + ``field_type_code=<raw>`` 로 출고하고, 다음 MINOR 에서 Literal 확장.
FieldKind = Literal[
    "date",
    "doc_date",
    "path",
    "bookmark",
    "mailmerge",
    "crossref",
    "calc",
    "clickhere",
    "summary",
    "userinfo",
    "hyperlink",
    "memo",
    "private_info",
    "toc",
    "unknown",
]


class Provenance(BaseModel):
    """블록의 원본 문서 내 위치. 다운스트림 청커가 원본을 역추적 가능하게 한다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_idx: int
    para_idx: int
    char_start: int | None = Field(
        default=None,
        description=(
            "Start character index (Unicode codepoints, 0-indexed). "
            "Compatible with Python str slicing: text[char_start:char_end]."
        ),
    )
    char_end: int | None = Field(
        default=None,
        description="End character index (Unicode codepoints, 0-indexed, exclusive).",
    )
    page_range: tuple[int, int] | None = Field(
        default=None,
        description=(
            "Inclusive (start_page, end_page). 렌더 단계에서만 계산되므로 파싱 경로는 None 을 출고한다."
        ),
    )


class InlineRun(BaseModel):
    """서식이 동일한 연속 문자 런.

    bold/italic/underline/strikethrough/href/ruby 외의 서식 속성 (폰트, 크기,
    색상 등) 은 ``raw_style_id`` 로 escape 된다 — 상류 ``doc_info`` 스타일 인덱스.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    href: str | None = None
    ruby: str | None = None
    raw_style_id: int | None = Field(
        default=None,
        description=(
            "Upstream doc_info 스타일 인덱스. 폰트/크기/색상 등 non-binary 서식을 escape 한다. "
            "None 은 char_shape 레코드가 없는 손상/비정상 입력 방어 경로 — "
            "정상 HWP 는 모든 런이 char_shape 에 대응되어 항상 값이 채워진다."
        ),
    )
    color_rgb: int | None = Field(
        default=None,
        description=(
            "Text colour as 0x00RRGGBB (COLORREF byte-order normalised by Rust patch). "
            "None means black or no explicit colour. Only populated by patched wheel."
        ),
    )


class DocumentSource(BaseModel):
    """문서 출처 — RAG 응답 역추적 시 "이 답이 어느 파일에서 나왔나" 에 응답한다.

    스키마는 ``uri`` 형식을 강제하지 않으므로 소비자가 file://, https://, 혹은
    ``mem://{hash}`` 같은 custom 스킴으로 정규화할 수 있다. 향후 ``format``,
    ``bytes_size``, ``sha256`` 등 재현성 필드는 기본값 있는 옵셔널로만 추가 —
    이 경로는 기존 JSON 과 MINOR 호환 유지.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    uri: str = Field(
        description=(
            "파일 시스템 경로, URL, 혹은 소비자 정의 식별자. "
            "RFC 3986 URI reference 로 해석 가능한 문자열이면 충분하다."
        ),
    )


class DocumentMetadata(BaseModel):
    """문서 레벨 메타데이터. 시각은 ISO 8601 문자열로 출고한다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str | None = None
    author: str | None = None
    creation_time: str | None = None
    modification_time: str | None = None


class Section(BaseModel):
    """HWP 구역 식별자. 용지·단·헤더 레퍼런스 등 상세 속성은 향후 추가된다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_idx: int


class ParagraphBlock(BaseModel):
    """단락 블록. 서식 런 리스트 + 평탄 텍스트 파생 필드를 병기한다.

    ``text`` 는 ``inlines`` 의 ``text`` 필드를 이어붙인 결과 — LLM 에 넘기는
    평문화 경로. 원본 서식 보존이 필요한 소비자만 ``inlines`` 를 직접 순회한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["paragraph"] = "paragraph"
    text: str = ""
    inlines: list[InlineRun] = Field(default_factory=list)
    prov: Provenance


class ListItemBlock(BaseModel):
    """목록 항목 — HWP ``ParaShape`` 의 ``head_type`` 가 비-None 인 단락.

    HWP 상류는 list group 컨테이너가 없다 (``ParaShape.head_type`` 가
    Number/Bullet/Outline 인 단락이 곧 list item) — group container 는 도입하지
    않고 평면 (``level + marker + enumerated``) 으로 표현. RAG 청킹 시 항목 단위
    검색에 그대로 매핑.

    ``marker`` 는 v0.3.0 단순 정책: ``"•"`` (bullet) / ``"1."`` (number/outline).
    상류 ``Numbering.level_formats`` lookup 으로 정확한 마커 (예: ``"가."``,
    ``"(a)"``) 추출은 v0.4.0+ 에서 검토 — 현 시점은 placeholder 만.

    ``text`` 는 마커 제외 본문 (``ParagraphBlock`` 과 동일) — 마커는
    ``marker`` 필드로 별도. ``"1. 제목"`` 이 아니라 ``marker="1."``,
    ``text="제목"`` 형태.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["list_item"] = "list_item"
    text: str = ""
    inlines: list[InlineRun] = Field(default_factory=list)
    enumerated: bool = Field(
        default=False,
        description="True: 번호 매김 (1./가./i. 등), False: 글머리표 (•/■/▶ 등).",
    )
    marker: str = Field(
        default="-",
        description=(
            '표시 마커 placeholder. v0.3.0 은 ``"•"`` / ``"1."`` 만 출고 — '
            "정확 마커는 상류 Numbering lookup 필요해 v0.4.0+ 검토."
        ),
    )
    level: int = Field(
        default=0,
        description=(
            "0-indexed nesting depth. 상류 ``ParaShape.para_level`` (0~6, "
            "1~7 수준 표시) 를 그대로 매핑."
        ),
    )
    prov: Provenance


class ImageRef(BaseModel):
    """이미지 참조 — binary 자체는 IR JSON 에 inline 되지 않는다.

    URI 스킴:

    - ``bin://<bin_data_id>`` (기본): 상류 ``Picture.image_attr.bin_data_id`` 그대로.
      ``Document.bytes_for_image(picture)`` 로 raw bytes 해석.
    - ``data:image/...;base64,...``: embedded 모드 (v0.4.0+ opt-in 검토)
    - ``file://path``: external 모드 (v0.4.0+ opt-in 검토)

    ``uri`` 는 strict 검증 회피를 위해 plain ``str`` — JSON Schema strict mode 가
    ``format: uri`` 를 거부하는 경우가 있고, ``bin://`` / ``data:`` 모두 허용해야 하므로.
    URL 검증은 사용자 책임.

    width/height/dpi 는 v0.3.0 S1 에서 항상 ``None`` — 상류 Picture 가 픽셀
    dimension 을 직접 노출하지 않으며 (border 좌표만 노출) HWPUNIT 계산은
    v0.4.0+ 에서 검토.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    uri: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    dpi: int | None = None


class CaptionBlock(BaseModel):
    """캡션 블록 — 그림/표 등에 부착되는 보조 설명.

    HWP 는 ``Picture.caption: Option<Caption>`` / ``Table.caption: Option<Caption>``
    으로 항상 1:1 부착 관계 — 캡션은 부모 블록의 필드로 컨테인먼트 (ref-id 미도입).
    Azure DI / Docling 의 string-ref 패턴은 1:N 주소가 가능하지만 HWP 사용처에서
    이점이 없고 소비자가 JSON-Pointer resolver 를 구현해야 하므로 거부 (spec § 5).

    ``blocks`` 가 재귀 ``Block`` 리스트 — 캡션 안의 인라인 수식·필드도 자연스럽게
    표현 (예: ``"<그림 1> 회로도 ${}^{2}$"`` 같은 캡션).

    ``direction`` 은 캡션 배치 방향. 상류 ``CaptionDirection`` (Left/Right/Top/Bottom)
    을 lowercase Literal 로 매핑. 기본값 ``"bottom"`` 은 HWP 기본 + Docling 관례
    일치.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["caption"] = "caption"
    blocks: list["Block"] = Field(default_factory=list)
    direction: Literal["top", "bottom", "left", "right"] = "bottom"
    prov: Provenance


class PictureBlock(BaseModel):
    """그림 블록 — HWP ``Control::Picture``.

    ``image is None`` 은 명시적 broken reference — 상류 ``Picture.image_attr.bin_data_id``
    가 0 (미할당) 인 케이스만 해당. ``bin_data_id`` 가 0 이 아니어도 실제 binary
    lookup 이 실패할 수 있다 (Link 타입이거나 bin_data_content 누락) — 이 경우
    ImageRef 는 ``mime_type="application/octet-stream"`` 으로 출고되고 실패는
    ``Document.bytes_for_image`` 호출 시점에 ValueError 로 표면화된다 (forensics
    위해 bin_data_id 자체는 URI 에 보존).

    ``caption`` 은 v0.3.0 S3 부터 채워지는 구조화 캡션 — 부모 ``PictureBlock`` 의
    필드로 컨테인먼트 (ref-id 없이 직접 연결, spec § 5).

    ``description`` 은 HWP 의 alt-text 슬롯 — caption paragraph 의 평문 fallback
    (S1 호환 보존). v0.4.0+ 에서 caption 충실하게 채워지면 description 은 deprecate
    검토.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["picture"] = "picture"
    image: ImageRef | None = None
    caption: "CaptionBlock | None" = Field(
        default=None,
        description=(
            "구조화 캡션 — v0.3.0 S3 부터 채워짐. ``blocks`` 안에 표/수식/필드도 "
            "재귀 표현. None 은 캡션 부재 (HWP Picture.caption == None)."
        ),
    )
    description: str | None = Field(
        default=None,
        description=(
            "HWP 의 alt-text — 상류 caption paragraph 평문 fallback (S1 보존). "
            "구조화 캡션이 필요하면 ``caption`` 필드 사용."
        ),
    )
    prov: Provenance


class FormulaBlock(BaseModel):
    """수식 블록 — HWP ``Control::Equation``.

    HWP 수식은 자체 스크립트 (``script``) 로 저장된다 (예: ``"1 over 2 + sqrt{x^2}"``).
    HWP equation script → LaTeX/MathML 자동 변환은 공개 도구 부재로 v0.3.0 미제공
    (spec § 비목표). ``script_kind="hwp_eq"`` 로 raw 출고 → 사용자가 외부 변환 후
    ``model_copy(update={"script": tex, "script_kind": "latex"})`` 로 재구성 가능.

    ``text_alt`` 는 RAG 폴백 — 단순 정규화 (``over`` → ``/``, ``sqrt{...}`` → ``√(...)``)
    까지만 적용. 실패 시 None.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["formula"] = "formula"
    script: str
    script_kind: Literal["hwp_eq", "latex", "mathml"] = "hwp_eq"
    text_alt: str | None = Field(
        default=None,
        description=(
            "평문 근사 — RAG fallback. ``script`` 의 사람이 읽을 수 있는 형태 "
            "(``over`` → ``/`` 등) 를 단순 정규화. 실패 시 None."
        ),
    )
    inline: bool = Field(
        default=False,
        description="True: 본문 인라인 수식, False: 별도 디스플레이 수식.",
    )
    prov: Provenance


class FootnoteBlock(BaseModel):
    """각주 블록 — HWP ``Control::Footnote``.

    각주 본문은 ``furniture.footnotes`` 로 라우팅되어 RAG 의 body 검색을 오염시키지
    않는다. ``marker_prov`` 는 본문 인용 마커 (``…기존 연구[3]…`` 의 ``[3]`` 위치) 의
    parent paragraph (section_idx, para_idx) 를 가리킨다 — 정확한 char_offset 까지는
    상류 ``field_ranges`` 매핑이 필요해 v0.4.0+ 검토. ``prov`` 는 각주 본문 자체의
    위치 = 마커가 등장한 paragraph 와 동일 (각주는 그 paragraph 에서 파생).

    ``blocks`` 가 재귀 ``Block`` 리스트라 각주 본문 안의 표·그림·수식도 자연 지원.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["footnote"] = "footnote"
    number: int = Field(description="표시 번호 (1, 2, 3, ...).")
    blocks: list["Block"] = Field(default_factory=list)
    marker_prov: Provenance = Field(
        description="본문 인용 마커 위치 — RAG 가 각주가 어디서 인용됐는지 역추적.",
    )
    prov: Provenance


class EndnoteBlock(BaseModel):
    """미주 블록 — HWP ``Control::Endnote``.

    각주와 같은 구조지만 배치가 다르다 (각주: 페이지 하단, 미주: 문서/구역 끝).
    HWP 가 별도 struct 로 분리하므로 IR 도 분리 — 통합 시 정보 손실.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["endnote"] = "endnote"
    number: int
    blocks: list["Block"] = Field(default_factory=list)
    marker_prov: Provenance
    prov: Provenance


class TocEntryBlock(BaseModel):
    """목차 항목 — ``TocBlock.entries`` 안에서만 살아 있는 leaf type.

    Block 유니온 멤버가 아니다 (``TableCell`` 과 같은 패턴) — ``iter_blocks`` 는
    ``TocBlock`` 만 yield 하고, 항목 순회는 ``toc.entries`` 직접 접근.

    ``cached_page`` 는 HWP 가 저장 시점에 박제한 페이지 번호 — 문서가 편집된 후에
    heading 이 이동하면 stale 가능 (`is_stale=True`). ``is_stale`` 정확 검출은
    heading hierarchy 와 cached text 비교 + bookmark resolution 필요 — v0.3.0 은
    cached value 만 노출하고 stale 검출은 v0.4.0+ 에 위임 (spec § 6 결정).

    ``target_section_idx`` 는 raw bookmark 이름 → section 인덱스 resolution 결과.
    상류 bookmark resolver 가 필요해 v0.3.0 은 항상 None — raw
    ``target_bookmark_name`` 만 보존.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["toc_entry"] = "toc_entry"
    text: str
    level: int = Field(
        default=1,
        description="1-indexed (h1, h2, h3, ...) — TOC 표시 레벨.",
    )
    target_bookmark_name: str | None = Field(
        default=None,
        description="HWP bookmark 이름 (raw) — v0.4.0+ 의 resolver 입력.",
    )
    target_section_idx: int | None = Field(
        default=None,
        description="resolved section idx — v0.3.0 은 항상 None (resolver 미도입).",
    )
    cached_page: int | None = Field(
        default=None,
        description=(
            "저장 시점 페이지 번호 (HWP frozen at save). 편집 후 heading 이 "
            "이동하면 stale 가능. 정확 navigation 은 heading hierarchy 쪽."
        ),
    )
    is_stale: bool = Field(
        default=False,
        description=(
            "cached info ≠ 현재 heading 일치 여부. v0.3.0 은 항상 False — 정확 "
            "검출은 v0.4.0+ 에서 (spec § 6)."
        ),
    )
    prov: Provenance


class TocBlock(BaseModel):
    """목차 블록 — HWP ``Control::Field`` with ``FieldType::TableOfContents``.

    HWP TOC 는 frozen at save time — 소비자가 신뢰할 수 있는 navigation 은
    (있다면) heading hierarchy 쪽이며 TOC 는 사람이 마지막에 본 표시 그대로의
    스냅샷이다.

    v0.3.0 S3 매퍼는 TOC field 검출만 수행 — 항목 추출은 v0.4.0+ 에서 검토
    (spec § 6 결정). 따라서 v0.3.0 출고 시 ``entries`` 는 빈 리스트가 일반적.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["toc"] = "toc"
    entries: list[TocEntryBlock] = Field(default_factory=list)
    prov: Provenance


class FieldBlock(BaseModel):
    """필드 컨트롤 — HWP ``Control::Field`` (TOC 제외 13 종 + Unknown).

    상류 ``FieldType`` 14 종 → 닫힌 ``FieldKind`` Literal 매핑. ``TableOfContents``
    는 별도 ``TocBlock`` 으로 라우팅되므로 ``FieldBlock`` 에는 ``"toc"`` 가
    원칙적으로 등장 안 함 — Literal 로 보존만 하고 (사용자가 직접 구성 시 호환).

    ``InlineRun.href`` 와의 중복: HWP ``Hyperlink`` / ``Bookmark`` Field 는 본문
    InlineRun 의 ``href`` 로 표현될 수도 있지만 v0.3.0 은 모든 Field control 을
    별도 FieldBlock 으로 emit 한다 — InlineRun.href 자동 채움 path 는 미구현.

    ``raw_instruction`` 은 round-trip 보존용 — Word ``<w:instrText>`` 와 같은 raw
    명령 문자열. v0.3.0 소비자는 보통 ``cached_value`` 만 사용하지만, 미래
    writeback 시 raw 가 필요.

    ``field_type_code`` 는 forward-compat — 상류가 새 FieldType 을 추가하면
    매퍼는 ``field_kind="unknown"`` + ``field_type_code=<raw>`` 로 출고하고,
    다음 MINOR (v0.4.0) 에서 Literal 확장.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["field"] = "field"
    field_kind: FieldKind = "unknown"
    cached_value: str | None = Field(
        default=None,
        description='저장 시점 표시 값 (예: ``"2026-04-26"``). 동적 필드는 stale 가능.',
    )
    raw_instruction: str | None = Field(
        default=None,
        description="HWP field command (Word ``<w:instrText>`` 대응) — round-trip 보존.",
    )
    field_type_code: int | None = Field(
        default=None,
        description="미지의 raw 코드 — 상류 FieldType 추가 시 forward-compat.",
    )
    prov: Provenance


def _unknown_kind_schema_extra(schema: dict[str, Any]) -> None:
    """``UnknownBlock.kind`` 의 JSON Schema 에 ``not.enum`` 추가.

    callable 로 분리한 이유 — ``_KNOWN_KINDS`` 가 ``UnknownBlock`` 정의 *뒤* 에
    위치하므로 클래스 정의 시점에는 미정의. 함수는 호출 시점 (schema 생성
    시점) 에만 ``_KNOWN_KINDS`` 평가하므로 모듈 fully-loaded 상태 보장.

    ``Field(json_schema_extra=callable)`` 표준 hook — schema dict 를 in-place 변경.
    """
    schema["not"] = {"enum": sorted(_KNOWN_KINDS)}


class UnknownBlock(BaseModel):
    """Forward-compatibility catch-all.

    Pydantic V2 의 기본 string discriminator 는 미지의 ``kind`` 를 만나면
    ``union_tag_invalid`` 로 문서 전체 파싱을 거부한다. callable Discriminator
    로 미지 ``kind`` 를 본 variant 로 라우팅하여, 나중에 새로운 블록 타입이
    추가되어도 구 버전 소비자가 읽기-불가 상태가 되지 않게 한다.

    소비자는 ``case UnknownBlock(): skip`` 패턴을 사용한다. ``assert_never``
    패턴은 새 variant 추가 시 빌드가 깨지므로 **사용 금지**.
    """

    # ^ extra="allow" — 미지 variant 의 payload 를 보존해 소비자가 최소한 로그/raw 접근 가능
    model_config = ConfigDict(extra="allow", frozen=True)

    kind: Annotated[
        str,
        Field(
            description=(
                "Unknown block kind — must NOT match any known block kind. "
                "callable Discriminator (`_block_discriminator`) 가 미지 kind 만 "
                "본 variant 로 라우팅하므로 SSOT 와 정합."
            ),
            json_schema_extra=_unknown_kind_schema_extra,
        ),
    ]
    prov: Provenance


class TableCell(BaseModel):
    """표 셀. ``blocks`` 가 재귀 ``Block`` 리스트라 중첩 표를 자연 지원한다.

    ``role`` 어휘는 DocLayNet 파생. ``"layout"`` 은 구조 유지용 비의미 셀
    (병합된 빈 영역 등) — LLM 이 "데이터 없음이 아닌 레이아웃 요소" 로 인식하도록 태깅한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    grid_index: int = Field(
        description=(
            "Anchor cell position in row-major flat index (row * table.cols + col). "
            "Not a reverse-lookup key; span-covered positions do not appear as separate cells."
        ),
    )
    role: Literal["data", "column_header", "row_header", "layout"] = Field(
        default="data",
        description=(
            "DocLayNet-derived cell role. Current producer maps HWP 'is_header' to "
            "'column_header' and tags merged-empty cells as 'layout'; 'row_header' "
            "is reserved for producers that can distinguish row vs column headers."
        ),
    )
    blocks: list["Block"] = Field(default_factory=list)


class TableBlock(BaseModel):
    """표 블록. 단일 표현으로 RAG 품질 최대화 불가 → 3중 표현 병기.

    - ``cells`` : 프로그래매틱 접근 (SQL 생성, 셀 순회)
    - ``html``  : LLM 에 제공, rowspan/colspan 보존 (HtmlRAG 호환)
    - ``text``  : 단순 검색·diff 용 폴백 (행은 개행, 셀은 탭 구분)

    ``caption`` (str) 은 v0.2.0 호환 평문 슬롯 — caption_block 의 첫 paragraph
    텍스트 fallback. 구조화 캡션이 필요하면 ``caption_block`` 사용.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["table"] = "table"
    rows: int
    cols: int
    cells: list[TableCell] = Field(default_factory=list)
    html: str = ""
    text: str = ""
    caption: str | None = Field(
        default=None,
        description=(
            "v0.2.0 호환 평문 캡션 — ``caption_block.blocks`` 첫 ParagraphBlock 의 "
            "평문이면 일관성 유지. 구조화 캡션은 ``caption_block`` 사용."
        ),
    )
    caption_block: "CaptionBlock | None" = Field(
        default=None,
        description=(
            "v0.3.0 S3 신규 — 구조화 캡션. v0.2.0 ``caption: str`` 필드는 그대로 "
            "유지하고 옵셔널 신설."
        ),
    )
    prov: Provenance


_KNOWN_KINDS: Final = frozenset(
    {
        # ^ v0.2.0
        "paragraph",
        "table",
        # ^ v0.3.0 S1
        "picture",
        # ^ v0.3.0 S2
        "formula",
        "footnote",
        "endnote",
        # ^ v0.3.0 S3
        "list_item",
        "caption",
        "toc",
        "field",
    }
)
# ^ TocEntryBlock 은 union 멤버 아님 (TocBlock.entries 안 leaf type) — _KNOWN_KINDS 미포함.


def _block_discriminator(v: Any) -> str:
    """dict/모델 어느 쪽에서도 ``kind`` 를 추출해 known/unknown 분기.

    새 블록 타입을 추가할 때는 ``_KNOWN_KINDS`` 에 등록하고 ``Block`` 유니온에
    ``Annotated[NewBlock, Tag("new")]`` 를 추가한다.
    """
    kind = v.get("kind") if isinstance(v, dict) else getattr(v, "kind", None)
    return kind if kind in _KNOWN_KINDS else "unknown"


Block = Annotated[
    Annotated[ParagraphBlock, Tag("paragraph")]
    | Annotated[TableBlock, Tag("table")]
    | Annotated[PictureBlock, Tag("picture")]
    | Annotated[FormulaBlock, Tag("formula")]
    | Annotated[FootnoteBlock, Tag("footnote")]
    | Annotated[EndnoteBlock, Tag("endnote")]
    | Annotated[ListItemBlock, Tag("list_item")]
    | Annotated[CaptionBlock, Tag("caption")]
    | Annotated[TocBlock, Tag("toc")]
    | Annotated[FieldBlock, Tag("field")]
    | Annotated[UnknownBlock, Tag("unknown")],
    Discriminator(_block_discriminator),
]


class Furniture(BaseModel):
    """장식 노드 컨테이너 — RAG 가 임베딩에서 필터링 가능.

    v0.3.0 S1 부터 ``page_headers`` / ``page_footers`` 가 실제 채워진다.
    v0.3.0 S2 부터 ``footnotes`` / ``endnotes`` 도 실제 채워지며 타입이
    ``list[FootnoteBlock]`` / ``list[EndnoteBlock]`` 으로 강화된다.

    iter_blocks(scope="furniture") 순서: page_headers → page_footers →
    footnotes → endnotes (spec § 8 furniture 순서 계약).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_headers: list["Block"] = Field(default_factory=list)
    page_footers: list["Block"] = Field(default_factory=list)
    footnotes: list[FootnoteBlock] = Field(default_factory=list)
    endnotes: list[EndnoteBlock] = Field(default_factory=list)


class HwpDocument(BaseModel):
    """Document IR 루트.

    ``schema_name`` / ``schema_version`` 으로 인스턴스 자기-기술. body 와
    furniture 를 분리해 RAG 가 장식 노드를 필터링할 수 있다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Annotated[str, StringConstraints(pattern=r"^HwpDocument$")] = "HwpDocument"
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION
    source: DocumentSource | None = None
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    sections: list[Section] = Field(default_factory=list)
    body: list["Block"] = Field(default_factory=list)
    furniture: Furniture = Field(default_factory=Furniture)

    @field_validator("schema_version")
    @classmethod
    def _warn_forward_version(cls, v: str) -> str:
        """major 상향 시 UserWarning — 외부 파일 읽기 경계는 forward-compat 을 위해 완화한다."""
        major = int(v.split(".")[0])
        current_major = int(CURRENT_SCHEMA_VERSION.split(".")[0])
        if major > current_major:
            warnings.warn(
                f"schema_version {v!r} is newer than supported "
                f"{CURRENT_SCHEMA_VERSION!r}. Some fields may be ignored. "
                f"Upgrade rhwp-python.",
                UserWarning,
                stacklevel=2,
            )
        return v

    def iter_blocks(
        self,
        *,
        scope: Literal["body", "furniture", "all"] = "body",
        recurse: bool = True,
    ) -> Iterator["Block"]:
        """블록을 순서대로 스트리밍한다.

        Args:
            scope: 순회 대상.

                - ``"body"`` (기본, RAG-safe): 본문 블록만
                - ``"furniture"``: 머리글 → 꼬리말 → 각주 → 미주 순
                - ``"all"``: 본문 먼저, 이어서 장식
            recurse: True 면 컨테이너 블록 (TableCell.blocks, FootnoteBlock.blocks,
                EndnoteBlock.blocks, CaptionBlock.blocks) 재귀 진입.

        ``PictureBlock.caption`` / ``TableBlock.caption_block`` 은 부모 블록의
        metadata 로 간주되어 ``recurse=True`` 여도 진입하지 않는다 (LangChain
        loader 가 caption 을 별도 Document 로 중복 로드하는 noise 회피).

        구조 기반 작업에는 ``doc.body`` / ``doc.furniture`` 속성 직접 접근이
        더 간결하다. 본 메서드는 scope + recurse 조합이 필요한 경우용
        (예: ``sum(1 for b in doc.iter_blocks(scope="all") if isinstance(b, TableBlock))``).
        """
        if scope in ("body", "all"):
            yield from _walk_blocks(self.body, recurse)
        if scope in ("furniture", "all"):
            yield from _walk_blocks(self.furniture.page_headers, recurse)
            yield from _walk_blocks(self.furniture.page_footers, recurse)
            yield from _walk_blocks(self.furniture.footnotes, recurse)
            yield from _walk_blocks(self.furniture.endnotes, recurse)

    def to_markdown(self) -> str:
        """IR → GFM (GitHub Flavored Markdown) 문자열.

        결정 사항: ``docs/roadmap/v0.4.0/view-renderer.md`` §결정 사항 (1, 2, 5, 6,
        7, 8). 표는 모든 셀 ``span == 1`` 일 때 GFM ``|...|`` 표, 병합 셀이 있으면
        ``TableBlock.html`` 인라인 폴백. 이미지는 placeholder (``picture.image.uri``
        pass-through), 수식은 ``script_kind`` / ``inline`` 분기, 각주/미주는 본문
        끝 정의 + 본문 paragraph 안 ``[^N]`` reference. 머리글/꼬리말은 출력 미포함.

        호출이 IR 인스턴스를 변경하지 않아 ``frozen=True`` 와 정합 — 동일 IR 에
        대한 두 번 호출은 byte-equal (idempotency).
        """
        from rhwp.ir._view import render_markdown

        # ^ py3.10 pyright 가 Self 와 nominal HwpDocument 를 다르게 처리 — 동일 클래스라 호출 정합
        return render_markdown(self)  # type: ignore[arg-type]

    def to_html(self, *, include_css: bool = False) -> str:
        """IR → 완전 HTML5 문서 (``<!DOCTYPE html>`` + ``<html>`` + ``<head>`` + ``<body>``).

        결정 사항: ``docs/roadmap/v0.4.0/view-renderer.md`` §결정 사항 (1, 3, 4, 5,
        6, 7, 8). 표는 ``TableBlock.html`` 그대로 inline (재합성 안 함, rowspan/
        colspan 보존). 이미지는 ``picture.image.uri`` pass-through, 수식 디스플레이
        는 ``<div class="math">``, 각주/미주는 본문 직후 ``<aside id="...">`` 정의
        블록 + 본문 안 ``<sup><a href="#...">[N]</a></sup>`` 인용 마커. 머리글/
        꼬리말은 출력 미포함.

        Args:
            include_css: True 면 ``<head>`` 안 embedded ``<style>`` 1 회 동봉
                (브라우저 표시용). 기본 False — RAG 임베딩 / 텍스트 추출 사용처용.
                외부 ``<link rel="stylesheet">`` 는 영구 비목표 (extras 정책 일관).
        """
        from rhwp.ir._view import render_html

        # ^ py3.10 pyright 가 Self 와 nominal HwpDocument 를 다르게 처리 — 동일 클래스라 호출 정합
        return render_html(self, include_css=include_css)  # type: ignore[arg-type]


def _walk_blocks(blocks: Sequence["Block"], recurse: bool) -> Iterator["Block"]:
    """블록 리스트 DFS 순회 — recurse=True 면 컨테이너 블록 내부까지 진입.

    재귀 진입 컨테이너: ``TableCell.blocks``, ``FootnoteBlock.blocks``,
    ``EndnoteBlock.blocks``, ``CaptionBlock.blocks``. ``PictureBlock.caption`` /
    ``TableBlock.caption_block`` 은 부모 블록 metadata 로 간주되어 진입하지 않음
    (RAG 노이즈 회피).

    Sequence 로 받아 furniture.footnotes (list[FootnoteBlock]) / endnotes
    (list[EndnoteBlock]) 같은 협소 타입 list 도 invariant 충돌 없이 수용한다.
    """
    for block in blocks:
        yield block
        if not recurse:
            continue
        if isinstance(block, TableBlock):
            for cell in block.cells:
                yield from _walk_blocks(cell.blocks, recurse)
        elif isinstance(block, (FootnoteBlock, EndnoteBlock, CaptionBlock)):
            yield from _walk_blocks(block.blocks, recurse)


# 재귀 유니온 (Block ↔ TableCell ↔ TableBlock ↔ FootnoteBlock/EndnoteBlock
# ↔ CaptionBlock ↔ PictureBlock.caption ↔ TableBlock.caption_block)
# forward reference 해소.
TableCell.model_rebuild()
FootnoteBlock.model_rebuild()
EndnoteBlock.model_rebuild()
CaptionBlock.model_rebuild()
PictureBlock.model_rebuild()
TableBlock.model_rebuild()
Furniture.model_rebuild()
HwpDocument.model_rebuild()
