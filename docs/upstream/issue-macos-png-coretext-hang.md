---
status: Active
description: "업스트림 제안 — headless macOS (CI 등) 에서 PNG 렌더가 미설치 폰트 fallback 시 CoreText downloadable lookup IPC 로 hang. 시스템 폰트 사전 필터링 patch 로 실측 0.43초 정상화 검증. 상류 등록 보류."
last_updated: 2026-05-11
---

> 외부 binding (`rhwp-python`) 구현 중 업스트림에서 수정이 필요해 보이는 부분을 발견하여, Claude 로 조사 및 다차례 사실 검증을 거친 결과입니다.

## 현상

`SkiaLayerRenderer::render_raster_with_options` 가 **headless macOS** (GHA `macos-latest` 등) 에서 무한 hang. interactive 데스크톱과 SVG export 는 정상이라 **실질 영향은 CI / 빌드팜 한정**입니다.

HWP 본문이 지정한 `한컴*` / `새*` / `함초롬*` 폰트가 시스템에 없을 때 CoreText 가 `fontd` 에 다운로드 가능 여부를 IPC 로 문의 → headless 환경에서는 `launchd` 가 `fontd` 를 안 띄워 응답자 부재 → `mach_msg2_trap` 영구 차단 (timeout 도 없음).

생성 시점에 시스템 폰트 family 를 캐시해 missing family 는 `match_family_style` 호출 자체를 skip 하면 해결 (실측 30분 hang → 0.43초).

## 원인

`src/renderer/skia/renderer.rs:286` 부근 fallback chain 루프가 missing family 를 `match_family_style` 에 전달 → CoreText 다운로드 lookup → `fontd` IPC 영구 대기. 첫 family 에서 막혀 chain 후속 family 는 시도조차 안 됨. brew 로 Noto / Nanum 등 chain 폰트 사전 설치도 효과 없음 (실측).

<details>
<summary><code>sample(1)</code> native stack (hang 중)</summary>

```
CTFontDescriptorCreateMatchingFontDescriptor  (CoreText)
  TDescriptor::CreateMatchingDescriptorInternal
    TDescriptorSource::CopyDescriptorsForRequest
      libFontRegistry::XTCopyFontsWithProperties
        TDownloadableFontManager::Download()
          libFontRegistryUI::DownloadFontsForProperties
            CFMessagePortSendRequest → mach_msg2_trap   ← 영구 차단
```

DispatchQueue `com.apple.FontRegistryUI`, leaf `mach_msg2_trap` — 네트워크가 아니라 로컬 IPC 수신자 부재.

</details>

## 재현

- 환경: GHA `macos-latest` (= `macos-15` 비대화형, ARM64), rhwp pin `62a458aa317e962cd3d0eec6096728c172d57110`
- 호출: `samples/aift.hwp` + `render_raster_with_options(page=0)` → 30분+ hang
- 대조: 같은 runner 의 `rhwp export-svg` 6초 / 개발자 desktop (HWP 폰트 설치) 53ms

trigger = AND(PNG raster path, HWP 명시 폰트 시스템 부재, `fontd` 미기동). macOS 13–16 / 26 모두 동일 조합이면 영향 가능 (직접 검증은 15.7.4).

## 제안 — 시스템 폰트 사전 필터링

```rust
use std::collections::{HashMap, HashSet};

pub struct SkiaLayerRenderer {
    font_mgr: FontMgr,
    custom_typefaces: HashMap<String, Typeface>,
    system_families: HashSet<String>,   // ← 추가
}

impl SkiaLayerRenderer {
    pub fn new() -> Self {
        let font_mgr = FontMgr::default();
        let system_families: HashSet<String> = font_mgr.family_names().collect();
        Self { font_mgr, custom_typefaces: HashMap::new(), system_families }
    }
}

// src/renderer/skia/renderer.rs:286 근처
for family in &families {
    if !self.system_families.contains(AsRef::<str>::as_ref(family)) {
        continue;   // missing family 는 CoreText 호출 회피
    }
    if let Some(tf) = self.font_mgr.match_family_style(family, font_style) {
        push(&mut chain, &mut seen, tf);
    }
}
```

`family_names()` 가 `CTFontManagerCopyAvailableFontFamilyNames` 호출이라 자체적으로 downloadable lookup 안 함 (실측 hang 해소로 후행 검증). 비고: `CTFontManagerSetAutoActivationSetting(null, kCTFontManagerAutoActivationDisabled)` 도 시도했으나 `libFontRegistryUI` lookup 까지 끄지 못해 같은 hang 실측.

## 검증

| 상태 | 결과 | CI run |
|---|---|---|
| baseline (patch 없음) | 30분 hang | [#25646433838](https://github.com/DanMeon/rhwp-python/actions/runs/25646433838) |
| `SetAutoActivationSetting` 시도 | hang 재현 | [#25649592697](https://github.com/DanMeon/rhwp-python/actions/runs/25649592697) |
| 사전 필터링 적용 | `1 passed in 0.43s` / `592 passed in 51.25s` | [#25650400186](https://github.com/DanMeon/rhwp-python/actions/runs/25650400186) |

SVG path / custom typeface 루프 regression 없음. cost: 생성 시 `family_names()` 1회 (수십 ms), 이후 HashSet O(1). 코드 약 10줄. 실효는 CI / headless 환경의 hang 해소 한 가지 — interactive desktop 은 `fontd` 응답이 빨라 perf 차이 사실상 없음, 다른 OS 도 영향 없음.

## 참고 위치

- `src/renderer/skia/renderer.rs:19-33` — `SkiaLayerRenderer` 구조체 / `new` (필드 추가, 캐싱 위치)
- `src/renderer/skia/renderer.rs:286` 근처 — fallback chain 루프 (수정 대상)
- `src/renderer/style_resolver.rs:566-583` — `한컴` / `새` / `함초롬` family 매핑 (trigger 원인)
