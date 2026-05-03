"""rhwp.ir._raw_types — Rust `#[derive(IntoPyObject)]` 출력의 TypedDict 미러.

``src/ir.rs`` 의 ``RawDocument`` / ``RawParagraph`` / ``RawTable`` / ``RawCell`` /
``RawCharRun`` / ``RawPicture`` / ``RawImageRef`` / ``RawFormula`` / ``RawFootnote``
/ ``RawEndnote`` / ``RawListInfo`` / ``RawCaption`` / ``RawToc`` / ``RawTocEntry``
/ ``RawField`` struct 가 Python 에 PyDict 로 출고되는데, 그 dict 의 key 구조를
정적 타입으로 고정한다.

### 왜 TypedDict 인가

Rust 계약이 이미 구조를 보장하므로 Python 레이어에서의 재검증은 이중 비용이다.
TypedDict 는 런타임 비용 0, 정적 typing 만으로 ``raw["row"]`` key 오타를 pyright
가 컴파일 타임에 검출한다. 검증 기반 모델 (런타임 validation) 과 비교해 nested
구조에서 수 배 빠르므로 internal raw record 용도에 적합하다.

### 계약 동기화

필드 추가/이름 변경은 ``src/ir.rs`` 의 struct 와 **양방향으로** 갱신해야 한다 —
Rust 는 출고 key 를, 이 파일은 소비 key 를 정의한다.
"""

from typing import TypedDict


class RawCharRun(TypedDict):
    """``src/ir.rs::RawCharRun`` 과 1:1 대응."""

    start_cp: int
    end_cp: int
    char_shape_id: int
    bold: bool
    italic: bool
    underline: bool
    strikethrough: bool


class RawCell(TypedDict):
    """``src/ir.rs::RawCell``. ``paragraphs`` 는 셀 내부 문단 (중첩 표 자연 지원)."""

    row: int
    col: int
    row_span: int
    col_span: int
    is_header: bool
    paragraphs: list["RawParagraph"]


class RawCaption(TypedDict):
    """``src/ir.rs::RawCaption`` (S3 신규).

    HWP ``shape::Caption`` (Picture/Table 양쪽) 의 paragraphs + direction 추출.
    Python mapper 가 paragraphs 를 ``_flatten_paragraph`` 로 평탄화 → ``CaptionBlock.blocks``.
    """

    direction: str  # ^ "top" | "bottom" | "left" | "right" — Rust 가 lowercase 출고
    section_idx: int
    para_idx: int
    paragraphs: list["RawParagraph"]


class RawTable(TypedDict):
    """``src/ir.rs::RawTable``. ``rows``/``cols`` 는 upstream 원값 그대로 (보정 없음).

    ``caption`` (S1) 은 평문 fallback (호환). ``caption_block`` (S3 신규) 은 구조화
    캡션 — 둘 다 source 가 같은 HWP Table.caption 이지만 표현 형태만 다름.

    ``char_offset`` (v0.3.1) 은 부모 paragraph 안 zero-width character 위치 — mapper 가
    Provenance.char_start/char_end 양쪽에 동일 값 복제. None 은 부모의 char_offsets 가
    빈 paragraph (정확 character index 의미 없음).
    """

    rows: int
    cols: int
    cells: list[RawCell]
    caption: str | None
    caption_block: RawCaption | None
    char_offset: int | None


class RawImageRef(TypedDict):
    """``src/ir.rs::RawImageRef``. URI 합성 / mime 매핑은 mapper 책임."""

    bin_data_id: int
    extension: str | None
    has_content: bool


class RawPicture(TypedDict):
    """``src/ir.rs::RawPicture``. ``image=None`` 은 broken reference (bin_data_id=0).

    ``description`` (S1) 은 caption 평문 fallback 호환. ``caption`` (S3 신규) 은
    구조화 캡션 — Picture 가 caption 을 가지면 둘 다 채워진다.

    ``char_offset`` (v0.3.1) 은 부모 paragraph 안 zero-width character 위치 (TAC /
    floating 무관). None 은 부모의 char_offsets 가 빈 paragraph.
    """

    section_idx: int
    para_idx: int
    image: RawImageRef | None
    description: str | None
    caption: RawCaption | None
    char_offset: int | None


class RawFormula(TypedDict):
    """``src/ir.rs::RawFormula``. ``text_alt`` 는 raw script 의 단순 정규화 결과 (S2 신규).

    ``char_offset`` (v0.3.1) 은 부모 paragraph 안 zero-width character 위치.
    """

    section_idx: int
    para_idx: int
    script: str
    text_alt: str | None
    char_offset: int | None


