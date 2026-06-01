# 099 PSD-like V3: V1 + Deki YOLO Candidate Enhancement

## Status

Active.

## Summary

V2 is paused. V3 is an isolated experiment that keeps the V1 PSD-like visual fidelity baseline and adds Deki YOLO only as an extra candidate source. OCR remains the only text authority. YOLO `Text` is diagnostic only and must not create or mutate `TextLayer`.

The goal is not to rebuild Codia or create a semantic UI tree. The goal is to reduce avoidable raster/inpaint failures around UI controls by turning reliable YOLO `View` boxes into vector `ShapeLayer` backgrounds, while using YOLO `ImageView` boxes to improve raster candidates for icons, avatars, thumbnails, photos, and illustration-like regions.

## Scope

V3 adds new experiment files only:

- `services/backend-python/tools/deki_yolo_export.py`
- `services/backend-python/tools/psd_like_v3_deki_yolo_experiment.py`
- `services/backend-python/tools/psd_like_v3_batch_eval.py`
- `services/backend-python/tests/test_psd_like_v3_deki_yolo.py`

V1 remains the A/B baseline and must not be edited. V2 changes are stashed and must not be mixed into V3 commits.

## Runtime Contract

Deki YOLO produces an external JSON artifact:

```json
{
  "version": "deki_yolo_candidates.v1",
  "modelPath": "/Volumes/WorkDrive/Models/deki-yolo.pt",
  "sourceImage": "...",
  "canvas": {"width": 941, "height": 1672},
  "candidates": [
    {
      "id": "yolo_0001",
      "classId": 1,
      "className": "ImageView",
      "bbox": {"x": 315, "y": 302, "width": 68, "height": 66},
      "confidence": 0.9665
    }
  ]
}
```

V3 reads the artifact with:

```bash
uv run python tools/psd_like_v3_deki_yolo_experiment.py \
  --image <png> \
  --ocr <ocr_blocks.v1.json> \
  --deki-json <deki_yolo_candidates.v1.json> \
  --out <out_dir>
```

Output artifacts:

- `deki_yolo_candidates.v1.json`
- `deki_yolo_overlay.png`
- `layer_stack.v3.json`
- `draft_runtime.v3.dsl.v1_0.json`
- `preview.v3.html`
- `draft_preview.v3.png`
- `ownership_report.v3.json`
- `diagnostics.v3.md`
- `assets/*.png`

## Authority Rules

OCR owns text content and text bbox. YOLO `Text` is written only to diagnostics.

YOLO `View` can become a shape candidate only when deterministic gates pass:

- contains one or two OCR blocks with strong containment;
- is not full-page backing or a large hero/background region;
- has stable non-text fill and low texture;
- has button/tab/input/small-card geometry;
- emits `ShapeLayer` only, with no raster crop and no inpainting.

YOLO `ImageView` can become a raster candidate only when deterministic gates pass:

- confidence and area pass thresholds;
- it does not materially cover OCR text;
- it is not full-page or huge background backing;
- it is merged with V1 raster candidates through NMS instead of duplicated.

Layer order is fixed:

```text
ShapeLayer: 1000-1999
RasterLayer: 2000-2999
TextLayer: 3000+
```

## Anti-Specialization

Do not add rules tied to sample name, path, visible text, brand, fixed coordinates, fixed bboxes, fixed screen size, Codia golden JSON, or one screenshot structure. Thresholds must be geometric or photometric and validated on batch output.

## Validation

Unit tests must cover:

- YOLO artifact normalization and unknown class diagnostics;
- YOLO `Text` does not create `TextLayer`;
- YOLO `View` plus contained OCR creates `ShapeLayer + TextLayer`, with no button raster asset;
- YOLO `ImageView` creates a raster asset when it avoids OCR text;
- YOLO `ImageView` covering OCR is suppressed;
- V1 raster and YOLO raster overlap merges instead of duplicating;
- text z is higher than raster and shape z.

Required local checks:

```bash
cd services/backend-python
uv run pytest -q
python -m py_compile tools/psd_like_v3_deki_yolo_experiment.py tools/psd_like_v3_batch_eval.py app/*.py
uv run python tools/psd_like_v3_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v3_deki_yolo_ab_eval \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --deki-model /Volumes/WorkDrive/Models/deki-yolo.pt
git diff --check
git status --short --branch
```

Acceptance gates:

- V3 DSL valid for all batch cases.
- Missing asset count is `0`.
- Visible full-page backing is `0`.
- TextLayer count equals OCR block count.
- `rawTextOverlapRaster <= V1`.
- `rasterTextKnockoutCount < V1`.
- Average `visualMae` is not meaningfully worse than V1.
- Button-like YOLO `View` candidates reduce button raster/inpainting cases without suppressing real photos.
