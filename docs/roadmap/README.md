# Roadmap

rhwp-python 의 버전별 로드맵 + **활성 spec 인덱스 SSOT**. 모든 spec 의 Status / GA / Target 을 본 페이지에서 추적한다. 문서 관리 정책은 [docs/CONVENTIONS.md](../CONVENTIONS.md) 참조.

본 문서는 Living — 자유 갱신.

## 현재 상태 (2026-05-06)

- **v0.1.0 / v0.1.1** — Frozen, PyPI 배포 완료
- **v0.2.0** — Frozen, Document IR v1 GA (2026-04-25)
- **v0.3.0** — Frozen, Phase 2 (IR 확장 + `rhwp-py` CLI) GA (2026-04-28)
- **v0.3.1** — Frozen, inline 컨트롤 마커 char offset 출고 GA (2026-05-03)
- **v0.3.2** — Frozen, UTF-16 → codepoint 변환 SSOT 단일화 GA (2026-05-03)
- **v0.4.0** — Frozen, IR view 렌더러 (Markdown / HTML) GA (2026-05-05)
- **v0.5.0** — Draft, MCP server (`rhwp-mcp`) — [v0.5.0/mcp.md](v0.5.0/mcp.md)
- **v0.6.0+** — 미착수 (주제 미정, demand-driven)

## 활성 spec 인덱스

각 row 는 spec 한 개 + 짝이 되는 design research (있으면). Status 는 [CONVENTIONS.md § 문서 수명 4 분류](../CONVENTIONS.md) 정의에 따름.

| 버전 | Status | Roadmap spec | Design research (ADR) |
|---|---|---|---|
| v0.1.0 / v0.1.1 | Frozen | [v0.1.0/rhwp-python.md](v0.1.0/rhwp-python.md) | — |
| v0.2.0 | Frozen | [v0.2.0/ir.md](v0.2.0/ir.md) | [design/v0.2.0/ir-research.md](../design/v0.2.0/ir-research.md) |
| v0.3.0 (IR 확장) | Frozen | [v0.3.0/ir-expansion.md](v0.3.0/ir-expansion.md) | [design/v0.3.0/ir-expansion-research.md](../design/v0.3.0/ir-expansion-research.md) |
| v0.3.0 (CLI) | Frozen | [v0.3.0/cli.md](v0.3.0/cli.md) | [design/v0.3.0/cli-research.md](../design/v0.3.0/cli-research.md) |
| v0.3.1 (IR marker char offset) | Frozen | [v0.3.1/ir-marker-char-offset.md](v0.3.1/ir-marker-char-offset.md) | [design/v0.3.1/ir-marker-char-offset-research.md](../design/v0.3.1/ir-marker-char-offset-research.md) |
| v0.3.2 (IR upstream UTF-16 helper) | Frozen | [v0.3.2/ir-upstream-utf16-helper.md](v0.3.2/ir-upstream-utf16-helper.md) | [design/v0.3.2/ir-upstream-utf16-helper-research.md](../design/v0.3.2/ir-upstream-utf16-helper-research.md) |
| v0.4.0 (view 렌더러) | Frozen | [v0.4.0/view-renderer.md](v0.4.0/view-renderer.md) | [design/v0.4.0/view-renderer-research.md](../design/v0.4.0/view-renderer-research.md) |
| v0.5.0 (MCP server) | Draft | [v0.5.0/mcp.md](v0.5.0/mcp.md) | [design/v0.5.0/mcp-research.md](../design/v0.5.0/mcp-research.md) |

## 미착수 작업 계획

본 섹션은 결정 미정 narrative — `vX.Y.Z` 디렉토리가 아직 없는 minor 들의 의도/스코프. 작업 시점이 가까워지면 `/new-spec <version> <topic>` 으로 정식 spec 으로 promote.

### v0.6.0+ — 미정 (demand-driven)

v0.5.0 MCP server (Draft, [v0.5.0/mcp.md](v0.5.0/mcp.md)) 이후 다음 minor 들. 주제 미정 — v0.3.0 LangChain integration 이 RAG 사용처 분모를 이미 커버하는 상황에서 추가 RAG 프레임워크 통합은 **demand-driven 으로 보류** (HWP × 비-LangChain RAG 교집합이 좁을 가능성). 구체화되면 `/new-spec <version> <topic>` 으로 promote.

> v0.4.0 view 렌더러 (Markdown / HTML) 은 GA 완료 — [v0.4.0/view-renderer.md](v0.4.0/view-renderer.md) 가 SSOT.

### v0.8.0 ~ v1.0.0 — JSON IR → HWP 역생성

선행 조건: v0.5.0 MCP server GA + v0.6.0+ minor 들 GA + rhwp Rust 코어의 HWP writer API 안정.

