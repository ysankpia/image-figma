# 104 PSD-like V1 ONNX Semantic Annotation

## Status

deferred / paused after 86-image probe

This plan is intentionally not active. The experiment is promising, but the current PSD-like V1 baseline should remain frozen while product usability is evaluated. Future work should resume from this document, not from chat history.

Reason for pause:

- PSD-like V1 already has a stable physical ownership baseline.
- The ONNX model is useful for semantic labels, but it must not become bbox, OCR, crop, or ownership authority.
- Directly wiring YOLO classes into DSL generation would risk breaking the current stable V1 output.
- The next immediate product need is to test real editing/import cost, not to start another reconstruction branch.

## Probe Evidence

Model:

```text
/Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx
```

Model classes:

```text
BackgroundImage
Bottom_Navigation
Card
CheckedTextView
Drawer
EditText
Icon
Image
Map
Modal
Multi_Tab
PageIndicator
Spinner
Switch
Text
TextButton
Toolbar
UpperTaskBar
```

Full 86-image probe output:

```text
/Users/luhui/Downloads/psd_like_hybrid_eval_all_onnx
```

Run result:

```text
caseCount: 86
failureCount: 0
elapsedSeconds: 538.875
```

Visual artifacts:

```text
/Users/luhui/Downloads/psd_like_hybrid_eval_all_onnx/hybrid_onnx_focused_contact_sheet.png
/Users/luhui/Downloads/psd_like_hybrid_eval_all_onnx/hybrid_onnx_all_contact_sheet.png
```

Source scratch script:

```text
/Users/luhui/.gemini/antigravity/scratch/hybrid_decomposition_inference.py
```

The scratch script currently:

```text
source image
-> PSD-like V1 deterministic physical proposals
-> ONNX YOLO semantic detections
-> IoU match between V1 proposals and YOLO boxes
-> label overlay image
```

## Conclusion

This direction is valuable, but only as a semantic annotation layer after V1 physical decomposition.

Correct authority order:

```text
V1 OCR / physical proposal / ownership / asset crop / shape fill
> ONNX semantic label
```

The ONNX model can help move from:

```text
editable layers
-> understandable layers
-> groupable/component-ready layers
```

It should not replace V1 or decide final visible layers.

## Future Goal

Create an isolated semantic annotation experiment:

```text
V1 layer_stack.v1.json
+ OCR blocks
+ source image
+ ONNX YOLO detections
-> semantic_annotations.v1.json
-> semantic_overlay.png
-> semantic_summary.md
-> semantic_contact_sheet.png
```

## Proposed Contract

```json
{
  "version": "semantic_annotations.v1",
  "modelPath": "/Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx",
  "sourceImage": "/path/to/source.png",
  "layers": [
    {
      "layerId": "shape_0012",
      "layerType": "shape",
      "semanticRole": "TextButton",
      "yoloClass": "TextButton",
      "yoloConfidence": 0.84,
      "matchIoU": 0.61,
      "matchKind": "iou",
      "reason": "v1_shape_matched_yolo_textbutton"
    }
  ],
  "warnings": []
}
```

Allowed semantic roles should initially be the ONNX class set plus `Unknown`.

## Rules

ONNX may:

```text
annotate V1 layers with semanticRole
provide confidence and class evidence
help layer naming
help grouping/component hints later
```

ONNX must not:

```text
generate new bbox
generate OCR text
generate assets
delete V1 layers
create final DSL nodes
change shape/raster/text ownership
change crop boxes
change z-order
override OCR
```

## Matching Strategy

Do not rely only on IoU. The scratch script uses IoU first, which is useful but insufficient because V1 physical boxes and YOLO semantic boxes often represent different granularity.

Future matcher should combine:

```text
IoU
IoA layer-in-yolo
IoA yolo-in-layer
center distance
size/aspect compatibility
OCR containment
V1 layer type
V1 reason
```

Decision examples:

```text
shape + OCR + yolo TextButton/EditText -> TextButton/EditText annotation
small raster + no OCR + yolo Icon -> Icon annotation
large raster + internal media text + yolo Image/Map/BackgroundImage -> media annotation
surface band + yolo Toolbar/Bottom_Navigation/Multi_Tab -> structural region annotation
low confidence or conflicting matches -> Unknown with warning
```

## Implementation Sketch

Create an isolated tool, not a V1 rewrite:

```text
services/backend-python/tools/psd_like_v1_onnx_semantic_annotation.py
```

Inputs:

```text
--case-dir <V1 case output directory>
--model /Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx
--out <output directory>
```

Batch runner:

```text
services/backend-python/tools/psd_like_v1_onnx_semantic_batch_eval.py
```

Outputs:

```text
semantic_annotations.v1.json
semantic_overlay.png
semantic_summary.md
semantic_contact_sheet.png
```

## Validation Plan

Targeted 10-image probe:

```text
case_0001_0667dd917e
case_0003_0aa4f748a3
case_0017_2982d971d2
case_0034_6e50a36c36
case_0052_a6cbbd0038
case_0068_ca3aaed3a5
case_0071_cd2c7fbe97
case_0073_d923e89039
case_0074_d93a2693f3
case_0081_f01eb628f1
```

Then full 86-image batch.

Metrics:

```text
caseCount
failureCount
annotatedLayerCount
unknownLayerCount
lowConfidenceCount
conflictingMatchCount
role counts by semanticRole
TextButton/EditText recall on accepted V1 control surfaces
Icon annotation count on small rasters
Map/Image annotation count on media rasters
```

Hard gates:

```text
V1 DSL output unchanged
V1 layer count unchanged
V1 asset refs unchanged
OCR text unchanged
86/86 annotation batch does not crash
```

## Anti-Specialization

Do not use:

```text
sample names
file paths
visible text
brand
fixed coordinates
fixed bbox
fixed screen sizes
theme-specific rules
```

Model path can be a CLI argument/default, but production logic must not branch on this dataset or these 86 images.

## Resume Conditions

Resume this plan only after the V1 baseline has been evaluated in a real preview/import workflow, or when component grouping/layer naming becomes the active bottleneck.

The first resumed step should be report-only annotation. Do not write semantic roles into final Draft DSL until the annotation report proves value and a separate plan approves metadata integration.
