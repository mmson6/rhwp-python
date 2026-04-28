"""rhwp.cli — ``rhwp-py`` 명령 entry point.

typer 는 ``[cli]`` extras (또는 ``[examples]``) 미설치 시 ImportError. ``app()``
호출 시점까지 typer import 를 지연하여 패키지 import 자체는 typer 없이도
성공한다. ``[project.scripts] rhwp-py = "rhwp.cli:app"`` 로 등록.

관련 spec: ``docs/roadmap/v0.3.0/cli.md``.
"""

import sys


def app() -> None:
    """``rhwp-py`` 명령 entry point — typer 또는 그 transitive deps 미설치 시 친절 에러 + exit 2.

    ``rhwp.cli.app`` import chain 안에서 발생하는 ImportError 는 ``rhwp.cli`` 자체
    모듈 외 라이브러리 부재로 간주 — typer / click / rich / shellingham 등 어느
    것이 빠져도 같은 친절 메시지를 출력하고 exit 2. ``rhwp`` 자체 모듈 결함은
    원본 ImportError 가 그대로 노출 (e.name 이 ``rhwp.*`` 또는 ``rhwp`` 시작).
    """
    try:
        from rhwp.cli.app import app as _app
    except ImportError as e:
        # ^ rhwp 자체 모듈 import 실패는 진단 단서 보존을 위해 그대로 raise
        if e.name and (e.name == "rhwp" or e.name.startswith("rhwp.")):
            raise
        sys.stderr.write(
            f"rhwp-py requires typer (missing module: {e.name!r}). Install with:\n"
            '    pip install "rhwp-python[cli]"\n'
        )
        raise SystemExit(2) from e
    _app()