IR 을 축으로 한 양방향 변환 — 사용자가 IR 을 편집해 새 HWP/HWPX 를 생성할 수 있게 함. 본 라인은 rhwp **Rust 코어의 쓰기 API 성숙도** 에 좌우됨. 업스트림 [edwardkim/rhwp](https://github.com/edwardkim/rhwp) 가 HWP writer 를 안정화해야 진행 가능. 시작 전 업스트림 상태 재평가 + 필요 시 writer PR 기여로 진입.

범위:
- IR → **HWPX** 역직렬화 (HWPX 가 XML 기반이라 먼저)
- IR → **HWP5** 역직렬화 (OLE 컴파운드 파일 — 더 복잡)
- 왕복 (round-trip) 보장 테스트: parse → IR → write → parse 결과가 의미적으로 동일
- Python API: `rhwp.write(ir, path)` / `rhwp.Document.from_ir(ir).save(path)`

릴리스 분할:

| 버전 | 범위 |
|---|---|
| v0.8.0 | HWPX writeback baseline (단순 문서 왕복) |
| v0.9.0 | HWPX writeback 확장 (표·이미지·수식) |
| v0.10.0 | HWP5 writeback baseline |
| v1.0.0 | HWP5 writeback 확장 + API 안정 선언 |

SemVer 0.x.y 단계에서 minor 는 단조 증가 — v0.9 다음은 v0.10 (v1.0 으로 점프하지 않음). v1.0.0 은 API 안정 선언과 함께 별도 도달.

1.0 안정화 기준:
- HWPX 왕복 무결성 ≥ 99% (bytewise 는 불가능, 의미적 동등성 기준)
- HWP5 왕복 최소 가능
- Breaking change 없이 12개월 유지된 API
- 공식 메인테이너 (또는 공신력 있는 커뮤니티) 검토 통과

비범위:
- 완전한 레이아웃 보존 (폰트 embedding 미포함 상태의 재생성) — 뷰어 차이 허용
- 매크로·폼 필드·OLE 임베딩 — HWP 독자 확장 기능은 장기 과제

> 과거 GA 완료된 minor (v0.1.x ~ v0.3.0) 의 historical record 는 [v0.1.0/rhwp-python.md](v0.1.0/rhwp-python.md) / [v0.2.0/ir.md](v0.2.0/ir.md) / [v0.3.0/ir-expansion.md](v0.3.0/ir-expansion.md) / [v0.3.0/cli.md](v0.3.0/cli.md) 가 보유.

## 구현 / 검증 로그 (Frozen)

작업 완료 후 로그. Frozen — 변경 없음.

| 버전 | 구현 로그 | 검증 리포트 |
|---|---|---|
| v0.1.0 | [implementation/v0.1.0/migration.md](../implementation/v0.1.0/migration.md) | [verification/v0.1.0/spinoff-review.md](../verification/v0.1.0/spinoff-review.md) |
| v0.2.0 | [implementation/v0.2.0/stages/](../implementation/v0.2.0/stages/) (S1~S5) | — |
| v0.3.0 | [implementation/v0.3.0/stages/](../implementation/v0.3.0/stages/) (S1~S4) + [aparse-cleanup.md](../implementation/v0.3.0/aparse-cleanup.md) | — |
| v0.3.1 | [implementation/v0.3.1/migration.md](../implementation/v0.3.1/migration.md) | — |
| v0.4.0 | [implementation/v0.4.0/migration.md](../implementation/v0.4.0/migration.md) | — |

## 원칙

- **MINOR 단위 증분** — 기능 한 덩어리씩. 깨지는 변경 없이 누적
- **Phase 경계는 breaking 없음** — Phase 1 → 2 이동해도 기존 API 유지
- **Rust 코어 커밋 고정** — 각 릴리스는 `external/rhwp` submodule 의 특정 upstream commit 에 pin. 코어 업그레이드 시 CHANGELOG 에 명시
- **버전은 git tag 와 동일한 `v` prefix** — 디렉토리명·문서명 일관성
- **Spec 라이프사이클**: Draft → (GA) → Frozen → (필요 시) → Superseded by …. 상세: [CONVENTIONS.md § 새 spec 추가 절차](../CONVENTIONS.md)
- **Stage 분할 기준** — 단일 세션/수일 규모는 단일 `migration.md` 로. 여러 주 이상·의존성 추적이 필요한 대형 작업 (v0.2.0 IR 구현 등) 만 `stages/stage-N.md` 로 분할

## 연표 (대략)

| 버전 | 대략 목표 시점 |
|---|---|
| v0.1.0 / v0.1.1 | 2026 Q2 (GA 완료) |
| v0.2.0 | 2026 Q2 (GA 완료) |
| v0.3.0 | 2026 Q3 |
| v0.4.0 ~ v0.6.0 | 2027 |
| v1.0.0 | 2027+ |

타임라인은 **유동적** — 상류 `edwardkim/rhwp` 진척과 커뮤니티 수요에 따라 변경.

## 비범위 (영구)

- rhwp 코어 자체의 수정 — 모두 업스트림 PR 로
- HWP/HWPX 가 아닌 다른 한국 문서 포맷 (ARX / GUL 등) — rhwp 범위 밖
- OCR / 이미지 내 텍스트 인식 — 별도 도메인
