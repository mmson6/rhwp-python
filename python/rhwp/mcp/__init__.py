"""rhwp.mcp — ``rhwp-mcp`` MCP 서버 entry point.

``fastmcp`` 는 ``[mcp]`` extras 미설치 시 ImportError. ``run()`` 호출 시점까지
``rhwp.mcp.server`` import 를 지연하여 패키지 import 자체는 ``fastmcp`` 없이도
성공한다. ``[project.scripts] rhwp-mcp = "rhwp.mcp:run"`` 로 등록.

관련 spec: ``docs/roadmap/v0.5.0/mcp.md``.
"""

import sys


def run() -> None:
    """``rhwp-mcp`` 명령 entry point — ``fastmcp`` 미설치 시 친절 에러 + exit 2.

    ``rhwp.mcp.server`` import chain 안에서 발생하는 ImportError 는 ``rhwp.mcp``
    자체 모듈 외 라이브러리 부재로 간주 — ``fastmcp`` / ``pydantic-settings`` /
    ``starlette`` 등 transitive 의존성 어느 것이 빠져도 같은 친절 메시지 +
    exit 2. ``rhwp`` 자체 모듈 결함은 원본 ImportError 가 그대로 노출 (e.name
    이 ``rhwp.*`` 또는 ``rhwp`` 시작) — ``rhwp.cli.app`` 와 동일 분기.
    """
    try:
        from rhwp.mcp.server import run as _run
    except ImportError as e:
        if e.name and (e.name == "rhwp" or e.name.startswith("rhwp.")):
            raise
        sys.stderr.write(
            f"rhwp-mcp requires `fastmcp` (missing module: {e.name!r}). Install with:\n"
            '    pip install "rhwp-python[mcp]"\n'
        )
        raise SystemExit(2) from e
    _run()
