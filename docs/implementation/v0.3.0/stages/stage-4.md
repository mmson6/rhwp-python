---
status: Frozen
description: "v0.3.0 S4 작업 로그 — Schema v1.1 GA + 'rhwp-py' CLI 재도입 + LangChain include_furniture (IR 확장 + CLI 두 축 동시 GA)"
ga: v0.3.0
last_updated: 2026-04-28
---

# Stage S4 — Schema v1.1 GA + rhwp-py CLI + LangChain include_furniture (완료)

**작업일**: 2026-04-28
**계획 문서**: [roadmap/v0.3.0/ir-expansion.md](../../../roadmap/v0.3.0/ir-expansion.md) §구현 스테이지 분할 + [roadmap/v0.3.0/cli.md](../../../roadmap/v0.3.0/cli.md)
**선행 stage**: [stage-3.md](stage-3.md) (ListItem + Caption + Toc + Field)
**두 축 동시 GA**: IR 확장과 CLI 두 spec 을 한 릴리스에 동시 GA.

## 스코프

ir-expansion.md §S4 row + cli.md §S1~S4 row 를 한 stage 에 통합 — 두 축 동시 GA 정책에 따라 IR 확장 GA 와 CLI 재도입을 같은 시점에 발행한다.

**ir-expansion.md §S4 row 매핑**:

- SchemaVersion `1.1` GA — in-package JSON in-place 갱신 (S3 에서 1.1 정착, S4 는 publish path 정비)
- Content-addressed alias `hwp_ir_v1-sha256-<hash>.json` 발행 — `publish-schema.yml` 의 page artifact 준비 단계에 추가
- `rhwp-py blocks --kind` 확장 — IR 확장 8 신규 kind + `paragraph`/`table` + `all` = 11 종 enum
- `HwpLoader(mode="ir-blocks")` 신규 매핑 — `include_furniture: bool` 옵션 추가 (S3 알려진 한계 격상)
- README/examples 업데이트

**cli.md §S1~S4 row 통합 매핑**:

