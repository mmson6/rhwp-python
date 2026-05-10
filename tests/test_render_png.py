"""v0.6.0 페이지 PNG 렌더링 회귀 가드 — render_png / arender_png / MCP 도구 검증.

AC-1 ~ AC-7 매핑은 ``docs/roadmap/v0.6.0/png-vlm-render.md`` § 인수조건. PIL 은
``testing`` dependency-group 에 포함 (디코드 후 dimension 검증 — AC-3) — 미설치
환경에서는 file-level skip 으로 본 파일 전체가 1 skip 으로 카운트.
"""

import asyncio
import base64
import io
from pathlib import Path

import pytest

# ^ test-without-extras CI job 의 expected skip count 를 위해 file-level 가드.
#   testing 그룹 (dev / 본 CI test job) 에는 Pillow 포함 — 정상 실행.
PilImage = pytest.importorskip("PIL.Image")

import rhwp

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestRenderPng:
    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-1")
    def test_returns_png_magic(self, parsed_hwp: rhwp.Document) -> None:
        png = parsed_hwp.render_png(0)
        assert isinstance(png, bytes)
        assert png[:8] == PNG_MAGIC

    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-2")
    def test_render_all_count_matches_page_count(self, parsed_hwp: rhwp.Document) -> None:
        all_pngs = parsed_hwp.render_all_png()
        assert len(all_pngs) == parsed_hwp.page_count
        # ^ 각 페이지가 PNG magic 으로 시작해야 — render_all 이 단순 list[bytes] 인지 확인
        assert all(p[:8] == PNG_MAGIC for p in all_pngs)

    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-3")
    def test_scale_doubles_width(self, parsed_hwp: rhwp.Document) -> None:
        png_1x = parsed_hwp.render_png(0, scale=1.0)
        png_2x = parsed_hwp.render_png(0, scale=2.0)
        w1 = PilImage.open(io.BytesIO(png_1x)).width
        w2 = PilImage.open(io.BytesIO(png_2x)).width
        # ^ 상류 raster_dimension 가 (value * scale).ceil() 이라 1px 정도 rounding 가능
        assert abs(w2 - w1 * 2) <= 2, f"expected w2 ≈ 2 × w1, got w1={w1} w2={w2}"

    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-4")
    def test_max_pixels_guard_raises(self, parsed_hwp: rhwp.Document) -> None:
        with pytest.raises(ValueError, match="pixel count out of range"):
            parsed_hwp.render_png(0, max_pixels=1)


class TestExportPng:
    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-7")
    def test_writes_files_with_png_magic(self, parsed_hwp: rhwp.Document, tmp_path: Path) -> None:
        out_dir = tmp_path / "png_out"
        paths = parsed_hwp.export_png(str(out_dir))
        assert len(paths) == parsed_hwp.page_count
        for path_str in paths:
            path = Path(path_str)
            assert path.exists()
            with open(path, "rb") as f:
                assert f.read(8) == PNG_MAGIC


class TestArenderPng:
    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-6")
    def test_async_returns_png_without_panic(self, hwp_sample: Path) -> None:
        # ^ aparse + sync render_png 패턴 — Document 가 thread 경계 안 넘는지 검증
        png = asyncio.run(rhwp.arender_png(str(hwp_sample), 0))
        assert png[:8] == PNG_MAGIC


class TestMcpRenderPagePng:
    @pytest.mark.spec("v0.6.0/png-vlm-render#AC-5")
    def test_returns_image_content(self, hwp_sample: Path) -> None:
        # ^ fastmcp 가 없으면 mcp.types import 도 실패 — per-test 가드로 file-level
        #   skip 회피 (다른 AC 가드는 fastmcp 무관하게 실행)
        pytest.importorskip("fastmcp")
        from mcp.types import ImageContent
        from rhwp.mcp.tools import render_page_png

        result = render_page_png(str(hwp_sample), 0)
        assert isinstance(result, ImageContent)
        assert result.type == "image"
        assert result.mimeType == "image/png"
        png = base64.b64decode(result.data)
        assert png[:8] == PNG_MAGIC
