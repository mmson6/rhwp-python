use std::cell::OnceCell;

use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyType};

use crate::errors::{parse_error_to_py, ParseError};
use crate::ir;

// ^ unsendable: DocumentCore 내부 RefCell 필드로 !Sync — 다른 스레드 접근 시 런타임 패닉 방어
// ^ name = "_Document": underscore prefix 는 "Rust thin core" 임을 명시. 사용자-대면 심볼
//   `rhwp.Document` 는 Python wrapper 클래스가 제공하며 이 타입을 _inner 로 감싼다
#[pyclass(name = "_Document", module = "rhwp._rhwp", unsendable)]
pub struct PyDocument {
    pub(crate) inner: rhwp::document_core::DocumentCore,
    // ^ 생성자에 전달된 파일 경로 — IR `DocumentSource.uri` 로 전파. RAG 응답 역추적 경로.
    source_uri: Option<String>,
    // ^ 첫 to_ir() 호출 시 1회 구성, 이후 재사용. unsendable 단일-스레드 보장 덕에 lock 불필요
    ir_cache: OnceCell<Py<PyAny>>,
}

fn load_document(path: String) -> Result<rhwp::document_core::DocumentCore, ParseError> {
    let bytes = std::fs::read(&path).map_err(ParseError::Io)?;
    rhwp::document_core::DocumentCore::from_bytes(&bytes)
        .map_err(|e| ParseError::Parse(format!("{e:?}")))
}

#[pymethods]
impl PyDocument {
    #[new]
    fn new(py: Python<'_>, path: &str) -> PyResult<Self> {
        // ^ py.detach 로 파일 I/O + 파싱 동안 GIL 해제 (DocumentCore 는 클로저 내부에서만 생성)
        let path_owned = path.to_owned();
        let source_uri = path_owned.clone();
        let doc = py
            .detach(move || load_document(path_owned))
            .map_err(parse_error_to_py)?;
        Ok(PyDocument {
            inner: doc,
            source_uri: Some(source_uri),
            ir_cache: OnceCell::new(),
        })
    }

    /// 메모리 bytes 로부터 Document 구성 — aparse 경로의 async 파일 I/O 용.
    ///
    /// ``source_uri`` 는 파일 경로·URL·custom 식별자 중 호출자가 선택 (기본 None).
    /// 파싱은 GIL 해제 구간에서 실행 (`py.detach`) — 다른 async task 와 병렬.
    #[classmethod]
    #[pyo3(signature = (data, *, source_uri = None))]
    fn from_bytes(
        cls: &Bound<'_, PyType>,
        data: Vec<u8>,
        source_uri: Option<String>,
    ) -> PyResult<Self> {
        let py = cls.py();
        let doc = py
            .detach(move || rhwp::document_core::DocumentCore::from_bytes(&data))
            .map_err(|e| parse_error_to_py(ParseError::Parse(format!("{e:?}"))))?;
        Ok(PyDocument {
            inner: doc,
            source_uri,
            ir_cache: OnceCell::new(),
        })
    }

    #[getter]
    fn source_uri(&self) -> Option<&str> {
        // ^ IR 을 만들지 않고도 출처 확인 가능 — 관찰성·디버깅용. to_ir() 후의 ir.source.uri 와 동일 값
        self.source_uri.as_deref()
    }

    #[getter]
    fn section_count(&self) -> usize {
        self.inner.document().sections.len()
    }

    #[getter]
    fn paragraph_count(&self) -> usize {
        self.inner
            .document()
            .sections
            .iter()
            .map(|s| s.paragraphs.len())
            .sum()
    }

    #[getter]
    fn page_count(&self) -> u32 {
        self.inner.page_count()
    }

    fn extract_text(&self) -> String {
        self.inner
            .document()
            .sections
            .iter()
            .flat_map(|s| s.paragraphs.iter())
            .map(|p| p.text.as_str())
            .filter(|t| !t.is_empty())
            .collect::<Vec<_>>()
            .join("\n")
    }

    fn paragraphs(&self) -> Vec<String> {
        self.inner
            .document()
            .sections
            .iter()
            .flat_map(|s| s.paragraphs.iter())
            .map(|p| p.text.clone())
            .collect()
    }

    fn render_svg(&self, page: u32) -> PyResult<String> {
        self.inner
            .render_page_svg_native(page)
            .map_err(|e| PyValueError::new_err(format!("render page {page} failed: {e:?}")))
    }

    fn render_all_svg(&self) -> PyResult<Vec<String>> {
        self.render_all_svg_internal()
    }

