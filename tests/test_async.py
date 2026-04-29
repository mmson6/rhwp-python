"""Async API 검증 — ``rhwp.aparse`` (stdlib ``asyncio.to_thread`` 기반 파일 I/O + sync 파싱).

``#[pyclass(unsendable)]`` 제약 상 ``asyncio.to_thread(parse, path)`` 는 panic —
Document 가 스레드 경계를 넘기 때문. 대신 파일 read 만 stdlib ``asyncio.to_thread``
로 thread pool offload 하고, 파싱은 event loop 스레드에서 sync 실행 (GIL 은 Rust 가 해제).

따라서 Document 객체 수준의 ``a-`` prefix 메서드 (``ato_ir`` 등) 는 제공되지
않는다. async 환경에서 Document 를 쓰려면 파싱만 :func:`rhwp.aparse` 로 하고,
이후 메서드 호출은 sync 로 한다.

v0.3.0+ : aiofiles 의존성 제거 — stdlib 만으로 동등 효과 (둘 다 thread pool wrapping).
"""

import asyncio
from pathlib import Path

import pytest

import rhwp

pytestmark = pytest.mark.spec("v0.1.0/rhwp-python")
# ^ soft retrofit — file-level spec mapping; v0.4.0+ specs add #AC-N to specific tests (CONVENTIONS § Trace report)


def test_aparse_returns_document_instance(hwp_sample: Path) -> None:
    doc = asyncio.run(rhwp.aparse(str(hwp_sample)))
    assert isinstance(doc, rhwp.Document)


def test_aparse_source_uri_matches_arg(hwp_sample: Path) -> None:
    doc = asyncio.run(rhwp.aparse(str(hwp_sample)))
    assert doc.source_uri == str(hwp_sample)


def test_aparse_result_equivalent_to_parse(hwp_sample: Path) -> None:
    async_doc = asyncio.run(rhwp.aparse(str(hwp_sample)))
    sync_doc = rhwp.parse(str(hwp_sample))
    assert async_doc.section_count == sync_doc.section_count
    assert async_doc.paragraph_count == sync_doc.paragraph_count
    assert async_doc.extract_text() == sync_doc.extract_text()


def test_aparse_hwpx(hwpx_sample: Path) -> None:
    doc = asyncio.run(rhwp.aparse(str(hwpx_sample)))
    assert isinstance(doc, rhwp.Document)
    assert doc.source_uri == str(hwpx_sample)


def test_aparse_document_can_be_used_in_same_thread(hwp_sample: Path) -> None:
    """aparse 로 받은 Document 를 event loop 스레드 에서 정상 사용."""

    async def flow() -> tuple[int, str]:
        doc = await rhwp.aparse(str(hwp_sample))
        return doc.section_count, doc.extract_text()

    sections, text = asyncio.run(flow())
    assert sections > 0
    assert text  # 비어있지 않음


def test_aparse_ir_shares_cache(hwp_sample: Path) -> None:
    """aparse → to_ir 캐시 identity 가 여전히 작동."""

    async def flow():
        doc = await rhwp.aparse(str(hwp_sample))
        ir1 = doc.to_ir()
        ir2 = doc.to_ir()
        return ir1, ir2

    ir1, ir2 = asyncio.run(flow())
    assert ir1 is ir2


def test_aparse_no_external_dependency(hwp_sample: Path) -> None:
    """v0.3.0+ : aparse 는 외부 lib 의존성 없음 — stdlib 만으로 동작.

    aiofiles 설치 여부와 무관하게 동작해야 한다 (이전 버전은 ImportError 였음).
    """
    doc = asyncio.run(rhwp.aparse(str(hwp_sample)))
    assert isinstance(doc, rhwp.Document)


def test_aparse_raises_file_not_found_for_missing_path() -> None:
    """존재하지 않는 경로는 FileNotFoundError — async 경로도 동일."""
    with pytest.raises(FileNotFoundError):
        asyncio.run(rhwp.aparse("/nonexistent/path/file.hwp"))
