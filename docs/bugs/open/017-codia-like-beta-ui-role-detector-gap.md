# 017 Codia-like Beta UI Role Detector Gap

- 状态：open
- 创建日期：2026-05-30
- 所属主线：Go Codia-like compiler rebuild
- 当前上线判断：不阻塞 Beta / 内部试用上线，但阻塞 Codia 1:1 质量目标
- 关联计划：[089 Go Codia-like Compiler Rebuild](../../plans/archive/deferred/089-go-codia-like-compiler-rebuild.md)
- 当前 smoke gate：`services/backend-go/tools/codia_smoke_2img.sh`

## Executive Summary

当前 Go Codia-like compiler 已经具备可用的第一版主链：

```text
PNG + OCR
-> Go M29.0 physical evidence
-> evidence tokens
-> Codia leaf IR
-> control synthesis
-> role-aware tree builder
-> Figma-like emitter
-> Codia diff / audit
```

它可以作为 best-effort / Beta reconstruction 上线试用，但不能宣称 Codia 1:1。当前主要质量瓶颈不是 tree builder、XY-cut、children order 或 Button permission，而是上游缺少 learned UI role detector / role-aware evidence refinement。M29.0 是 pixel evidence provider，不是 Codia-level UI component detector。

最新两图 smoke 基线：

```text
sample generated matched extra missed edgeP edgeR topAction
t018   149       95      54    51     0.419 0.428 m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView:13
t022   106       92      14    28     0.619 0.546 m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView:13
```

当前最高优先级瓶颈：

```text
m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView
```

这意味着：Codia golden 中存在 ImageView 节点，但当前 M29 physical evidence / evidence token / Codia leaf bridge 没有产出可匹配的 source leaf candidate。后续修复不能先去改 `internal/codia/tree` 猜节点，也不能回到 `m29visualtree` / `xycut` 调阈值；需要补上更强的 UI role 感知来源，短期可以通过外部 detector probe 或局部 source refinement，长期应接入训练好的 UI role detector。

## Current User-Facing Contract

上线时只能承诺：

```text
Beta screenshot-to-Figma reconstruction.
The output is editable and structured on a best-effort basis.
Small icons, fine UI glyphs, internal image crops, and exact Codia-like hierarchy may be incomplete.
```

不能承诺：

```text
Codia 1:1
所有 ImageView 都能召回
所有小图标 / 光标 / 状态栏 glyph / 键盘元素都能变成独立节点
所有 Button / EditText / Background ownership 都完全匹配 Codia
```

这个限制必须在产品和运维语境里叫做 Beta 质量限制，而不是隐藏成“偶发 bug”。如果上线后用户反馈“图标漏了、图片切不出来、结构不够像 Codia”，应先读本文恢复当前背景。

## Source Truth

本 bug 的事实来源只包括：

```text
raw Codia/Figma canvas JSON
paired source PNG
Go M29 physical evidence artifacts
Codia leaf/control/tree IR artifacts
codia_structure_diff.v1.json
codia_failure_audit.v1.json
```

当前 golden samples：

```text
docs/reference/codia-samples/tencent-comic-018.canvas.json
docs/reference/codia-samples/tencent-comic-022.canvas.json
docs/reference/codia-samples/lizhi-011.canvas.json
docs/reference/codia-samples/xianyu.canvas.json
docs/reference/codia-samples/images/腾讯动漫_018_1440.png
docs/reference/codia-samples/images/腾讯动漫_022_1440.png
docs/reference/codia-samples/images/荔枝_011_1440.png
docs/reference/codia-samples/images/闲鱼.png
```

Do not use archived prose or old reverse-engineering notes as implementation truth. They are historical background only. Raw `.canvas.json` files remain golden truth because they are source artifacts.

## Current Baseline

Command:

```bash
bash services/backend-go/tools/codia_smoke_2img.sh
```

Latest result on 2026-05-30:

