"""``python -m rhwp.cli`` — entry point 와 동일 동작 (rhwp-py 명령 미등록 시 폴백)."""

from rhwp.cli import app

if __name__ == "__main__":
    app()
