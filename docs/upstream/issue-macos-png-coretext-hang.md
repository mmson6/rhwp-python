---
status: Frozen
description: "업스트림 제안 — headless macOS (CI 등) 에서 PNG 렌더가 미설치 폰트 fallback 시 CoreText downloadable lookup IPC 로 hang. 시스템 폰트 사전 필터링 patch 로 실측 0.43초 정상화 검증. 상류 등록 [#823](https://github.com/edwardkim/rhwp/issues/823)."
last_updated: 2026-06-21
---

> **RESOLVED 2026-06-04** — 상류 [#823](https://github.com/edwardkim/rhwp/issues/823) 이 v0.7.13 에서 해결 (closed). headless macOS 에서 `render_png` 가 hang 없이 동작한다. 본 binding 은 v0.8.0 상류 sync (pin `7d9aae7f`, v0.7.16+36) 로 fix 를 흡수하고 `ci.yml` 의 macOS smoke 잡을 복원했다.

> 외부 binding (`rhwp-python`) 구현 중 업스트림에서 수정이 필요해 보이는 부분을 발견하여, Claude 로 조사 및 다차례 사실 검증을 거친 결과입니다.

## 현상

`SkiaLayerRenderer::render_raster_with_options` 가 **headless macOS** (GHA `macos-latest` 등) 에서 무한 hang. interactive 데스크톱과 SVG export 는 정상이라 **실질 영향은 CI / 빌드팜 한정**입니다.

HWP 본문이 지정한 `한컴*` / `새*` / `함초롬*` 폰트가 시스템에 없을 때 CoreText 가 `fontd` 에 다운로드 가능 여부를 IPC 로 문의 → headless 환경에서는 `launchd` 가 `fontd` 를 안 띄워 응답자 부재 → `mach_msg2_trap` 영구 차단 (timeout 도 없음).

시스템 폰트 family 를 한 번 캐시해 missing family 는 `match_family_style` 호출 자체를 skip 하면 해결 (실측 30분 hang → 0.43초).

## 원인

시스템에 없는 폰트를 `match_family_style` 에 전달하면 CoreText 가 다운로드 가능 여부 lookup → `fontd` IPC 영구 대기. fallback chain 의 첫 family 에서 막혀 chain 후속은 시도조차 안 됨. brew 로 Noto / Nanum 등 chain 폰트 사전 설치도 효과 없음 (실측).

호출 사이트는 상류 main `a9dcdee3` 기준 네 곳:

| 위치 | 형태 |
|---|---|
| `src/renderer/skia/text_replay.rs:107` | 본문 fallback chain 루프 (이슈 최초 등록 시점에는 `renderer.rs:286` 부근, PR #769 refactor 로 이동) |
| `src/renderer/skia/text_replay.rs:648` | `make_mark_font` 의 `match_family_style("DejaVu Sans", ..)` **단발 호출** — fallback 루프 자체가 없어 단독 trigger 가능 |
| `src/renderer/skia/renderer.rs:687` | CJK fallback 루프 (`"AppleGothic"` 등). 보통 `AppleGothic` hit, missing 명시 family 가 chain 앞쪽에 있으면 trigger |
| `src/renderer/skia/equation_conv.rs:443` | `EQ_FONT_FAMILY` split fallback chain (수식 폰트) |

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

- 환경: GHA `macos-latest` (= `macos-15` 비대화형, ARM64), rhwp `62a458aa` (CI 검증 시점, 이후 refactor 로 호출 사이트 4곳 확장)
- 호출: `samples/aift.hwp` + `render_raster_with_options(page=0)` → 30분+ hang
- 대조: 같은 runner 의 `rhwp export-svg` 6초 / 개발자 desktop (HWP 폰트 설치) 53ms

trigger = AND(PNG raster path, HWP 명시 폰트 시스템 부재, `fontd` 미기동). macOS 13–16 / 26 모두 동일 조합이면 영향 가능 (직접 검증은 15.7.4).

## 제안 — 시스템 폰트 사전 필터링

`SkiaLayerRenderer` 생성 시 `font_mgr.family_names()` 를 `HashSet` 으로 캐시하고, 호출부에서 멤버십 체크로 missing family 는 `match_family_style` 호출 자체를 skip:

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

// text_replay.rs:107 / renderer.rs:687 등 fallback chain 루프 공통 패턴
for family in &families {
    if !self.system_families.contains(AsRef::<str>::as_ref(family)) {
        continue;
    }
    if let Some(tf) = self.font_mgr.match_family_style(family, font_style) {
        push(&mut chain, &mut seen, tf);
    }
}
```

`family_names()` 가 `CTFontManagerCopyAvailableFontFamilyNames` 호출이라 자체적으로 downloadable lookup 안 함 (실측 hang 해소로 후행 검증). 비고: `CTFontManagerSetAutoActivationSetting(null, kCTFontManagerAutoActivationDisabled)` 도 시도했으나 `libFontRegistryUI` lookup 까지 끄지 못해 같은 hang 실측.

### 사이트별 특이사항

- **`text_replay.rs:648` (단발 `"DejaVu Sans"` 호출)** — fallback 루프 자체가 없어 사전 멤버십 체크로 `None` 처리하는 형태 필요:
  ```rust
  let primary = if self.system_families.contains("DejaVu Sans") {
      self.font_mgr.match_family_style("DejaVu Sans", FontStyle::normal())
  } else {
      None
  };
  let mut font = primary
      .or_else(|| self.font_mgr.legacy_make_typeface(None::<&str>, FontStyle::normal()))
      ...
  ```
- **`equation_conv.rs:443` (free function)** — `SkiaLayerRenderer` 인스턴스 캐시를 어떻게 전달할지 결정 필요 (인자 추가 / 모듈 정적 `OnceCell` / 별도 helper).

## 검증 (CI 검증은 `62a458aa` 시점 단일 사이트 patch 기준)

| 상태 | 결과 | CI run |
|---|---|---|
| baseline (patch 없음) | 30분 hang | [#25646433838](https://github.com/DanMeon/rhwp-python/actions/runs/25646433838) |
| `SetAutoActivationSetting` 시도 | hang 재현 | [#25649592697](https://github.com/DanMeon/rhwp-python/actions/runs/25649592697) |
| 사전 필터링 적용 (text replay fallback chain 1곳) | `1 passed in 0.43s` / `592 passed in 51.25s` | [#25650400186](https://github.com/DanMeon/rhwp-python/actions/runs/25650400186) |

SVG path / custom typeface 루프 regression 없음. cost: 생성 시 `family_names()` 1회 (수십 ms), 이후 HashSet O(1). 코드 약 10줄. 실효는 CI / headless 환경의 hang 해소 한 가지 — interactive desktop 은 `fontd` 응답이 빨라 perf 차이 사실상 없음, 다른 OS 도 영향 없음.

위 CI 검증 시점에는 사이트가 한 곳이라 한 곳만 패치해도 PNG 테스트가 통과했으나, PR #769 이후 네 곳 모두 동일 패턴으로 보강해야 같은 보장이 성립합니다.
