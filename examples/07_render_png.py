"""HWP/HWPX 페이지를 PNG 로 렌더링하는 예제 (VLM 입력).

사용법:
    python examples/07_render_png.py path/to/file.hwp
    python examples/07_render_png.py path/to/file.hwp --page 2 --scale 2.0
    python examples/07_render_png.py path/to/file.hwp --all
    python examples/07_render_png.py path/to/file.hwp --all --scale 1.5 --output-dir ./out

설치:
    pip install "rhwp-python[examples]"
"""

import io
from pathlib import Path as PathLibPath

import rhwp
import typer

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _describe(data: bytes) -> str:
    size_kb = len(data) / 1024
    magic_ok = data.startswith(PNG_MAGIC)
    parts = [f"{size_kb:.1f} KB", "PNG magic OK" if magic_ok else "PNG magic FAIL"]
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        parts.append(f"{img.size[0]}×{img.size[1]}")
    except ImportError:
        parts.append("Pillow 미설치 (dimension 검증 생략)")
    return ", ".join(parts)


def main(
    path: PathLibPath = typer.Argument(..., help="HWP 또는 HWPX 파일 경로"),
    page: int = typer.Option(0, "--page", "-p", help="0-based 페이지 인덱스 (단일 모드)"),
    all_pages: bool = typer.Option(False, "--all", help="전 페이지 일괄 렌더링 (--page 무시)"),
    scale: float = typer.Option(1.0, "--scale", "-s", help="픽셀 너비/높이 배율 (default 1.0)"),
    max_pixels: int | None = typer.Option(
        None, "--max-pixels", help="DoS 가드 픽셀 상한 (default 8192×8192)"
    ),
    output_dir: PathLibPath = typer.Option(
        PathLibPath("./render_output"), "--output-dir", "-o", help="출력 디렉토리"
    ),
    prefix: str = typer.Option("page", "--prefix", help="PNG 파일명 접두사"),
) -> None:
    """HWP/HWPX 를 파싱한 뒤 PNG 로 렌더링.

    단일 페이지 (기본): `--page` 인덱스 한 장을 `{prefix}.png` 로 저장.
    전체 페이지 (`--all`): `{prefix}_{NNN}.png` 패턴으로 저장 (1-based 0-padded 3자리).
    `--scale` 또는 `--max-pixels` 가 기본값과 다르면 page 단위 루프로 처리 (export_png 가 두 인자 미수령).
    """
    if not path.exists():
        typer.echo(f"파일이 없습니다: {path}", err=True)
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"파싱 중: {path}")
    doc = rhwp.parse(str(path))
    typer.echo(f"  페이지 수: {doc.page_count}")

    if all_pages:
        typer.echo(f"\n[PNG, all pages] {output_dir}/{prefix}*.png  (scale={scale})")
        custom_opts = scale != 1.0 or max_pixels is not None
        if custom_opts:
            for p in range(doc.page_count):
                data = doc.render_png(p, scale=scale, max_pixels=max_pixels)
                if doc.page_count == 1:
                    out = output_dir / f"{prefix}.png"
                else:
                    out = output_dir / f"{prefix}_{p + 1:03d}.png"
                out.write_bytes(data)
                typer.echo(f"  {out}  ({_describe(data)})")
        else:
            paths = doc.export_png(str(output_dir), prefix=prefix)
            for p in paths:
                size_kb = PathLibPath(p).stat().st_size / 1024
                typer.echo(f"  {p}  ({size_kb:.1f} KB)")
    else:
        if page >= doc.page_count:
            typer.echo(f"--page {page} 가 페이지 수 {doc.page_count} 를 초과합니다.", err=True)
            raise typer.Exit(code=1)
        out = output_dir / f"{prefix}.png"
        typer.echo(f"\n[PNG, page {page}] {out}  (scale={scale}, max_pixels={max_pixels})")
        data = doc.render_png(page, scale=scale, max_pixels=max_pixels)
        out.write_bytes(data)
        typer.echo(f"  {_describe(data)}")

    typer.echo(f"\n완료. 결과물: {output_dir}/")


if __name__ == "__main__":
    typer.run(main)
