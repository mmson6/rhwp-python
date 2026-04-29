# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — 문서 시스템 대규모 개편

본 변경은 메타 — 사용자 facing API / wheel 영향 0. 내부 문서 운영 체계 정비.

- spec 메타데이터를 inline `**Status**: ...` 라인 → YAML frontmatter 로 전면 마이그 (24개 spec 일괄, Frozen 19 / Draft 2 / Active 3). Living-policy schema migration — CONVENTIONS § Frozen 면제 조항 신설 (non-semantic 형식 갱신은 in-place 허용).
- `AGENTS.md` 를 정본 agent context 파일로 도입 (`CLAUDE.md` 는 1줄 stub). Codex / Factory / Cursor / Kilo 등 비-Claude 도구 호환.
- `scripts/lint_docs.py` + `scripts/_doc_lint.py` (공통 lib) 신설 — frontmatter schema / supersede chain / kebab-case / 페어 / cross-link 방향성 / 깨진 링크 8 룰 일괄 검증. `.claude/hooks/docs-lint.py` 가 동일 lib 재사용. CI `docs.yml` workflow 분리 (paths-filter — build/test 와 독립).
- `pytest.mark.spec("vX.Y.Z/topic#AC-N")` marker + `scripts/generate_spec_trace.py` (AST 정적 분석) → `docs/traces/coverage.md` (Living) 자동 매핑. v0.4.0+ 신규 spec 부터 적용, 기존 v0.1.0 ~ v0.3.0 Frozen 미변경.
- `/new-spec <version> <topic>` Claude Code skill 신설 — 새 version spec + 짝 페어 ADR + README 인덱스 row + EARS placeholder 일괄 생성, lint 자동 검증.
- `last_updated` 자동 갱신 hook (`.claude/hooks/update-last-updated.py`, PostToolUse) — Frozen / Superseded / Living 은 skip.
- CONVENTIONS.md 갱신: EARS notation (v0.4.0+) / CHANGELOG ↔ implementation log 역할 분리 / 상대경로 implicit 표준 / Frozen 외부 의존성 부패 정책 / Trace report / verification 약화 / meta-level implementation 슬롯.
- 부수 정리: 상류 `edwardkim/rhwp#390` (find_control_text_positions) 옵션 A 채택 → cherry-pick 머지 → 본 spec in-place Frozen 전환 + RESOLVED notice. design 파일 `<topic>-design-research.md` → `<topic>-research.md` 명명 통일 (v0.2.0/ir, v0.3.0/cli rename + 24 cross-link 일괄 정정).
- 본 PR 의 a/b/c 결정 비교 + 14개 결정 historical record 는 [docs/implementation/spec-system-overhaul.md](docs/implementation/spec-system-overhaul.md) (Frozen) 가 보유.

## [0.3.0] — 2026-04-28

### Changed — async API 의존성 정리

- `rhwp.aparse` 가 `aiofiles` 대신 stdlib `asyncio.to_thread` 사용 — 외부 의존성 제거. `[async]` extras 키는 빈 배열로 보존 (`pip install rhwp[async]` 명령 호환 유지, v0.4.0 에서 키 자체 제거 검토). 의미·성능 동등 — Python `asyncio` 가 native async file I/O 를 미지원하는 한 모든 async file lib (aiofiles 포함) 도 결국 thread pool wrapping 이라 둘은 같은 메커니즘. CI `test-without-extras` skip count 5 → 4 (`test_async.py` 가 더 이상 gated 아님).

MINOR release — Phase 2 두 축 동시 GA. v0.2.0 의 Document IR v1.0 위에 HWP 고유 의미 요소 8 종을 추가하고 (SchemaVersion 1.1), 동시에 Python 고유 가치 (IR/LangChain 청크/스키마 export) 를 shell 에서 직접 소비할 수 있는 `rhwp-py` CLI 를 재도입한다. 모든 v0.2.0 공개 API 보존 — 추가만 있고 기존 코드는 그대로 동작.

