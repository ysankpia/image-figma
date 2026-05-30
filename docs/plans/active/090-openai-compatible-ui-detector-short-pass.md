# 090 OpenAI-compatible UI Detector Short Pass

- 状态：active / Go Codia Beta runtime path; detector integration implemented; 2026-05-31 output-quality repair ongoing
- 创建日期：2026-05-30
- 负责人：未指定
- 关联暂停计划：[089 Go Codia-like Compiler Rebuild](../archive/deferred/089-go-codia-like-compiler-rebuild.md)
- 关联质量债：[017 Codia-like Beta UI Role Detector Gap](../../bugs/open/017-codia-like-beta-ui-role-detector-gap.md)

## Goal

把 2026-05-30 的 VLM detector 实验结果固化为 Go Codia-like compiler / Codia Beta 的当前实现计划。

核心目标不是让大模型直接生成 Codia 树，而是建立一个稳定的上游候选层：

```text
source screenshot
-> OpenAI-compatible short-pass UI detector
-> ui_detector_candidates.v1.json
-> detector eval / report-only audit
-> permission-gated merge
-> existing Codia leaf/control/tree/emitter pipeline
```

这条线现在是插件 `Generate Beta` 的 Go 后端路径：`services/backend-go/cmd/codiaserver -> /api/codia-preview -> DSL v0.2 -> renderCodiaRuntimeDesign`。它仍不进入保留的 Python/FastAPI `/api/upload-preview` DSL v0.1 路径；调试 Codia Beta 输出质量时必须从 Go artifacts 和 renderer runtime 入手。

## Why

当前 Go Codia-like compiler 的主要瓶颈已经不是 `xycut`、tree builder、children order 或 Button permission。当前 dominant failure 是：

```text
m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView
```

也就是 Codia golden 里存在的 ImageView、小图标、封面图、右侧 rail 缩略图、卡片内部图块、状态栏/底部导航 glyph，M29 physical evidence / evidence token / Codia leaf bridge 没有稳定产出。tree builder 只能组织已有材料，不能凭空恢复丢失的可见 UI 物料。

正确抽象是：

```text
VLM / detector 负责看见候选材料。
Go compiler 负责证据合并、ownership、结构和 emission。
golden 只用于 eval，不能参与 generation。
```

## Scope

包含：

- 记录 VLM detector 实验结果。
- 定义 `ui_detector_candidates.v1.json` 作为 detector 和 Go compiler 之间的唯一合同。
- 实现 Go-first `short pass` detector 的 report-only CLI、eval、overlay 和 `codiacompile` manifest 接入。
- 规划后续 ImageView-only permission merge。

不包含：

- 不替换当前 `/api/upload-preview` -> DSL v0.1 -> Renderer 产品主链。
- 不让模型直接输出 final Codia tree。
- 不让 detector 单独创建 Button、Background、ViewGroup 或 ListView 结构。
- 不把 Codia golden、节点名、固定 bbox、样本路径、文案或品牌规则输入 generation。
- 不把 API key、token、临时网关凭证写入 repo、artifact 或文档。

## Practice Results

### GPT-5.5 full-image simple prompt on Tencent 022

OpenAI-compatible visual model可以直接输出有用的 UI role/bbox 候选，但 single full-image prompt 会把 Button 报得过多。

```text
image: docs/reference/codia-samples/images/腾讯动漫_022_1440.png
sent size: 591 x 1280
latency: ~60.6s
candidate count: 50
```

Golden eval:

| role | golden | detector | matched@0.5 | matched@0.6 | notes |
| --- | ---: | ---: | ---: | ---: | --- |
| ImageView | 37 | 25 | 19 | 12 | 有明显补 leaf 价值 |
| Button | 4 | 19 | 3 | 3 | extra 太多，不能直接 merge |
| EditText | 1 | 1 | 1 | 1 | bbox quality acceptable，best IoU ~0.859 |
| StatusBar | 1-like | 1 | 1 | 1 | best IoU ~0.846 |
| BottomNavigation | 1 | 1 | 1 | 1 | best IoU ~0.905 |

结论：

```text
full-image prompt 可以证明 VLM 能看见 UI role/bbox。
但 Button extras 明显，Button 不能靠 detector 单独进入最终树。
```