```text
sample generated matched extra missed edgeP edgeR topAction
t018   149       95      54    51     0.419 0.428 m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView:13
t022   106       92      14    28     0.619 0.546 m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView:13
artifacts: /tmp/codia_smoke_2img
```

Artifact locations:

```text
/tmp/codia_smoke_2img/compile-t018/
/tmp/codia_smoke_2img/compile-t022/
```

Important files:

```text
extract/m29_physical_evidence.v1.json
tokens/evidence_tokens.v1.json
leaves/codia_leaf_ir.v1.json
controls/codia_control_stage.v1.json
tree/codia_tree_ir.v1.json
diff/codia_structure_diff.v1.json
audit/codia_failure_audit.v1.json
audit/codia_failure_audit_report.md
```

## Reproduction

Run the smoke gate:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
bash services/backend-go/tools/codia_smoke_2img.sh
```

Inspect current top action:

```bash
python3 - <<'PY'
import json
from pathlib import Path

for sample in ["t018", "t022"]:
    p = Path(f"/tmp/codia_smoke_2img/compile-{sample}/audit/codia_failure_audit.v1.json")
    data = json.loads(p.read_text())
    print(sample, data["summary"].get("topAction"))
    for item in data.get("rankedActions", [])[:5]:
        print(" ", item.get("owningLayer"), item.get("diagnosis"), item.get("role"), item.get("count"))
PY
```

Inspect missed ImageView nodes:

```bash
python3 - <<'PY'
import json
from pathlib import Path

for sample in ["t018", "t022"]:
    diff = json.loads(Path(f"/tmp/codia_smoke_2img/compile-{sample}/diff/codia_structure_diff.v1.json").read_text())
    print("\\n==", sample, diff["summary"]["roleMetrics"].get("ImageView"))
    for node in diff.get("goldenNodes", []):
        if node.get("role") == "ImageView" and node.get("verdict") == "missed":
            print("MISS", node.get("id"), node.get("bbox"), "bestIoU", round(node.get("bestIoU", 0), 3), "best", node.get("bestId"), node.get("bestBBox"), node.get("bestEvidenceKind"))
PY
```

Inspect Codia tiny ImageView evidence in the Xianyu golden:

```bash
cd services/backend-go
go run ./cmd/codiaanalyze \
  -input /Users/luhui/Downloads/figma/json/闲鱼.json \
  -out /tmp/codia_xianyu_analysis

python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/tmp/codia_xianyu_analysis/codia_canvas_analysis.v1.json").read_text())
items = []
for node in data["nodes"]:
    if node.get("role") != "ImageView":
        continue
    b = node["bbox"]
    items.append((b["width"] * b["height"], b["width"], b["height"], node["schemaId"], b, node["path"]))
items.sort()
for item in items[:12]:
    print(item)
