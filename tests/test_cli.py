"""rhwp-py CLI 서브커맨드 smoke + 통합 테스트.

typer.testing.CliRunner 기반 smoke + 실제 sample 통합. 파일 레벨
``importorskip("typer")`` 로 typer 미설치 시 file 전체 skip — gated 파일
총 카운트 검증은 CI ``test-without-extras`` 잡이 SSOT.
"""

import json
import sys
from pathlib import Path

import pytest

# ^ typer extras 가드 — 미설치 시 file 전체 skip
pytest.importorskip("typer")
import rhwp  # noqa: E402
from rhwp.cli.app import app  # noqa: E402
from typer.testing import CliRunner  # noqa: E402  (importorskip 뒤 import)

pytestmark = pytest.mark.spec("v0.3.0/cli")
# ^ soft retrofit — file-level spec mapping; v0.4.0+ specs add #AC-N to specific tests (CONVENTIONS § Trace report)

# * Click 8.2+ 부터 CliRunner 가 stdout/stderr 를 기본 분리 — result.stderr 단독 검증 가능
_RUNNER = CliRunner()


def _run(*args: str):
    return _RUNNER.invoke(app, list(args))


# * --help 검증 — 모든 6 서브커맨드 노출


def test_help_lists_all_subcommands() -> None:
    result = _run("--help")
    assert result.exit_code == 0
    for cmd in ("parse", "version", "schema", "ir", "blocks", "chunks"):
        assert cmd in result.stdout, f"subcommand {cmd!r} missing from --help"


# * version — rhwp.version() / rhwp_core_version() 일치


def test_version_outputs_match_rhwp_module() -> None:
    result = _run("version")
    assert result.exit_code == 0
    assert rhwp.version() in result.stdout
    assert rhwp.rhwp_core_version() in result.stdout


# * parse — 한 줄 sections=N paragraphs=N pages=N + 한 줄 버전


def test_parse_summary_format(hwp_sample: Path) -> None:
    result = _run("parse", str(hwp_sample))
    assert result.exit_code == 0
    assert "sections=" in result.stdout
    assert "paragraphs=" in result.stdout
    assert "pages=" in result.stdout
    assert "rhwp-python=" in result.stdout
    assert "rhwp-core=" in result.stdout


def test_parse_missing_file_exit_1(tmp_path: Path) -> None:
    result = _run("parse", str(tmp_path / "missing.hwp"))
    assert result.exit_code == 1
    assert "file not found" in result.stderr


# * schema — stdout 결과가 export_schema() 와 동일


def test_schema_stdout_matches_export_schema() -> None:
    from rhwp.ir.schema import export_schema

    result = _run("schema")
    assert result.exit_code == 0
    assert json.loads(result.stdout) == export_schema()


def test_schema_to_file_writes_valid_json(tmp_path: Path) -> None:
    out = tmp_path / "schema.json"
    result = _run("schema", "--out", str(out))
    assert result.exit_code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["$id"].endswith("/schema/hwp_ir/v1/schema.json")
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"


# * ir — to_ir_json 위에. default 한 줄, --indent 들여쓰기


def test_ir_default_compact_single_line(hwpx_sample: Path) -> None:
    result = _run("ir", str(hwpx_sample))
    assert result.exit_code == 0
    body = result.stdout.rstrip("\n")
    assert body.count("\n") == 0
    assert '"schema_version"' in body


def test_ir_indent_produces_multiline(hwpx_sample: Path) -> None:
    result = _run("ir", str(hwpx_sample), "--indent", "2")
    assert result.exit_code == 0
    assert result.stdout.count("\n") > 5


def test_ir_to_file(hwpx_sample: Path, tmp_path: Path) -> None:
    out = tmp_path / "ir.json"
    result = _run("ir", str(hwpx_sample), "--out", str(out))
    assert result.exit_code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_name"] == "HwpDocument"


# * blocks — ndjson default, json 전체, text 평문


def test_blocks_ndjson_each_line_is_independent_json(hwpx_sample: Path) -> None:
    result = _run("blocks", str(hwpx_sample), "--format", "ndjson", "--limit", "5")
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) <= 5
    assert len(lines) > 0
    for line in lines:
        obj = json.loads(line)
        assert "kind" in obj
        assert "prov" in obj


def test_blocks_kind_filter_table(hwpx_sample: Path) -> None:
    result = _run("blocks", str(hwpx_sample), "--kind", "table", "--format", "ndjson")
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) > 0  # ^ 샘플에 표 9개
    for line in lines:
        assert json.loads(line)["kind"] == "table"


def test_blocks_format_json_returns_array(hwpx_sample: Path) -> None:
    result = _run("blocks", str(hwpx_sample), "--format", "json", "--limit", "3")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) <= 3
    if data:
        assert "kind" in data[0]


def test_blocks_format_text_outputs_plain_strings(hwp_sample: Path) -> None:
    """text 모드는 평문만 — HTML 마크업 부재 + non-empty 라인."""
    result = _run(
        "blocks", str(hwp_sample), "--format", "text", "--kind", "paragraph", "--limit", "5"
    )
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) > 0  # ^ 빈 단락은 skip 됐지만 5 한도 안에 non-empty 단락이 충분
    for line in lines:
        # ^ paragraph 만 필터했으므로 HTML 태그가 절대 등장하면 안 됨
        assert "<table>" not in line
        assert "</p>" not in line


def test_blocks_scope_furniture_exits_zero(hwp_sample: Path) -> None:
    result = _run("blocks", str(hwp_sample), "--scope", "furniture", "--format", "ndjson")
    assert result.exit_code == 0