    #[pyo3(signature = (output_dir, prefix=None))]
    fn export_svg(&self, output_dir: &str, prefix: Option<&str>) -> PyResult<Vec<String>> {
        let out_dir = std::path::Path::new(output_dir);
        std::fs::create_dir_all(out_dir).map_err(|e| PyIOError::new_err(e.to_string()))?;

        let page_count = self.inner.page_count();
        let stem = prefix.unwrap_or("page");
        let mut written = Vec::with_capacity(page_count as usize);
        for page in 0..page_count {
            let svg = self
                .inner
                .render_page_svg_native(page)
                .map_err(|e| PyValueError::new_err(format!("render page {page} failed: {e:?}")))?;
            let filename = if page_count == 1 {
                format!("{stem}.svg")
            } else {
                format!("{stem}_{:03}.svg", page + 1)
            };
            let path = out_dir.join(&filename);
            std::fs::write(&path, &svg).map_err(|e| PyIOError::new_err(e.to_string()))?;
            written.push(path.to_string_lossy().into_owned());
        }
        Ok(written)
    }

    fn render_pdf<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        // ^ SVG 렌더링은 GIL 유지 (&self.inner 필요). PDF 변환만 py.detach 로 GIL 해제 —
        //   소유권 있는 Vec<String> 전달로 !Sync/!Send 경계 회피 (가이드 §12.3)
        let svgs = self.render_all_svg_internal()?;
        let bytes = py
            .detach(move || rhwp::renderer::pdf::svgs_to_pdf(&svgs))
            .map_err(|e| PyValueError::new_err(format!("PDF conversion failed: {e}")))?;
        Ok(PyBytes::new(py, &bytes))
    }

    fn export_pdf(&self, py: Python<'_>, output_path: &str) -> PyResult<usize> {
        let svgs = self.render_all_svg_internal()?;
        let output_path = output_path.to_owned();
        py.detach(move || -> PyResult<usize> {
            let bytes = rhwp::renderer::pdf::svgs_to_pdf(&svgs)
                .map_err(|e| PyValueError::new_err(format!("PDF conversion failed: {e}")))?;
            std::fs::write(&output_path, &bytes).map_err(|e| PyIOError::new_err(e.to_string()))?;
            Ok(bytes.len())
        })
    }

    /// 특정 페이지를 PNG bytes 로 렌더링한다 (상류 native-skia raster).
    ///
    /// `scale` / `dpi` / `max_pixels` 는 RasterRenderOptions 의 동일 필드로 wire-through.
    /// 미지정 시 상류 default (`scale=1.0` / `dpi=None` / `max_pixels=67_108_864` ≈ 8192×8192).
    /// 픽셀 한도 위반 시 상류 메시지 그대로 ValueError (예: "raster pixel count out of range: ...").
    #[pyo3(signature = (page, *, scale=None, dpi=None, max_pixels=None))]
    fn render_png<'py>(
        &self,
        py: Python<'py>,
        page: u32,
        scale: Option<f64>,
        dpi: Option<f64>,
        max_pixels: Option<u64>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let bytes = self.render_png_internal(py, page, scale, dpi, max_pixels)?;
        Ok(PyBytes::new(py, &bytes))
    }

    fn render_all_png<'py>(&self, py: Python<'py>) -> PyResult<Vec<Bound<'py, PyBytes>>> {
        let page_count = self.inner.page_count();
        let mut out = Vec::with_capacity(page_count as usize);
        for page in 0..page_count {
            let bytes = self.render_png_internal(py, page, None, None, None)?;
            out.push(PyBytes::new(py, &bytes));
        }
        Ok(out)
    }

    #[pyo3(signature = (output_dir, *, prefix=None))]
    fn export_png(
        &self,
        py: Python<'_>,
        output_dir: &str,
        prefix: Option<&str>,
    ) -> PyResult<Vec<String>> {
        let out_dir = std::path::Path::new(output_dir);
        std::fs::create_dir_all(out_dir).map_err(|e| PyIOError::new_err(e.to_string()))?;

        let page_count = self.inner.page_count();
        let stem = prefix.unwrap_or("page");
        let mut written = Vec::with_capacity(page_count as usize);
        for page in 0..page_count {
            let bytes = self.render_png_internal(py, page, None, None, None)?;
            let filename = if page_count == 1 {
                format!("{stem}.png")
            } else {
                format!("{stem}_{:03}.png", page + 1)
            };
            let path = out_dir.join(&filename);
            std::fs::write(&path, &bytes).map_err(|e| PyIOError::new_err(e.to_string()))?;
            written.push(path.to_string_lossy().into_owned());
        }
        Ok(written)
    }

    /// 문서를 Document IR (Pydantic `HwpDocument`) 로 변환하여 반환한다.
    ///
    /// 첫 호출 시 문서 트리를 순회하며 IR 을 구성하고 결과를 인스턴스에 캐시한다.
    /// 재호출은 캐시된 객체를 반환. IR 모델은 `frozen=True` 이므로 반환 객체 수정
    /// 시 Pydantic `ValidationError` 가 발생한다. 독립 사본이 필요하면
    /// `ir.model_copy(deep=True)` 를 사용한다.
    fn to_ir(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        // ^ OnceCell::get_or_try_init 은 stable 에서 사용 불가 — 수동 get/set.
        //   unsendable 덕에 get→set 사이 경쟁 없음 (expect 패닉 불가능)
        if let Some(cached) = self.ir_cache.get() {
            return Ok(cached.clone_ref(py));
        }
        // ^ Rust 는 raw 평탄 구조만 출고. 도메인 변환 (HTML/role/Pydantic 합성)
        //   은 rhwp.ir._mapper 가 담당 — IR 진화 시 maturin rebuild 회피.
        //   GIL 해제 불가: self.inner (DocumentCore) 가 RefCell 캐시로 !Sync —
        //   closure 가 &self 를 캡처하면 py.detach 의 Ungil 바운드 불만족.
        //   parse 단계 (from_bytes — owned bytes) 와 render_pdf/export_pdf
        //   (owned svgs) 만 GIL 해제 가능.
        let raw = ir::build_raw_document(self.inner.document(), self.source_uri.as_deref());
        let mapper = py.import("rhwp.ir._mapper")?;
        let ir = mapper.call_method1("build_hwp_document", (raw,))?.unbind();
        self.ir_cache
            .set(ir)
            .expect("ir_cache was empty just above");
        Ok(self
            .ir_cache
            .get()
            .expect("ir_cache was just set")
            .clone_ref(py))
    }

    /// `bin_data_id` (1-based) 에 해당하는 이미지 raw bytes 를 반환.
    ///
    /// `Document.bytes_for_image(picture)` Python 헬퍼가 ``picture.image.uri`` 의
    /// ``bin://`` 스킴을 파싱한 결과를 본 메서드에 위임한다. 상류 BinData 가
    /// Embedding 타입이 아니거나 (Link/Storage) `bin_data_content` 에 누락된
    /// 경우 None — Python wrapper 가 ValueError 로 변환.
    ///
    /// 혼합 (Link + Embedding) 문서에서는 상류 `bin_data_content` 가 Embedding
    /// 만 추려 더 짧으므로 잘못된 entry 를 반환할 수 있다 — 상류 renderer 도
    /// 같은 가정을 공유하므로 SVG/PDF 렌더링과 동일한 lookup 결과 (상류 패리티).
    fn bytes_for_image_id<'py>(
        &self,
        py: Python<'py>,
        bin_data_id: u16,
    ) -> PyResult<Option<Bound<'py, PyBytes>>> {
        if bin_data_id == 0 {
            return Ok(None);
        }
        Ok(self
            .inner
            .get_bin_data((bin_data_id - 1) as usize)
            .map(|bytes| PyBytes::new(py, bytes)))
    }

    /// IR 을 JSON 문자열로 반환한다. `to_ir()` 캐시를 공유한다.
    ///
    /// `indent` 를 주면 Pydantic `model_dump_json(indent=...)` 으로 들여쓰기.
    #[pyo3(signature = (*, indent = None))]
    fn to_ir_json(&self, py: Python<'_>, indent: Option<usize>) -> PyResult<String> {
        let ir_obj = self.to_ir(py)?;
        let bound = ir_obj.bind(py);
        let kwargs = PyDict::new(py);
        if let Some(n) = indent {
            kwargs.set_item("indent", n)?;
        }
        let result = bound.call_method("model_dump_json", (), Some(&kwargs))?;
        result.extract::<String>()
    }

    fn __repr__(&self) -> String {
        format!(
            "Document(sections={}, paragraphs={}, pages={})",
            self.section_count(),
            self.paragraph_count(),
            self.page_count()
        )
    }
}