PY
```

Known tiny ImageView examples from the Xianyu raw canvas:

```text
ImageView_17_646_86   bbox 21,649,4,7
ImageView_37_850_68   bbox 41,853,3,15
ImageView_347_30_126  bbox 351,35,24,5
```

These examples are not local hardcoding targets. They show why a pure connected-component / XY-cut / threshold stack is the wrong long-term perception authority.

## Impact

User-visible symptoms:

```text
small icons or glyphs are missing
status-bar / keyboard / cursor-like tiny visuals may be absent
some internal cover/thumb ImageViews remain part of a large raster
some card or image crops are too large or shifted
some backgrounds remain fragments or extras
parent-child structure is usable but not Codia-like 1:1
```

Measured impact in current smoke:

```text
t018: topAction upstream_leaf_missing ImageView:13
t022: topAction upstream_leaf_missing ImageView:13
```

Current t022 ImageView precision is already relatively high after recent source-evidence work; therefore broad small-image filtering is the wrong fix. The missing class is not “all small images are noise.” Raw Codia output includes legitimate tiny ImageViews.

## Root Cause

M29.0 currently produces physical evidence:

```text
text regions
raster regions
symbol clusters
background/control surface candidates
relations and crop evidence
```

That evidence is useful, but it is not the same as Codia's emitted UI role layer. Codia output shows role-aware nodes:

```text
TextView
ImageView
Button
EditText
Background
bg_Button
bg_EditText
ViewGroup
ListView
StatusBar
ActionBar
BottomNavigation
```

The current gap is the missing bridge:

```text
low-level physical evidence
-> role-aware UI component candidates
-> ownership graph
-> Codia-like tree emitter
```

Current code already has pieces of the last two steps:

```text
internal/codia/leaf
internal/codia/control
internal/codia/tree
internal/codia/emitter
internal/codia/diff
internal/codia/audit
```

The missing strong layer is a learned or externally provided UI role detector / role-aware evidence refinement layer before leaf/control/tree construction.

## Why This Does Not Block Beta Launch

The system is already useful for Beta because it can emit a structured, editable, inspectable best-effort tree with diagnostics:

```text
TextView OCR leaves
ImageView / Background crops when M29 evidence exposes them
Button / EditText synthesis from source background evidence
ActionBar / StatusBar / BottomNavigation / ListView / ViewGroup candidates
Figma-like emission
role-aware diff and audit artifacts
```

The remaining gap affects quality ceiling, not basic pipeline viability. It should block “Codia 1:1” claims, not block an early controlled release.

Beta release condition:

```text
the smoke gate must pass current non-regression thresholds;
diagnostic artifacts must be retained;
known limitations must remain documented;
user feedback / bad cases must be stored for future detector data.
```

## Do Not Fix This By

Do not use these approaches:

```text
do not tune m29visualtree / xycut thresholds as the main solution
do not create ImageView/Button/EditText from text bbox alone
do not filter all small image/icon candidates globally
do not fabricate missing leaves in internal/codia/tree
do not read golden Codia JSON during generation
do not key logic to sample name, file path, visible text, brand, theme, fixed coordinate, fixed bbox, fixed screen size, or task id
do not patch Renderer or Figma plugin to invent source ownership
do not let materializer or emitter decide semantic role
```

Why:

```text
XY-cut and geometry thresholds operate after information has already been lost.
Tree builder can organize candidates but cannot recover missing source leaves.
Text bbox proves text, not button background or image glyph.
Small visual nodes are sometimes real Codia ImageViews, not noise.
Golden JSON is only an eval target, not runtime input.
```

## Correct Long-Term Path

The long-term architecture should be:

```text
PNG
-> OCR / text evidence
-> UI role detector
-> M29 physical evidence / pixel source checks
-> role-aware candidate merge
-> ownership graph
-> Codia tree IR
-> Figma-like emitter
-> diff / audit / QA
```

The model should answer:

```text
what UI-role candidates are visible here?
```

The ownership graph should answer:

```text
who owns whom?
which Background becomes bg_Button or bg_EditText?
which ImageView belongs inside a Button?
which nodes belong to StatusBar, ActionBar, BottomNavigation, ListView, or ViewGroup?
```

The emitter should answer:

```text
how to serialize the decided role tree into Codia-like Figma nodes?
```

This is the intended split:

```text
learned perception + deterministic structure compiler
```

Do not build a model that directly emits full Codia tree JSON as the first production path. That is harder to debug, harder to constrain, and harder to validate. The first learned component should emit normalized detector candidates only.

## Future Detector Contract

Report-only detector candidate file:

```text
ui_detector_candidates.v1.json
ui_detector_report.md
ui_detector_overlay.png
```

Candidate shape:

```json
{
  "schemaName": "UIDetectorCandidates",
  "version": "1.0",
  "provider": {
    "name": "yolov8n-ui-role-detector",
    "modelVersion": "v0"
  },
  "image": {
    "width": 480,
    "height": 1039,
    "sourcePath": "input.png"
  },
  "candidates": [
    {
      "id": "det_000001",
      "sourceRole": "ImageView",
      "mappedRole": "ImageView",
      "bbox": {"x": 21, "y": 649, "width": 4, "height": 7},
      "confidence": 0.82,
      "source": "detector",
      "tile": {"x": 0, "y": 512, "width": 512, "height": 512}
    }
  ]
}
```

First useful detector roles:

```text
ImageView
Background
Button
EditText
StatusBar
ActionBar
BottomNavigation
```

Do not train or directly emit:

```text
bg_Button      derived by ownership graph
bg_EditText    derived by ownership graph
root           compiler-created
TextView       OCR remains primary in v0
residual ViewGroup/ListView as a broad catch-all in v0
```

`ListView` may be added later when enough data exists. Broad `ViewGroup` should be treated carefully because it is often a structural ownership result rather than a clean visual object.

## Future Dataset Plan

Training data sources, in priority order:

```text
P0: Codia golden JSON + paired PNG
    Best target-domain labels. Use primarily for validation, fine-tune, and calibration.