### GPT-5.5 long prompt on Tencent 018

长提示词 + 大图 + 大 JSON 输出不稳定。

Observed failure:

```text
SSL record layer failure
```

结论：

```text
不要走“一张大图 + 一个超长 prompt + 一次性完整结构 JSON”的路线。
这条路线慢、不稳、难重试，输出越大越容易被网关或 JSON parser 卡死。
```

### Qwen3-VL-8B ModelScope probe on Tencent 018

Qwen 8B 能描述 UI，但不是当前 Codia-like detector 主力。

Long structured prompt:

```text
sent size: 591 x 1280
latency: ~159s
failure: JSON truncated / parse error
```

Compact prompt:

```text
sent size: 473 x 1024
latency: ~93s
candidate count: 50
role counts: TextView 30, ImageView 16, Background 1, Button 1, StatusBar 1, BottomNavigation 1
```

Golden eval:

| role | golden | detector | matched@0.5 |
| --- | ---: | ---: | ---: |
| ImageView | 39 | 16 | 0 |
| TextView | 48 | 30 | 1 |
| Button | 9 | 1 | 0 |
| Background | 9 | 1 | 0 |
| BottomNavigation | 1 | 1 | 0 |

结论：

```text
Qwen3-VL-8B 当前不适合作为 Codia-like primary detector。
它可以保留为低成本语义描述/实验模型，但不应进入第一版 Go detector 主线。
```

### GPT-5.5 short prompt multi-pass on Tencent 018

这是当前最有价值的结果。

