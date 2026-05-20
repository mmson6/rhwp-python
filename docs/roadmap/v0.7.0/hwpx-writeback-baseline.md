---
status: Draft
description: "v0.7.0 — HWPX writeback baseline. parse 결과를 'export_hwpx' / 'to_hwpx_bytes' 로 HWPX 저장 — 상류 'serialize_hwpx' 위임 + 텍스트·문단 round-trip 보장"
target: v0.7.0
last_updated: 2026-05-20
---

# v0.7.0 — HWPX writeback baseline

parse 한 `Document` 를 다시 HWPX 파일로 저장하는 첫 역방향 표면을 추가한다. v0.2.0 ~ v0.6.0 의 IR / SVG / PDF / PNG 산출물은 모두 read-only 출력이었고, v0.7.0 은 상류 `edwardkim/rhwp` 의 `serialize_hwpx` 를 `Document.to_hwpx_bytes()` / `Document.export_hwpx(path)` 로 노출하여 "parse → 저장" round-trip 을 연다. 추가만 있고 기존 IR / 렌더 / MCP 표면은 모두 보존 (additive only) — IR SchemaVersion 영향 없음.

주요 결정의 근거·대안·실패 시나리오는 짝 페어: [hwpx-writeback-baseline-research.md](../../design/v0.7.0/hwpx-writeback-baseline-research.md).

## 배경

v0.4.0 view 렌더러 / v0.5.0 MCP / v0.6.0 PNG 까지 모든 표면은 HWP/HWPX 를 *읽어* 텍스트·이미지·IR 로 평탄화하는 단방향이었다. 상류 `serializer/hwpx/` 모듈이 `Document` IR → HWPX(ZIP+XML) 직렬화를 공개 API (`serialize_hwpx`) 로 제공하면서, binding 측에서 PyO3 표면만 노출하면 역방향 round-trip 이 성립하는 상태가 됐다.

`Document` IR 은 포맷 독립이다 — HWP5 / HWPX / HWP3 파서가 모두 동일한 `model::document::Document` 로 변환하므로, HWP5 로 parse 한 문서도 `serialize_hwpx` 로 HWPX 출력이 가능하다 (HWP5 → HWPX 포맷 변환이 부수 효과로 성립).

보존 범위는 상류 serializer 의 현 보존 범위에 위임한다. 상류는 텍스트·문단·표·그림·도형·수식의 직렬화 코드를 보유하되 round-trip 의미 보존의 검증 (IrDiff) 은 요소별로 점진 확장 중이다. 본 baseline 이 회귀로 보장하는 것은 **텍스트·문단 round-trip** 이며, 표·그림 등은 crash-free + 상류 보존 범위를 그대로 따른다. 표·그림의 의미 보존 보장은 v0.8.0 으로 분리.

## 결정 사항

| 항목 | 값 | 근거 |
|---|---|---|
| 1 — 직렬화 source | 상류 `serialize_hwpx` 위임 | 자체 직렬화 구현 금지 (upstream-first). HWPX writer 결함/누락은 상류 이슈로 보고. 자세한 본체 비교는 ADR §1 |
| 2 — API 표면·명명 | `to_hwpx_bytes() -> bytes` + `export_hwpx(path) -> int` | `render_pdf` / `export_pdf` 의 메모리/파일 분리 패턴과 대칭. `render_*` (raster 전용) / `save_*` (mutable 연상) 회피. 자세한 본체 비교는 ADR §2 |
| 3 — GIL 전략 | baseline 은 GIL 보유 | `serialize_hwpx(self.inner.document())` 가 `&self.inner` 캡처 — `DocumentCore` 가 RefCell 로 `!Sync` 라 `py.detach` 클로저 이동 불가. clone 후 detach 는 측정 후 (ADR §3) |
| 4 — 입력 포맷 | HWP5 / HWPX 모두 수용 | `Document` IR 포맷 독립. HWP5 → HWPX 변환 허용. 입력 포맷에 따른 분기 없음 |
| 5 — 보존 boundary | 텍스트·문단 round-trip 보장, 표·그림은 상류 위임 (crash-free) | 상류 IrDiff 검증 범위가 점진 확장 중. 표·그림 의미 보존 보장은 v0.8.0. 자세한 본체 비교는 ADR §4 |

## 인수조건

- **AC-1** — 텍스트·문단만 있는 HWPX 를 parse → `export_hwpx(out)` → `parse(out)` 했을 때, 재파싱 결과의 섹션 수 / 문단 수 / 각 문단 `text` 가 원본과 동등하다 (round-trip 의미 보존)
- **AC-2** — `to_hwpx_bytes()` 출력은 valid HWPX 컨테이너다: ZIP magic `b"PK\x03\x04"` 으로 시작하고, 첫 ZIP 엔트리가 STORED 방식 `mimetype` = `application/hwp+zip`
- **AC-3** — HWP5 파일 (`aift.hwp`) 을 parse → `to_hwpx_bytes()` 가 AC-2 를 만족하는 bytes 를 반환한다 (HWP5 → HWPX 포맷 변환)
- **AC-4** — 표·그림을 포함한 실문서 (`table-vpos-01.hwpx`) 를 parse → `to_hwpx_bytes()` 가 예외 없이 bytes 를 반환한다 (해당 fixture 경험적 검증, 의미 보존 미보장). 단 무조건 crash-free 는 아니다 — 컨트롤 직렬화 실패는 상류가 per-control graceful 처리하나, 참조 무결성 실패 (BinData 누락 등) 는 `ValueError` 로 전파된다
- **AC-5** — `export_hwpx(path)` 는 `path` 에 파일을 생성하고 작성 바이트 수 (> 0) 를 반환한다. 존재하지 않는 부모 디렉토리 등 쓰기 실패 시 `OSError`
- **AC-6** — `to_hwpx_bytes()` / `export_hwpx()` 는 `Document` 의 기존 IR / 렌더 메서드 (`to_ir` / `render_pdf` / `render_png` 등) 와 독립적으로 동작하며, 호출 후에도 기존 메서드 결과가 변하지 않는다 (additive, 부작용 없음)

## 영구 비목표

- **IR mutable 편집 후 재저장** — `Document` 는 parse 결과 read-only 이고 Python IR (`HwpDocument`) → Rust `Document` 역매퍼가 없다. IR 을 편집해 새 문서를 생성하는 빌더 API 는 v1.0 API 안정 선언 시점에 통합 검토
- **HWP5 binary 출력 (`export_hwp`)** — 상류 `serialize_hwp` 는 존재하나 본 baseline 은 HWPX 출력만. HWP5 binary writeback 은 v0.9.0
- **표·그림·수식 round-trip 의미 보존 보장** — 상류 IrDiff 검증 범위 확장에 의존. baseline 은 crash-free 만 보장. 의미 보존은 v0.8.0
- **bytewise 동일성** — round-trip 은 의미적 동등성 기준. ZIP 압축 / 타임스탬프 / canonical default 주입 등으로 원본과 byte 단위 동일은 보장하지 않는다
- **CLI / MCP 노출** — SDK 표면 (`Document` 메서드) 만. `rhwp-py` CLI 의 변환 서브명령 / MCP 도구 노출은 별도 demand 시 후속

## 참조

- 짝 페어 (ADR): [hwpx-writeback-baseline-research.md](../../design/v0.7.0/hwpx-writeback-baseline-research.md)
- 상류 HWPX serializer: `external/rhwp/src/serializer/hwpx/` (`serialize_hwpx`)
- 상류 직렬화 trait: `external/rhwp/src/serializer/mod.rs` (`DocumentSerializer` / `SerializeError`)
