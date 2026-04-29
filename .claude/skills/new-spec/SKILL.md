---
name: new-spec
description: Scaffold a new version spec and paired ADR following docs/CONVENTIONS.md
argument-hint: <version> <topic>
arguments:
  - version
  - topic
disable-model-invocation: true
---

# /new-spec — 새 spec 스캐폴드

목적: `<version>` (예: `v0.4.0`) + `<topic>` (예: `view-renderer`) 인자로 신규 per-version spec + 짝 페어 ADR + roadmap 인덱스 row 를 일괄 생성.

## 산출물

다음 4가지를 한 번에 생성/갱신:

1. **`docs/roadmap/<version>/<topic>.md`** — spec 본문 (frontmatter `status: Draft`, `target: <version>`)
2. **`docs/design/<version>/<topic>-research.md`** — 짝 페어 ADR (frontmatter `status: Draft`, `target: <version>`)
3. **`docs/roadmap/README.md`** — § 활성 spec 인덱스 표에 row 추가
4. **§ 인수조건 placeholder** — EARS 5종 키워드 예시 (Ubiquitous / Event-Driven / State-Driven / Optional / Unwanted)

## 작업 절차

본 skill 호출 시 모델은 다음 순서로 진행:

1. **인자 검증**
   - `version` 이 `vX.Y.Z` SemVer 형식인지
   - `topic` 이 kebab-case 인지
   - `docs/roadmap/<version>/<topic>.md` 가 이미 존재하면 abort (기존 spec 침해 방지)

2. **CONVENTIONS.md 정독** — frontmatter schema / 명명 규칙 / cross-link 방향성 / EARS notation 섹션을 읽고 본 작업에 적용

3. **디렉토리 생성** (없으면)
   - `docs/roadmap/<version>/`
   - `docs/design/<version>/`

4. **`docs/roadmap/<version>/<topic>.md` 작성** — 아래 템플릿:

   ```markdown
   ---
   status: Draft
   target: <version>
   last_updated: <오늘 YYYY-MM-DD>
   ---

   # <version> — <topic 의 한국어 요약 제목>

   <한 문단 요약 — 본 spec 이 무엇을 도입하고 왜 필요한지>.

   주요 결정의 근거·대안·실패 시나리오는 짝 페어: [<topic>-research.md](../../design/<version>/<topic>-research.md).

   ## 결정 사항

   | 항목 | 값 | 근거 |
   |---|---|---|
   | 1 | (placeholder) | (placeholder) |

   ## 인수조건

   <!-- EARS notation (CONVENTIONS § 인수조건 형식) — AC-N ID 부여, 테스트 marker 와 1:1 매핑 -->

   - **AC-1** (Ubiquitous) — `THE <system> SHALL <response>`
   - **AC-2** (Event-Driven) — `WHEN <trigger>, THE <system> SHALL <response>`
   - **AC-3** (State-Driven) — `WHILE <state>, THE <system> SHALL <response>`
   - **AC-4** (Optional) — `WHERE <feature>, THE <system> SHALL <response>`
   - **AC-5** (Unwanted) — `IF <condition>, THEN THE <system> SHALL <response>`

   ## 영구 비목표

   - (본 spec 의 범위에서 명시적으로 제외하는 항목)

   ## 참조

   - 짝 페어 (ADR): [<topic>-research.md](../../design/<version>/<topic>-research.md)
   ```

5. **`docs/design/<version>/<topic>-research.md` 작성** — 아래 템플릿:

   ```markdown
   ---
   status: Draft
   target: <version>
   last_updated: <오늘 YYYY-MM-DD>
   ---

   # <version> <topic> — 설계 의사결정 리서치 요약

   [<version>/<topic>.md](../../roadmap/<version>/<topic>.md) §결정 사항 중 외부 독자가 "왜?" 를 던질 만한 N건의 업계 선례·대안·실패 시나리오를 기록한다. <topic>.md 본문이 최종 결정을 기술하고, 본 문서는 그 결정의 근거를 담는다.

   ## 결정 매트릭스

   | # | 항목 | 옵션 비교 | 채택 | 1차 근거 |
   |---|---|---|---|---|
   | 1 | (placeholder) | A: ... / B: ... / C: ... | (?) | (?) |

   ## 1. <첫 결정 항목>

   ### 팩트
   ### 검증자 반박
   ### 최종 결정
   ### 1차 소스

   ## 참조

   - [roadmap/<version>/<topic>.md](../../roadmap/<version>/<topic>.md) — 본 리서치의 결정 요약
   ```

6. **`docs/roadmap/README.md` 의 § 활성 spec 인덱스 표에 row 추가** — 기존 표 마지막 줄 다음에:

   ```markdown
   | <version> (<topic>) | Draft | [<version>/<topic>.md](<version>/<topic>.md) | [design/<version>/<topic>-research.md](../design/<version>/<topic>-research.md) |
   ```

7. **무결성 검증** — 작업 후 `python3 scripts/lint_docs.py docs/` 실행. 위반 시 사용자에게 보고하고 수정 안내.

## 규칙 (CONVENTIONS.md 준수)

- frontmatter schema 정확 적용 (status enum / target SemVer / last_updated YYYY-MM-DD)
- spec ↔ research 페어 외 다른 spec 파일 직접 link **금지** (인덱스 경유)
- kebab-case 파일명, vX.Y.Z 디렉토리명
- 상대경로 implicit (`./` prefix 금지)

## 한계

- spec 본문은 placeholder — 실제 결정 / 인수조건 / 비목표는 사용자가 채움
- design research 의 결정 매트릭스도 placeholder — N개 결정의 실제 비교는 사용자가 작성

본 skill 은 **구조 일관성** (frontmatter / 페어 / 인덱스 / EARS placeholder) 만 자동화. 콘텐츠 결정은 사람의 판단.