class RawFootnote(TypedDict):
    """``src/ir.rs::RawFootnote``. ``blocks`` 는 각주 본문의 paragraph 들 (S2 신규).

    ``marker_section_idx`` / ``marker_para_idx`` 는 본문 인용 마커가 등장한 parent
    paragraph 위치 — RAG 가 각주 → 본문 역추적 시 사용.

    ``marker_char_offset`` (v0.3.1) 은 본문 인용 마커의 zero-width character 위치
    (상류 ``Paragraph::control_text_positions`` v0.7.8 활용). 부모 paragraph 의
    ``char_offsets`` 가 빈 경우 None.
    """

    marker_section_idx: int
    marker_para_idx: int
    marker_char_offset: int | None
    number: int
    blocks: list["RawParagraph"]


class RawEndnote(TypedDict):
    """``src/ir.rs::RawEndnote``. Footnote 와 동일 구조 — 배치만 다름 (페이지 하단 vs 문서 끝)."""

    marker_section_idx: int
    marker_para_idx: int
    marker_char_offset: int | None
    number: int
    blocks: list["RawParagraph"]


class RawListInfo(TypedDict):
    """``src/ir.rs::RawListInfo`` (S3 신규).

    Paragraph 가 list item 인지 표시 — 상류 ``ParaShape.head_type`` 가 비-None
    일 때 채워진다. mapper 가 본 dict 가 있으면 ParagraphBlock 대신 ListItemBlock
    을 emit.

    ``head_type`` 은 ``"number"`` / ``"bullet"`` / ``"outline"`` lowercase string —
    Python mapper 가 marker placeholder + enumerated 를 결정 (도메인 분기는 Python
    책임). v0.4.0+ 의 정확 marker 추출 (Numbering.level_formats lookup) 도 동일
    위치에서.
    """

    head_type: str
    level: int


class RawTocEntry(TypedDict):
    """``src/ir.rs::RawTocEntry`` (S3 신규).

    v0.3.0 에서는 매퍼가 빈 entries 만 출고 — 본 TypedDict 는 v0.4.0+ 의
    entry 추출 시점 forward-compat 용 placeholder.
    """

    text: str
    level: int
    target_bookmark_name: str | None
    cached_page: int | None


class RawToc(TypedDict):
    """``src/ir.rs::RawToc`` (S3 신규). ``FieldType::TableOfContents`` 검출 시 emit.

    ``char_offset`` (v0.3.1) 은 부모 paragraph 안 zero-width character 위치.
    """

    section_idx: int
    para_idx: int
    entries: list[RawTocEntry]
    char_offset: int | None


class RawField(TypedDict):
    """``src/ir.rs::RawField`` (S3 신규).

    ``field_kind`` 는 Rust 에서 lowercase string 으로 직렬화된 ``FieldType`` —
    Python 측 ``FieldKind`` Literal 과 정확히 같은 어휘여야 한다 (mapper 가
    Literal 검증). 미지의 FieldType 은 ``"unknown"`` + ``field_type_code`` 채움.

    ``char_offset`` (v0.3.1) 은 부모 paragraph 안 zero-width character 위치.
    """

    section_idx: int
    para_idx: int
    field_kind: str
    cached_value: str | None
    raw_instruction: str | None
    field_type_code: int | None
    char_offset: int | None


class RawParagraph(TypedDict):
    """``src/ir.rs::RawParagraph``.

    ``tables`` / ``pictures`` / ``formulas`` / ``tocs`` / ``fields`` 는 문단의
    ``controls`` 중 해당 타입만 추출된 리스트. ``section_idx`` / ``para_idx`` 는
    외부 paragraph 의 위치 — 셀 내부 문단이라도 외부 표가 속한 문단의 값을 공유한다
    (Provenance 계약).

    ``list_info`` (S3 신규) 가 비-None 이면 mapper 가 ParagraphBlock 대신
    ListItemBlock 을 emit — paragraph 자체가 list item 으로 분류된다.
    """

    section_idx: int
    para_idx: int
    text: str
    char_runs: list[RawCharRun]
    tables: list[RawTable]
    pictures: list[RawPicture]
    formulas: list[RawFormula]
    tocs: list[RawToc]
    fields: list[RawField]
    list_info: RawListInfo | None


class RawDocument(TypedDict):
    """``src/ir.rs::RawDocument`` — ``to_ir`` Rust→Python 경계의 루트.

    ``headers`` / ``footers`` 는 furniture.page_headers / page_footers 로,
    ``footnotes`` / ``endnotes`` 는 furniture.footnotes / endnotes 로 매핑된다.
    """

    source_uri: str | None
    section_count: int
    paragraphs: list[RawParagraph]
    headers: list[RawParagraph]
    footers: list[RawParagraph]
    footnotes: list[RawFootnote]
    endnotes: list[RawEndnote]
