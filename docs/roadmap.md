# Image-to-Figma Roadmap

- 状态：active
- 更新日期：2026-06-05

## Purpose

本文档固定当前路线，避免后续工作继续在旧 Python preview、Codia-like tree、官方 Codia JSON、Go Draft、YOLO 主裁判、Pencil-Go、组件化、Auto Layout 和代码生成之间来回跳。

当前产品目标只有一个：

```text
1..N images -> user-confirmed Pencil/Figma handoff package
```

当前主线是 Pencil Assisted Slice Workspace：

```text
1..N images
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

第一性原理边界：

```text
PNG 像素是输入真相源。
PSD-like/M29/OCR/foreground audit/model evidence 提供候选。
用户确认的 manual_slices.v1.json 是最终交付真相源。
Pencil exporter 只机械裁 source.png 并按坐标放回，不修自动 ownership。
Codia golden 只做 eval/reference，不进入 generation。
```

硬不变量：

```text
manual_slices.v1.json -> one selected slice contract
```

这条不变量优先级高于自动候选质量、节点数量和未来可编辑性。自动候选可以错，最终交付必须以用户确认的 source-image 坐标为准。

## Current Runtime Surfaces

当前 assisted slice 主链：

```text
GET /api/pencil/slice-projects/workspace
-> POST /api/pencil/slice-projects
-> GET /api/pencil/slice-projects/{projectId}/review
-> PUT /api/pencil/slice-projects/{projectId}/manual-slices
-> POST /api/pencil/slice-projects/{projectId}/export-preview
-> POST /api/pencil/slice-projects/{projectId}/export
-> GET /api/pencil/slice-projects/{projectId}/download.zip
-> GET /api/pencil/slice-projects/{projectId}/selected-assets.zip
```

当前工作台、候选、manual slices、导出预览、ZIP 合同和部署问题都先归到：

```text
services/pencil-python-backend/app/slice_projects.py
services/pencil-python-backend/app/routes/slice_projects.py
services/pencil-python-backend/app/routes/slice_project_pages.py
services/pencil-python-backend/scripts/slice_workspace_acceptance.py
docs/reference/pencil-python-backend-api.md
docs/runbooks/pencil-python-backend-handoff.md
```

旧运行面状态：

- Go Draft `/api/draft-preview`：历史/延后自动可编辑稿路线，不是当前交付主线。
- Python/FastAPI `/api/upload-preview`：历史 preview/reference path，不是 Draft runtime。
- Codia generation path：已从产品代码移除。
- Official Codia JSON：eval/reference material only。
- `services/pencil-go`：已被 Python Pencil backend 取代。
- YOLO/M29/PSD-like 自动 ownership：只作为候选/eval/debug，不作为最终交付裁判。

## What To Improve Next

### 1. Stabilize Assisted Slice Workspace

最高优先级是让真实样图稳定完成候选、人工确认、预览、导出和 ZIP 合同检查，而不是继续追一个全自动 semantic tree。

重点：

- Workspace 能批量创建项目、恢复历史项目、继续处理。
- 候选可以框选、加入、拒绝、恢复。
- manual slices 能保存、刷新恢复、批量管理。
- export-preview 与最终 ZIP 一致。
- `.pen` visible refs 无绝对路径、无 `source.png`、无 raw crops、无 masks、无 debug、无 `../`。
- `selected-assets.zip` 只包含用户确认的资源。

### 2. Candidate Quality, Not Final Authority

候选质量值得继续提升，但候选不是最终 authority。PSD-like、M29、OCR、foreground audit 和模型都只能减少用户手工成本，不能覆盖 `manual_slices.v1.json`。

需要继续收敛：

- candidate ranking：recommended / normal / noise / text / rejected。
- 多页候选统计和页面处理状态。
- 更稳的 bbox 合并/去噪，但不写样本名、固定坐标、品牌、可见文字规则。
- 透明底和智能命名只能作为可选增强，不改变默认矩形裁剪真相。

### 3. Real Sample Validation

每次改 assisted slice 工作台或导出链路都要跑真实样例，而不是只看单元测试。

当前最小样例集：

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages
/Users/luhui/Downloads/dorm_selection_ui_assets 2
```

验收信号：

- projectCreated=true。
- candidateCount>0。
- manualSliceSaved=true。
- reviewStateSaved=true。
- exportPreviewGenerated=true。
- projectZipExists=true。
- selectedAssetsZipExists=true。
- selectedAssetCount == selected PNG count。
- badRefs=0。
- missingRefs=0。

### 4. Code Slimming

重构方向是删掉错误抽象，不是给旧 Codia-like、Draft ownership 或 YOLO 主裁判路径打补丁。

优先整理：

```text
services/pencil-python-backend/app/slice_projects.py
services/pencil-python-backend/app/routes/slice_project_pages.py
services/pencil-python-backend/app/routes/slice_projects.py
services/pencil-python-backend/scripts/slice_workspace_acceptance.py
```

原则：

- 行为变更和命名/拆文件分开提交。
- 不创建 `utils`、`common`、`misc` 垃圾桶。
- 不恢复 `codia`、`tree`、`control`、`leaf`、`emitter`、`compiler` 作为产品生成命名。

### 5. Eval, Not Generation

Codia 仍有用，但只在 eval/reference 层有用。

允许：

```text
docs/reference/codia-samples/
services/backend-go/internal/eval/codia
cmd/drafteval
```

禁止：

```text
generation imports internal/eval/codia
generation reads Codia golden JSON
new product endpoint named codia
official Codia JSON as output target
```

## Non-Goals For The Next Phase

下一阶段不要做：

```text
Auto Layout
Figma Component/Instance
frontend code generation
official Codia JSON clone
semantic UI control tree as product contract
YOLO as final owner
services/pencil-go revival
Go Draft as default delivery route
quality dashboard
account/payment/quota
```

这些不是永远不做。它们被阻塞到 assisted slice workspace、manual slices、ZIP 合同和真实样图验收稳定之后。