P1: Android screenshot + uiautomator / accessibility dump
    Best scalable source for role + bbox + hierarchy.

P2: Synthetic UI
    Useful for tiny icons, status bar, keyboard, cursor, tab indicator, and repeated controls.

P3: Public UI datasets or external detectors
    Useful for pretraining/probing, not source truth for Codia.
```

Required dataset builder:

```text
raw Codia canvas JSON + PNG
-> normalized labels
-> COCO labels
-> YOLO labels
-> overlay QA images
-> dataset_report.md
-> train/val/test manifests
```

Required label fields:

```json
{
  "source": "xianyu",
  "imagePath": "images/闲鱼.png",
  "nodeId": "ImageView_17_646_86",
  "role": "ImageView",
  "bbox": [21, 649, 4, 7],
  "parentNodeId": "ListView_0_621_73",
  "path": "/1/1/0/5/0",
  "figmaType": "ROUNDED_RECTANGLE",
  "visibleName": "Image"
}
```

Tiny UI targets require crop/tile training data. Full screenshot training alone will shrink 3px-7px targets too much.

Dataset builder must generate:

```text
full screenshot samples
local crop/tile samples around tiny and small targets
overlays for human QA
class distribution
bbox size distribution
source distribution
invalid / out-of-bounds / duplicate label report
```

## Future Training Plan

Local Mac mini M4 / 16GB can be used for:

```text
dataset builder
overlay QA
small YOLOv8n smoke training
existing detector probe
offline inference and Codia diff
```

It is not the right place for:

```text
large-scale training
large model training
high-resolution 1280+ large-batch training
multi-model sweep
```

First local smoke training shape:

```bash
yolo detect train \
  model=yolov8n.pt \
  data=/path/to/codia-ui-detector/data.yaml \
  imgsz=640 \
  epochs=20 \
  batch=4 \
  device=mps \
  workers=2 \
  cache=False
```

If stable:

```text
imgsz=960 batch=2
imgsz=1024 batch=1
```

Deployment export happens after training:

```bash
yolo export \
  model=runs/detect/train/weights/best.pt \
  format=onnx \
  half=True \
  imgsz=1024
