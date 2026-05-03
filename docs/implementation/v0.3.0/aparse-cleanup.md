---
status: Frozen
description: "v0.3.0 cleanup 로그 — 'rhwp.aparse' 의 'aiofiles' 우회를 stdlib 'asyncio.to_thread' 로 정리. extras 의존성 제거"
ga: v0.3.0
last_updated: 2026-04-28
---

# v0.3.0 — `aparse` aiofiles 제거 (stdlib `asyncio.to_thread` 전환)

v0.2.0 에서 도입한 `rhwp.aparse` 의 `aiofiles` 기반 우회를 stdlib `asyncio.to_thread` 로 정리. v0.3.0 GA 전 cleanup — 별도 patch (v0.3.1) 로 분리하지 않고 v0.3.0 에 합침. 본 implementation note 는 결정 근거 (거부된 대안 비교) 를 보존 — CHANGELOG 한 줄로는 표현 부족한 정보.

## 배경

v0.2.0 부터 `rhwp.aparse(path)` 는 Rust `_Document` 의 `#[pyclass(unsendable)]` 제약 (상류 `RefCell` 기반 캐시 → `!Sync`) 을 우회하기 위해 `aiofiles.open()` 사용:

```python
async with aiofiles.open(path, "rb") as f:
    data = await f.read()
return Document.from_bytes(data, source_uri=path)
```

`aiofiles` 는 `[async]` extras 로 격리 — `pip install rhwp[async]` opt-in. 이 정책의 문제:

- **우회 비용을 사용자에게 위임한 일관성 깨짐** — `unsendable` 우회는 우리 측 책임인데 그 비용 (extras install) 만 사용자에게 떠넘김
- **stdlib 대안 존재** — Python 3.9+ `asyncio.to_thread` 가 동일 메커니즘을 stdlib 만으로 제공
- **의존성 그래프 불필요한 노드** — security audit, version bump, extras 매트릭스 (`test-without-extras` skip count 관리) 비용 추가

## 1. aiofiles vs stdlib `asyncio.to_thread` — 메커니즘 비교

| 항목 | aiofiles | `asyncio.to_thread` (Python 3.9+) |
|---|---|---|
| Backend | 자체 dedicated thread (default 1 worker) | `asyncio` default `ThreadPoolExecutor` (`min(32, cpu+4)` workers) |
| Syscall | blocking `read(2)` on thread | blocking `read(2)` on thread |
| Async wrapper | `async with`, chunked read 지원 | callable wrapping, 단발 호출 |
| Cancellation | async-friendly (await 시점 cancel) | thread 시작 후 cancel 불가 — 단발 read 라 무관 |
| 의존성 | external (`pip install aiofiles`) | stdlib (Python 3.9+) |

**핵심 등가성**: Python `asyncio` 자체는 native async file I/O 미지원 — Linux `io_uring` / Windows IOCP 같은 OS-level async file I/O 를 stdlib 가 노출 안 함. 따라서 모든 async file lib (aiofiles 포함) 가 결국 thread pool 에 sync read 를 offload 하는 우회. aiofiles 의 추가 가치는 **`async with` 표현 문법 + chunked read 옵션** 둘뿐.

**HWP 시나리오 영향**:

| 요소 | aiofiles 가 유리 | 실제 영향 |
|---|---|---|
| Chunked read (large file) | streaming gather | `Document.from_bytes(전체)` 가 어차피 bytes 전부 메모리 보유 — chunked 의 이득 zero |
| Per-call overhead | 자체 thread 재사용 | `to_thread` 도 default pool 재사용 — 차이 μs 단위 |
| Cancellation | async-friendly | `aparse` 는 단발 read — cancel 시나리오 거의 없음 |
| Thread pool 크기 | dedicated 1 | default `min(32, cpu+4)` — 다중 파일 동시 처리 시 stdlib 가 살짝 유리 |

**dominant cost**: HWP 파싱 (`Document.from_bytes`) = 수십~수백 ms vs File read = 수 ms. I/O 방식 차이는 파싱 시간의 noise (1% 미만).