Input:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
golden: /tmp/codia-golden-018/codia_ir.v1.json
output: /tmp/ui-detector-018-short-pass/
```

Passes:

| pass | latency | candidates | purpose |
| --- | ---: | ---: | --- |
| `layout` | ~18.4s | 11 | major regions / chrome / nav / list |
| `imageview` | ~40.9s | 28 | concrete image/icon objects only |
| `background` | ~32.9s | 28 | visible surfaces/backgrounds only |
| `bottom_nav` | ~17.0s | 11 | bottom navigation region and tab-local elements |

Merged output:

| role | count |
| --- | ---: |
| ImageView | 28 |
| Background | 28 |
| TextView | 5 |
| ViewGroup | 4 |
| ActionBar | 3 |
| StatusBar | 1 |
| BottomNavigation | 1 |
| ListView | 1 |
| Button | 0 |

Golden eval:

| role | golden | detector | matched@0.5 | matched@0.6 |
| --- | ---: | ---: | ---: | ---: |
| ImageView | 39 | 28 | 26 | 17 |
| TextView | 48 | 5 | 5 | 4 |
| Button | 9 | 0 | 0 | 0 |
| EditText | 0 | 0 | 0 | 0 |
| Background | 9 | 28 | 7 | 7 |
| StatusBar | 0 | 1 | 0 | 0 |
| ActionBar | 1 | 3 | 0 | 0 |
| BottomNavigation | 1 | 1 | 1 | 1 |
| ListView | 5 | 1 | 1 | 1 |
| ViewGroup | 24 | 4 | 2 | 2 |

结论：

```text
short prompt + role-focused multi-pass 是当前正确方向。
ImageView recall 明显有价值：26/39 @ IoU 0.5。
Background 候选也有价值：7/9 matched，但 extra 多，必须 report-only 或 permission-gated。
BottomNavigation 可以稳定做 region hint。
Button 第一版应保留为 detector evidence，但不得直接 merge。否则 eval/audit 会误判成模型没识别到控件；真正的 Button 创建必须等 OCR、control surface、M29 source/pixel support 和 ownership gate 一起通过。
```

## Detector Contract

Detector 和 Go compiler 之间只通过一个 artifact 通信：

```text
ui_detector_candidates.v1.json
```

建议结构：

```json
{
  "version": "ui_detector_candidates.v1",
  "image": {
    "path": "/path/source.png",
    "width": 665,
    "height": 1440,
    "sha256": "..."
  },
  "provider": {
    "name": "openai-compatible",
    "wireApi": "responses",
    "model": "gpt-5.5"
  },
  "preprocess": {
    "passes": [
      {
        "id": "imageview",
        "kind": "role_focus",
        "sourceBBox": {"x": 0, "y": 0, "width": 665, "height": 1440},
        "sentWidth": 591,
        "sentHeight": 1280
      }
    ]
  },
  "candidates": [
    {
      "id": "det_000001",
      "role": "ImageView",
      "rawLabel": "cover thumbnail",
      "confidence": 0.9,
      "bbox": {"x": 42.0, "y": 318.0, "width": 177.0, "height": 113.0},
      "bboxNormalizedInPass": {"x": 0.063, "y": 0.221, "width": 0.266, "height": 0.078},
      "source": {
        "kind": "vision_model",
        "passId": "imageview",
        "modelOutputIndex": 0,
        "preferredByPass": true,
        "reason": "role-focused detector pass"
      },
      "merge": {
        "state": "report_only",
        "reason": "image evidence candidate; merge requires ImageView permission gate"
      }
    }
  ]
}
```

Hard rules:

```text
All bbox values in `bbox` are original screenshot pixel coordinates.
The raw model response may be saved separately for debugging, but Go compiler must not depend on raw prose.
Every candidate has role, confidence, bbox, passId, provider/model provenance, and merge state.
Pass focus is recorded as `source.preferredByPass`; it is not a candidate filter.
Default merge state is report_only.
No API key or auth token may appear in this artifact.
Golden Codia data may not appear in this artifact.
```

Allowed roles:

```text
ImageView
TextView
Background
StatusBar
ActionBar
BottomNavigation
ListView
ViewGroup
Button
EditText
```

Unknown roles are dropped. Known roles returned by a pass are preserved even when they are not that pass's preferred role. Example: a `Button` returned by the `layout` pass stays in `ui_detector_candidates.v1.json` with `source.preferredByPass=false` and `merge.state=report_only`.

Initial merge-eligible roles:

```text
ImageView only, after explicit permission gate.
```

Initial hint-only roles:

```text
EditText
StatusBar
BottomNavigation
ActionBar
ListView
ViewGroup
Background
```

Initial blocked roles:

```text
Button
```

Reason:

```text
Button extras are too easy. A Button must be detector candidate + M29 control surface + OCR/icon foreground + ownership context.
Detector alone must not create Button.
```

## Short Pass Design

Do not use one giant prompt. Use several short, role-focused passes.

Initial pass set:

| pass | image region | prompt target | first merge use |
| --- | --- | --- | --- |
| `layout` | full image | major visible regions, chrome, nav, list surfaces | report-only / region hints |
| `imageview` | full image, optionally tiled later | concrete image/icon objects only | ImageView permission merge |
| `background` | full image | visible surfaces/backgrounds only | report-only, later surface hints |
| `bottom_nav` | bottom band | bottom navigation container, icons, tab slots | hint only |
| `top_chrome` | top band | status/action/search/chrome icons and surfaces | later hint |
| `right_rail` | right band | vertical rail thumbnails/markers/items | later ImageView/ListView hints |

第一版 Go implementation 可以先固化已经跑通的四个 pass：

```text
layout
imageview
background
bottom_nav
```

然后再加：

```text
top_chrome
right_rail
search_bar
```

### Prompt Contract

Prompt 要求模型输出“候选”，不是输出 Codia tree。

Common rules:

```text
Return JSON only.
Use normalized bbox coordinates relative to the received image.
Detect visible UI elements, not inferred semantics.
Do not output full final hierarchy.
Do not include every OCR text as TextView unless this pass asks for sparse labels.
Prefer concrete visible bbox over semantic region guesses.
Include small icons when the pass asks for ImageView/icons.
Roles must come from the fixed role whitelist.
```

Example `imageview` prompt intent:

```text
Detect only concrete visible image/icon elements in this mobile UI screenshot.
Include small icons, thumbnails, cover images, badges, arrows, status glyphs, and navigation icons.
Do not output text labels as TextView.
Do not output containers, buttons, or backgrounds.
Return only JSON with elements: [{role, label, confidence, bbox}].
bbox is normalized [x1,y1,x2,y2] relative to this image.
```

Example `background` prompt intent:

```text
Detect only visible background/surface regions: cards, bars, pills, panels, selected tab surfaces, and obvious large background blocks.
Do not output text, icons, or final hierarchy.
Do not infer invisible containers.
Return only JSON with elements: [{role:"Background", label, confidence, bbox}].
```

Example `layout` prompt intent:

```text
Detect only major mobile UI layout regions: status/action/top chrome, main content list, bottom navigation, side rails, repeated content bands, and major cards.
Do not output every text label or tiny icon.
Return coarse candidates only.
```

The exact prompt text should live in Go source or prompt fixture files with tests for JSON parsing, not inside chat history.

## Go Implementation Plan

Expected new package/CLI layout:

```text
services/backend-go/internal/codia/detector/
services/backend-go/internal/codia/detector/candidates.go
services/backend-go/internal/codia/detector/openai.go
services/backend-go/internal/codia/detector/passes.go
services/backend-go/internal/codia/detector/normalize.go
services/backend-go/internal/codia/detector/eval.go
services/backend-go/internal/codia/detector/merge.go
services/backend-go/cmd/codiadetector/
```

Implemented surface as of 2026-05-30:

```text
services/backend-go/internal/codia/detector/
services/backend-go/cmd/codiadetector/
services/backend-go/internal/codia/assembly/
services/backend-go/internal/codia/canvasexport/
services/backend-go/internal/codia/compiler detector manifest + assembly hook
services/backend-go/cmd/codiacompile -detector-candidates
```

Current implementation no longer stops at report-only. `codiadetector` can call OpenAI-compatible providers, write candidates, report, overlay, raw responses, and run detector-vs-golden eval. `codiacompile -detector-candidates` now feeds detector candidates into `internal/codia/assembly`, where only detector-supported `ImageView` candidates may become bbox-authority source candidates. `Button`, `Background`, `ViewGroup`, `ListView`, `ActionBar`, `StatusBar`, and `BottomNavigation` detector outputs remain hint-only/report-only; they cannot directly create controls or regions yet.

`assembly` is the ownership arbitration layer between raw leaves and `control/tree`: it emits `assembly/codia_ir.v1.json`, `codia_source_candidates.v1.json`, `codia_ownership_graph.v1.json`, and `codia_assembly_report.md`. Destructive consume/suppress is gated on detector ImageView support. Without detector ImageView candidates, assembly preserves M29/OCR leaves conservatively so the existing smoke baseline does not regress.

`canvasexport` writes `codia_canvas_like.v1.canvas.json` and `codia_canvas_export_report.md` from the final Codia IR. The output is analyzer-compatible `version/root/blobs` canvas JSON with `DOCUMENT -> CANVAS -> FRAME "Figma design - ..." -> Root`, deterministic GUIDs, transforms, sizes, role/name/schema pluginData, textData, and basic fills. It deliberately does not claim byte-for-byte Figma internals for commandsBlob, derived geometry, glyph geometry, or true image blob hashes.

Python was useful for probes, but production side-path is Go-first because the compiler, diff, audit, merge gates, and canvas export are already Go. Python can remain an optional research harness, not the runtime boundary.

### Stage 1: Report-only `codiadetector`

Add a Go CLI:

```bash
cd services/backend-go
go run ./cmd/codiadetector \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -out /tmp/ui-detector-018 \
  -provider openai-responses \
  -model gpt-5.5 \
  -passes layout,imageview,background,bottom_nav \
  -merge-mode report_only
