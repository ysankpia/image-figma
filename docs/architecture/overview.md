# 架构总览

当前分支的架构目标是生成可编辑 Figma 草稿，而不是复刻 Codia 内部结构。

```text
PNG
-> OCR + M29 physical evidence + optional VLM candidates/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

## System Summary

项目由五个独立边界组成：

- Figma Plugin：上传 PNG、轮询 task、获取 DSL/assets、调用 Renderer。
- Renderer：把 Draft Runtime DSL 渲染成 Figma 节点。
- Go backend：执行 Draft pipeline，产出 layer graph、assets、DSL 和审计报告。
- M29 physical evidence：从 PNG/OCR 中提取可审计的物理候选。
- Vision provider：给出 UI 语义候选和可选二次 review，不能直接生成最终 DSL。

旧 Codia Beta 和官方 Codia JSON 不再是生成路径。它们只保留为 eval/reference。

## Current Product Mainline

```text
Figma Plugin
-> POST /api/draft-preview
-> services/backend-go internal/app
-> internal/m29 physical evidence
-> internal/vision detector/review
-> internal/draft assemble/asset/group/exportdsl/validate
-> GET /api/draft-preview/{taskId}/dsl
-> GET /api/draft-preview/{taskId}/assets/{assetId}.png
-> packages/image-to-figma-renderer
-> Figma Canvas
```

## Main Contracts

- `m29_physical_evidence.v1.json`：物理证据，不是 UI object authority。
- `ui_detector_candidates.v1.json`：视觉模型候选，不是最终结构。
- `ui_candidate_review.v1.json`：模型 review 决策，不是最终结构。
- `editable_layer_graph.v1.json`：后端主合同，表达可编辑 layer ownership。
- `draft_runtime.dsl.v1.json`：Renderer 输入合同。
- `draft_validation_report.md`：运行时合同检查结果。
- `asset_manifest.json`：RasterLayer asset 可解析性合同。

## Module Boundaries

Renderer 只消费 DSL，不做 OCR、M29、VLM、像素裁剪、ownership、cleanup 或质量评分。

Plugin 只负责 UI、上传、轮询、获取 DSL/assets 和 Figma API 调用。Plugin 不理解 M29、VLM、Codia golden 或 layer ownership 决策。

Go backend 不操作 Figma 画布。它负责提取证据、仲裁 layer ownership、写资产、导出 DSL 和报告。

M29 只负责物理证据：bbox、像素、连通域、颜色、边缘、纹理、OCR mask、relation。M29 不创建最终 Figma layer。

Vision provider 只负责候选和 review：语义标签、缺漏提示、merge/refine/suppress 建议。模型不能直接生成 final Figma tree 或 final DSL。

Draft assembly 是唯一的 layer ownership authority。它决定 emit、consume、suppress、refine 和 z-order。

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