def test_blocks_no_recurse_skips_table_cells(hwpx_sample: Path) -> None:
    """--no-recurse 면 TableCell.blocks 안의 paragraph 가 yield 되지 않는다."""
    result_recurse = _run("blocks", str(hwpx_sample), "--kind", "paragraph", "--format", "ndjson")
    result_no_recurse = _run(
        "blocks",
        str(hwpx_sample),
        "--kind",
        "paragraph",
        "--no-recurse",
        "--format",
        "ndjson",
    )
    assert result_recurse.exit_code == 0
    assert result_no_recurse.exit_code == 0
    n_recurse = sum(1 for line in result_recurse.stdout.splitlines() if line)
    n_no_recurse = sum(1 for line in result_no_recurse.stdout.splitlines() if line)
    # ^ HWPX 샘플은 표 안에 단락이 있으므로 recurse=True 가 더 많은 단락을 yield
    assert n_recurse >= n_no_recurse


# * chunks — langchain-text-splitters 미설치 시 exit 2 (monkeypatch 로 simulate)


def test_chunks_missing_text_splitters_exit_2(
    hwp_sample: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """langchain_text_splitters 가 import 불가하면 exit 2 + stderr 메시지."""
    monkeypatch.setitem(sys.modules, "langchain_text_splitters", None)
    result = _run("chunks", str(hwp_sample))
    assert result.exit_code == 2
    assert "langchain-text-splitters" in result.stderr
    assert "rhwp-python[cli-chunks]" in result.stderr


@pytest.mark.langchain
def test_chunks_paragraph_default(hwp_sample: Path) -> None:
    pytest.importorskip("langchain_text_splitters")
    result = _run(
        "chunks",
        str(hwp_sample),
        "--format",
        "ndjson",
        "--size",
        "300",
        "--overlap",
        "30",
    )
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) > 0
    for line in lines[:5]:
        obj = json.loads(line)
        assert "page_content" in obj
        assert "metadata" in obj


@pytest.mark.langchain
def test_chunks_ir_blocks_mode(hwpx_sample: Path) -> None:
    pytest.importorskip("langchain_text_splitters")
    result = _run(
        "chunks",
        str(hwpx_sample),
        "--mode",
        "ir-blocks",
        "--format",
        "ndjson",
        "--size",
        "500",
    )
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) > 0
    # ^ ir-blocks 모드: metadata.kind 가 paragraph/table/picture/... 중 하나
    obj = json.loads(lines[0])
    assert obj["metadata"]["kind"] in {
        "paragraph",
        "table",
        "picture",
        "formula",
        "footnote",
        "endnote",
        "list_item",
        "caption",
        "toc",
        "field",
    }


@pytest.mark.langchain
def test_chunks_include_furniture_yields_more_or_equal(hwp_sample: Path) -> None:
    """--include-furniture 면 body 만일 때보다 출력 청크 ≥ — fixture-agnostic invariant.

    aift.hwp 샘플에 footnote 가 있어 실제로는 strict greater 지만, 테스트가 샘플
    구성 (footnote 유무) 에 brittle 하지 않게 ≥ 만 검증. furniture 블록의
    metadata.scope 검증은 별도 LangChain loader 테스트가 수행.
    """
    pytest.importorskip("langchain_text_splitters")
    args_common = [
        "chunks",
        str(hwp_sample),
        "--mode",
        "ir-blocks",
        "--format",
        "ndjson",
        "--size",
        "500",
    ]
    body_only = _run(*args_common)
    with_furn = _run(*args_common, "--include-furniture")
    assert body_only.exit_code == 0
    assert with_furn.exit_code == 0
    n_body = sum(1 for line in body_only.stdout.splitlines() if line)
    n_with = sum(1 for line in with_furn.stdout.splitlines() if line)
    assert n_with >= n_body, (
        f"--include-furniture 가 body-only 보다 적은 청크를 반환: body={n_body}, with={n_with}"
    )
    # ^ furniture 추가 청크가 있다면 그 중 적어도 하나는 scope=furniture metadata 보유
    if n_with > n_body:
        scopes = {
            json.loads(line)["metadata"].get("scope")
            for line in with_furn.stdout.splitlines()
            if line
        }
        assert "furniture" in scopes


# * typer 미설치 환경의 entry point 검증은 ci.yml test-without-extras 잡이 담당


def test_chunks_missing_file_exit_1(tmp_path: Path) -> None:
    """존재하지 않는 파일 — exit 1 (extras 미설치 가드보다 뒤 검사 순서지만 monkeypatch 없이)."""
    pytest.importorskip("langchain_text_splitters")
    result = _run("chunks", str(tmp_path / "missing.hwp"))
    assert result.exit_code == 1


# * footnote/caption 평문화 회귀 — ListItemBlock 누락 방지 (--format text)
#
# ``rhwp.ir._plain_text.join_inline_blocks`` 도입 전에는 footnote/caption 안의
# ListItemBlock 이 평문에 포함되지 않았다. CLI ``--format text`` 도 동일한 누락이
# 있었으므로 같은 회귀를 가드한다.


def test_block_to_text_includes_list_items_in_footnote() -> None:
    from rhwp.cli.ir import _block_to_text
    from rhwp.ir.nodes import FootnoteBlock, ListItemBlock, ParagraphBlock, Provenance

    prov = Provenance(section_idx=0, para_idx=0)
    footnote = FootnoteBlock(
        number=1,
        marker_prov=prov,
        prov=prov,
        blocks=[
            ParagraphBlock(text="참고:", prov=prov),
            ListItemBlock(text="첫째", marker="1.", enumerated=True, prov=prov),
        ],
    )
    assert _block_to_text(footnote) == "참고:\n1. 첫째"
