---
status: Frozen
description: "v0.5.0 S2 작업 로그 — view 도구 추가 (to_markdown / to_html). v0.4.0 view 렌더러 위 thin wrapper, 도구 카운트 4 → 6"
target: v0.5.0
last_updated: 2026-05-06
---

# Stage S2 — view 도구 추가 (완료)

**작업일**: 2026-05-06
**계획 문서**: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md) §구현 스테이지 분할 S2
**선행 stage**: [stage-1.md](stage-1.md) (서버 스켈레톤 + 코어 4 도구)

## 스코프

mcp.md §구현 스테이지 분할 S2 행 정확 매핑:

- `python/rhwp/mcp/tools.py` 에 `to_markdown(path)` / `to_html(path, *, include_css=False)` 추가
- `python/rhwp/mcp/server.py` `build_server()` 에 두 도구 등록 — 도구 카운트 4 → 6
- `tests/test_mcp_server.py` 의 `test_lists_exactly_four_tools` → `test_lists_exactly_six_tools` 갱신 + `TestToMarkdown` / `TestToHtml` 클래스 추가 (AC-6 spec 매핑)
- v0.4.0 view 렌더러 (`HwpDocument.to_markdown()` / `to_html(*, include_css=...)`) 위 thin wrapper — 추가 변환 / sanitize / wrapping 없이 pass-through

S3 (`chunks` extras gate), S4 (streamable-http transport), S5 (문서화·검증) 는 본 스테이지 범위 밖.

## 산출물

| 파일 | 변동 | 내용 |
|---|---|---|
| `python/rhwp/mcp/tools.py` | +30 / -1 | `to_markdown(path) -> str` / `to_html(path, *, include_css=False) -> str` 추가. 모듈 docstring 의 stage 분할 주석 갱신 (S1 4 + S2 2). v0.4.0 view API 와 동일하게 `include_css` keyword-only 강제 |
| `python/rhwp/mcp/server.py` | +3 / -2 | `build_server()` 가 6 도구 등록 — `server.tool(tools.to_markdown)` / `server.tool(tools.to_html)` 추가. 주석 갱신 ("S1 코어 4 + S2 view 2") |
| `tests/test_mcp_server.py` | +44 / -5 | 모듈 docstring AC 매핑 갱신 (AC-6 추가), `test_lists_exactly_six_tools` 로 rename + 도구 set 6 개로 확장, `TestToMarkdown` (2 테스트) / `TestToHtml` (3 테스트) 신설 — 모두 AC-6 spec 매핑 |
| `docs/traces/coverage.md` | +5 | auto-regen — `v0.5.0/mcp#AC-6` 매핑 3 개 추가 (TestToMarkdown::test_matches_view_api, TestToHtml::test_matches_view_api_no_css, TestToHtml::test_matches_view_api_with_css) |

## S2 확정 결정 사항

| 결정 | 선택 | 근거 |
|---|---|---|
| **`to_html` 의 `include_css` keyword-only 강제** | `def to_html(path: str, *, include_css: bool = False)` (positional 거부) | v0.4.0 `HwpDocument.to_html(*, include_css=False)` 의 invariant 와 동일. `include_css=True` 가 의미적으로 부울 플래그이고 호출처가 의도를 명시해야 한다는 view-layer 결정을 wrapper 가 침식하지 않게 함. JSON Schema 출고에는 영향 없음 (positional/keyword 구분 없음) — Python 호출 측면의 invariant 보존 |
| **"thin wrapper" 의미 — byte-equality 강제** | 도구 출력 == `HwpDocument.to_xxx(...)` 직접 호출 출력 (bytewise 동일) | AC-6 의 "thin wrapper" 를 "추가 변환 / sanitize 없음" 으로 해석. 테스트 (`TestToMarkdown::test_matches_view_api` / `TestToHtml::test_matches_view_api_no_css` / `..._with_css`) 가 byte-equality 검증. 이로써 향후 view API 가 진화해도 wrapper 가 "투명한 통과" 에서 벗어나면 자동 회귀 검출 |
| **docstring 에 view 동작 요약 복제** | tools.py 의 `to_markdown` / `to_html` docstring 이 GFM 표 / `<aside>` 각주 등 view 동작을 짧게 요약 | LLM 이 도구 호출 의도 / 결과를 정확히 추론하도록 schema 에 노출되는 description 을 간결하지만 informative 하게 유지. drift 위험 (view API 결정사항이 바뀌면 두 곳 동기화 필요) 은 인지하면서 LLM 도구 호출 정확도 우선 |
| **새 도구 등록 위치 — 같은 `build_server()` factory** | 별도 `build_view_tools()` 분기 없이 inline 등록 | S3 의 `chunks` 도구는 extras-gate 가 필요 (langchain-text-splitters 미설치 시 도구 자체 미등록 vs 등록 후 호출 시 에러) — 이 결정은 S3 에서 해결. S2 는 무조건 v0.4.0 view API (코어 wheel 내장) 가용하므로 분기 불필요 |
| **AC-2 의 도구 카운트** | S2 시점 6 (S1 의 4 + S2 의 2). spec 본문은 GA 기준 7 개 (S3 chunks 후 충족) | mcp.md AC-2 본문은 그대로 두고 (GA 기준 = 7 개), impl-log 에서 stage 별 진행 카운트만 기록 — stage-1 § S2 진입 조건 row 4 의 인계 사항 그대로 적용 |

## 비타협 제약 준수