```

Do not train from the FP16 / quantized deployment artifact. Train from a `.pt` checkpoint; export FP16/ONNX only after validation.

## External Detector Probe Before Training

Before training a custom detector, run existing models as offline probes:

```text
Salesforce/GPA-GUI-Detector
Microsoft OmniParser v2 icon_detect
android_ui_detection_yolov8
uitag-yolo11s-ui-detect-v1
deki / UIED-like mobile screen parsers
```

Probe output must use the same detector candidate contract:

```text
ui_detector_candidates.v1.json
ui_detector_overlay.png
ui_detector_eval_report.md
```

Acceptance for adopting an external detector source:

```text
it improves ImageView recall on golden samples;
it does not explode ImageView extras;
it helps Button/EditText/Background candidate quality;
it can be mapped into the role-aware candidate layer without reading golden data;
its license is acceptable for the intended deployment.
```

License note:

```text
some OmniParser / YOLO-derived weights may carry AGPL or other restrictive terms.
Do not put a model into product runtime until the license has been checked.
```

## How To Fix After Detector Exists

When a usable detector or trained model exists, integrate in stages.

### Stage 1: Report-only adapter

Add a detector adapter that writes:

```text
ui_detector_candidates.v1.json
ui_detector_report.md
ui_detector_overlay.png
```

Rules:

```text
no Codia IR changes
no tree builder changes
no materializer changes
no fallback to golden JSON
```

Validation:

```bash
cd services/backend-go
go test ./internal/codia/... ./internal/m29/... ./cmd/codiacompile
bash tools/codia_smoke_2img.sh
```

The smoke output should remain identical unless a separate eval command consumes detector candidates.

### Stage 2: Offline detector eval

Compare detector candidates to golden Codia IR without altering generation:

```text
ImageView precision / recall
tiny ImageView recall
Button / EditText candidate recall
Background candidate recall
bbox IoU distribution
extra candidate rate
```

The eval should identify whether detector failures are:

```text
missing visual candidate
wrong role
bad bbox
duplicate candidate
overbroad region
small target missed
```

### Stage 3: Candidate merge

Introduce a role-aware candidate merge layer:

```text
OCR
M29 physical evidence
detector candidates
-> Codia source candidates
```

Detector candidates can suggest roles, but M29 still provides pixel/crop/source evidence. Low-confidence detector outputs should remain report-only until backed by source evidence or accepted by a specific permission gate.

### Stage 4: Ownership graph

Use deterministic ownership scoring:

```text
Button owns contained TextView/ImageView + matching Background
EditText owns placeholder text/icon + matching Background
Background becomes bg_Button or bg_EditText only after owner assignment
BottomNavigation owns bottom row candidates + local background
ActionBar / StatusBar own top chrome candidates
ListView owns repeated item candidates
ViewGroup owns residual coherent regions
```

Every ownership edge must have:

```text
edge kind
score
reason
source candidate ids
accepted/rejected decision
```

### Stage 5: Tree emitter and smoke gate

Emit final Codia-like tree and rerun:

```bash
bash services/backend-go/tools/codia_smoke_2img.sh
```

Expected improvement before closing this bug:

```text
t018/t022 topAction no longer dominated by upstream_leaf_missing ImageView
ImageView recall improves without large extra explosion
Button precision remains near current 1.0 behavior
Background/control fragments do not regress
parent edge precision/recall improves or remains stable
```

## Closure Criteria

Do not close this bug just because a model exists.

Close only when all of these are true:

```text
1. Detector or role-aware candidate layer is integrated behind an explicit contract.
2. The detector path is report-only first and then permission-gated before generation.
3. `codia_smoke_2img.sh` improves or preserves the current baseline.
4. `upstream_leaf_missing ImageView` is no longer the dominant topAction on t018/t022.
5. Xianyu tiny ImageView-style cases have a documented eval path.
6. No runtime generation reads Codia golden JSON.
7. Docs and code map describe the new detector/candidate contract.
8. Tests cover candidate parsing, candidate merge, ownership use, and no-golden generation.
```

Minimum validation before closure:

```bash
cd services/backend-go
go test ./internal/m29/pipeline ./internal/m29/evidence ./internal/codia/... ./cmd/codiaanalyze ./cmd/codialeaves ./cmd/codiacontrols ./cmd/codiadiff ./cmd/codiacompile ./cmd/codiaaudit

cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
bash services/backend-go/tools/codia_smoke_2img.sh
git diff --check
git status --short --branch
```

## Release Note For Beta

Recommended internal release note:

```text
Codia-like reconstruction is enabled as a Beta quality path. It produces editable role-aware structure and diagnostic artifacts, but small visual elements and exact Codia-like hierarchy are still known weak points. Current tracked quality debt is upstream UI role detection, especially ImageView recall for small icons/glyphs and internal crops. The next quality upgrade is a detector-backed role-aware candidate layer.
```