```

Inputs:

```text
source PNG
provider config from env
pass list
max image side / crop band settings
```

Outputs:

```text
ui_detector_candidates.v1.json
ui_detector_report.md
ui_detector_overlay.png
raw_model_response/<pass>.json or .txt
```

Validation:

```text
Can call OpenAI-compatible Responses provider.
Can save raw response without secrets.
Can parse JSON even when model wraps output in markdown.
Can map normalized bbox back to source screenshot pixels.
Overlay proves bbox alignment.
All candidates remain report_only.
```

### Stage 2: Multi-pass preprocessing and dedupe

Implement pass execution:

```text
full-image role passes
top/bottom/right/sourceBBox crops
optional resize to max_side
normalized bbox -> original bbox restore
per-pass timeout and retry
```

Dedupe rules:

```text
same role and IoU >= 0.75: keep higher confidence / better pass priority
ImageView inside BottomNavigation: keep ImageView but tag region hint
ImageView vs Button high-overlap: keep ImageView; Button stays blocked/report-only
Background vs ViewGroup high-overlap: keep both in report-only, do not merge yet
tiny candidates keepable only when pass is imageview/top_chrome/bottom_nav and confidence is high
```

This stage must not read golden.

### Stage 3: Detector eval against golden

Add eval mode:

```bash
go run ./cmd/codiadetector \
  -eval \
  -candidates /tmp/ui-detector-018/ui_detector_candidates.v1.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/ui-detector-018/eval