**결론**: 의미·성능 등가. stdlib 채택 시 사용자 인지 가능한 회귀 없음.

## 2. 채택 옵션 비교 — 왜 (c) stdlib 인가

| 옵션 | 의존성 | aparse 동작 | 채택 |
|---|---|---|---|
| (a) v0.3.0 이전 — `[async]` extras | aiofiles (optional) | 미설치 시 ImportError | ✗ — 우회 비용을 사용자에게 위임, 일관성 깨짐 |
| (b) aiofiles 기본 의존성 | aiofiles (required) | 항상 동작 | ✗ — stdlib 대안 있는데 외부 의존성 강제는 weak |
| (c) **stdlib 만 사용** | 없음 | 항상 동작 | **✓** — 가장 깔끔, 외부 의존성 zero, 의미·성능 동등 |

**(c) 채택 이유**:

1. **본질적 정답** — stdlib 으로 동등 효과 가능한데 외부 의존성 강제는 weak justification
2. **의존성 graph 비용 절감** — security audit, version bump, extras 매트릭스, CI 분기 제거
3. **사용자 install UX** — `pip install rhwp` 만으로 async API 동작 → 문서·온보딩 단순화
4. **(b) 와의 차이** — (b) 도 install 부담 zero 이지만 외부 의존성을 굳이 끼고 있을 명분 없음

## 3. extras 키 처리 — 빈 배열 유지

`pip install rhwp[async]` 를 적은 기존 사용자에게 어떤 영향?

| 처리 | 결과 | 채택 |
|---|---|---|
| `async` 키 완전 제거 | pip unknown extra 경고 (warning + skip), install 성공 — noisy | 보류 (v0.4.0 검토) |
| `async = []` 빈 배열 유지 | 사용자 명령 그대로 동작, no warning | **✓ v0.3.0** |
| `async = ["aiofiles>=23"]` 유지 | aiofiles 가 unused dependency 로 install — 의존성 그래프 오염 | ✗ |

빈 배열 유지가 가장 무해 — 사용자 install 명령이 그대로 동작하면서 실제 aiofiles 는 끌어오지 않음. v0.4.0 에서 키 자체 제거 검토 (CHANGELOG 충분히 알린 후).

## 4. `unsendable` 자체 해결 — 왜 v0.3.0 범위 밖

본 cleanup 의 결정 범위 밖이지만, 미래 reference 차원 옵션:

| 옵션 | WASM 영향 | 변경 면적 | 평가 |
|---|---|---|---|
| A. `RefCell` → `Mutex` 통일 | atomic op 1-2 추가 — 측정 가능 회귀 거의 없음 | small | 가장 빠른 PR. 메인테이너 승인 필요 |
| B. `cfg(target_arch)` 분기 | zero | medium (코드 두 갈래) | 두 코드패스 유지 부담 — 메인테이너 보통 거부 |
| C. Cache 구조 분리 refactor | zero (read-only `Arc` + `OnceLock`) | large | 가장 우아. cache 사용 패턴 전수 분석 필요 |

**현 시점 우선순위 낮음** — 우리 측 wrapping (stdlib `asyncio.to_thread`) 비용이 낮고 위험도 작음. [find-control-text-positions](../../upstream/issue-find-control-text-positions.md) 쪽이 IR Provenance 정확도에 직접 영향이라 상류 push 우선순위가 더 높음. 본 항목은 issue 등록 후보로만 추적.

## 5. 산출물 (코드 / CI / 문서)

