# rhwp-python

**한국어** | [**English**](README_EN.md)

[![PyPI](https://img.shields.io/pypi/v/rhwp-python.svg)](https://pypi.org/project/rhwp-python/)
[![Python](https://img.shields.io/pypi/pyversions/rhwp-python.svg)](https://pypi.org/project/rhwp-python/)
[![CI](https://github.com/DanMeon/rhwp-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DanMeon/rhwp-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> ⚠️ **비공식 커뮤니티 패키지입니다.** 본 프로젝트는 [edwardkim/rhwp](https://github.com/edwardkim/rhwp) 의 **공식 배포가 아니며**, rhwp 메인테이너가 직접 PyPI 에 올릴 경우를 대비해 이름을 `rhwp-python` 으로 양보해 둔 상태입니다. rhwp 코어 버그는 [업스트림](https://github.com/edwardkim/rhwp/issues) 에 보고해 주세요.

[rhwp](https://github.com/edwardkim/rhwp) — Rust 기반 HWP/HWPX(한컴오피스 문서) 파서·렌더러 — 의 PyO3 Python 바인딩.

- **PyPI 패키지명**: `rhwp-python`
- **Python import**: `import rhwp`
- **Rust 코어**: [`edwardkim/rhwp`](https://github.com/edwardkim/rhwp)

## 왜 rhwp-python 인가

- **HWP + HWPX 동시 지원** — 대표 대안인 `pyhwp` 는 HWP5 만 지원하고 2016년 이후 유지보수 중단 상태. rhwp 는 두 포맷을 같은 API 로 처리.
- **텍스트 추출 62배 빠름** — HWP5 기준 `pyhwp` 대비 96 ms vs 5,980 ms (sandbox 벤치).
- **LangChain 즉시 연동** — `rhwp.integrations.langchain.HwpLoader` 를 extras 로 제공, RAG 파이프라인에 바로 플러그인 가능.
- **타입 완비** — `py.typed` + `.pyi` 스텁, pyright clean.

## 요구 사항

- Python 3.10+ (abi3-py310 wheel 하나로 3.10 ~ 3.13+ 커버)
- 코어 API 는 **런타임 Python 의존성 없음**
- `rhwp-python[langchain]` extras 는 `langchain-core>=0.2` 하나만 추가 설치

## 설치

```bash
pip install rhwp-python
# 또는
uv add rhwp-python
```

## 사용법

```python
import rhwp

# HWP / HWPX 파싱 — 파일 I/O + 파싱 단계에서 GIL 해제
doc = rhwp.parse("report.hwp")
print(doc.section_count, doc.paragraph_count, doc.page_count)

# 텍스트
full_text: str = doc.extract_text()          # 빈 문단 제외, "\n" 으로 join
paragraphs: list[str] = doc.paragraphs()      # 빈 문단 포함 원본 리스트

# SVG 렌더링 — 단일 페이지 또는 전체
svg_page0: str = doc.render_svg(page=0)
all_svgs: list[str] = doc.render_all_svg()
written: list[str] = doc.export_svg("output/", prefix="page")
# → page_001.svg, page_002.svg, ... (단일 페이지면 page.svg)

# PDF 렌더링 — list[int] 가 아니라 Python `bytes` 반환
pdf: bytes = doc.render_pdf()
byte_size: int = doc.export_pdf("output.pdf")
```

`rhwp.Document(path)` 는 `rhwp.parse(path)` 와 동일하게 동작.

## 페이지 PNG 렌더링 (VLM 입력)

VLM (Vision-Language Model — Claude / GPT-4V / Gemini Vision 등) 의 시각 입력
용도. 텍스트 표면 (SVG / Markdown / IR) 으로는 평탄화되는 표 셀 병합 / 수식의
공간 배치 / 그림 / 복잡 레이아웃의 시각 의미를 보존한다. 상류 `rhwp` v0.7.10
의 native-skia raster pipeline (PR #599) 위 thin wrapper — 별도 extras 없이
default wheel 에 통합 (skia binary 포함).

```python
import rhwp

doc = rhwp.parse("report.hwp")

# 단일 페이지 — bytes (PNG magic 으로 시작)
png: bytes = doc.render_png(page=0)
png_2x: bytes = doc.render_png(page=0, scale=2.0)        # 픽셀 너비 약 2배

# 모든 페이지 일괄 (메모리 모델 — 페이지 100 × 약 500 KB ≈ 50 MB)
all_pngs: list[bytes] = doc.render_all_png()

# 디스크 export — page_001.png, page_002.png, ... (단일 페이지면 page.png)
written: list[str] = doc.export_png("output/", prefix="page")

# Async 변형 (파일 read 만 thread offload, render 는 호출 스레드)
import asyncio
png = asyncio.run(rhwp.arender_png("report.hwp", 0, scale=1.5))
```

**Anthropic Vision API 호출 예** — Claude 가 페이지 시각 정보를 직접 해석:

```python
import base64
import anthropic
import rhwp

png_bytes = rhwp.parse("report.hwp").render_png(page=0, scale=1.5)
client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(png_bytes).decode("ascii"),
                },
            },
            {"type": "text", "text": "이 페이지의 표 셀 병합 구조를 설명해."},
        ],
    }],
)
print(message.content[0].text)
```

`max_pixels` 는 DoS 방어용 픽셀 상한 (기본 8192 × 8192 = 67_108_864). 초과 시
`ValueError("raster pixel count out of range: ...")`. 사용자가 명시 override
가능 — 예: `doc.render_png(0, max_pixels=200_000_000)`.

## LangChain 통합

```bash
pip install "rhwp-python[langchain]"
```

```python
from rhwp.integrations.langchain import HwpLoader

# 문서 전체를 단일 Document 로 (기본 — single 모드)
docs = HwpLoader("report.hwp").load()

# 빈 문단 제외, 문단 1개당 Document 1개 (RAG 청킹용 — paragraph 모드)
docs = HwpLoader("report.hwp", mode="paragraph").load()

# lazy_load: Document 를 on-the-fly 로 yield (paragraph 모드에서 O(1) peak memory)
for d in HwpLoader("report.hwp", mode="paragraph").lazy_load():
    index_into_vector_store(d)   # 사용자 파이프라인

# 표준 LangChain 텍스트 스플리터에 바로 연결
from langchain_text_splitters import RecursiveCharacterTextSplitter
chunks = RecursiveCharacterTextSplitter(chunk_size=500).split_documents(docs)
```

모든 Document 메타데이터: `source`, `section_count`, `paragraph_count`,
`page_count`, `rhwp_version`. `paragraph` 모드에서는 `paragraph_index` 추가.

## Document IR

RAG / LLM 파이프라인이 직접 소비하는 구조화 문서 모델. Pydantic V2 모델 + JSON
Schema (Draft 2020-12) — HWP 의 구역 / 단락 / 표 / 그림 / 수식 / 각주 / 목록 /
캡션 / 목차 / 필드를 손실 없이 노출한다.

```python
from rhwp.ir.nodes import ParagraphBlock, TableBlock

doc = rhwp.parse("report.hwp")
ir = doc.to_ir()                       # -> rhwp.ir.nodes.HwpDocument (Pydantic, frozen)
json_str = doc.to_ir_json(indent=2)    # JSON 직렬화

# 본문 블록을 순서대로 스트리밍 (표/문단 혼합, TableCell.blocks 까지 재귀)
for block in ir.iter_blocks(scope="body"):
    if isinstance(block, ParagraphBlock):
        print("P", block.prov.section_idx, block.prov.para_idx, block.text)
    elif isinstance(block, TableBlock):
        print("T", block.rows, "x", block.cols, "cells=", len(block.cells))
```

**표 3중 표현** — `cells` (구조화 SQL/순회용) + `html` (HtmlRAG 호환 LLM 프롬프트) +
`text` (평문 검색 폴백) 가 병기된다. 중첩 표는 `TableCell.blocks` 재귀로 자연 지원.

**LangChain 통합** — 기존 loader 에 `mode="ir-blocks"` 추가:

```python
from rhwp.integrations.langchain import HwpLoader

docs = HwpLoader("report.hwp", mode="ir-blocks").load()
# ^ 단락은 page_content=text, 표는 page_content=HTML. 메타에 kind / section_idx /
#   para_idx / (표의 경우) rows / cols / text / caption 포함
```

**JSON Schema** — `rhwp.ir.schema.export_schema()` / `load_schema()`. 공개 `$id`:
`https://danmeon.github.io/rhwp-python/schema/hwp_ir/v1/schema.json` (불변 경로).

**View 변환 (v0.4.0+)** — `HwpDocument.to_markdown()` / `to_html(include_css=False)`
인스턴스 메서드로 IR 을 외부 view 포맷으로 직접 변환:

```python
ir = rhwp.parse("report.hwp").to_ir()

md = ir.to_markdown()                 # GFM (표 / 각주 / 수식 / 이미지 placeholder)
html = ir.to_html(include_css=True)   # 완전 HTML5 문서, <head> 안 단일 <style> 동봉
```

표는 모든 셀 `span == 1` 일 때 GFM `|...|`, 병합 셀 (rowspan/colspan > 1) 은
`TableBlock.html` 그대로 inline. 각주/미주는 본문 paragraph 안 `[^N]` reference +
끝 정의 (Markdown) / `<aside id="fn-N">` 정의 (HTML). 이미지는 `picture.image.uri`
(`bin://N`) pass-through — raw bytes 가 필요하면 `Document.bytes_for_image(picture)`
를 별도 호출 (embedded 모드 미지원). 머리글/꼬리말은 출력 미포함 (페이지 단위 장식).

호출은 IR 인스턴스를 변경하지 않아 (`frozen=True`) 동일 IR 에 대한 재호출은 byte-equal.

## rhwp-py CLI

```bash
pip install "rhwp-python[cli]"          # parse / version / schema / ir / blocks
pip install "rhwp-python[cli-chunks]"    # + chunks (langchain text splitter)

rhwp-py parse report.hwp
rhwp-py blocks report.hwp --kind table --format ndjson | jq '.rows'
rhwp-py chunks report.hwp --size 1000 --format ndjson
```

`rhwp-py` 는 구조 추출 (IR / 블록 / 청크 / 스키마) 전담 — 시각 출력 (SVG/PDF) /
메타데이터 덤프는 상류 `rhwp` Rust 바이너리. 자세한 사용은 `rhwp-py --help`
또는 [cli.md](docs/roadmap/v0.3.0/cli.md) 참조.

## MCP server (`rhwp-mcp`)

[Model Context Protocol](https://modelcontextprotocol.io/) 서버 — Claude Desktop /
Cursor / Cline / Continue.dev / Goose 등 LLM 에이전트가 HWP/HWPX 파일을 직접
파싱·요약·청크화할 수 있다. standalone [fastmcp v3](https://github.com/jlowin/fastmcp)
기반 (2026-05 기준 MCP 서버 약 70% 시장 점유의 사실상 표준).

```bash
pip install "rhwp-python[mcp]"           # 도구 6 종 (parse / extract / IR / blocks / view×2)
pip install "rhwp-python[mcp-chunks]"    # + chunks (RAG 청킹 — langchain-text-splitters)
```

### 노출 도구 (8 종)

| 도구 | 입력 | 출력 |
|---|---|---|
| `parse_hwp_summary` | `path` | `ParseSummary` — sections / paragraphs / pages 카운트 + rhwp-core 버전 |
| `extract_text` | `path` | `str` — 단락별 평문 (LF 결합) |
| `get_ir` | `path` | `HwpDocument` — Document IR 전체 (Pydantic 모델, fastmcp 자동 직렬화) |
| `iter_blocks` | `path`, `kind?`, `scope`, `limit?` | `list[Block]` — discriminated union (paragraph / table / picture / ... 11 변형, kind / scope 필터링) |
| `to_markdown` | `path` | `str` — GFM Markdown (v0.4.0 view API thin wrapper) |
| `to_html` | `path`, `include_css` | `str` — HTML5 문서 (v0.4.0 view API thin wrapper) |
| `chunks` | `path`, `mode`, `size`, `overlap`, `include_furniture` | `list[ChunkRecord]` — LangChain `RecursiveCharacterTextSplitter` 적용 청크. `[mcp-chunks]` extras 필요 |
| `render_page_png` | `path`, `page`, `scale`, `max_pixels?` | `ImageContent` — base64 PNG + `mimeType="image/png"`. VLM 시각 입력용 (v0.6.0+) |

> **v0.5.1 마이그 노트** — 출력 시그니처가 dict / list[dict] 에서 Pydantic 모델로 강화됐습니다 (PATCH). fastmcp Client 의 `result.structured_content` (raw dict, MCP wire format) 는 v0.5.0 과 byte-equal — 외부 LLM 프롬프트 / 후처리 코드 영향 0. 다만 `result.data` 사용 패턴은 변경: v0.5.0 의 `result.data["body"]` (dict 인덱싱) → v0.5.1 의 `result.data.body` (typed attribute) 또는 `result.data.model_dump()["body"]`. `iter_blocks` 의 list element 는 fastmcp v3 의 `oneOf` deserialization 한계로 dict 폴백 — `block["kind"]` access 패턴은 그대로 동작.

### Claude Desktop 등록

`claude_desktop_config.json` 에 추가:

```json
{
  "mcpServers": {
    "rhwp": {
      "command": "rhwp-mcp"
    }
  }
}
```

(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`. Windows:
`%APPDATA%\Claude\claude_desktop_config.json`.) Claude Desktop 재시작 후 도구
아이콘에 8 개 도구 노출.

### 다른 클라이언트

| 클라이언트 | stdio | streamable-http | 등록 방법 |
|---|---|---|---|
| Claude Desktop | ✅ | ❌ | `claude_desktop_config.json` (위 예시) |
| Cline (VSCode) | ✅ | ✅ | VSCode 설정 → MCP servers |
| Cursor | ✅ | ❌ | Settings → Features → Model Context Protocol |
| Continue.dev | ✅ | ⚠️ (실험) | `~/.continue/config.json` |
| Goose (Block) | ✅ | ✅ | `goose configure` |
| 자체 에이전트 | ✅ | ✅ | Anthropic SDK 의 MCP client / fastmcp Client |

### Streamable HTTP (서버 배포)

서버 컨테이너 / 다중 클라이언트 시나리오는 streamable-http transport:

```bash
rhwp-mcp --transport streamable-http --port 8000
# 외부 노출 (보안: reverse proxy + 인증 운영자 책임)
rhwp-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

기본 `--host 127.0.0.1` — 외부 노출 회피. `rhwp-mcp` 는 인증 / TLS / sandboxing 미내장 — Caddy / Nginx 등 reverse proxy 가 책임. 자세한 사용은 `rhwp-mcp --help` 또는 [mcp.md](docs/roadmap/v0.5.0/mcp.md) 참조.

## 성능

Apple M2 (8 코어) release 빌드. Parse = 파일 읽기 + 전체 파싱 + Document 생성.
워크로드: 9 개 파일 (`aift.hwp` 5.5 MB + `table-vpos-01.hwpx` 359 KB + `tac-img-02.hwpx` 3.96 MB, ×3).

| 워커 수 | Parse 시간 | 순차 대비 가속 |
| ------- | ---------: | ----------------: |
| 1       | 268 ms     | 1.00× (기준)      |
| 2       | 141 ms     | 1.91×             |
| 4       | 97 ms      | 2.76×             |
| 8       | 67 ms      | **4.01×**         |

`parse()` 와 PDF 변환 단계는 `py.detach` 로 GIL 을 해제하므로 `ThreadPoolExecutor` 가
코어 수에 비례해 스케일. PDF 렌더링 자체는 `usvg` + `pdf-writer` 내부에서 CPU/allocator
바운드라 2 ~ 3 워커에서 약 1.1× 정도만 향상됨 — 재현은 `benches/bench_gil.py` 참고.

## 알려진 제약 / 운영 노트

운영상 제약 (`Document` 의 단일 스레드 모델, async 진입점, PDF stdout 노이즈)
및 미구현 영역 요약은 [KNOWN_ISSUES.md](KNOWN_ISSUES.md). 작업 중 / 계획 항목은
[docs/roadmap/](docs/roadmap/README.md) 의 활성 spec 인덱스.

## 개발

소스에서 빌드·테스트·기여하는 절차는 [CONTRIBUTING.md](CONTRIBUTING.md) 참조.

## 버전 관리

이 Python 패키지와 `rhwp` Rust 코어는 **독립적으로** 버저닝됩니다.
`rhwp.version()` 은 이 패키지 버전을, `rhwp.rhwp_core_version()` 은
번들된 Rust 코어 버전을 반환합니다.

## 라이선스

MIT. 저작권자: Edward Kim (rhwp Rust 코어) + DanMeon (rhwp-python 바인딩).
자세한 내용은 [LICENSE](LICENSE).

## 프로젝트 홈

- 바인딩 소스 / 이슈: https://github.com/DanMeon/rhwp-python
- rhwp Rust 코어: https://github.com/edwardkim/rhwp
