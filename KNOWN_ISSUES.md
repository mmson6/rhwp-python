# Known issues

이 패키지를 사용할 때 알아두면 좋은 운영상 제약. 미구현 기능 / 작업 중 항목은
[`roadmap/`](roadmap/README.md) 의 활성 spec 인덱스 참조.

## Document 객체는 단일 스레드 객체

`rhwp.Document` 는 PyO3 `#[pyclass(unsendable)]` 로 바인딩되어 있어 생성 스레드를
벗어난 접근은 `RuntimeError` 또는 panic 으로 이어진다. 상류 `rhwp` 코어가 내부에
`RefCell` 캐시를 가지고 있어 `Sync` 가 아니기 때문이다.

### 멀티스레드 처리 패턴

worker 내에서 `parse + consume` 까지 완결한 뒤 원시 타입 (`int`, `str`, `bytes`) 만
반환한다. Document 인스턴스가 worker 경계를 넘지 않는 한 안전하다.

```python
from concurrent.futures import ThreadPoolExecutor
import rhwp

def parse_and_extract(path: str) -> str:
    doc = rhwp.parse(path)         # ^ worker 내에서 생성
    return doc.extract_text()       # ^ str 만 main thread 로 반환

with ThreadPoolExecutor(max_workers=4) as ex:
    texts = list(ex.map(parse_and_extract, paths))
```

벤치마크 / 재현은 `benches/bench_gil.py`.

### Async 진입점

`asyncio.to_thread(rhwp.parse, path)` 는 사용 금지 — Future 가 main thread 에서
resolve 되는 순간 첫 attribute 접근이 unsendable 위반으로 panic 한다.

대신 `rhwp.aparse(path)` 를 사용한다. 파일 I/O 만 thread pool 로 offload 하고
Document 는 event-loop thread 에서 생성되므로 thread 경계를 절대 넘지 않는다.

```python
import asyncio, rhwp

async def main():
    doc = await rhwp.aparse("report.hwp")
    text = doc.extract_text()
```

상류 `rhwp` 가 `RefCell` 캐시를 thread-safe 동기화로 전환하면 `unsendable` 제거
및 true `async fn pymethods` 가 가능해진다 — 현재는 미정.

## PDF 렌더 stdout 노이즈

상류 `rhwp` 코어가 PDF 렌더 경로에서 `[DEBUG_TAB_POS]` / `LAYOUT_OVERFLOW` 진단
로그를 stdout 으로 직접 출력한다. 본 바인딩은 이를 가로채지 않는다.

```bash
python script.py 2>&1 | grep -v -E "(DEBUG_TAB_POS|LAYOUT_OVERFLOW)"
```

상류 이슈로 추적 — 보고 채널은 [edwardkim/rhwp/issues](https://github.com/edwardkim/rhwp/issues).

## 읽기 / 렌더링 전용

HWP / HWPX **저장 (serialization)** 은 미지원이다. 본 패키지는 읽기 / 추출 /
렌더링 (SVG, PDF) 만 제공한다. 저장은 상류 코어가 export 경로를 GA 한 뒤
바인딩에 노출하는 구조이며, 현재 로드맵에 없다.