- **`unsendable` 안전 패턴** — 새 2 도구 모두 sync 함수, handler 안에서 `rhwp.parse(path) → .to_ir() → .to_xxx(...)` → `str` 반환. Document 가 thread 경계 절대 안 넘음. `TestSyncHandler::test_all_registered_tools_are_sync` 가 등록된 6 도구를 walk 해 자동 커버 (S1 의 함수 walk 패턴이 의도대로 동작)
- **v0.4.0 view API 위 thin wrapper** — 추가 변환 / sanitize / wrapping 없음. byte-equality 테스트가 invariant 보장
- **Pydantic V2 / Literal enum 정책** — 본 stage 는 새 모델 / enum 추가 없음 (str 입출력만)
- **`__init__.py` 모듈 레벨 third-party import 금지** — S1 그대로, 변경 없음
- **모듈 위치** `python/rhwp/mcp/` (top-level) — 변경 없음

## 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/ -m "not slow"` | **553 passed, 2 skipped** (S1 548 + S2 신규 5) |
| `uv run pytest tests/test_mcp_server.py -v` | **23 passed** (S1 18 + S2 5) |
| `uv run ruff check python/rhwp/mcp/ tests/test_mcp_server.py` | clean |
| `uv run pyright python/rhwp/mcp/ tests/test_mcp_server.py` | **0 errors** |
| `uv run python scripts/lint_docs.py` | exit 0 |
| `uv run python scripts/generate_spec_trace.py --check` | up to date — 8 AC 매핑 (S1 의 7 + S2 의 AC-6×3) |
| `code-reviewer` fresh-context 검증 | LOW 3 / MEDIUM 0 / HIGH 0 / BLOCKER 0 — LOW-1 (`include_css` keyword-only) 반영, LOW-2 / LOW-3 은 trade-off 명시 후 보류 |

### 테스트 커버리지 (mcp.md §S2 → AC 매핑)

| mcp.md AC | 테스트 |
|---|---|
| AC-2 (도구 6 개 노출 — S1 코어 4 + S2 view 2) | `TestToolRegistry::test_lists_exactly_six_tools` |
| AC-6 (view 도구 = `HwpDocument.to_xxx(...)` thin wrapper) | `TestToMarkdown::test_matches_view_api`, `TestToHtml::test_matches_view_api_no_css`, `TestToHtml::test_matches_view_api_with_css` (모두 byte-equality 검증) |
| AC-6 보조 (출력 형식 sanity) | `TestToMarkdown::test_returns_non_empty_string`, `TestToHtml::test_returns_html5_document` |

S1 의 AC-3 / AC-4 / AC-5 / AC-9 / AC-10 매핑은 그대로 유지 — `TestSyncHandler` 가 6 도구를 walk 하고 packaging 검증은 도구 카운트와 독립.

## 알려진 한계 (S3 이후 처리)

- **`to_markdown` / `to_html` docstring drift 위험** — view API 결정사항 (GFM 표 정책 / `<aside>` 각주 마커 등) 이 바뀌면 tools.py 의 docstring 도 함께 갱신 필요. 회귀 검출은 byte-equality 테스트가 담당하지만 docstring 자체는 자동 동기화 안 됨. v0.4.0 view API 가 GA 라 변동 가능성은 낮음 (CONVENTIONS § Frozen body 변경 금지 정책)
- **`include_css` 외 view API 옵션 미노출** — 현재 `to_html` 은 `include_css` 만 wrapper 인자로 노출. v0.4.0 view API 가 미래에 추가 옵션 (예: 외부 stylesheet URL / inline 이미지 base64 등) 을 도입하면 wrapper 갱신 필요. v0.5.0 GA 시점에는 v0.4.0 view API 가 frozen 이라 영향 없음

## S3 진입 조건 (인수인계)

S3 는 `chunks` 도구 — `langchain-text-splitters` extras gate. S1 / S2 에서 고정한 계약:

1. **`tools.py` 의 sync-only 패턴** — `chunks` 도구도 같은 형태. 단, `chunks` 는 langchain extras 미설치 환경에서 import 자체가 실패 — 도구 본체에서 lazy import + try/except 처리 또는 `server.py` 의 `build_server()` 에서 도구 등록 자체를 conditional 로 분리. mcp.md AC-7 ("chunks 도구 호출 시 langchain-text-splitters 미설치면 MCP isError=True 응답 — 서버 기동은 정상 + 다른 6 도구는 사용 가능") 이 후자 (등록은 무조건 + 호출 시 친절 에러) 를 시사
2. **`TestToolRegistry::test_lists_exactly_six_tools`** → S3 종료 시 7 로 재카운트. mcp.md AC-2 ("GA 시점 7 도구") 충족
3. **`TestSyncHandler::test_all_registered_tools_are_sync`** — 자동 커버 (등록 도구 walk)
4. **CI test-without-extras skip count** — S2 는 추가 변동 없음. S3 도 `test_mcp_server.py` 자체는 fastmcp 만 gate (langchain 미설치는 `chunks` 도구의 in-tool 분기) 라 skip count 그대로 5 유지 예상

## 참조

- 상위 설계: [roadmap/v0.5.0/mcp.md](../../../roadmap/v0.5.0/mcp.md)
- 결정 사항 증거: [design/v0.5.0/mcp-research.md](../../../design/v0.5.0/mcp-research.md)
- 선행 stage: [stage-1.md](stage-1.md)
- v0.4.0 view 렌더러 (의존 대상): `python/rhwp/ir/nodes.py` `HwpDocument.to_markdown()` / `to_html(*, include_css=...)`
- v0.4.0 spec: roadmap/v0.4.0/view-renderer.md (Frozen, GA 2026-05-05)
