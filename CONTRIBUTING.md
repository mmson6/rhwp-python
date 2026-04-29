# rhwp-python 기여 가이드

**한국어** | [**English**](CONTRIBUTING_EN.md)

기여에 관심 가져주셔서 감사합니다. AI 기반 기여 (이슈 작성 / 코딩 / 리뷰) 도 환영합니다.

## TL;DR — 빠른 시작

```bash
git clone --recurse-submodules https://github.com/DanMeon/rhwp-python.git
cd rhwp-python
uv sync --no-install-project --group all
uv run maturin develop --release
uv run pytest tests/ -m "not slow"
```

위 4 명령이 모두 통과하면 작업 시작 준비 완료. `main` 에서 분기 → Conventional Commits 으로 commit → push → PR.

submodule 없이 클론한 경우: `git submodule update --init --recursive`.

## 기여 유형 선택

| 작업 종류 | 추가로 읽을 문서 | 비고 |
|---|---|---|
| 버그 수정 / 테스트 추가 | — | 가장 흔한 경로 — `main` 으로 PR |
| Python API 또는 LangChain 기능 추가 | [AGENTS.md](AGENTS.md) (프로젝트 규칙) | 큰 기능은 spec 문서 필요할 수 있음 — 먼저 issue 로 논의 |
| Rust 코어 / 파서 변경 | — | [edwardkim/rhwp](https://github.com/edwardkim/rhwp) 에 issue 등록 — 본 리포는 바인딩만 다룸 |
| 기존 문서 수정 | [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | `docs/*.md` 편집 시 Claude Code hook + CI 가 자동 lint. frontmatter `last_updated` 는 hook 이 갱신하므로 수기 변경 금지 |
| 새 version spec 작성 | [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | `/new-spec <vX.Y.Z> <topic>` Claude Code skill 사용, 또는 CONVENTIONS § 새 spec 추가 절차 따라 수기 작성 |

PR 의 90% 이상은 첫 행 (버그 수정 / 테스트) — spec 시스템 정책을 읽을 필요 없음.

## 제출 전 체크리스트

모두 CI 에서 실행되지만, 로컬 선실행이 round-trip 절약:

- `uv run pytest tests/ -m "not slow"` — 통과 필수 (PDF 테스트는 `-m slow`)
- `uv run ruff check python/ tests/ benches/` — 통과 필수
- `uv run pyright python/ tests/` — 통과 필수
- Rust 변경 (`src/*.rs`) 후엔 `uv run maturin develop --release` 재실행 + `cargo clippy --all-targets -- -D warnings`
- 문서 변경 시: `uv run --no-project --with "typer>=0.12" python scripts/lint_docs.py docs/` (CI 의 `Docs lint` job 과 동일)

## 코드 스타일

- Python 3.10+, `T | None` (`Optional[T]` 금지), PEP 561 typed
- Rust 1.83+ (PyO3 0.28 MSRV). 바인딩 레이어에 새 `unsafe` 추가 금지

## Pull Request

1. 브랜치 명명: **PATCH** = `<type>/<topic>` (단명, `main` 직머지, 예: `fix/empty-paragraph`). **MINOR** = `feature/vX.Y.0` (장명, stage 간 외부 contract 변경 격리). `<type>` 는 [Conventional Commits](https://www.conventionalcommits.org/) 따름 (`fix` / `chore` / `refactor` / `docs` / `build` / `ci` / `perf` / `test` / `revert`)
2. Commit subject: lowercase `<type>: <description>`
3. PR body 는 [.github/pull_request_template.md](.github/pull_request_template.md) 양식 — Summary / Why / Related Issues
4. PR 단위는 한 가지 기능 / 한 가지 수정으로 집중
5. rhwp Rust 코어 변경이 필요하면 [edwardkim/rhwp](https://github.com/edwardkim/rhwp) 에 먼저 issue — 본 리포는 바인딩만 추가

## 더 읽을 자료

- **프로젝트 규칙 + 아키텍처**: [AGENTS.md](AGENTS.md) — `CLAUDE.md` 와 동일 내용 (symlink). async 패턴, GIL release 규칙, extras-gated 테스트 카운트 등
- **문서 운영 정책**: [docs/CONVENTIONS.md](docs/CONVENTIONS.md) — 수명 (Living/Active/Draft/Frozen/Superseded), frontmatter schema, EARS notation, supersede chain
- **활성 spec 인덱스**: [docs/roadmap/README.md](docs/roadmap/README.md) — 어떤 spec 이 GA 됐고 어떤 게 진행 중인지
- **상류 commit pin**: 각 릴리스 tag 의 git submodule 이 SSOT — `git ls-tree v0.3.0 external/rhwp` / CHANGELOG 의 산문 노트
