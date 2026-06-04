# 架构总览

当前分支的可交付架构目标是生成用户确认后的 Pencil/Figma 交付包，而不是继续追求全自动可编辑 Figma 草稿或复刻 Codia 内部结构。

Go Draft / Editable Layer Graph / Draft Runtime DSL 仍保留为历史自动化路线和未来恢复参考，但不是当前分支的默认产品交付主线。

```text
1..N images
-> Pencil Python Backend
-> candidates.v1.json
-> assisted slice workspace
-> manual_slices.v1.json
-> project.zip + selected-assets.zip
```

## System Summary

项目由五个独立边界组成：

- Pencil Python Backend：当前产品交付入口，负责上传、候选生成、Canvas 工作台、manual slices、Pencil `.pen` 和 ZIP 导出。
- PSD-like / M29 / OCR / foreground audit：生成候选和 debug evidence，不能直接决定最终 visible asset。
- Assisted slice workspace：用户确认、手动画框、调整、删除、命名的 plain HTML + Canvas 工作台。
- Pencil exporter：按 `manual_slices.v1.json` 从 `source.png` 裁图，生成三种 `.pen` 模式和资源包。
- Go Draft / Figma Plugin / Renderer：历史自动化路线，保留为未来恢复参考和显式调试目标。

旧 Codia Beta 和官方 Codia JSON 不再是生成路径。它们只保留为 eval/reference。

## Current Product Mainline

```text
GET /api/pencil/slice-projects/workspace
-> POST /api/pencil/slice-projects
-> candidates.v1.json
-> GET /api/pencil/slice-projects/{projectId}/review
-> PUT /api/pencil/slice-projects/{projectId}/manual-slices
-> POST /api/pencil/slice-projects/{projectId}/export-preview
-> POST /api/pencil/slice-projects/{projectId}/export
-> project.zip + selected-assets.zip
```

## Main Contracts

- `candidates.v1.json`：候选建议，不是最终裁判。
- `review_state.v1.json`：工作台状态，不参与最终交付真相。
- `manual_slices.v1.json`：当前产品最终交付真相源。
- `project.zip`：Pencil/Figma 项目包。
- `selected-assets.zip`：前端切图资源包。
- `m29_physical_evidence.v1.json`：物理证据，不是 UI object authority。
- `ui_detector_candidates.v1.json`：视觉模型候选，不是最终结构。
- `ui_candidate_review.v1.json`：模型 review 决策，不是最终结构。
- `editable_layer_graph.v1.json`：历史 Draft 后端合同。
- `draft_runtime.dsl.v1.json`：历史 Renderer 输入合同。
- `draft_validation_report.md`：历史 Draft 运行时合同检查结果。
- `asset_manifest.json`：历史 Draft RasterLayer asset 可解析性合同。

## Module Boundaries

Pencil exporter 只按 `manual_slices.v1.json` 裁图和放回坐标，不重新当自动 ownership 裁判。

Assisted slice workspace 只保存用户确认状态和 manual slices；pan、zoom、筛选是 view/workbench state，不是交付真相。

Go backend 不再是当前产品交付入口。`m29extract` 可作为 Pencil candidate/evidence 子工具使用。

M29 只负责物理证据：bbox、像素、连通域、颜色、边缘、纹理、OCR mask、relation。M29 不创建最终交付 slice。

Vision provider 只负责候选和 review：语义标签、缺漏提示、merge/refine/suppress 建议。模型不能直接生成 final visible owner、Figma tree 或 final DSL。

`manual_slices.v1.json` 是当前 assisted slice 产品唯一的 delivery authority。

Historical Draft assembly 曾是 Draft route 的 layer ownership authority；恢复它需要新的 active plan。

Eval/Codia 包只读官方 Codia JSON 和生成结果做 diff。Generation 包不能 import eval 包。

## Package Direction

Target Go package layout:

```text
services/backend-go/
  cmd/
    draftserver/
    draftcompile/
    draftdetect/
    drafteval/
    m29extract/
    m29trace/

  internal/
    app/
      server/
      storage/
      task/

    image/
      crop/
      geometry/
      pngio/
      color/
      mask/

    m29/
      primitive/
      evidence/
      relation/
      visualtree/
      ocr/
      pipeline/

    vision/
      detector/
      provider/
      prompt/
      review/

    draft/
      contract/
      assemble/
      asset/
      group/
      exportdsl/
      validate/
      report/

    eval/
      codia/
      metrics/
```

Names such as `codia`, `tree`, `control`, `leaf`, `emitter`, and `compiler` must not be used for new product-generation packages. They describe historical implementation artifacts, not the product truth.

## Hard Invariants

```text
one visible foreground pixel -> one visible owner
```

- Original PNG is not a visible full-page backing.
- Reference image is hidden/locked diagnostic context only.
- Text layers are above same-region shape/raster layers.
- Raster layers need resolvable assets.
- Shape layers represent backgrounds, surfaces, separators, and simple geometry.
- Group layers organize movement and selection; they do not own pixels.
- Every decision is auditable through source refs and reasons.

## Legacy Boundaries

The following are not current generation architecture:

```text
Codia assembly/control/tree/emitter
Generate Beta as product mainline
codia_runtime.dsl.v0_2.json as the product target
Python /api/upload-preview as Draft runtime
M29 Direct compare
legacy M30 materialization
M31-M39/M39.1 runtime
ONNX proposer
```

If a legacy idea remains useful, re-express it in Draft terms: layer ownership, region grouping, asset crop, z-order, validation, or eval metric.
