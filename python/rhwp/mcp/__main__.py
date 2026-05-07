"""``python -m rhwp.mcp`` — entry point 와 동일 동작 (rhwp-mcp 명령 미등록 시 폴백)."""

from rhwp.mcp import run

if __name__ == "__main__":
    run()
