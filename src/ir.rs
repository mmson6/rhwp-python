//! Document raw 추출기 — Rust `Document` → Python primitive 트리.
//!
//! IR 도메인 변환 (HTML 직렬화, cell role 분류, mime 매핑, Pydantic 모델 합성)
//! 은 Python `rhwp.ir._mapper` 에 위임한다. 이 모듈의 책임은:
//!
//! - HWP binary 모델 (rhwp upstream) 을 Python 친화 평탄 구조로 펼치기
//! - upstream 내부 표현 (UTF-16 char offset, char_shape 테이블 등) 을 캡슐화 —
//!   raw 출력은 codepoint index 와 boolean 으로 미리 해소된다
//!
//! `#[derive(IntoPyObject)]` 가 struct field 이름을 PyDict key 로 자동 매핑한다.
//! key 명세는 Python `_mapper.py` 가 소비하는 계약이므로 변경 시 양쪽 동기화 필요.

use pyo3::prelude::*;

use rhwp::model::control::{Control, Equation, Field, FieldType};
use rhwp::model::document::{DocInfo, Document};
use rhwp::model::footnote::{Endnote, Footnote};
use rhwp::model::image::Picture;
use rhwp::model::paragraph::Paragraph;
use rhwp::model::shape::{Caption, CaptionDirection};
use rhwp::model::style::{HeadType, UnderlineType};
use rhwp::model::table::{Cell, Table};

#[derive(IntoPyObject)]
pub(crate) struct RawCharRun {
    pub start_cp: usize,
    pub end_cp: usize,
    pub char_shape_id: u32,
    pub bold: bool,
    pub italic: bool,
    pub underline: bool,
    pub strikethrough: bool,
}

#[derive(IntoPyObject)]
pub(crate) struct RawListInfo {
    // ^ 상류 ParaShape.head_type 가 비-None 일 때 채워진다. mapper 가 이 dict 를 보면
    //   ParagraphBlock 대신 ListItemBlock 을 emit. spec § 4 ListItemBlock 매핑.
    //
    //   head_type 은 lowercase string ("number"/"bullet"/"outline") — Python mapper 가
    //   marker placeholder + enumerated 결정 (도메인 분기는 Python 책임, IR 진화 시
    //   maturin rebuild 회피). 미래 v0.4.0+ 의 정확 marker 추출은 raw
    //   numbering_id 추가 + Python 의 Numbering.level_formats lookup.
    pub head_type: String,
    pub level: u32,
}