상류 `edwardkim/rhwp` 커밋 핀을 `bea635b` → `033617e` 로 bump (upstream v0.6.x → v0.7.7 흡수, 380 commits). IR 확장이 사용하는 first-class struct/enum (Picture, Equation, Footnote/Endnote, Caption, Field/FieldType, Header/Footer, ParaShape) 자체는 핀 변경 전부터 노출돼 있어 IR 매핑 작업은 상류 변경에 의존하지 않는다 — bump 의 효과는 직교 영역에 한정: 렌더 경로 정정 (TypesetEngine pagination drift, TAC 표/그림 좌표 통합 수정), export text/markdown 추가 (Task #237), v0.7.6/v0.7.7 릴리즈 흡수.

### Added — Document IR v1.1 (8 신규 블록 + Furniture 채움)

- `PictureBlock` (S1) — 이미지. `image: ImageRef | None` (URI 스킴 `bin://<bin_data_id>` 기본), `caption: CaptionBlock | None` (S3 부터), `description: str | None` (HWP alt-text). `Document.bytes_for_image(picture)` 헬퍼로 raw bytes 해석.
- `FormulaBlock` (S2) — 수식. `script: str` (HWP equation script raw) + `script_kind: Literal["hwp_eq", "latex", "mathml"]` + `text_alt: str | None` (RAG 폴백 평문 근사). LaTeX/MathML 자동 변환은 v0.3.0 미제공 (공개 변환기 부재).
- `FootnoteBlock` / `EndnoteBlock` (S2) — 각주 / 미주. `blocks: list[Block]` 재귀, `marker_prov` (본문 인용 위치) 와 `prov` (각주 본문 위치) 분리. 각주/미주 본문은 `furniture.footnotes` / `endnotes` 로 라우팅 — body 검색 오염 회피.
- `ListItemBlock` (S3) — 목록 항목. `level + marker + enumerated` 평면 모델 (group container 미도입, HWP 상류가 list group 미지원). `marker` 는 v0.3.0 placeholder (`"•"` / `"1."` / `"-"`) — 정확 marker (`"가."`, `"(a)"`) 는 v0.4.0+.
- `CaptionBlock` (S3) — 캡션. `blocks: list[Block]` 재귀 + `direction: Literal["top", "bottom", "left", "right"]`. 부모 컨테인먼트 — `PictureBlock.caption` / `TableBlock.caption_block` 으로 1:1 부착 (ref-id 미도입). v0.2.0 `TableBlock.caption: str` 보존 + `caption_block` 옵셔널 추가.
- `TocBlock` + `TocEntryBlock` (S3) — 목차. `entries: list[TocEntryBlock]` (TocEntryBlock 은 leaf type, Block 유니온 멤버 아님). v0.3.0 entries 는 빈 placeholder — 항목 추출은 v0.4.0+ (heading hierarchy + bookmark resolver 필요).
- `FieldBlock` + `FieldKind` (S3) — 필드. 닫힌 `Literal` 14 종 (`date`/`crossref`/`hyperlink`/...) + `"unknown"` 안전판 + `field_type_code: int | None` (forward-compat). `FieldType::Formula` 는 `"calc"` (Equation 의 `"formula"` 와 이름 충돌 회피).
- `Furniture` 채움 (S1+S2) — `page_headers` / `page_footers` (master_pages + Control::Header/Footer 매핑) / `footnotes` / `endnotes` 모두 실제 본문 출고. `iter_blocks(scope="furniture")` 순서: page_headers → page_footers → footnotes → endnotes (v0.2.0 furniture 순서 계약 확장).

### Added — `rhwp-py` CLI 재도입

v0.2.0 에서 폐기됐던 CLI 를 별도 이름 (`rhwp-py`) 으로 재도입. 상류 Rust `rhwp` 바이너리와 PATH 충돌 회피 + Python 고유 가치 (IR / LangChain) 에 집중 — 기능 중복 0.

- 신규 entry point: `rhwp-py = "rhwp.cli:app"` (typer 지연 로드, 미설치 시 친절 에러 + exit 2).
- 서브커맨드: `parse` (요약 정보) / `version` / `schema` (in-package JSON Schema) / `ir` (전체 IR JSON) / `blocks` (블록 스트림 NDJSON / JSON / text) / `chunks` (LangChain RecursiveCharacterTextSplitter 결과).
- `blocks` 의 `--kind` enum 11 종 (`paragraph` / `table` + 8 신규 + `all`) — IR 확장 GA 와 동기.
- `chunks --include-furniture` — `HwpLoader(mode="ir-blocks", include_furniture=True)` 와 동일 정책.
- 글로벌 옵션 `--quiet/-q` — stderr progress 메시지 가드.
- 새 extras: `[cli]` (typer 만), `[cli-chunks]` (typer + langchain-text-splitters).
- 업스트림 바이너리와의 역할 분담: 구조 추출은 `rhwp-py`, 시각 출력 (SVG/PDF) / 메타데이터 덤프 (`info`/`dump`) / 라운드트립 진단 (`diag`/`ir-diff`) 은 상류 `rhwp` — overlap 0.

### Added — LangChain `HwpLoader.include_furniture`

- `HwpLoader(mode="ir-blocks", include_furniture=True)` — body 다음에 furniture (page_headers / page_footers / footnotes / endnotes) 도 LangChain Document 로 yield. 각 furniture Document 는 `metadata.scope="furniture"` 로 표시되어 RAG 가 body / furniture 분리 색인 가능.
- 기본 `include_furniture=False` — v0.2.0 시절 동작 (body 만) 보존.
- `mode="single"` / `"paragraph"` 에서는 `include_furniture` 무시 — text 추출은 항상 body 만.

### Added — Schema GA + content-addressed alias

- SchemaVersion `"1.0"` → `"1.1"` (in-place v1 URL — major 안의 minor 추가).
- `_KNOWN_KINDS` 11 known kinds (10 known + UnknownBlock) — `Block` Annotated Union 11 멤버. callable Discriminator 는 O(1) lookup.
- JSON Schema in-place 갱신 — `python/rhwp/ir/schema/hwp_ir_v1.json` (1,261 lines, 20 `$defs`).
- Content-addressed alias `hwp_ir_v1-sha256-<hash>.json` — `publish-schema.yml` 가 매 deploy 시 hash-tagged immutable copy 를 alongside 발행. 구 hash 는 영구 보존 (SchemaStore / 외부 도구 reproducibility).
- `_harden_unknown_variant` 가 `_KNOWN_KINDS` SSOT 를 사용 — `TocEntryBlock.kind="toc_entry"` 같은 leaf-only kind 가 not.enum 에 포함되어 라운드트립 깨지는 케이스 회피.

### Fixed

- LangChain `HwpLoader(mode="ir-blocks")` 와 CLI `rhwp-py blocks --format text` 가 각주·미주·캡션 본문을 평문화할 때 `ParagraphBlock` 만 처리하여 `ListItemBlock` 으로 변환된 list 항목이 RAG 색인에서 통째로 누락되던 문제 정정. 신규 `rhwp.ir._plain_text` 모듈에 `ParagraphBlock` + `ListItemBlock` + `FormulaBlock` + `FieldBlock` 평문 추출 SSOT 헬퍼 (`block_inline_text` / `join_inline_blocks`) 를 도입하고 integration / CLI 양쪽에서 공유한다. caption 평문화도 동일 정책으로 통합 (`langchain.py::_caption_plain_text` / `cli/ir.py::_caption_plain` 제거).

### Documentation

- `docs/roadmap/v0.3.0/ir-expansion.md` — IR 확장 spec (8 결정 사항 + research 인용).
- `docs/roadmap/v0.3.0/cli.md` — `rhwp-py` 재도입 spec (이름 선정 + overlap=0 + extras 정책).
- `docs/design/v0.3.0/ir-expansion-research.md` / `cli-research.md` — 결정 증거.
- `docs/implementation/v0.3.0/stages/stage-{1..4}.md` — 단계별 구현 로그 (S1: Picture+Furniture, S2: Formula+Footnote/Endnote, S3: ListItem+Caption+Toc+Field, S4: Schema GA + CLI + LangChain include_furniture + 문서).
- `README.md` — v0.3.0 신규 블록 + `rhwp-py` CLI 섹션 추가, content-addressed alias 안내.

### Tests

- 5 신규 IR 테스트 파일 (S1 picture+furniture, S2 formula+footnote, S3 list+caption+toc+field) + 1 CLI 테스트 파일 → 405 (S3) → S4 추가.
- `tests/test_cli.py` — typer.testing.CliRunner 기반 smoke + 통합 (parse/version/schema/ir/blocks/chunks 전 서브커맨드 + exit code 1/2 검증 + langchain-text-splitters 미설치 monkeypatch).
- `tests/test_langchain_loader_ir.py` 확장 — `include_furniture` 옵션 4 테스트.
- CI `test-without-extras` skip count 4 → 5 (typer 추가).
- `tests/test_ir_plain_text.py` 신규 + footnote/caption 회귀 테스트 (LangChain·CLI 양쪽) — ListItemBlock 누락 정정 가드.
- 테스트 docstring 의 가변 카운트·스테이지 마커 정리 — 다른 파일·CI 잡에 의존하는 카운트가 박혀 있어 stale 되는 안티패턴 (`5 skipped 카운트 중 1` / `exactly 29 테스트 유지` 등) 제거, SSOT 단일화.

### Deferred to v0.4.0+

- `ListItemBlock` 정확 marker (`"가."`, `"(a)"`) — `Numbering.level_formats` lookup.
- `TocBlock.entries` 채움 + `target_section_idx` resolver + `is_stale` 검출.
- `FieldBlock.cached_value` 추출 (paragraph text inline `field_ranges` 매핑 필요).
- `InlineRun.href` 자동 채움 (Hyperlink/Bookmark Field 와 cross-link).
- `PictureBlock` `embedded` / `external_dir` 임베딩 모드 (`Document.to_ir(image_mode=...)` 옵션).
- `RevisionMark` (변경 이력) — 상류 미지원 (영구 비목표 후보).

## [0.2.0] — 2026-04-25

MINOR release — Phase 2 착수. RAG / LLM 파이프라인이 직접 소비하는 구조화 Document IR v1 (Pydantic V2 + JSON Schema Draft 2020-12) 을 도입. 기존 `Document` / `HwpLoader` API 는 변경 없음 (backward-compatible). 상류 `edwardkim/rhwp` 커밋 핀을 `bea635b` (main HEAD) 로 갱신 — v0.1.0 의 `1636213` 이후 upstream 변경은 docs (매뉴얼 현행화 / README 동기화 / 자기검열) 만으로 코드 동작 변화 없음. BMP→PNG 재인코딩 fix (#240) 는 여전히 upstream `origin/devel` 에만 있으며 본 release pin 에 미포함 — BMP 임베딩 HWP 의 SVG/PDF 렌더링 이슈는 upstream main 머지를 대기.

### Added — Document IR v1

**Document IR v1** — RAG / LLM 파이프라인이 직접 소비 가능한 구조화 문서 모델. Pydantic V2 기반 공개 타입 + JSON Schema (Draft 2020-12).

- `rhwp.ir.nodes` 모듈 — `HwpDocument` / `ParagraphBlock` / `TableBlock` / `TableCell` / `InlineRun` / `Provenance` / `UnknownBlock` / `Furniture` / `DocumentMetadata` / `Section` (10 노드, 전부 `frozen=True` + `extra="forbid"`).
- Callable `Discriminator` 기반 `Block` 태그드 유니온 — 미지 `kind` 는 `UnknownBlock` 으로 라우팅하여 forward-compat 보장 (v0.3.0 의 새 블록 타입이 v0.2.0 소비자를 깨뜨리지 않음).
- `Document.to_ir() -> HwpDocument` + `Document.to_ir_json(*, indent=None) -> str` — Rust `OnceCell<Py<PyAny>>` lazy 캐시 (unsendable 덕에 lock 불필요).
- `HwpDocument.iter_blocks(*, scope, recurse)` — body/furniture/all scope + TableCell 재귀 DFS 순회.
- Rust 측 HTML/text 직렬화 — attribute 순서 고정 (rowspan→colspan), HtmlRAG 호환.
- JSON Schema export — `rhwp.ir.schema.export_schema()` / `load_schema()` / `SCHEMA_ID` / `SCHEMA_DIALECT` + in-package `hwp_ir_v1.json` + `python -m rhwp.ir.schema` CLI.
- Discriminator 후처리 — `_harden_unknown_variant()` 가 UnknownBlock.kind 에 `not.enum: [known kinds]` 주입하여 oneOf 검증 정확도 보장.
- `HwpLoader` 에 `mode="ir-blocks"` 추가 — Block 을 LangChain `Document` 로 매핑 (표는 HTML content + 구조화 메타, 단락은 text + Provenance).
- `TableCell.role="layout"` 자동 태깅 — 병합된 빈 셀 (구조 유지용 비의미 셀) 을 LLM 이 "레이아웃 요소" 로 인식하도록 시맨틱 구분. 보수적 heuristic: 병합 AND 공백만 있는 셀만 `layout`, 그 외 empty 셀은 `data` 유지.
- `.github/workflows/publish-schema.yml` — GitHub Pages 배포 파이프라인, 불변 경로 정책 (v1 URL 영구) 자동화.
- Provenance 단위는 **Unicode codepoint** — Python `str[i]` 슬라이싱과 직접 호환 (이모지/SMP CJK 혼용에서도 off-by-one 없음).
- 신규 런타임 의존성: `pydantic>=2.5,<3`. 테스트 의존성: `jsonschema>=4`.
- 문서: `docs/roadmap/v0.2.0/ir.md` (사양), `docs/design/v0.2.0/ir-research.md` (7개 결정 증거), `docs/implementation/v0.2.0/stages/stage-{1..5}.md`.
- 테스트: **165 passed** — IR schema/roundtrip/tables/iter/export + LangChain ir-blocks + Rust unit tests (`cargo test` 5 passed).

### Added — Binding 구조 개선 (Python wrapper class + async 진입점)

`#[pyclass(unsendable)]` 제약 안에서 가능한 최선의 binding 구조와 async 진입점을 정착. 사용자-대면 API 는 전부 보존 — 가산만 있음 (breaking 없음).

- **Python wrapper class 패턴**: Rust `_Document` 는 `#[pyclass(name = "_Document", module = "rhwp._rhwp", unsendable)]` thin core 로, Python `rhwp.Document` 는 `__slots__ = ("_inner",)` + `_from_rust` factory 로 thin core 를 감싸는 wrapper. 모든 메서드는 pass-through.
- `Document.from_bytes(data, *, source_uri=None) -> Document` — bytes 기반 생성 classmethod (Rust `_Document::from_bytes` + `py.detach` 로 GIL 해제). 네트워크 fetch / in-memory archive / `aparse` 내부 경로용.
- `rhwp.aparse(path) -> Document` async 함수 — `aiofiles` 로 파일 I/O 만 async 처리, 파싱은 event-loop 스레드에서 sync (`Document.from_bytes`). `unsendable` 제약 상 `asyncio.to_thread(parse, path)` 가 panic 하므로 이 경로가 유일하게 안전한 async 진입점.
- `[async]` optional extras 추가 — `aiofiles>=23`. 미설치 시 `aparse` 호출 시점에 명시적 `ImportError` (silent fallback 없음).
- `HwpLoader.aload` / `alazy_load` async override — `rhwp.aparse` 위에 구축. 공통 yield 로직 `_yield_documents` 헬퍼로 sync/async 공유.
- `python/rhwp/_rhwp.pyi` 신규 — Rust extension (`_Document`, `version`, `rhwp_core_version`) 의 Python 측 타입 stub.

### Changed — Phase 2 계획 전환

- 원안의 CLI 도구 (`rhwp` 바이너리) 는 **폐기**. 업스트림 `edwardkim/rhwp` 의 Rust 바이너리가 같은 이름을 점유하므로 충돌 방지 + Python 고유 가치 (RAG / LangChain 통합) 에 집중. 상세: `docs/roadmap/v0.2.0/ir.md` §방향 전환 배경.
- `python/rhwp/__init__.pyi` 에 `Document.to_ir` / `to_ir_json` 타입 힌트 추가.
- `pyproject.toml [tool.maturin] include` 에 `python/rhwp/ir/schema/*.json` 포함 (wheel + sdist).

### Changed — Python 지원 범위 상향 (3.10+)

- Python **3.9 지원 드랍** — `requires-python = ">=3.10"`, `pyo3` feature 를 `abi3-py39` → `abi3-py310` 으로 전환, CI 매트릭스에서 `3.9` 제거. Python 3.9 는 2025-10-31 EOL 이후 보안 패치가 중단된 상태 (> 6 개월 경과). 기존 공개 API 는 전부 호환 — 3.9 사용자는 PyPI 의 `rhwp-python 0.1.x` 를 계속 사용 가능.
- `rhwp.ir.schema.load_schema()` 의 `Traversable.joinpath()` 호출을 chain 패턴 (`joinpath(a).joinpath(b)`) 으로 정리 — `*descendants` 가변 인자 시그니처가 표준 라이브러리에 도입된 시점이 버전별로 달라 typeshed 기준 pyright 가 py3.9/3.10/3.11 에서 `reportCallIssue` 를 내는 문제 제거.

### Changed — IR 매핑 구조 (Rust → Python 이전)

IR 합성 (HTML 직렬화 / cell role 분류 / inline run 폴백) 을 Rust 에서 Python 으로 이전. IR 진화 시 `maturin rebuild` 회피 + Python-only 기여자 진입장벽 제거. 외부 API (`Document.to_ir()`, `to_ir_json()`, `iter_blocks` 등) 모두 동일, 캐시 identity (`doc.to_ir() is doc.to_ir()`) 유지.

- `src/ir.rs` 527 → 254 줄. raw 평탄화 + UTF-16↔codepoint 변환만 담당. `#[derive(IntoPyObject)]` struct 5개 (`RawDocument` / `RawParagraph` / `RawTable` / `RawCell` / `RawCharRun`) 로 PyDict 자동 생성.
- `python/rhwp/ir/_mapper.py` 신규 — raw dict → `HwpDocument` 합성. Rust 에 있던 `escape_html` / `cell_role` / `table_to_html` / `build_inline_runs` 폴백 로직 전부 이전.
- `python/rhwp/ir/_raw_types.py` 신규 — Rust struct 미러 `TypedDict` 5개. nested 구조에서 `BaseModel` 대비 약 2.5× 빠른 internal raw record (공식 벤치마크 기준).
- `tests/test_ir_mapper.py` 신규 — Rust 에서 사라진 `#[cfg(test)]` 단위 테스트 (escape 순서, cell role 3갈래, inline run 폴백 정책) 의 Python 측 보존.
- `tests/test_from_bytes.py` 신규 — bytes 기반 생성 검증.
- `tests/test_async.py` 신규 — `aparse` + `aiofiles` 경로 검증 + 미설치 시 `ImportError` 검증.

### Documentation

- `CLAUDE.md` async direction 섹션 갱신 — `asyncio.to_thread(rhwp.parse, path)` 가 `unsendable` 제약 상 panic 함을 실험으로 확인. forbidden vs supported async 패턴, `aparse` + `aiofiles` 권장 경로, 향후 upstream `RefCell` 변경 시 재검토 가능성 안내.

### Deferred to v0.3.0+

- `PictureBlock` / `FormulaBlock` / `FootnoteBlock` / `ListItemBlock` / `CaptionBlock` / `TocEntryBlock` / `FieldBlock` — 현재는 미지 `kind` → `UnknownBlock` 폴백.
- Furniture 본문 파싱 (머리글/꼬리말/각주 내용).
- `DocumentMetadata.creation_time` / `modification_time` 을 `datetime` 으로 교체 (현재 `str | None`).
- text/table 정확 interleaving (컨트롤 문자 0x0B 위치 기반).
- LLM strict-mode 완전 호환 — `export_schema(strict=True)` 옵션.
- SchemaStore 카탈로그 등록 / content-addressed alias — GA 후 별도 PR.

## [0.1.1] — 2026-04-23

Patch release: fixes the sdist packaging so the source distribution stays within PyPI's 100 MB file size limit.

### Fixed

- `maturin sdist` now excludes `external/rhwp/samples/` (≈60 MB of test fixture HWP/HWPX files). The v0.1.0 sdist exceeded PyPI's 100 MB limit and was rejected by PyPI; wheels were unaffected and the `rhwp-python 0.1.0` wheels on PyPI remain functional.

### Changed

- `[tool.maturin] exclude` in `pyproject.toml` adds `**/samples/**` for the sdist format.

## [0.1.0] — 2026-04-22

Initial PyO3 Python bindings for the rhwp Rust HWP/HWPX parser and renderer.
Phase 1 milestone (upstream issue [edwardkim/rhwp#227](https://github.com/edwardkim/rhwp/issues/227)).

Distributed as `rhwp-python` on PyPI; `import rhwp` for usage.
The `rhwp` Rust core is consumed via git submodule pinned to upstream commit `1636213` (edwardkim/rhwp `main` as of 2026-04-22).

### Added

- Core bindings:
  - `rhwp.version()` — this Python package version.
  - `rhwp.rhwp_core_version()` — underlying Rust core version.
  - `rhwp.parse(path)` → `Document`.
  - `rhwp.Document(path)` — direct constructor, equivalent to `parse()`.
  - Attributes: `section_count`, `paragraph_count`, `page_count`.
  - Methods: `extract_text()`, `paragraphs()`, `render_svg(page)`,
    `render_all_svg()`, `export_svg(dir, prefix=None)`,
    `render_pdf() → bytes`, `export_pdf(path) → int`, `__repr__()`.
- GIL release (`py.detach`) on `parse()`, `render_pdf()`, and `export_pdf()` PDF-conversion step — parallel parse throughput up to **4.01×** on 8 cores (Apple M2).
- Crossplatform `abi3-py39` wheels: Linux x86_64 + aarch64 (manylinux auto), macOS x86_64 + aarch64, Windows.
- Optional extras `rhwp-python[langchain]`:
  - `rhwp.integrations.langchain.HwpLoader(BaseLoader)` with `single` / `paragraph` modes.
  - `lazy_load()` yields `Document` objects on-the-fly for O(1) peak memory in `paragraph` mode.
  - Metadata: `source`, `section_count`, `paragraph_count`, `page_count`, `rhwp_version`, plus `paragraph_index` in paragraph mode.
- PEP 561 typed API (`py.typed` + `.pyi` stubs), pyright clean on valid usage, four intentional-error samples verified.
- pytest suite: 48 core + 29 LangChain = **77 tests**.
- Error mapping preserves Python exception hierarchy: `FileNotFoundError` (NotFound), `PermissionError` (PermissionDenied), `OSError` (other I/O), `ValueError` (invalid format).

### Security

- No known CVEs.
- Built with Rust 1.83+ (PyO3 0.28 MSRV). Bindings layer adds no `unsafe` code.

### Known limitations

- `Document` is `#[pyclass(unsendable)]` — cross-thread use raises `RuntimeError`. Run `parse + consume` inside worker threads.
- No font embedding / debug overlay / page metadata APIs (Phase 2+).
- No HWP/HWPX serialization (save) — read/render only.
- No structured access to tables / images / formulas — text extraction only.

### Distribution

- Local `maturin build --release` wheel (3.0 MB) verified end-to-end in a clean venv: install → import → `rhwp.parse` → `HwpLoader` load. (Note: the v0.1.0 sdist exceeded PyPI's 100 MB limit and did not upload; fixed in [0.1.1](#011--2026-04-23).)
- GitHub Actions workflow (`publish.yml`) builds Linux (x86_64 + aarch64) / macOS (x86_64 + aarch64) / Windows wheels + sdist on release publish, then uploads via PyPI Trusted Publisher (OIDC).

[Unreleased]: https://github.com/DanMeon/rhwp-python/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/DanMeon/rhwp-python/releases/tag/v0.3.0
[0.2.0]: https://github.com/DanMeon/rhwp-python/releases/tag/v0.2.0
[0.1.1]: https://github.com/DanMeon/rhwp-python/releases/tag/v0.1.1
[0.1.0]: https://github.com/DanMeon/rhwp-python/releases/tag/v0.1.0