// * Python 에 노출되지 않는 내부 헬퍼
impl PyDocument {
    fn render_all_svg_internal(&self) -> PyResult<Vec<String>> {
        let page_count = self.inner.page_count();
        (0..page_count)
            .map(|p| {
                self.inner
                    .render_page_svg_native(p)
                    .map_err(|e| PyValueError::new_err(format!("render page {p} failed: {e:?}")))
            })
            .collect()
    }

    fn render_png_internal(
        &self,
        py: Python<'_>,
        page: u32,
        scale: Option<f64>,
        dpi: Option<f64>,
        max_pixels: Option<u64>,
    ) -> PyResult<Vec<u8>> {
        // ^ layer tree 빌드는 GIL 유지 (DocumentCore 의 RefCell 캐시 접근 — !Sync).
        //   결과 PageLayerTree 는 owned values 만 포함 → py.detach 클로저로 이동 가능.
        let layer_tree = self
            .inner
            .build_page_layer_tree(page)
            .map_err(|e| PyValueError::new_err(format!("render page {page} failed: {e:?}")))?;
        let mut options = rhwp::renderer::layer_renderer::RasterRenderOptions::default();
        if let Some(s) = scale {
            options.scale = s;
        }
        if let Some(d) = dpi {
            options.dpi = Some(d);
        }
        if let Some(mp) = max_pixels {
            options.max_pixels = mp;
        }
        py.detach(move || {
            use rhwp::renderer::layer_renderer::LayerRasterRenderer;
            rhwp::renderer::skia::SkiaLayerRenderer::new()
                .render_png_with_options(&layer_tree, options)
                .map_err(|e| PyValueError::new_err(format!("render page {page} failed: {e:?}")))
        })
    }
}