```

Artifacts:

```text
ui_detector_eval.v1.json
ui_detector_eval_report.md
ui_detector_overlay.png
ui_detector_missed_overlay.png
```

Metrics:

```text
role-level golden count / detector count / matched@0.5 / matched@0.6
precision / recall / F1 by role
extra and missed by role
matched contribution by pass
missed ImageView with no nearby candidate
candidate bbox too large / too small
Button false-positive counts, even when Button is merge-blocked
```

Golden is eval-only:

```text
The eval command may read golden.
The generation command may not read golden.
```

### Stage 4: `codiacompile` integration

Implemented optional detector artifact input:

```bash
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -detector-candidates /tmp/ui-detector-018/ui_detector_candidates.v1.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018
```

Stage 4 behavior now includes:

```text
Copy/reference detector candidates into compile manifest.
Feed detector candidates into assembly before control synthesis.
Write assembly source candidates and ownership graph artifacts.
Keep Button/Background/ViewGroup/ListView detector output hint-only.
Keep no-detector smoke score unchanged.
```

Generation still never reads golden. Golden is used only by diff/eval after generation.

### Stage 5: ImageView-only permission merge

Implemented merge gate after M29 evidence tokens / Codia leaves, before control synthesis:

```text
detector ImageView candidate
-> permission gate
-> synthetic Codia leaf evidence kind: vision_detector_image_candidate
```

Permission gate:

```text
role == ImageView
confidence >= threshold
bbox area within scale-profile bounds
not high-IoU duplicate of existing M29 ImageView leaf
not mostly inside OCR text body unless pass is imageview/top_chrome/bottom_nav/search_bar and candidate is icon-like
not a pure background/card edge fragment
not a Button/TextView/ViewGroup candidate recast as image
```

Every merged leaf must retain:

```text
detectorCandidateId
passId
provider/model
confidence
rawLabel
original bbox
merge reason
```

Acceptance:

```text
upstream_leaf_missing:ImageView drops on 018/022.
ImageView extra does not explode.
Button precision stays protected because Button remains blocked.
Existing Codia smoke artifacts still explain all detector-origin leaves by candidate id.
```

### Region hint ownership wiring

This is not a new plan stage. It is the implementation of the original plan item:

```text
BottomNavigation/ActionBar/ListView/ViewGroup:
detector only provides region hints;
tree builder owns parent assignment and structure.
```

Implemented in the Stage 0-5 backend closure:

```text
EditText: bbox hint for search/input surfaces; still needs M29 surface/OCR context.
StatusBar/ActionBar/BottomNavigation: tree builder may use detector region bbox as proposal, but still needs real children.
Background: control/card surface hint only; not direct visible leaf unless backed by pixel source evidence.
ViewGroup/ListView: body region hints are converted only when they can form a real slot-list from existing children.
Button: detector + M29 surface + OCR/icon foreground + ownership context required.
```

First-principles boundary:

```text
Detector region candidates are not source nodes.
They are bbox proposals for parent assignment.
Tree builder remains the ownership judge.
```

Implemented behavior:

```text
Root assembly evidence kind: assembly_region_hint
-> tree parses role/bbox/confidence/source id
-> StatusBar/ActionBar/BottomNavigation can take hint bbox when plausible
-> ViewGroup/ListView hints enter body only as ListView -> ViewGroup slot proposals
-> empty hints, huge body panels, and text-only hints do not emit structure
```

Important validation result:

```text
Tencent 018 initially showed that emitting a raw detector ViewGroup box creates two extra ViewGroup nodes with no matched gain.
The implementation was tightened to slot-list gating.
After tightening, Tencent 018 detector compile returns to the Stage 5 numbers:
generated 123, matched 97, extra 26, missed 49.
```

This means region hint wiring is a safe closure step, not a structural recall breakthrough by itself. It is complete only because it prevents raw VLM region boxes from becoming final structure.

## 2026-05-31 Output-quality Repair

The first plugin-connected Codia Beta runs exposed two compiler-contract defects that are not model/provider problems:

```text
assembly over-promoted a root/header-scale raster crop as final ImageView
tree let body overlap BottomNavigation by extending bodyEnd past bottomNav.Y
```

Concrete failing evidence from Lizhi 011 before repair:

```text
leaf_0002 ImageView emit bbox 0,0,665,452 reason=m29_independent_image_candidate
tree_body_0001 bbox 0,0,665,1355
tree_bottom_nav_0001 bbox 0,1300,665,140
```

Repair boundary:

```text
large root/top raster crops are structural evidence, not final ImageView
top solid Background evidence may remain editable to preserve header fill
only compact media owners may consume OCR/internal fragments
BottomNavigation region hint is a hard body boundary
```

Implemented behavior:

```text
structural M29 image_crop -> suppress with reason=m29_structural_raster_region_not_final_image
root/top-scale detector ImageView -> suppress with reason=detector_image_not_final_media_candidate
imageOwnerCanConsumeInternals now requires compact media geometry
topRegionBackground allows header-scale solid Background up to one third of the screen
buildBody clips bodyEnd to bottomNav.SourceBBox.Y
```

Targeted validation on Lizhi 011:

```text
out: /tmp/codia-lizhi-011-quality-fix
leaf_0002 decision=suppress reason=m29_structural_raster_region_not_final_image
leaf_0001 Background remains with SOLID fill
leaf_0016/leaf_0017 OCR title texts remain TextView
tree_body_0001 bbox 0,0,665,1300
tree_bottom_nav_0001 bbox 0,1300,665,140
body/nav overlap = 0
```

Regression validation after repair:

```text
go test ./internal/codia/assembly ./internal/codia/tree ./internal/codia/compiler ./cmd/codiacompile ./cmd/codiaserver
bash services/backend-go/tools/codia_smoke_4img.sh
CODIA_DETECTOR_T018=/private/tmp/ui-detector-018-short-pass/ui_detector_candidates.v1.json bash services/backend-go/tools/codia_smoke_4img.sh
temporary codiaserver HTTP flow: upload -> task completed -> DSL returned -> first asset returned 200
```

### Runtime paint-order repair

Plugin-connected testing also exposed a renderer-side mapping issue: Codia IR/analyzer checks keep `bg_Button` / `bg_EditText` as last logical children, but Figma paints later-appended siblings above earlier siblings. The Codia Runtime renderer now preserves DSL paths and logical order in the data contract while appending siblings to Figma by paint order:

```text
Background/bg_* shapes -> ImageView -> containers -> TextView
```

This keeps text visually above images/backgrounds without changing the Codia tree or weakening the `button background last child` analyzer contract.

## Provider Compatibility

The implementation should support provider interfaces, not one hardcoded model call.

Initial provider:

```text
OpenAI-compatible Responses API
```

Secondary provider:

```text
OpenAI-compatible Chat Completions API for models that only support chat vision format
```

Future provider:

```text
local HTTP detector adapter for YOLO/ONNX/OmniParser/custom model
```

Compiler contract remains the same:

```text
Any provider must output ui_detector_candidates.v1.json.
```

Env contract:

```text
CODIA_UI_DETECTOR_PROVIDER=openai-responses
CODIA_UI_DETECTOR_WIRE_API=responses
CODIA_UI_DETECTOR_BASE_URL=https://api.openai.com
CODIA_UI_DETECTOR_API_KEY=...
CODIA_UI_DETECTOR_MODEL=gpt-5.5
CODIA_UI_DETECTOR_MAX_IMAGE_SIDE=1280
CODIA_UI_DETECTOR_PASSES=layout,imageview,background,bottom_nav
CODIA_UI_DETECTOR_TIMEOUT_SECONDS=180
CODIA_UI_DETECTOR_TEMPERATURE=0
```

Auth:

```text
API keys come from process env only.
No key is written to candidate JSON, raw response files, reports, overlays, logs, or docs.
```

## Acceptance

Plan-level acceptance:

- This document records the practical VLM results and the chosen short-pass route.
- 089 and bug 017 link to this plan as the resumed detector direction.
- Current mainline docs make clear this is not the active `/api/upload-preview` runtime.

Stage 1 acceptance:

- `codiadetector` writes `ui_detector_candidates.v1.json`, report, overlay, and raw responses.
- All candidates are `report_only`.
- Tencent 018 can reproduce the short-pass shape: useful ImageView candidates, preserved Button/Background/ViewGroup evidence, and no direct Button merge.

Stage 2 acceptance:

- Multi-pass bbox restore is correct on overlay.
- Dedupe removes obvious duplicate candidates without suppressing tiny icon candidates.

Stage 3 acceptance:

- Eval report prints per-role matched@0.5/matched@0.6/precision/recall/F1.
- Reports identify pass contribution and extra/missed distribution.

Stage 4 acceptance:

- `codiacompile -detector-candidates` writes `detector/detector_manifest.v1.json` and assembly artifacts.
- No-detector smoke remains unchanged against the existing two-image gate.
- Detector candidates remain traceable by candidate id; generation does not read golden.

Stage 5 acceptance:

- `upstream_leaf_missing:ImageView` decreases on Tencent 018 when detector candidates are provided.
- Generated ImageView extras remain controlled.
- Button precision is not hurt.
- BottomNavigation remains matched.
- Every detector-origin emitted leaf is traceable to one candidate id.

Region hint ownership acceptance:

- `tree` consumes `assembly_region_hint` without letting detector create Button/Background/standalone ViewGroup.
- BottomNavigation hint can refine the container bbox but still requires real tab children.
- Body ViewGroup/ListView hints emit only when existing children form at least three rich slots.
- Empty detector region hints do not emit structure.
- No-detector smoke remains unchanged.
- Tencent 018 detector compile does not regress ImageView/Button/BottomNavigation metrics or add hinted-region extras.

Backend closure acceptance:

- `services/backend-go/tools/codia_smoke_4img.sh` runs the four Codia golden samples end to end.
- Each sample goes through `codiaanalyze` golden import, `codiacompile`, structure diff/audit, canvas export, and `codiaanalyze` read-back of the generated `.canvas.json`.
- Detector candidates are optional per sample through `CODIA_DETECTOR_T018`, `CODIA_DETECTOR_T022`, `CODIA_DETECTOR_LIZHI`, and `CODIA_DETECTOR_XIANYU`.
- The default no-detector run locks the current deterministic four-image floor. Detector-enhanced runs may improve it, but must still pass the same closure gate.

Validated 2026-05-30 on Tencent 018 with `/private/tmp/ui-detector-018-short-pass/ui_detector_candidates.v1.json`:

| path | generated | matched | extra | missed | ImageView precision | ImageView recall | Button precision | BottomNavigation precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no detector smoke baseline | 149 | 95 | 54 | 51 | 0.429 | 0.538 | 1.000 | 1.000 |
| detector assembly | 123 | 97 | 26 | 49 | 0.769 | 0.769 | 1.000 | 1.000 |
| detector assembly + Stage 6 hints | 123 | 97 | 26 | 49 | 0.769 | 0.769 | 1.000 | 1.000 |

The detector assembly run also passed `codiaanalyze` on `codia_canvas_like.v1.canvas.json` with 123 analyzable nodes and 3 root children. The no-detector `services/backend-go/tools/codia_smoke_2img.sh` gate remains:

| sample | generated | matched | extra | missed |
| --- | ---: | ---: | ---: | ---: |
| Tencent 018 | 149 | 95 | 54 | 51 |
| Tencent 022 | 106 | 92 | 14 | 28 |

The four-image backend closure gate is now:

```bash
bash services/backend-go/tools/codia_smoke_4img.sh
```

Validated 2026-05-30 default no-detector closure:

| sample | generated | golden | matched | extra | missed | edgeP | edgeR | canvas nodes | root children |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tencent 018 | 149 | 146 | 95 | 54 | 51 | 0.419 | 0.428 | 149 | 3 |
| Tencent 022 | 106 | 120 | 92 | 14 | 28 | 0.619 | 0.546 | 106 | 4 |
| Lizhi 011 | 89 | 93 | 61 | 28 | 32 | 0.193 | 0.185 | 89 | 2 |
| Xianyu | 116 | 132 | 64 | 52 | 68 | 0.339 | 0.298 | 116 | 1 |

Validated 2026-05-30 with available Tencent 018 detector candidates:

```bash
CODIA_SMOKE_4IMG_WORK=/tmp/codia_smoke_4img_detector018 \
CODIA_DETECTOR_T018=/private/tmp/ui-detector-018-short-pass/ui_detector_candidates.v1.json \
bash services/backend-go/tools/codia_smoke_4img.sh
```

| sample | generated | golden | matched | extra | missed | edgeP | edgeR | canvas nodes | root children |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tencent 018 + detector | 123 | 146 | 97 | 26 | 49 | 0.574 | 0.483 | 123 | 3 |
| Tencent 022 | 106 | 120 | 92 | 14 | 28 | 0.619 | 0.546 | 106 | 4 |
| Lizhi 011 | 89 | 93 | 61 | 28 | 32 | 0.193 | 0.185 | 89 | 2 |
| Xianyu | 116 | 132 | 64 | 52 | 68 | 0.339 | 0.298 | 116 | 1 |

## Validation

Documentation validation for this checkpoint:

```bash
git diff --check
rg -n "090-openai-compatible-ui-detector-short-pass|ui_detector_candidates|short-pass" docs
git status --short --branch
```

Future implementation validation:

```bash
cd services/backend-go
go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiadetector ./cmd/codiaanalyze
bash tools/codia_smoke_4img.sh

