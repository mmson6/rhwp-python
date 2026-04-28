# CLAUDE.md — rhwp-python

Project-specific instructions. Inherits all rules from `~/.claude/CLAUDE.md` (global).

## Project context

- **What it is**: PyO3 Python bindings for the [edwardkim/rhwp](https://github.com/edwardkim/rhwp) Rust HWP/HWPX parser & renderer
- **Names**: PyPI `rhwp-python` / `import rhwp` / extension `rhwp._rhwp`
- **Core delivery**: Rust core consumed via git submodule at `external/rhwp`, pinned to a specific upstream commit (tracked in `CHANGELOG.md` + `.gitmodules`)
- **License**: MIT — dual copyright (Edward Kim for rhwp core, DanMeon for bindings). Both LICENSE files are bundled in the wheel (`license-files = ["LICENSE", "external/rhwp/LICENSE"]`)
- **Status**: unofficial community package. The `rhwp` name on PyPI is intentionally left for the upstream maintainer

## Quick start

```bash
git clone --recurse-submodules https://github.com/DanMeon/rhwp-python
cd rhwp-python
uv sync --no-install-project --group all
uv run maturin develop --release
uv run pytest -m "not slow"
```

If the repo is already cloned without submodules: `git submodule update --init --recursive`.

## Quality checks

- `uv run ruff format python/ tests/ benches/` — format
- `uv run ruff check python/ tests/ benches/` — lint
- `uv run pyright python/ tests/` — type check
- `cargo clippy --all-targets -- -D warnings` — Rust lint (run after any `src/*.rs` change)

Autolint hook (`~/.claude/hooks/autolint.js`) runs ruff/pyright on edited files automatically; the commands above are for cross-file / cold checks.

## Global rules inherited

All rules from `~/.claude/CLAUDE.md` apply. This file adds only project-specific details — do not restate global rules here.

## Project-specific rules

### Rust + Python hybrid build
- After any Rust change (`src/*.rs`): `uv run maturin develop --release` before `pytest`. Without it, tests run against the stale binary
- PyO3 `#[pyclass(unsendable)]`: `_Document` is bound to its creation thread (upstream `DocumentCore` holds `RefCell` fields — `!Sync`). Same-thread worker pattern (`parse + consume + return primitives` inside one thread) works; `asyncio.to_thread(rhwp.parse, path)` does NOT — the Future resolves on the main thread and first attribute access panics with `_rhwp::document::PyDocument is unsendable, but sent to another thread`
- GIL release via `py.detach` in `_Document::from_bytes` / `render_pdf()` / `export_pdf()` — keep this pattern when adding new CPU/IO-bound methods
- `abi3-py310` feature: **one wheel covers 3.10–3.13+**. Don't bind to Python version-specific C API

### Async direction
- Python-surface APIs for I/O and integrations are **async-first**: when adding LangChain / LlamaIndex / Haystack loaders, implement `aload` / `alazy_load` / async counterparts alongside sync versions
- **Forbidden pattern**: `asyncio.to_thread(rhwp.parse, path)` — `_Document` is unsendable (see Rust+Python hybrid build note above), the returned Document panics on main-thread access. `async fn` in `#[pymethods]` is also incompatible (PyO3 requires `Send + 'static` futures)
- **Supported async pattern**: `aparse(path)` uses stdlib `asyncio.to_thread` to offload the file read to a thread pool, then calls `Document.from_bytes(data)` on the event-loop thread. Document never crosses a thread boundary. No external dependency — Python `asyncio` lacks native async file I/O so all async file libs (aiofiles etc.) wrap thread pools anyway; stdlib achieves the same effect with zero install footprint
- **Document instance-level async methods (`doc.ato_ir()` etc.) are NOT provided** — they would require thread offload which unsendable forbids. For async code, `await rhwp.aparse(path)` once, then call sync methods on the Document directly (these are fast, in-memory, GIL-holding operations)
- If upstream rhwp ever replaces its `RefCell` caches with thread-safe synchronization, revisit this — `unsendable` could then be dropped, enabling true `async fn pymethods`

### Tests
- Real HWP fixtures live in the submodule: `external/rhwp/samples/aift.hwp` (HWP5), `table-vpos-01.hwpx` (HWPX). `tests/conftest.py` + `benches/bench_gil.py` reference this path
- When changing one path, change both
- Markers: `slow` (PDF render), `langchain` (extras required). Default run: `pytest -m "not slow"`
- Extras-gated test files use module-level `pytest.importorskip` so the whole file counts as **1 skip** when the extra is missing. Current gated files: `test_langchain_loader.py` + `test_langchain_loader_ir.py` (langchain-core), `test_ir_schema_export.py` (jsonschema), `test_cli.py` (typer) → CI's `test-without-extras` job validates **exactly 4 skipped** (see `.github/workflows/ci.yml`). When adding a new extras-gated file, bump the count in both CLAUDE.md and ci.yml
- `tests/type_check_errors.py` holds **exactly 4 intentional pyright errors** — CI validates that too. When editing, preserve count; don't fix them

### Git workflow
- Single-branch trunk model: feature branches off `main` → PR to `main`. No `develop` / `staging`
- Branch naming: **MINOR** = `feature/vX.Y.0` (long-lived, isolates external contract changes across stages). **PATCH** = `<type>/<topic>` (short-lived, merges directly to main, tag only `vX.Y.Z`) where `<type>` follows [Conventional Commits](https://www.conventionalcommits.org/) (`fix` / `chore` / `refactor` / `docs` / `build` / `ci` / `perf` / `test` / `revert`)
- Commit subject: lowercase `type: description` (seed commit: `init: 프로젝트 초기화`)
- PR body follows [.github/pull_request_template.md](.github/pull_request_template.md) — Summary / Why / Related Issues
- Full contributor flow (fork, pre-submit checks, rhwp-core changes): [CONTRIBUTING.md](CONTRIBUTING.md)

### Versioning / release
- Git tags `vX.Y.Z`, SemVer, MINOR-sized increments
- **No breaking changes across Phase boundaries** (Phase 1 → 2 must keep existing APIs)
- Release trigger: GitHub Release `published` event fires `publish.yml`. Draft releases don't trigger
- `publish.yml` runs `verify-version` — Cargo.toml `version` must match the tag or publish aborts. Always bump Cargo.toml before tagging
- Every release records the `external/rhwp` submodule commit hash in CHANGELOG

### Documentation
Authoritative policy is `docs/CONVENTIONS.md` — read it before any docs work. Active spec index SSOT is `docs/roadmap/README.md`.

Hard rules (auto-applied without further instruction):
- Every per-version spec / ADR / impl-log / verification report carries a Status metadata line right after its first heading: `**Status**: <Active | Draft | Frozen | Superseded by [link]> · **GA**: vX.Y.Z` *or* `**Target**: vX.Y.Z` · `**Last updated**: YYYY-MM-DD`. Living docs (README, CHANGELOG, CLAUDE.md, CONVENTIONS itself) skip the Status line.
- **Frozen spec body is immutable** — typo / broken-link fixes only. Decision changes go to a *new* spec; the old one's Status flips to `Superseded by [link]` (single-line edit).
- **Spec ↔ spec direct cross-links are forbidden** even within the same `vX.Y.Z/` directory. Use `phase-N.md` § two-axis-integration sections (or `roadmap/README.md`) as the bridge. **Exception**: pair files `<topic>.md` ↔ `<topic>-research.md` (the spec ↔ ADR pair) link directly.
- **`phase-N.md` carries no concrete decisions / open issues** — those belong in `vX.Y.Z/*.md`. Phase docs hold intent, scope, and two-axis integration only.
- New version `vX.Y.Z`: create `docs/roadmap/vX.Y.Z/<topic>.md` + `docs/design/vX.Y.Z/<topic>-research.md` (Status: Draft, Target: vX.Y.Z), then add a row to the active-spec index in `roadmap/README.md`. On GA: flip Status Draft → Frozen, write `implementation/vX.Y.Z/...` (Frozen on creation), refresh README index.

### CI / secrets
- No secrets required. PyPI publish uses Trusted Publisher (OIDC) — no API token to manage
- `secrets.GITHUB_TOKEN` is injected automatically; don't try to "register" it
- Workflow permissions stay minimal. `publish.yml` declares `id-token: write` at the job level only

## Directory layout

```
.
├── src/                    Rust bindings (lib.rs + document/errors/version.rs)
├── python/rhwp/            Python package
│   ├── __init__.py(.pyi)
│   ├── py.typed
│   └── integrations/langchain.py(.pyi)
├── tests/                  pytest — conftest reads external/rhwp/samples
├── benches/bench_gil.py    GIL-release benchmark
├── examples/               typer-based usage samples (extras: [examples])
├── external/rhwp/          git submodule — pinned upstream commit
└── docs/                   4-axis documentation
```

## Common mistakes to avoid

- Forgetting `--recurse-submodules` on clone → samples missing. Fix: `git submodule update --init --recursive`
- Forgetting `maturin develop --release` after Rust changes → tests run against stale binary
- Changing `tests/conftest.py` sample path without updating `benches/bench_gil.py`
- Adding a runtime dependency to `[project] dependencies` when it belongs in `[project.optional-dependencies]` (LangChain, typer currently gated as extras)
- Bumping the version only in `pyproject.toml` — **Cargo.toml is the source of truth** via `dynamic = ["version"]`
- Modifying `external/rhwp/` directly — it's upstream-owned. Upstream PRs only
