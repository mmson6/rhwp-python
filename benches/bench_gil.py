"""GIL 해제 효과 측정 — 단일 vs 멀티스레드 parse / render_pdf / render_png 처리 시간.

`py.detach` 를 적용한 `parse()` / `render_pdf()` / `render_png()` 가
`ThreadPoolExecutor` 에서 실제 병렬 실행되는지 (GIL 해제 작동) 확인.

`#[pyclass(unsendable)]` 제약: `Document` 객체는 생성된 스레드에서만 유효.
벤치는 각 워커가 parse → 추출 / render_pdf → bytes / render_png → bytes 까지
완결 후 int 반환 (현업 패턴).

옵션:
    --json   결과를 stdin 친화 JSON 으로 출력 (drift 추적 / ADR 첨부용)
"""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rhwp

# ^ 경로: <REPO_ROOT>/benches/bench_gil.py
#   샘플은 rhwp 코어 submodule (external/rhwp) 내부 samples/ 디렉터리에 있음
REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "external" / "rhwp" / "samples"


def parse_task(path: str) -> int:
    # ^ 워커 스레드 내에서 Document 생성/소멸 완결. int 만 반환
    doc = rhwp.parse(path)
    return doc.paragraph_count


def pdf_task(path: str) -> int:
    # ^ parse + render_pdf 를 한 워커에서 처리. bytes 길이만 반환
    doc = rhwp.parse(path)
    pdf = doc.render_pdf()
    return len(pdf)


def png_task(path: str) -> int:
    # ^ parse + render_png(page=0) 를 한 워커에서 처리. bytes 길이만 반환
    doc = rhwp.parse(path)
    png = doc.render_png(0)
    return len(png)


def bench(task, file_list: list[str], workers: int, repeats: int) -> float:
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        if workers == 1:
            results = [task(p) for p in file_list]
        else:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(task, file_list))
        times.append(time.perf_counter() - start)
        assert len(results) == len(file_list)
    return min(times)


def _run_section(task, file_list, worker_list, repeats):
    rows = []
    baseline = bench(task, file_list, workers=1, repeats=repeats)
    rows.append({"workers": 1, "seconds": baseline, "speedup": 1.0})
    for w in worker_list:
        t = bench(task, file_list, workers=w, repeats=repeats)
        rows.append({"workers": w, "seconds": t, "speedup": baseline / t})
    return rows


def _print_table(title: str, subtitle: str, rows: list[dict], task_count: int) -> None:
    print()
    print("=" * 72)
    print(title)
    print(subtitle)
    print("=" * 72)
    print(f"{'워커 수':<12} {'처리 시간':<15} {'단일 대비':<15} {'이상적 가속':<15}")
    print("-" * 72)
    for r in rows:
        ideal = min(r["workers"], task_count)
        label = "1 (순차)" if r["workers"] == 1 else str(r["workers"])
        print(
            f"{label:<12} {f'{r['seconds'] * 1000:.0f}ms':<15} "
            f"{f'{r['speedup']:.2f}x':<15} {f'{ideal:.0f}x (이상치)':<15}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="결과를 JSON 으로 stdout 에 dump"
    )
    args = parser.parse_args()

    files = [
        str(SAMPLES / "aift.hwp"),
        str(SAMPLES / "table-vpos-01.hwpx"),
        str(SAMPLES / "tac-img-02.hwpx"),
    ]
    parse_workload = files * 3  # ^ 9 태스크 (3 파일 × 3회 반복)

    parse_rows = _run_section(parse_task, parse_workload, [2, 4, 8], repeats=3)
    pdf_rows = _run_section(pdf_task, files, [2, 3], repeats=2)
    png_rows = _run_section(png_task, files, [2, 3], repeats=2)

    if args.json:
        payload = {
            "system": {
                "cpu_count": os.cpu_count(),
                "rhwp_version": rhwp.version(),
                "rhwp_core_version": rhwp.rhwp_core_version(),
            },
            "parse": {"task_count": len(parse_workload), "rows": parse_rows},
            "pdf": {"task_count": len(files), "rows": pdf_rows},
            "png": {"task_count": len(files), "rows": png_rows},
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"시스템 코어 수: {os.cpu_count()}")
    print(f"rhwp 버전: {rhwp.version()}  /  rhwp core: {rhwp.rhwp_core_version()}")
    _print_table(
        "Parse 벤치마크 — 9개 파일 (aift + table-vpos + tac-img, 각 3회)",
        "",
        parse_rows,
        len(parse_workload),
    )
    _print_table(
        "PDF 렌더링 벤치마크 — 3개 문서 (parse + render_pdf 워커 내 완결)",
        "",
        pdf_rows,
        len(files),
    )
    _print_table(
        "PNG 렌더링 벤치마크 — 3개 문서 (parse + render_png(0) 워커 내 완결)",
        "",
        png_rows,
        len(files),
    )


if __name__ == "__main__":
    main()