go run ./cmd/codiadetector \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -out /tmp/ui-detector-018 \
  -passes layout,imageview,background,bottom_nav \
  -merge-mode report_only

go run ./cmd/codiadetector \
  -eval \
  -candidates /tmp/ui-detector-018/ui_detector_candidates.v1.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/ui-detector-018/eval

go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -detector-candidates /tmp/ui-detector-018/ui_detector_candidates.v1.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018
```

## Risks

Latency:

```text
Multi-pass VLM can take 1-2 minutes per image. This is acceptable for offline/Beta audit, not yet for default product runtime.
```

Cost:

```text
Full production use needs rate, cache, budget, and retry controls.
```

Stability:

```text
Large prompt + large image + large JSON is rejected. Short prompts and smaller pass outputs are required.
```

False positives:

```text
Button and Background false positives are expected. They must stay report-only until backed by M29 pixel/source evidence and ownership gates.
```

Provider lock-in:

```text
The compiler must depend on ui_detector_candidates.v1.json, not provider-specific raw output.
```

Security:

```text
No secret may be persisted. Reports should record provider type and model, not credentials.
```

## Current Decision

Use OpenAI-compatible VLM short-pass as the immediate upstream candidate provider. Defer RICO/YOLO self-training as a future replacement or cost-reduction path.

The implementation order is now:

```text
report-only detector CLI          [implemented]
-> multi-pass + dedupe + overlay  [implemented]
-> detector eval                  [implemented]
-> codiacompile assembly hook      [implemented]
-> ImageView-only permission merge [implemented]
-> hint-only region/control integration [implemented]
-> assembly material classification + hard region partition [implemented]
-> codiaserver detector fallback + optional streaming provider calls [implemented]
-> runtime full-body backing suppression [implemented]
```

The hard boundary remains:

```text
Detector proposes visible role/bbox candidates.
Go compiler decides source permission, ownership, structure, and emission.
```

For the Beta server path, online detector is best-effort evidence. Provider TLS errors, timeouts, 5xx, empty responses, or invalid model JSON must not fail `/api/codia-preview`; `codiaserver` records `CODIA_DETECTOR_FALLBACK`, writes `compile/detector/detector_fallback.v1.json`, and continues compiling from M29/OCR. OpenAI-compatible streaming is available through `CODIA_UI_DETECTOR_STREAM=true` or `codiadetector -stream`, but it remains a provider transport option, not a new compiler contract.

Runtime DSL v0.2 must not use a full body/source crop as a visible backing layer under editable TextView/ImageView/shape nodes. That creates duplicate source foreground pixels and text ghosting. Large structural backgrounds should remain as Background evidence or region-owned shapes; if a raster cannot be cleanly separated from foreground, it must stay a local media ImageView or be suppressed by ownership, not repaired by dsl02 asset inpainting.