- S1 (CLI 스켈레톤): `python/rhwp/cli/{__init__.py, __main__.py, app.py}` + `parse` / `version` / `schema` 서브커맨드 + `[cli]` extras + `[project.scripts] rhwp-py` entry point
- S2 (IR 커맨드): `python/rhwp/cli/ir.py` 의 `ir` / `blocks` 서브커맨드 + `--format json|ndjson|text`
- S3 (LangChain chunks): `python/rhwp/cli/chunks.py` + `[cli-chunks]` extras gate
- S4 (문서화·검증): README / CHANGELOG / 실제 HWP 검증

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/cli/__init__.py` | +27 (신규) | `app()` entry point — typer ImportError 가드 (typer/click 부재 시 친절 메시지 + exit 2). 패키지 import 자체는 typer 없이도 성공 (지연 로드) |
| `python/rhwp/cli/__main__.py` | +6 (신규) | `python -m rhwp.cli` 진입점 — entry point 와 동일 동작 (`rhwp-py` 명령 미등록 시 폴백) |
| `python/rhwp/cli/_state.py` | +16 (신규) | `--quiet/-q` 글로벌 플래그 모듈 변수 — callback (app.py) ↔ 서브커맨드 (ir.py) 중립 모듈로 순환 import 회피 |
| `python/rhwp/cli/app.py` | +117 (신규) | Typer 앱 + `_global_options` callback (`--quiet`) + `parse_cmd` / `version_cmd` / `schema_cmd` 본 모듈 + `register_ir_commands` / `register_chunks_command` 호출 |
| `python/rhwp/cli/ir.py` | +222 (신규) | `ir_cmd` (전체 IR JSON) + `blocks_cmd` (NDJSON 기본). `BlockKindOpt` (11 종) / `BlockScopeOpt` (3) / `BlocksFormatOpt` (3) str Enum. `_filter_blocks` (kind/limit) + `_emit_blocks` (포맷 분기) + `_block_to_text` (10 블록 평문 추출, LangChain `_block_to_content_and_meta` 와 같은 정책) |
| `python/rhwp/cli/chunks.py` | +104 (신규) | `chunks_cmd` — `langchain_text_splitters` 미설치 시 exit 2 + 친절 메시지. `ChunksMode` (3) / `ChunksFormat` (3) str Enum. `--include-furniture` 플래그 → `HwpLoader(include_furniture=...)` 전달 |
| `python/rhwp/integrations/langchain.py` | +27 / -1 | `HwpLoader.__init__` 에 `include_furniture: bool = False` 파라미터. `_yield_documents` 가 ir-blocks 모드에서 body 다음 furniture 블록도 yield (`metadata.scope="furniture"`). single/paragraph 모드는 옵션 무시 |
| `python/rhwp/integrations/langchain.pyi` | +8 / -1 | stub 에 `include_furniture: bool` attribute + `__init__` 키워드 인자 추가 |
| `pyproject.toml` | +24 | `[cli]` (typer 만) / `[cli-chunks]` (typer + langchain-core + langchain-text-splitters) extras 추가, `[project.scripts] rhwp-py = "rhwp.cli:app"` entry point 등록, `[dependency-groups] testing` 에 typer 추가, `[langchain]` extras 에 `langchain-text-splitters>=0.2` 추가 (M3 fix — `[cli,langchain]` 조합으로도 chunks 작동), `[tool.ruff.lint.per-file-ignores]` 로 `cli/*.py` + `examples/*.py` 의 B008 ignore (typer 관용 패턴) |
| `tests/test_cli.py` | +285 (신규) | 20 테스트 — 파일 레벨 `importorskip("typer")` (CI 5 skip 카운트 중 1). `--help` smoke / `version` / `parse` (포맷 + exit 1) / `schema` (stdout vs `export_schema()` 동등 + `--out`) / `ir` (default 한 줄 vs `--indent` 다중 줄 + `--out`) / `blocks` (NDJSON / JSON array / text + `--kind table` 필터 + `--scope furniture` + `--no-recurse` 차이) / `chunks` (`--mode`, `--include-furniture`, monkeypatch 로 langchain-text-splitters 부재 시 exit 2) |
| `tests/test_langchain_loader_ir.py` | +33 | `include_furniture` 4 테스트 — default False / True 면 body_only ≤ with_furn (일반 invariant) / `metadata.scope` in {None, "furniture"} / paragraph 모드는 옵션 무시 (a/b 동등) |
| `.github/workflows/ci.yml` | +3 / -2 | `pyright` scoped 목록에 `tests/test_cli.py` 추가. `test-without-extras` 잡의 skip count 4 → 5 (typer 추가) + 에러 메시지 갱신 |
| `.github/workflows/publish-schema.yml` | +13 / -2 | `Prepare pages directory` 단계에 content-addressed alias 발행 추가 — `shasum -a 256 $f` 로 해시 추출, `pages/schema/hwp_ir/${name}-sha256-${sha}.json` 파일 alongside 복사. 이름 패턴은 ir-expansion.md § 스키마 버저닝 정확 매핑. paths 트리거를 `hwp_ir_v1.json` → `hwp_ir_v*.json` glob 으로 일반화 (m5 fix — v2 도입 시 자동 트리거) |
| `README.md` | +13 / -3 | "v0.3.0 신규" 단락 + "rhwp-py CLI" 섹션 (압축형 — 핵심 명령 3 개 + 상류 분담 한 줄 + cli.md spec 링크). content-addressed alias 안내 한 줄 추가. LangChain 섹션에 `include_furniture=True` 한 줄 |
| `CHANGELOG.md` | +68 / -1 | `[0.3.0] — 2026-04-28` 신규 항목 — 8 신규 IR 블록 / `rhwp-py` CLI / `include_furniture` / Schema GA + alias / 문서 / 테스트 / Deferred to v0.4.0+ 7 개 카테고리. footer anchor link `[0.3.0]` 추가 + `[Unreleased]` compare URL 갱신 (m3 fix) |
| `docs/implementation/v0.3.0/stages/stage-4.md` | (본 문서) | S4 구현 로그 — v0.2.0 패턴 재사용 |

## S4 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **두 spec (ir-expansion + cli) 동시 GA** | 한 stage 에 통합 | 두 축 동시 GA 정책 — "IR 확장 매퍼/Pydantic 모델이 먼저 GA 가능 상태에 도달해야 CLI enum 도 의미 있게 노출 — 따라서 구현 순서는 IR 확장 stage S1~S3 → IR 확장 S4 (스키마 1.1) + CLI S2 (`blocks` enum 확장) 동시 진행이 자연" |
| **`[langchain]` extras 에 langchain-text-splitters 포함 (M3 fix)** | 포함 | cli.md spec 의 `[cli,langchain]` 조합 약속 위반 회피. RAG 사용처에서 text-splitters 거의 항상 동반 — v0.2.0 사용자 업그레이드 시 자동 설치 비용 ≪ spec 충실성. 단일 source of truth |
| **`rhwp.cli.app` import chain 의 모든 ImportError 를 친절 처리 (M2 fix)** | `rhwp.*` 자체 모듈만 raise, 그 외는 모두 typer 설치 결함 메시지 + exit 2 | `e.name in ("typer", "click")` 화이트리스트는 transitive (rich/shellingham/annotated-doc) 누락 시 raw traceback 노출 — 사용자에게 cli.md spec § typer 미설치 시 동작 약속 위반 |
| **`blocks --format ndjson|json` 도 빈 블록 skip (m1 fix)** | LangChain loader 와 일관 — `_filter_blocks` 에서 모든 포맷 공통 skip | RAG 1차 사용처 일관성 — `rhwp-py blocks --format ndjson` 결과를 vector DB 에 흘리는 사용자가 LangChain loader 의 결과와 동일 청크 수를 기대. 원시 IR 모두 보려면 `rhwp-py ir` 사용 |
| **CLI 패키지 분리 구조** | spec stage 표 그대로 (`app.py` / `ir.py` / `chunks.py`) | cli.md § 구현 스테이지 분할 표 충실. 단일 모듈로 합치면 chunks 의 langchain extras 가드와 IR 확장 매핑이 한 파일에 섞여 향후 진화 비용 |
| **`_state.py` 16 줄 모듈 분리** | 별도 모듈 유지 | `--quiet` 는 cli.md § 글로벌 옵션 표 명시. callback (app.py) ↔ 서브커맨드 (ir.py) 중립 import 가 필요 — app.py 인라인하면 ir.py 가 app.py import 시 순환. 작은 모듈이지만 의도 명확 |
| **CLI 평문 추출 (`_block_to_text`) 정책** | LangChain loader 와 의도적으로 동일 우선순위 | RAG 일관성 — Picture caption→description 폴백, Formula text_alt→script 등 같은 정책. CLI 가 langchain-core 의존을 가질 수 없어 헬퍼 공유 불가 → 양쪽에 작성하되 docstring 상호 참조 |
| **`--quiet` 가드 범위** | schema/ir 의 `wrote N bytes` 메시지만 | 다른 stderr 출력은 모두 에러 메시지 (exit 1/2 와 함께) — quiet 무관하게 항상 출력. cli.md spec 의 "stderr 메시지 최소화" 본질은 progress 메시지 |
| **`BlockKindOpt` enum 11 종** | str Enum + `value` = IR `kind` 값 | typer 0.24 가 str Enum 자동 매핑 — 사용자 입력 (`--kind list_item`) 과 IR `block.kind` 값 1:1. Literal 도 가능하지만 typer 의 Click 바인딩이 안전한 Enum 패턴. global 룰 (Pydantic field 의 Literal 권장) 은 CLI option 컨텍스트에 무관 |
| **`--format` 기본값** | `parse`/`version` 사람 가독, `ir`/`schema` JSON, `blocks`/`chunks` NDJSON | cli.md § 결정 #3 정확 매핑 — kubectl/aws/gh 의 "스크립팅 primary 는 JSON" 관행 + jq streaming 친화 |
| **Exit code 규약** | 0 / 1 (사용자 오류) / 2 (extras 미설치) | cli.md § Exit code 규약 — typer 의 Click 기본은 usage error → exit 2. 우리는 cli.md spec 충실 위해 `path.exists()` 직접 검사 + `raise typer.Exit(code=1)` |
| **content-addressed alias 위치** | `pages/schema/hwp_ir/hwp_ir_v1-sha256-<hash>.json` (root level) | ir-expansion.md § 스키마 버저닝 의 정확 filename pattern. v1 디렉토리 하위 alias 도 가능했지만 spec text 의 "hwp_ir_v1-sha256-<hash>.json" 그대로 명시 |
| **alias 발행 스크립트** | bash + `shasum -a 256` | Linux runner (ubuntu-latest) 에서 표준. `awk '{print $1}'` 로 hash 추출 — `cut` 보다 공백 강건 |
| **`HwpLoader.include_furniture` default** | `False` | cli.md / ir-expansion.md spec 본문 — v0.2.0 시절 동작 보존 (body 만). True 면 footnote/endnote/header/footer Document 도 yield, 각 `metadata.scope="furniture"` |
| **single/paragraph 모드의 `include_furniture`** | 무시 | 두 모드는 텍스트 추출만 — body 만. furniture 본문은 IR 의 영역. 옵션을 명시적으로 raise 안 하고 silent ignore — 사용자가 모드를 자유로 전환 가능하도록 |
| **alias filename pattern 의 mutable scheme.json 와 공존** | `pages/schema/hwp_ir/v1/schema.json` (mutable, canonical `$id` URL) + `pages/schema/hwp_ir/hwp_ir_v1-sha256-<hash>.json` (immutable alias) | 둘은 같은 파일 복사본 — 사용자가 reproducible 한 snapshot 이 필요하면 alias URL, 항상 최신은 canonical. v2 추가 시 같은 루프가 v1/v2 alias 모두 발행 |
| **CI test-without-extras skip count 4 → 5** | typer 가 pytest 만 설치 시 부재 → test_cli.py file 레벨 importorskip → +1 | cli.md § CI 명시 — 새 extras-gated 테스트 파일 추가 시 ci.yml 의 skip count 동기 갱신 |

## 비타협 제약 준수

- 모든 신규 IR 모델 변경 없음 — S3 까지 정착한 11 멤버 Block 유니온 + 10 known kinds 유지 (`_KNOWN_KINDS` SSOT)
- `Literal` / `Enum` 어휘 모두 닫힌 형태 — CLI Enum value 가 IR `kind` 값과 1:1 (`list_item` 등)
- `Field(ge=/le=/gt=/lt=)` 사용 **없음** (S3 부터 유지)
- mapper 도메인 분기 (caption direction 폴백, FieldKind 어휘 검증, list marker placeholder) 변경 없음 — Python 위치 유지
- `__init__.pyi` 만 변경 (langchain.pyi) — `__init__.py` 는 추가 import 없음
- 외부 LLM-facing 어휘 (FieldKind / caption direction / Block kind) 는 S3 의 SSOT 유지
- CLI 도메인 분기는 모두 Python — Rust 변경 0 (clippy clean 자동 통과)
- 새 IR 도메인 모델 없음 — S4 는 publish + CLI + LangChain include_furniture 만 추가, IR 자체 진화 없음

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest -m "not slow"` | **429 passed** (S3 의 405 + S4 신규 24: CLI 20 + LangChain include_furniture 4; 2 skipped — 샘플에 수식·미주 부재) |
| `uv run pyright python/ tests/<scoped CI list> + tests/test_cli.py` | **0 errors, 0 warnings, 0 informations** |
| `uv run ruff check python/rhwp/cli/ tests/test_cli.py tests/test_langchain_loader_ir.py` | All checks passed (m4 per-file-ignores 로 typer B008 회피) |
| `cargo clippy --all-targets -- -D warnings` | clean (Rust 변경 0) |
| Schema regenerate diff (`python -m rhwp.ir.schema` vs in-package JSON) | no diff — S3 에서 정착한 1,261 lines / 20 `$defs` JSON 그대로 |
| CLI smoke `rhwp-py --help` | 6 서브커맨드 모두 노출 (parse / version / schema / ir / blocks / chunks) |
| CLI 통합 — `rhwp-py blocks table-vpos-01.hwpx --kind table --format ndjson` | 표 9 개 NDJSON yield, 각 줄 독립 JSON parse 가능 |
| CLI extras 가드 — monkeypatch 로 `sys.modules["langchain_text_splitters"] = None` | exit 2 + stderr "rhwp-py chunks requires `langchain-text-splitters`" |
| `code-reviewer` fresh-context 검증 | Critical 0 / Major 3 / Minor 5 / Nit 3 — 모든 11 건 fix 적용 (M1 chunks help Rich markup escape, M2 ImportError 가드 transitive deps 확장, M3 `[langchain]` extras text-splitters 추가, m1 ndjson/json 도 빈 블록 skip, m2 furniture 테스트 invariant 강화, m3 CHANGELOG footer, m4 ruff B008 ignore, m5 publish-schema paths glob, n1 cli/app.py imports 정리, n2 README v0.3.0 신규 H3 분리, n3 text 모드 HTML 부재 검증) |

### 테스트 커버리지 (cli.md §테스트 전략 → 실제 케이스)

| cli.md 요구 | 테스트 |
|---|---|
| `typer.testing.CliRunner` 기반 smoke 전 커맨드 | `test_help_lists_all_subcommands`, `test_version_outputs_match_rhwp_module`, `test_parse_summary_format`, `test_schema_stdout_matches_export_schema`, `test_ir_default_compact_single_line`, `test_blocks_ndjson_each_line_is_independent_json`, `test_chunks_paragraph_default` |
| `--help` 출력에 모든 서브커맨드 포함 | `test_help_lists_all_subcommands` |
| `--format json` 출력이 `json.loads` 로 파싱 | `test_blocks_format_json_returns_array`, `test_chunks_paragraph_default` |
| `--format ndjson` 각 줄 독립 JSON | `test_blocks_ndjson_each_line_is_independent_json`, `test_chunks_paragraph_default` |
| `version` 출력이 `rhwp.version()` 과 일치 | `test_version_outputs_match_rhwp_module` |
| `schema` 출력이 `rhwp.ir.schema.export_schema()` 와 동등 | `test_schema_stdout_matches_export_schema` |
| Exit code 1 (파일 없음) | `test_parse_missing_file_exit_1`, `test_chunks_missing_file_exit_1` |
| Exit code 2 (extras 부재) | `test_chunks_missing_text_splitters_exit_2` |
| 실제 샘플 통합 — `blocks --kind table --format ndjson` | `test_blocks_kind_filter_table` |
| `chunks --mode ir-blocks --format ndjson` ↔ `HwpLoader(mode="ir-blocks")` 동등 | `test_chunks_ir_blocks_mode` |
| **`--include-furniture` 동작** (cli.md spec § HwpLoader 변경) | `test_chunks_include_furniture_adds_scope_meta`, `test_include_furniture_yields_extra_documents`, `test_include_furniture_marks_scope_metadata` |

## 알려진 한계 (v0.4.0+ 검토)

- **`--quiet` 가드 범위 협소** — 현재는 `wrote N bytes` 두 메시지만 가드. 향후 verbose 모드 (`--verbose/-v`) 도입 시 reverse polarity 로 통합 검토. 현 시점은 spec 본문 § 글로벌 옵션 충실
- **`BlockKindOpt` 가 IR 의 `_KNOWN_KINDS` 와 별개 SSOT** — Python 어휘 두 곳에 11 종 Literal 중복. mapper 어휘 검증 set (`_VALID_FIELD_KINDS` 등) 과 같은 패턴이라 CLI 도 같은 trade-off — 도메인 별로 자체 어휘 보유 (Pydantic strict + typer Click 바인딩 양쪽 만족 위해)
- **`rhwp-py blocks --kind` 다중 선택 미지원** — cli.md spec 은 `<kinds>` 라 다중 가능성 시사하지만 v0.3.0 은 단일 kind 또는 `all`. 다중 선택 (`--kind paragraph,table`) 은 v0.4.0+ 에서 typer 의 list-of-Enum 패턴 검토
- **`chunks --mode single` 시 splitter 가 단일 거대 텍스트를 분할** — 사용자가 "single = 분할 안 함" 으로 오해 가능. cli.md spec 은 모드를 LangChain mapping 으로만 정의 — splitter 는 별개. v0.4.0+ 에서 `--no-split` 옵션 검토
- **content-addressed alias 가 매 deploy 마다 새 hash 생성 → pages 디렉토리 무한 누적** — 현재 alias 는 단순 `cp` 라 같은 hash 는 idempotent 하지만 `actions/deploy-pages@v4` 의 replace-all 동작 상 직전 deploy 의 alias 만 살아남는다. 영구 보존하려면 GitHub Pages 외부 (예: SchemaStore) 등록 필요 — v0.4.0+ 검토
- **`Document.to_ir(image_mode="embedded"|"external_dir")` 미구현** — ir-expansion.md § 비목표 명시. v0.3.0 은 `bin://` 단일 모드. embedded base64 inline 은 `[embed-images]` extras 후보 (v0.4.0+)
- **CLI 와 LangChain loader 의 평문 추출 정책 두 곳 작성** — `cli.ir._block_to_text` 와 `integrations.langchain._block_to_content_and_meta` 가 동일 정책. CLI 가 langchain-core 의존을 가질 수 없어 헬퍼 공유 불가 — 향후 별도 view module (`rhwp.ir._views`) 추출 검토 (v0.4.0+)
- **`blocks --format ndjson|json` 도 빈 블록 skip** (m1 fix 후 의도적 정책) — `_filter_blocks` 가 모든 포맷에서 `_block_to_text(block).strip() == ""` 인 블록을 skip 하여 LangChain loader 와 일관. 단점: 사용자가 "원시 IR 모든 블록" 을 보려면 `rhwp-py ir` 사용해야 (blocks 는 RAG-friendly stream 으로 위치). 결정 정당: ndjson/json 모드 ↔ LangChain Document 매핑 1:1 일관성, RAG 노이즈 회피

## v0.3.0 GA 진입 조건 (인수인계)

S4 가 GA 의 마지막 stage. release 진입 전 다음 명시:

1. **`Block` 유니온 + `_KNOWN_KINDS` 10 known** — S1~S3 에서 누적 정착, S4 변경 없음. 다음 MINOR 에서 새 kind 추가 시 `_KNOWN_KINDS` set + Block Annotated Union + `BlockKindOpt` Enum 세 곳 동기 갱신
2. **schema_version `"1.1"` GA** — JSON Schema in-package + GitHub Pages canonical URL + content-addressed alias 모두 발행 경로 정착. v2 (breaking change) 는 새 `python/rhwp/ir/schema/hwp_ir_v2.json` 추가만으로 발행 — `publish-schema.yml` 자동 처리
3. **`rhwp-py` 명령 경로** — `[project.scripts]` entry point + typer 지연 import 가드 패턴이 안정. 새 서브커맨드 추가는 `register_*_commands(app)` 패턴으로 — spec stage 표 그대로
4. **`HwpLoader.include_furniture` 패턴** — body 와 furniture 의 metadata 분리 (`scope="furniture"`) 가 v0.3.0 부터 contract. v0.4.0+ 에서 새 furniture 유형 (예: side-notes) 추가 시 같은 metadata 패턴 적용
5. **상류 visibility 의존성 추적** — `marker_prov.char_start/char_end` (S2) 와 `cached_value` (S3) 둘 다 상류 `find_control_text_positions` / `field_ranges` 매핑 필요. [docs/upstream/issue-find-control-text-positions.md](../../../upstream/issue-find-control-text-positions.md) 머지 시점에 v0.3.x patch 또는 v0.4.0 에서 격상 검토
6. **Cargo.toml version bump** — release tag `v0.3.0` 발행 전 Cargo.toml version 을 `0.3.0` 으로 갱신 (CLAUDE.md § Versioning / release 의 verify-version 규약 준수)
7. **실제 HWP 검증** — release 직전 examples/01~05 + `rhwp-py {parse,blocks,chunks,schema}` 를 본인 업무 HWP 파일 3 종 (일반 / 장문 / HWPX) 으로 돌려 출력 육안 확인

## 참조

- 상위 설계: [roadmap/v0.3.0/ir-expansion.md](../../../roadmap/v0.3.0/ir-expansion.md), [roadmap/v0.3.0/cli.md](../../../roadmap/v0.3.0/cli.md)
- 결정 사항 증거: [design/v0.3.0/ir-expansion-research.md](../../../design/v0.3.0/ir-expansion-research.md), [design/v0.3.0/cli-research.md](../../../design/v0.3.0/cli-research.md)
- 선행 stage: [stage-1.md](stage-1.md), [stage-2.md](stage-2.md), [stage-3.md](stage-3.md)
- 상류 제안 이슈 (S2 시점 정리): [docs/upstream/issue-find-control-text-positions.md](../../../upstream/issue-find-control-text-positions.md)
- v0.2.0 선례: [implementation/v0.2.0/stages/](../../v0.2.0/stages/) (S1~S5)
- Typer 공식: <https://typer.tiangolo.com/>
- Click 8.2+ CliRunner 변경 (`mix_stderr` 제거): <https://click.palletsprojects.com/en/stable/changes/#version-8-2-0>
