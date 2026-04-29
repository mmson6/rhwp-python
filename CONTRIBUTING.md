# Contributing to rhwp-python

Thanks for your interest! AI-assisted contributions (issue creation, coding, reviews) are welcome.

## TL;DR — quick start

```bash
git clone --recurse-submodules https://github.com/DanMeon/rhwp-python.git
cd rhwp-python
uv sync --no-install-project --group all
uv run maturin develop --release
uv run pytest tests/ -m "not slow"
```

If those four commands succeed, you're ready to make changes. Branch off `main`, commit (Conventional Commits), push, open a PR.

Already cloned without submodules? Run `git submodule update --init --recursive`.

## Pick your contribution path

| You want to... | Also read | Notes |
|---|---|---|
| Fix a bug / add a test | — | Most common path — open PR against `main` |
| Add a Python API or LangChain feature | [AGENTS.md](AGENTS.md) (project rules) | Larger features may need a spec doc — ask in an issue first |
| Change the Rust core / parser | — | File an issue at [edwardkim/rhwp](https://github.com/edwardkim/rhwp); this repo only wraps |
| Edit existing documentation | [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | A `docs/*.md` edit triggers lint auto via Claude Code hook (and CI). Don't touch frontmatter `last_updated` by hand — the hook does that |
| Add a new version spec | [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | Use `/new-spec <vX.Y.Z> <topic>` Claude Code skill, or scaffold manually following CONVENTIONS § 새 spec 추가 절차 |

90%+ of PRs are the first row — you don't need to read the spec system policy.

## Pre-submit checklist

All of these run in CI; running locally first saves a round trip:

- `uv run pytest tests/ -m "not slow"` — must pass (use `-m slow` for PDF tests)
- `uv run ruff check python/ tests/ benches/` — must pass
- `uv run pyright python/ tests/` — must pass
- After Rust changes (`src/*.rs`): re-run `uv run maturin develop --release` before pytest, plus `cargo clippy --all-targets -- -D warnings`
- Docs touched? `uv run --no-project --with "typer>=0.12" python scripts/lint_docs.py docs/` (also runs in CI as `Docs lint`)

## Code style

- Python 3.10+, `T | None` (not `Optional[T]`), PEP 561 typed
- Rust 1.83+ (PyO3 0.28 MSRV). No new `unsafe` in the bindings layer

## Pull requests

1. Branch naming: **PATCH** = `<type>/<topic>` (short-lived, merges to `main`, e.g. `fix/empty-paragraph`). **MINOR** = `feature/vX.Y.0` (long-lived, isolates external contract changes across stages). `<type>` follows [Conventional Commits](https://www.conventionalcommits.org/) (`fix` / `chore` / `refactor` / `docs` / `build` / `ci` / `perf` / `test` / `revert`)
2. Commit subject: lowercase `<type>: <description>`
3. PR body follows [.github/pull_request_template.md](.github/pull_request_template.md) — Summary / Why / Related Issues
4. Keep PRs focused — one feature or fix per PR
5. For changes touching rhwp Rust core, open an issue on [edwardkim/rhwp](https://github.com/edwardkim/rhwp) first; this repo only adds bindings

## Where to learn more

- **Project rules + architecture**: [AGENTS.md](AGENTS.md) — same content as `CLAUDE.md` (symlink). Async patterns, GIL release rules, extras-gated test counting, etc.
- **Documentation policy**: [docs/CONVENTIONS.md](docs/CONVENTIONS.md) — lifecycle (Living/Active/Draft/Frozen/Superseded), frontmatter schema, EARS notation, supersede chain
- **Active spec index**: [docs/roadmap/README.md](docs/roadmap/README.md) — what's GA, what's in progress, what's planned
- **Upstream commit pin**: [docs/upstream-pins.yaml](docs/upstream-pins.yaml) — which `external/rhwp` commit each release uses