| 파일 | 변경 |
|---|---|
| `python/rhwp/document.py` | `aparse` 본문 — `aiofiles.open()` → `asyncio.to_thread(_read_bytes, path)`. 새 헬퍼 `_read_bytes(path) -> bytes`. Module docstring 의 aiofiles 언급 제거 |
| `python/rhwp/integrations/langchain.py` | docstring + 클래스 docstring 의 "aiofiles 기반" / "[async] 필요" 언급 제거. ImportError raises 항목 제거 |
| `pyproject.toml` | `[project.optional-dependencies]` 의 `async = ["aiofiles>=23"]` → `async = []` (빈 배열). `[dependency-groups] testing` 에서 `aiofiles>=23` 제거 |
| `tests/test_async.py` | module-level `pytest.importorskip("aiofiles")` 제거. `test_aparse_raises_import_error_without_aiofiles` 삭제 (의미 없어짐). `test_aparse_no_external_dependency` + `test_aparse_raises_file_not_found_for_missing_path` 신규 |
| `.github/workflows/ci.yml` | `test-without-extras` expected skip count `5 → 4` (`test_async.py` 가 더 이상 gated 아님) |
| `CLAUDE.md` | "Async direction" 섹션 + "Tests" 섹션의 aiofiles 언급 제거 + stdlib 패턴으로 교체. "Forbidden pattern" 항목은 유지 (`asyncio.to_thread(rhwp.parse, path)` 는 여전히 panic — Document 자체를 thread 에서 send 못함) |
| `CHANGELOG.md` | `[0.3.0]` 의 `Changed` 섹션 신설 — `aparse` 의 aiofiles 의존성 제거 한 줄 |

## 6. 호환성

| 시나리오 | 결과 |
|---|---|
| 사용자가 `pip install rhwp` (extras 없이) 설치 → `aparse` 호출 | v0.2.0 까지 ImportError, **v0.3.0 부터 정상 동작** |
| 사용자가 `pip install rhwp[async]` 명령 사용 | 빈 배열 유지로 그대로 동작, 추가 패키지 install 없음 |
| 사용자 코드에서 `import aiofiles` 직접 사용 | rhwp 가 aiofiles 를 transitive 로 끌고 오지 않으므로 사용자가 직접 install 필요. v0.2.0 이전과 동일 |
| `aload` / `alazy_load` API 시그니처 | 변경 없음 — backward-compat |

**API surface diff**: 없음. 내부 구현만 교체. semver PATCH 의미이지만 v0.3.0 GA 전이라 별도 PATCH release 분리 안 하고 합침.

## 7. 검증

| 검사 | 결과 |
|---|---|
| `uv run pytest tests/test_async.py -v` | 8 passed (기존 6 + 신규 2: `no_external_dependency` / `raises_file_not_found_for_missing_path`) |
| `uv run pytest -m "not slow"` | 전체 회귀 없음 |
| `uv run pyright python/ tests/<scoped>` | 0 errors |
| `cargo clippy --all-targets -- -D warnings` | clean (Rust 변경 없음) |
| Benchmark | 별도 측정 안 함 — § 1 의 메커니즘 등가성으로 충분 |

## 비목표

- **`unsendable` 제약 자체 해결** — § 4 옵션 A/B/C, 별도 추적
- **진짜 native async file I/O** (Linux `io_uring`, Windows IOCP 등) — Python stdlib 미지원, HWP 사용 케이스에서 over-engineering. 영구 비목표 후보
- **`aload` / `alazy_load` API surface 변경** — 시그니처 동일, 내부 구현만 교체. v0.4.0+ 에서도 변경 계획 없음

## 참조

### 1차 소스

- Python `asyncio.to_thread` (3.9+ stdlib): <https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread>
- aiofiles (thread pool wrapping 확인): <https://github.com/Tinche/aiofiles/blob/main/src/aiofiles/threadpool/__init__.py>
- PEP 508 (unknown extras 처리): <https://peps.python.org/pep-0508/>

### 상류 컨텍스트

- `external/rhwp/src/document_core/` — `RefCell` 기반 cache (unsendable 의 근본 원인)
- `src/document.rs` (rhwp-python) — `#[pyclass(unsendable)]` 선언 위치
- [docs/upstream/issue-find-control-text-positions.md](../../upstream/issue-find-control-text-positions.md) — 상류 visibility 변경 요청 선례 (참고)
