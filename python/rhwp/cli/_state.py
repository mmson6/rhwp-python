"""CLI 전역 상태 — ``--quiet`` 플래그 공유용.

Typer ``ctx.obj`` 를 거치지 않고 모듈 레벨 단순 변수로 처리한다 — CLI 한 번
실행에 한 번만 셋되고 서브커맨드 진입 시점엔 callback 이 항상 먼저 호출된다.
"""

_QUIET = False


def set_quiet(value: bool) -> None:
    global _QUIET
    _QUIET = value


def is_quiet() -> bool:
    return _QUIET
