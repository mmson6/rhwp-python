"""v0.7.0 HWPX writeback baseline 회귀 가드 — to_hwpx_bytes / export_hwpx 검증.

AC-1 ~ AC-6 매핑은 ``docs/roadmap/v0.7.0/hwpx-writeback-baseline.md`` § 인수조건.
상류 ``serialize_hwpx`` 위임 표면이라 외부 extra 의존이 없다 — 본 파일은 항상
실행되며 extras-gated 가 아니다 (test-without-extras CI skip count 무관).

AC-1 의 round-trip fixture 로는 텍스트 문단이 풍부한 ``business_overview.hwpx``
를 쓴다. samples 에 표·도형이 전혀 없는 순수 텍스트 HWPX 는 존재하지 않으나
(실문서는 머리말/꼬리말 도형을 동반), 본 검증 대상은 최상위 문단 수·텍스트의
의미 보존이며 표 컨트롤 유무와 독립이다.
"""

import io
import zipfile
from pathlib import Path

import pytest

import rhwp

ZIP_MAGIC = b"PK\x03\x04"
HWPX_MIMETYPE = b"application/hwp+zip"


def _assert_valid_hwpx_container(data: bytes) -> None:
    """AC-2 컨테이너 형태 단언 — ZIP magic + 첫 엔트리가 STORED ``mimetype``."""
    assert data[:4] == ZIP_MAGIC, "HWPX must start with ZIP local-file-header magic"
    zf = zipfile.ZipFile(io.BytesIO(data))
    first = zf.infolist()[0]
    assert first.filename == "mimetype", f"first entry must be 'mimetype', got {first.filename!r}"
    assert first.compress_type == zipfile.ZIP_STORED, "mimetype entry must be STORED (uncompressed)"
    assert zf.read("mimetype") == HWPX_MIMETYPE


class TestRoundtripPreservation:
    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-1")
    def test_text_paragraph_roundtrip(self, samples_dir: Path, tmp_path: Path) -> None:
        original = rhwp.parse(str(samples_dir / "hwpx" / "business_overview.hwpx"))
        # ^ 가드: 실제 텍스트가 있는 fixture 여야 round-trip 검증이 유의미
        assert any(p.strip() for p in original.paragraphs())

        out = tmp_path / "roundtrip.hwpx"
        original.export_hwpx(str(out))
        reparsed = rhwp.parse(str(out))

        assert reparsed.section_count == original.section_count
        assert reparsed.paragraph_count == original.paragraph_count
        assert reparsed.paragraphs() == original.paragraphs()


class TestContainerShape:
    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-2")
    def test_to_hwpx_bytes_is_valid_container(self, parsed_hwpx: rhwp.Document) -> None:
        data = parsed_hwpx.to_hwpx_bytes()
        assert isinstance(data, bytes)
        _assert_valid_hwpx_container(data)

    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-3")
    def test_hwp5_input_converts_to_hwpx_container(self, parsed_hwp: rhwp.Document) -> None:
        # ^ HWP5 입력도 Document IR 포맷 독립 → HWPX 컨테이너로 출력 (HWP5 → HWPX 변환)
        data = parsed_hwp.to_hwpx_bytes()
        assert isinstance(data, bytes)
        _assert_valid_hwpx_container(data)

    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-4")
    def test_table_document_serializes_without_crash(self, parsed_hwpx: rhwp.Document) -> None:
        # ^ table-vpos-01.hwpx (표·그림 포함 실문서) — 경험적 crash-free 검증.
        #   의미 보존은 미보장 (상류 위임), 예외 없이 유효 컨테이너 bytes 만 확인.
        data = parsed_hwpx.to_hwpx_bytes()
        assert isinstance(data, bytes)
        assert len(data) > 0
        _assert_valid_hwpx_container(data)


class TestExportHwpx:
    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-5")
    def test_export_writes_file_and_returns_byte_count(
        self, parsed_hwpx: rhwp.Document, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.hwpx"
        written = parsed_hwpx.export_hwpx(str(out))
        assert written > 0
        assert out.exists()
        assert out.stat().st_size == written
        assert out.read_bytes()[:4] == ZIP_MAGIC

    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-5")
    def test_export_to_missing_parent_raises_oserror(
        self, parsed_hwpx: rhwp.Document, tmp_path: Path
    ) -> None:
        bad = tmp_path / "does_not_exist" / "out.hwpx"
        with pytest.raises(OSError):
            parsed_hwpx.export_hwpx(str(bad))


class TestAdditiveNoSideEffects:
    @pytest.mark.spec("v0.7.0/hwpx-writeback-baseline#AC-6")
    def test_writeback_does_not_mutate_existing_surfaces(
        self, samples_dir: Path, tmp_path: Path
    ) -> None:
        # ^ 독립 parse — 공유 session fixture 캐시 간섭 없이 before/after 비교.
        #   paragraphs / extract_text / render_svg / count getter 는 매 호출 self.inner
        #   에서 재계산되므로, 동등성은 writeback 이 문서를 변형하지 않았음을 입증한다.
        doc = rhwp.parse(str(samples_dir / "hwpx" / "business_overview.hwpx"))

        ir_before = doc.to_ir_json()
        paras_before = doc.paragraphs()
        text_before = doc.extract_text()
        svg_before = doc.render_svg(0)
        counts_before = (doc.section_count, doc.paragraph_count, doc.page_count)

        doc.to_hwpx_bytes()
        doc.export_hwpx(str(tmp_path / "side_effect_check.hwpx"))

        assert doc.to_ir_json() == ir_before
        assert doc.paragraphs() == paras_before
        assert doc.extract_text() == text_before
        assert doc.render_svg(0) == svg_before
        assert (doc.section_count, doc.paragraph_count, doc.page_count) == counts_before