#[derive(IntoPyObject)]
pub(crate) struct RawCell {
    pub row: usize,
    pub col: usize,
    pub row_span: usize,
    pub col_span: usize,
    pub is_header: bool,
    pub paragraphs: Vec<RawParagraph>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawCaption {
    // ^ Picture/Table 양쪽의 캡션 paragraphs + direction 추출. Python mapper 가
    //   _flatten_paragraph 로 평탄화 → CaptionBlock.blocks. v0.3.0 S3 신규.
    //   direction 은 lowercase string ("top"/"bottom"/"left"/"right") — Python
    //   Literal 어휘와 1:1.
    pub direction: String,
    pub section_idx: usize,
    pub para_idx: usize,
    pub paragraphs: Vec<RawParagraph>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawTable {
    pub rows: usize,
    pub cols: usize,
    pub cells: Vec<RawCell>,
    pub caption: Option<String>,
    // ^ v0.3.0 S3 신규 — 구조화 캡션. caption (str) 은 v0.2.0 호환 평문 fallback.
    pub caption_block: Option<RawCaption>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawImageRef {
    pub bin_data_id: u16,
    // ^ 상류 BinData 의 extension (e.g. "jpg", "png", "bmp"). Python mapper 가 mime 매핑.
    //   Embedding 이 아닌 타입 (Link 등) 또는 누락 시 None — mapper 가
    //   "application/octet-stream" 으로 폴백한다.
    pub extension: Option<String>,
    // ^ Embedding 타입에 대해 binary 가 실제 로드됐는지 — broken reference 진단.
    //   true: bin_data_content 에 entry 존재. false: 누락 또는 Link/Storage 타입.
    pub has_content: bool,
}

#[derive(IntoPyObject)]
pub(crate) struct RawPicture {
    // ^ 그림 자체의 위치 = 부모 paragraph 의 (section_idx, para_idx) 공유.
    //   Provenance 계약: 컨트롤은 부모 문단 위치를 가리킨다 (Table 과 동일).
    pub section_idx: usize,
    pub para_idx: usize,
    pub image: Option<RawImageRef>,
    // ^ caption.paragraphs 첫 비-빈 텍스트 — S1 호환 평문 fallback (description).
    //   v0.3.0 S3 부터 caption (RawCaption) 으로 구조화 노출되며 description 은
    //   호환 보존만.
    pub description: Option<String>,
    // ^ v0.3.0 S3 신규 — 구조화 캡션. Picture.caption 이 None 이면 None.
    pub caption: Option<RawCaption>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawFormula {
    pub section_idx: usize,
    pub para_idx: usize,
    pub script: String,
    // ^ HWP equation script 는 항상 "hwp_eq" — LaTeX/MathML 변환은 Python 사용자
    //   책임 (spec § 비목표). text_alt 는 raw script 의 단순 정규화 결과.
    pub text_alt: Option<String>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawFootnote {
    // ^ 본문 인용 마커 위치 (parent paragraph 의 section_idx, para_idx).
    //   각주 본문은 같은 paragraph 에서 파생되므로 prov 도 동일 위치를 공유한다.
    //   정확한 char_offset 은 상류 field_ranges 매핑 필요 — v0.4.0+ 검토.
    pub marker_section_idx: usize,
    pub marker_para_idx: usize,
    pub number: u16,
    pub blocks: Vec<RawParagraph>,
    // ^ 각주 본문의 내부 paragraph — Python mapper 가 _flatten_paragraph 로
    //   처리해 표/그림/수식 등 nested 컨텐츠도 자연 지원
}

#[derive(IntoPyObject)]
pub(crate) struct RawEndnote {
    pub marker_section_idx: usize,
    pub marker_para_idx: usize,
    pub number: u16,
    pub blocks: Vec<RawParagraph>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawTocEntry {
    // ^ v0.3.0 placeholder — 실제 TOC entry 추출은 v0.4.0+ (bookmark resolver
    //   필요). 본 struct 는 forward-compat 를 위해 미리 정의.
    pub text: String,
    pub level: u32,
    pub target_bookmark_name: Option<String>,
    pub cached_page: Option<u32>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawToc {
    // ^ FieldType::TableOfContents 검출 시 emit. v0.3.0 entries 는 빈 Vec —
    //   spec § 6 결정 사항 7.
    pub section_idx: usize,
    pub para_idx: usize,
    pub entries: Vec<RawTocEntry>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawField {
    pub section_idx: usize,
    pub para_idx: usize,
    // ^ FieldType lowercase 표현 — Python Literal 어휘와 1:1. 미지 variant 는
    //   "unknown" + field_type_code 채움 (현재는 모두 알려져 있어 None).
    pub field_kind: String,
    // ^ HWP Field 는 cached_value 를 직접 노출하지 않는다 (paragraph text 안에
    //   inline 으로 들어있음). v0.3.0 은 None 출고 — 정확 추출은 field_ranges
    //   매핑 필요 (v0.4.0+ 검토).
    pub cached_value: Option<String>,
    // ^ HWP Field.command — Word <w:instrText> 대응. round-trip 보존용.
    pub raw_instruction: Option<String>,
    // ^ 미지의 raw 코드 — 상류 FieldType 추가 시 forward-compat. v0.3.0 은 모든
    //   variant 가 알려져 있으므로 항상 None.
    pub field_type_code: Option<u32>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawParagraph {
    pub section_idx: usize,
    pub para_idx: usize,
    pub text: String,
    pub char_runs: Vec<RawCharRun>,
    pub tables: Vec<RawTable>,
    pub pictures: Vec<RawPicture>,
    pub formulas: Vec<RawFormula>,
    // ^ v0.3.0 S3 신규 — TOC field 와 일반 field 분리 출고. mapper 가 각각
    //   TocBlock / FieldBlock 으로 합성.
    pub tocs: Vec<RawToc>,
    pub fields: Vec<RawField>,
    // ^ v0.3.0 S3 신규 — paragraph 가 list item 인지 표시. Some 이면 mapper 가
    //   ParagraphBlock 대신 ListItemBlock 을 emit.
    pub list_info: Option<RawListInfo>,
}

#[derive(IntoPyObject)]
pub(crate) struct RawDocument {
    pub source_uri: Option<String>,
    pub section_count: usize,
    pub paragraphs: Vec<RawParagraph>,
    // ^ furniture.page_headers / page_footers 로 매핑.
    pub headers: Vec<RawParagraph>,
    pub footers: Vec<RawParagraph>,
    // ^ furniture.footnotes / endnotes 로 매핑. v0.3.0 S2 신규.
    pub footnotes: Vec<RawFootnote>,
    pub endnotes: Vec<RawEndnote>,
}

/// 문서 전체를 raw 평탄 구조로 추출한다.
///
/// 호출 경로 전체가 Rust-only — `Python<'_>` 토큰을 받지 않으므로 호출 측이
/// `py.detach()` 로 GIL 을 해제할 수 있다. 결과 반환 시점에 PyO3 derive 가
/// 한 번에 PyDict 트리로 변환한다.
pub(crate) fn build_raw_document(doc: &Document, source_uri: Option<&str>) -> RawDocument {
    // ^ 총 단락 수 사전 계산으로 push 중 realloc 을 회피 — 큰 문서에서 의미 있음.
    let total_paras: usize = doc.sections.iter().map(|s| s.paragraphs.len()).sum();
    let mut paragraphs = Vec::with_capacity(total_paras);
    let mut acc = FurnitureAcc::default();
    for (section_idx, section) in doc.sections.iter().enumerate() {
        for (para_idx, para) in section.paragraphs.iter().enumerate() {
            paragraphs.push(build_raw_paragraph(section_idx, para_idx, para, doc));
            collect_furniture_from_paragraph(section_idx, para_idx, para, doc, &mut acc);
        }
        // ^ 바탕쪽 안의 Header/Footer 컨트롤도 furniture 로 라우팅 (spec § 8 매퍼 정책).
        //   바탕쪽 paragraph 자체는 furniture 에 넣지 않는다 — 페이지 배경 템플릿이지
        //   머리글/꼬리말이 아니므로. Header/Footer 컨트롤이 그 안에 있을 때만 추출.
        //   `enumerate()` 를 flat_map 바깥에 두어 여러 MasterPage 의 paragraph 가
        //   고유한 flat 인덱스를 받게 한다 (MasterPage 내부 별 0 부터 재시작 회피).
        for (mp_flat_idx, mp_para) in section
            .section_def
            .master_pages
            .iter()
            .flat_map(|mp| mp.paragraphs.iter())
            .enumerate()
        {
            collect_furniture_from_paragraph(section_idx, mp_flat_idx, mp_para, doc, &mut acc);
        }
    }
    RawDocument {
        source_uri: source_uri.map(String::from),
        section_count: doc.sections.len(),
        paragraphs,
        headers: acc.headers,
        footers: acc.footers,
        footnotes: acc.footnotes,
        endnotes: acc.endnotes,
    }
}

fn build_raw_paragraph(
    section_idx: usize,
    para_idx: usize,
    para: &Paragraph,
    doc: &Document,
) -> RawParagraph {
    let char_runs = build_char_runs(para, &doc.doc_info);
    // ^ 문단의 controls 중 Table / Picture / Equation / Field 만 추출 — 내부
    //   paragraph 들은 외부 (section, para) 를 공유한다 (Provenance 계약).
    //   Footnote / Endnote / Header / Footer 는 본문이 아니라 furniture 로
    //   라우팅되므로 여기서 처리하지 않음.
    let mut tables = Vec::new();
    let mut pictures = Vec::new();
    let mut formulas = Vec::new();
    let mut tocs = Vec::new();
    let mut fields = Vec::new();
    for ctrl in &para.controls {
        match ctrl {
            Control::Table(t) => {
                tables.push(build_raw_table(t, section_idx, para_idx, doc));
            }
            Control::Picture(p) => {
                pictures.push(build_raw_picture(p, section_idx, para_idx, doc));
            }
            Control::Equation(e) => {
                formulas.push(build_raw_formula(e, section_idx, para_idx));
            }
            Control::Field(f) => {
                if f.field_type == FieldType::TableOfContents {
                    tocs.push(build_raw_toc(f, section_idx, para_idx));
                } else {
                    fields.push(build_raw_field(f, section_idx, para_idx));
                }
            }
            _ => {}
        }
    }
    let list_info = build_raw_list_info(para, &doc.doc_info);
    RawParagraph {
        section_idx,
        para_idx,
        text: para.text.clone(),
        char_runs,
        tables,
        pictures,
        formulas,
        tocs,
        fields,
        list_info,
    }
}

/// `char_shapes` (UTF-16 offset 기반) 를 codepoint range 기반 RawCharRun 으로 해소한다.
///
/// 빈 텍스트나 char_shape 부재 시 빈 Vec 반환 — Python mapper 가 단일 style-less
/// 런으로 폴백한다. 이렇게 분리하면 Rust 는 "변환 가능한 런" 만 출고하고
/// 폴백 정책은 Python 도메인에서 결정한다.
fn build_char_runs(para: &Paragraph, doc_info: &DocInfo) -> Vec<RawCharRun> {
    let total_cp = para.text.chars().count();
    if total_cp == 0 || para.char_shapes.is_empty() {
        return Vec::new();
    }

    let mut runs = Vec::with_capacity(para.char_shapes.len());
    for i in 0..para.char_shapes.len() {
        let shape_ref = &para.char_shapes[i];
        let start_utf16 = shape_ref.start_pos;
        let end_utf16 = if i + 1 < para.char_shapes.len() {
            para.char_shapes[i + 1].start_pos
        } else {
            u32::MAX
        };

        let start_cp = utf16_to_cp(&para.char_offsets, start_utf16, total_cp);
        let end_cp = utf16_to_cp(&para.char_offsets, end_utf16, total_cp);

        if start_cp >= end_cp {
            continue;
        }

        let shape_id = shape_ref.char_shape_id;
        let shape = doc_info.char_shapes.get(shape_id as usize);
        runs.push(RawCharRun {
            start_cp,
            end_cp,
            char_shape_id: shape_id,
            bold: shape.map(|s| s.bold).unwrap_or(false),
            italic: shape.map(|s| s.italic).unwrap_or(false),
            underline: shape
                .map(|s| s.underline_type != UnderlineType::None)
                .unwrap_or(false),
            strikethrough: shape.map(|s| s.strikethrough).unwrap_or(false),
        });
    }

    runs
}

/// UTF-16 offset → codepoint index 변환.
///
/// `char_offsets[i]` 는 `text.chars().nth(i)` 에 해당하는 UTF-16 시작 위치.
/// 입력 `utf16` 이상인 첫 번째 codepoint 인덱스를 반환한다. 해당 offset 이
/// 텍스트 끝을 넘어가면 `fallback_end` 를 반환 (텍스트 codepoint 총 길이).
fn utf16_to_cp(char_offsets: &[u32], utf16: u32, fallback_end: usize) -> usize {
    if utf16 == u32::MAX {
        return fallback_end;
    }
    for (i, &off) in char_offsets.iter().enumerate() {
        if off >= utf16 {
            return i;
        }
    }
    fallback_end
}

fn build_raw_table(
    table: &Table,
    outer_section: usize,
    outer_para: usize,
    doc: &Document,
) -> RawTable {
    let cells = table
        .cells
        .iter()
        .map(|c| build_raw_cell(c, outer_section, outer_para, doc))
        .collect();
    let caption = table.caption.as_ref().and_then(extract_caption_text);
    let caption_block = table
        .caption
        .as_ref()
        .map(|c| build_raw_caption(c, outer_section, outer_para, doc));
    RawTable {
        rows: table.row_count as usize,
        cols: table.col_count as usize,
        cells,
        caption,
        caption_block,
    }
}

fn build_raw_cell(cell: &Cell, outer_section: usize, outer_para: usize, doc: &Document) -> RawCell {
    let paragraphs = cell
        .paragraphs
        .iter()
        .map(|p| build_raw_paragraph(outer_section, outer_para, p, doc))
        .collect();
    RawCell {
        row: cell.row as usize,
        col: cell.col as usize,
        row_span: cell.row_span.max(1) as usize,
        col_span: cell.col_span.max(1) as usize,
        is_header: cell.is_header,
        paragraphs,
    }
}

/// Picture 컨트롤 → raw 평탄 구조.
///
/// `bin_data_id` 는 상류 Picture 가 가리키는 BinData 인덱스 (1-based). extension /
/// has_content 는 doc.doc_info.bin_data_list 와 doc.bin_data_content 를 lookup 해서
/// 채운다. 0 (미할당) 또는 lookup 실패 시 image=None 으로 broken reference 표현.
fn build_raw_picture(
    pic: &Picture,
    section_idx: usize,
    para_idx: usize,
    doc: &Document,
) -> RawPicture {
    let bin_data_id = pic.image_attr.bin_data_id;
    let image = if bin_data_id == 0 {
        None
    } else {
        let bd_meta = doc
            .doc_info
            .bin_data_list
            .get((bin_data_id as usize).saturating_sub(1));
        let extension = bd_meta.and_then(|bd| bd.extension.clone());
        // ^ bin_data_content 는 Embedding 만 채워지므로 Link/Storage 는 false.
        //   상류 utils.rs::find_bin_data 와 동일한 인덱싱 (bin_data_id - 1).
        let has_content = doc
            .bin_data_content
            .get((bin_data_id as usize).saturating_sub(1))
            .is_some();
        Some(RawImageRef {
            bin_data_id,
            extension,
            has_content,
        })
    };
    let description = pic.caption.as_ref().and_then(extract_caption_text);
    let caption = pic
        .caption
        .as_ref()
        .map(|c| build_raw_caption(c, section_idx, para_idx, doc));
    RawPicture {
        section_idx,
        para_idx,
        image,
        description,
        caption,
    }
}

/// 본문 paragraph 에서 추출되는 furniture 누적 컨테이너.
#[derive(Default)]
struct FurnitureAcc {
    headers: Vec<RawParagraph>,
    footers: Vec<RawParagraph>,
    footnotes: Vec<RawFootnote>,
    endnotes: Vec<RawEndnote>,
}

/// 본문 paragraph 안의 furniture 컨트롤 (Header/Footer/Footnote/Endnote) 을 누적한다.
///
/// 각 furniture 컨트롤이 가지는 자체 paragraphs 들을 외부 (section_idx, para_idx) 와
/// 공유한 RawParagraph 로 변환한다. 본 paragraphs 는 furniture 가 어디서
/// "선언" 됐는지 (Provenance) 만 보존하면 충분 — 페이지별 반복 출현은 렌더 단계.
fn collect_furniture_from_paragraph(
    section_idx: usize,
    para_idx: usize,
    para: &Paragraph,
    doc: &Document,
    acc: &mut FurnitureAcc,
) {
    for ctrl in &para.controls {
        match ctrl {
            Control::Header(h) => {
                for hp in &h.paragraphs {
                    acc.headers
                        .push(build_raw_paragraph(section_idx, para_idx, hp, doc));
                }
            }
            Control::Footer(f) => {
                for fp in &f.paragraphs {
                    acc.footers
                        .push(build_raw_paragraph(section_idx, para_idx, fp, doc));
                }
            }
            Control::Footnote(fn_) => {
                acc.footnotes
                    .push(build_raw_footnote(fn_, section_idx, para_idx, doc));
            }
            Control::Endnote(en) => {
                acc.endnotes
                    .push(build_raw_endnote(en, section_idx, para_idx, doc));
            }
            _ => {}
        }
    }
}

/// Equation 컨트롤 → RawFormula. text_alt 는 raw script 의 단순 정규화 결과 —
/// 정상 변환 대신 RAG 폴백용으로만 충분. 실패하면 None (mapper 가 그대로 보존).
fn build_raw_formula(eq: &Equation, section_idx: usize, para_idx: usize) -> RawFormula {
    let script = eq.script.clone();
    let text_alt = simple_eq_text_alt(&script);
    RawFormula {
        section_idx,
        para_idx,
        script,
        text_alt,
    }
}

/// HWP equation script 의 단순 정규화 → 평문 근사. 완전한 변환이 아니라
/// RAG 검색용 폴백 — 정확한 LaTeX 가 필요하면 사용자가 외부 변환기 사용.
///
/// 적용 규칙 (모두 토큰 경계 인식 — `[A-Za-z0-9_]` 의 연속을 한 식별자로 본다):
/// - 식별자 토큰 `over` → `/` (분수). 예: `1 over 2` → `1 / 2`. `discover` 는 그대로.
/// - 식별자 토큰 `sqrt` → `√` (제곱근). 예: `sqrt{x}` → `√(x)`. `sqrtish` 는 그대로.
/// - 그룹 괄호 `{` → `(`, `}` → `)`. spec § 2 의 정규화 규약.
///
/// 빈 스크립트는 None 반환. UTF-8 multi-byte char (한글 등) 는 그대로 통과.
fn simple_eq_text_alt(script: &str) -> Option<String> {
    let trimmed = script.trim();
    if trimmed.is_empty() {
        return None;
    }
    let mut out = String::with_capacity(trimmed.len());
    let mut chars = trimmed.chars().peekable();
    while let Some(c) = chars.next() {
        if is_ident_start(c) {
            // ^ 식별자 토큰 시작 — 끝까지 읽고 키워드 비교
            let mut token = String::new();
            token.push(c);
            while let Some(&next) = chars.peek() {
                if is_ident_continue(next) {
                    token.push(next);
                    chars.next();
                } else {
                    break;
                }
            }
            match token.as_str() {
                "over" => out.push('/'),
                "sqrt" => out.push('√'),
                _ => out.push_str(&token),
            }
        } else {
            // ^ 비-식별자 char (공백, 괄호, 연산자, 한글 등)
            match c {
                '{' => out.push('('),
                '}' => out.push(')'),
                _ => out.push(c),
            }
        }
    }
    Some(out)
}

#[inline]
fn is_ident_start(c: char) -> bool {
    c.is_ascii_alphabetic() || c == '_'
}

#[inline]
fn is_ident_continue(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// Footnote → RawFootnote. 본문 인용 마커 위치 (parent paragraph) 를 보존하고
/// 각주 본문의 paragraph 들을 평탄화한다.
fn build_raw_footnote(
    fn_: &Footnote,
    marker_section_idx: usize,
    marker_para_idx: usize,
    doc: &Document,
) -> RawFootnote {
    let blocks = fn_
        .paragraphs
        .iter()
        .map(|p| build_raw_paragraph(marker_section_idx, marker_para_idx, p, doc))
        .collect();
    RawFootnote {
        marker_section_idx,
        marker_para_idx,
        number: fn_.number,
        blocks,
    }
}

fn build_raw_endnote(
    en: &Endnote,
    marker_section_idx: usize,
    marker_para_idx: usize,
    doc: &Document,
) -> RawEndnote {
    let blocks = en
        .paragraphs
        .iter()
        .map(|p| build_raw_paragraph(marker_section_idx, marker_para_idx, p, doc))
        .collect();
    RawEndnote {
        marker_section_idx,
        marker_para_idx,
        number: en.number,
        blocks,
    }
}

/// Caption → RawCaption (구조화 캡션, S3 신규).
///
/// shape::Caption 의 paragraphs 를 RawParagraph 로 평탄화. direction 은
/// CaptionDirection enum → lowercase string 으로 변환 (Python Literal 매칭).
/// section_idx / para_idx 는 부모 (Picture/Table) 의 위치 공유 — Provenance 계약.
fn build_raw_caption(
    cap: &Caption,
    section_idx: usize,
    para_idx: usize,
    doc: &Document,
) -> RawCaption {
    let paragraphs = cap
        .paragraphs
        .iter()
        .map(|p| build_raw_paragraph(section_idx, para_idx, p, doc))
        .collect();
    RawCaption {
        direction: caption_direction_to_str(cap.direction).to_string(),
        section_idx,
        para_idx,
        paragraphs,
    }
}

fn caption_direction_to_str(d: CaptionDirection) -> &'static str {
    match d {
        CaptionDirection::Top => "top",
        CaptionDirection::Bottom => "bottom",
        CaptionDirection::Left => "left",
        CaptionDirection::Right => "right",
    }
}

/// Caption 에서 텍스트만 추출한다 (S1 호환 description fallback 경로).
fn extract_caption_text(caption: &Caption) -> Option<String> {
    let text: Vec<String> = caption
        .paragraphs
        .iter()
        .map(|p| p.text.clone())
        .filter(|t| !t.is_empty())
        .collect();
    if text.is_empty() {
        None
    } else {
        Some(text.join("\n"))
    }
}

/// ParaShape.head_type → list_info (S3 신규).
///
/// ``HeadType::None`` 이면 None 반환 → mapper 가 ParagraphBlock 으로 emit.
/// 그 외 (Number / Bullet / Outline) 면 lowercase string 출고 → Python mapper 가
/// ListItemBlock 합성 (marker placeholder / enumerated 결정).
///
/// para_shape_id lookup 실패 시에도 None — 손상 파일 대비.
fn build_raw_list_info(para: &Paragraph, doc_info: &DocInfo) -> Option<RawListInfo> {
    let ps = doc_info.para_shapes.get(para.para_shape_id as usize)?;
    let head_type = match ps.head_type {
        HeadType::None => return None,
        HeadType::Number => "number",
        HeadType::Outline => "outline",
        HeadType::Bullet => "bullet",
    };
    Some(RawListInfo {
        head_type: head_type.to_string(),
        level: ps.para_level as u32,
    })
}

/// FieldType (TableOfContents 제외) → RawField. cached_value 는 v0.3.0 미추출.
fn build_raw_field(field: &Field, section_idx: usize, para_idx: usize) -> RawField {
    RawField {
        section_idx,
        para_idx,
        field_kind: field_type_to_str(field.field_type).to_string(),
        cached_value: None,
        raw_instruction: if field.command.is_empty() {
            None
        } else {
            Some(field.command.clone())
        },
        // ^ v0.3.0 은 모든 FieldType variant 가 알려져 있으므로 None — 상류가
        //   새 variant 추가 시 mapper 가 raw u32 채워야 한다 (v0.4.0+).
        field_type_code: None,
    }
}

/// FieldType::TableOfContents → RawToc. v0.3.0 은 entries 빈 Vec —
/// 실제 TOC 항목 추출은 v0.4.0+ (bookmark resolver 필요, spec § 6 결정).
fn build_raw_toc(_field: &Field, section_idx: usize, para_idx: usize) -> RawToc {
    RawToc {
        section_idx,
        para_idx,
        entries: Vec::new(),
    }
}

/// FieldType → Python FieldKind Literal value (lowercase string, 1:1 매핑).
///
/// 상류 ``Field::field_type_str`` 와 어휘가 다른 항목 (DocDate → "doc_date",
/// PrivateInfoSecurity → "private_info", Formula → "calc") 은 Python 어휘에
/// 맞추기 위해 자체 구현. ``"calc"`` 는 Equation ("formula" kind) 과의 이름
/// 충돌 회피 — spec § 7 FieldKind 표.
///
/// **TableOfContents arm**: 현 라우팅은 ``build_raw_paragraph`` 가
/// ``FieldType::TableOfContents`` 를 ``tocs`` 로 사전 분리하므로 본 arm 은
/// dead code. 그러나 (1) Python ``FieldKind`` Literal 어휘 동기 (15 종 일치)
/// (2) 미래 routing 정책 변경 시 (예: TocBlock 도 FieldBlock 통합) 활성화
/// — 두 이유로 어휘 보존.
fn field_type_to_str(ft: FieldType) -> &'static str {
    match ft {
        FieldType::Unknown => "unknown",
        FieldType::Date => "date",
        FieldType::DocDate => "doc_date",
        FieldType::Path => "path",
        FieldType::Bookmark => "bookmark",
        FieldType::MailMerge => "mailmerge",
        FieldType::CrossRef => "crossref",
        FieldType::Formula => "calc",
        FieldType::ClickHere => "clickhere",
        FieldType::Summary => "summary",
        FieldType::UserInfo => "userinfo",
        FieldType::Hyperlink => "hyperlink",
        FieldType::Memo => "memo",
        FieldType::PrivateInfoSecurity => "private_info",
        // ^ 현 라우팅에서는 도달 안 함 — 어휘 보존 + 미래 routing 변경 대비
        FieldType::TableOfContents => "toc",
    }
}

/// `bin_data_id` (1-based) 에 해당하는 raw bytes 를 반환.
///
/// 상류 `renderer/layout/utils.rs::find_bin_data` 와 동일한 lookup —
/// `bin_data_content` 는 Embedding 타입만 채워져 있고 인덱스는 1-based.
/// Embedding 이 아니거나 (`Link` / `Storage`) 누락 시 None.
///
/// **인덱스 정합성 가정**: `bin_data_content` 와 `bin_data_list` 는 같은 순서로
/// 같은 길이여야 한다 — 즉 모든 BinData entry 가 Embedding 타입이어야 정확.
/// 혼합 (Link + Embedding) 문서에서는 상류 `bin_data_content` 가 Embedding 만
/// 추려 더 짧으므로 잘못된 entry 를 반환할 수 있다 — 상류 renderer 도 같은
/// 가정을 공유하므로 SVG/PDF 렌더링도 같은 잘못된 lookup 을 한다 (상류 패리티).
pub(crate) fn lookup_bin_data_bytes(doc: &Document, bin_data_id: u16) -> Option<&[u8]> {
    if bin_data_id == 0 {
        return None;
    }
    doc.bin_data_content
        .get((bin_data_id as usize) - 1)
        .map(|bdc| bdc.data.as_slice())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn utf16_to_cp_sentinel_returns_fallback() {
        let offsets = vec![0u32, 1, 2];
        assert_eq!(utf16_to_cp(&offsets, u32::MAX, 3), 3);
    }

    #[test]
    fn utf16_to_cp_matches_first_ge() {
        let offsets = vec![0u32, 1, 3, 4]; // ^ 2번째 codepoint 는 SMP 라 2 code units
        assert_eq!(utf16_to_cp(&offsets, 0, 4), 0);
        assert_eq!(utf16_to_cp(&offsets, 1, 4), 1);
        assert_eq!(utf16_to_cp(&offsets, 2, 4), 2); // offset 2 는 char_offsets 에 없음 → 다음 >=2 인 3을 가진 인덱스 2
        assert_eq!(utf16_to_cp(&offsets, 3, 4), 2);
        assert_eq!(utf16_to_cp(&offsets, 5, 4), 4); // fallback
    }

    #[test]
    fn lookup_bin_data_zero_id_returns_none() {
        let doc = Document::default();
        assert!(lookup_bin_data_bytes(&doc, 0).is_none());
    }

    // * simple_eq_text_alt — 토큰 경계 인식 검증

    #[test]
    fn simple_eq_text_alt_empty_returns_none() {
        assert_eq!(simple_eq_text_alt(""), None);
        assert_eq!(simple_eq_text_alt("   "), None);
    }

    #[test]
    fn simple_eq_text_alt_over_keyword_replaced() {
        assert_eq!(simple_eq_text_alt("1 over 2").as_deref(), Some("1 / 2"));
        assert_eq!(simple_eq_text_alt("over").as_deref(), Some("/"));
    }

    #[test]
    fn simple_eq_text_alt_sqrt_keyword_replaced() {
        assert_eq!(simple_eq_text_alt("sqrt{x}").as_deref(), Some("√(x)"));
        assert_eq!(
            simple_eq_text_alt("sqrt{x^2 + 1}").as_deref(),
            Some("√(x^2 + 1)")
        );
    }

    #[test]
    fn simple_eq_text_alt_braces_become_parens() {
        assert_eq!(simple_eq_text_alt("{a + b}").as_deref(), Some("(a + b)"));
    }

    #[test]
    fn simple_eq_text_alt_keywords_inside_identifier_not_replaced() {
        // ^ "sqrt" 가 식별자 일부면 변환되면 안 됨
        assert_eq!(simple_eq_text_alt("sqrtish").as_deref(), Some("sqrtish"));
        // ^ "over" 가 다른 식별자 일부일 때도
        assert_eq!(simple_eq_text_alt("discover").as_deref(), Some("discover"));
        assert_eq!(simple_eq_text_alt("overflow").as_deref(), Some("overflow"));
        // ^ underscore 식별자
        assert_eq!(simple_eq_text_alt("_over_").as_deref(), Some("_over_"));
    }

    #[test]
    fn simple_eq_text_alt_combined_expression() {
        assert_eq!(
            simple_eq_text_alt("1 over 2 + sqrt{x^2 + 1}").as_deref(),
            Some("1 / 2 + √(x^2 + 1)")
        );
    }

    #[test]
    fn simple_eq_text_alt_unicode_passes_through() {
        // ^ 한글이 들어와도 변환 안 함 (HWP equation script 는 보통 ASCII 만)
        assert_eq!(simple_eq_text_alt("α + β").as_deref(), Some("α + β"));
    }

    // * field_type_to_str — Python FieldKind Literal 어휘와 1:1 일치

    #[test]
    fn field_type_to_str_all_variants_lowercase() {
        // ^ Python FieldKind Literal 의 14 + unknown 어휘. 추가/이름 변경 시 mapper.py
        //   _VALID_FIELD_KINDS 와 양방향 동기화 필요.
        assert_eq!(field_type_to_str(FieldType::Unknown), "unknown");
        assert_eq!(field_type_to_str(FieldType::Date), "date");
        assert_eq!(field_type_to_str(FieldType::DocDate), "doc_date");
        assert_eq!(field_type_to_str(FieldType::Path), "path");
        assert_eq!(field_type_to_str(FieldType::Bookmark), "bookmark");
        assert_eq!(field_type_to_str(FieldType::MailMerge), "mailmerge");
        assert_eq!(field_type_to_str(FieldType::CrossRef), "crossref");
        // ^ Formula → "calc" — Equation ("formula" kind) 와의 이름 충돌 회피
        assert_eq!(field_type_to_str(FieldType::Formula), "calc");
        assert_eq!(field_type_to_str(FieldType::ClickHere), "clickhere");
        assert_eq!(field_type_to_str(FieldType::Summary), "summary");
        assert_eq!(field_type_to_str(FieldType::UserInfo), "userinfo");
        assert_eq!(field_type_to_str(FieldType::Hyperlink), "hyperlink");
        assert_eq!(field_type_to_str(FieldType::Memo), "memo");
        assert_eq!(
            field_type_to_str(FieldType::PrivateInfoSecurity),
            "private_info"
        );
        assert_eq!(field_type_to_str(FieldType::TableOfContents), "toc");
    }

    // * caption_direction_to_str — Python CaptionBlock.direction Literal 과 1:1

    #[test]
    fn caption_direction_lowercase() {
        assert_eq!(caption_direction_to_str(CaptionDirection::Top), "top");
        assert_eq!(caption_direction_to_str(CaptionDirection::Bottom), "bottom");
        assert_eq!(caption_direction_to_str(CaptionDirection::Left), "left");
        assert_eq!(caption_direction_to_str(CaptionDirection::Right), "right");
    }
}
