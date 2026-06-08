# Legacy Code Inventory

本文件回答一个具体问题：哪些代码是当前主线，哪些代码还有价值但已经不该出现在默认产品路径里。

当前产品主线和新瘦资产路线如下：

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip

1..N images
-> services/pencil-asset-backend
-> YOLO/M29/PSD-like/OCR evidence
-> image/icon candidates
-> user-confirmed manual_slices.v1.json
-> pencil-handoff project.zip + selected-assets.zip
```

旧代码不能按“没用”粗暴删除。这个仓库里很多旧代码是 Codia-like、Draft、M29、PSD-like 和 Pencil 交付路线的研究资产。正确状态是冷冻、标注、隔离，而不是让它们继续伪装成当前产品。

## Classification

| Path | Status | Keep Reason | Current Rule |
| --- | --- | --- | --- |
| `services/pencil-python-backend/` | `current` | 当前 assisted slice workspace、Pencil `.pen` 导出、`project.zip`、`selected-assets.zip`、部署和验收脚本都在这里。 | 新产品交付和 P0/P1 修复默认落这里。 |
| `services/pencil-asset-backend/` | `current-slim` | 151 新增瘦 image/icon 资产 handoff 服务，只输出 PNG 工程资产和单一 `pencil-handoff` `.pen`，用于后续 Pencil MCP/人工补画。 | 新的 image/icon 资产交付实验和 P0/P1 修复落这里；不要把旧 Draft/Codia/三模式自动 ownership 搬进来。 |
| `services/psdlike-python/` | `diagnostic/dependency` | 当前 Pencil backend 默认 `boundarySource=psdlike` 会通过 `app/psdlike_runner.py` 调用 `tools/run_one.py`；部署 bundle 也显式包含该目录。 | 不能归档或删除。只能作为候选证据源，不是最终 visible owner。 |
| `services/backend-go/cmd/m29extract/` and `services/backend-go/internal/m29/` | `diagnostic/dependency` | 当前 Pencil backend 仍支持 `boundarySource=m29/hybrid`，部署 bundle 包含 `m29extract` 和 Go M29 内核。 | 保留为 M29 evidence/tooling。Go Draft 不因此恢复为产品主线。 |
| `services/backend-go/internal/draft/`, `services/backend-go/cmd/draft*`, `services/backend-go/internal/vision/`, `services/backend-go/internal/app/` | `legacy-research` | Draft runtime、vision review、DSL export 和旧 `/api/draft-preview` 仍有研究价值。 | 不作为 assisted slice 新功能入口。恢复前必须新建 active plan 和验收标准。 |
| `backend/` | `legacy-research` | 历史 Python/FastAPI `/api/upload-preview`、M29.0-M39 研究链、source ownership 和 materialization 代码仍有 Codia-like/Draft 研究价值。 | 不作为当前 Draft runtime 或 assisted slice 产品入口。除非任务明确点名 `/api/upload-preview`，否则不要从这里修当前产品。 |
| `services/backend-python/` | `legacy-research` | OmniParser/VLM/PSD-like 早期实验和测试仍可作为未来模型/候选策略参考。 | 冷冻为实验代码。不要接成当前默认服务。 |
| `services/pencil-go/` | `legacy-research` | Go 版 Pencil export/server 的 superseded experiment，可能保留实现参考。 | 不复活为产品路径。新 Pencil 交付默认走 Python backend。 |
| `packages/dsl-schema/` | `deferred-runtime-asset` | Draft runtime DSL 的 TypeScript contract 和 validator。 | 只在插件/Renderer/Draft 任务中维护，不参与 assisted slice `.pen` 导出合同。 |
| `packages/image-to-figma-renderer/` | `deferred-runtime-asset` | Draft DSL 到 Figma adapter 的 renderer。 | 只渲染 DSL contract，不修 backend ownership 问题。 |
| `figma-plugin/` | `deferred-runtime-asset` | Figma 插件仍调用 `/api/draft-preview` 和 renderer，是旧 Draft/plugin 资产。 | 不作为 assisted slice 工作台交付路径。若恢复插件交付，必须先定义新 runtime contract。 |
| `docs/reference/legacy/`, `docs/plans/archive/`, historical ADRs | `historical-docs` | 保存旧路线、逆向、计划和决策来源。 | 只能作背景。不能覆盖 `AGENTS.md`、`docs/index.md` 和当前 code map。 |
| `docs/code-reviews*/`, `docs/reports/`, `docs/prototypes/` | `research-evidence` | 保留审计、样例、视觉证据和问题追溯。 | 不作为当前产品规范。引用时要说明其历史/研究性质。 |

## What Not To Delete

这些目录现在看起来“不在主线”，但不是死代码：

```text
backend/
services/backend-python/
services/pencil-go/
services/backend-go/internal/draft/
services/backend-go/internal/vision/
figma-plugin/
packages/dsl-schema/
packages/image-to-figma-renderer/
docs/reference/legacy/
docs/plans/archive/
```

原因很简单：如果以后重新做 Codia-like 自动树、Draft 可编辑图层、插件渲染或者模型辅助识别，这些代码和文档就是历史证据和实现资产。删掉只会丢知识，不会让当前产品更稳定。

## What Can Be Deleted

可删除的不是 legacy source，而是本地运行产物：

```text
backend/tmp/
backend/storage/
services/backend-go/storage/
services/backend-go/tmp/
services/backend-go/bin/
services/pencil-python-backend/storage/
services/psdlike-python/storage/
figma-plugin/dist/
runs/
node_modules/
.venv/
*.log
*.zip
*.pen
```

这些路径已经在 `.gitignore` 中。当前审计没有发现这些目录下有 Git tracked 文件。

## Recovery Rules

以后如果要恢复旧能力，不能从旧目录直接继续堆代码。先回答三件事：

1. 恢复目标是什么：Codia-like tree、Draft editable graph、plugin rendering、model candidate，还是 Pencil export。
2. 当前真相源是什么：`manual_slices.v1.json`、`editable_layer_graph.v1.json`、DSL，还是新的 contract。
3. 验收门是什么：真实样例、artifact ref 检查、视觉检查、plugin render，还是 Codia eval 指标。

没有新的 active plan 和验收门，不允许把 `legacy-research` 目录重新接到当前产品默认路径。

## Audit Evidence

本轮使用 Repomix 打包了源码和文档，范围包括 `AGENTS.md`、`README.md`、`docs/**/*.md`、`backend/**/*.py`、`services/**/*.py`、`services/**/*.go`、`packages/**/*`、`figma-plugin/src/**/*` 和测试/工具脚本；排除了 `node_modules`、`.venv`、`dist`、`storage`、`tmp`、`runs`、图片、ZIP、`.pen` 和日志。

关键事实：

- `services/pencil-python-backend/app/config.py` 默认解析 `services/psdlike-python` 和 `services/backend-go/bin/m29extract`。
- `services/pencil-python-backend/app/psdlike_runner.py` 直接运行 `services/psdlike-python/tools/run_one.py`。
- `services/pencil-python-backend/scripts/build_deploy_bundle.py` 显式打包 `services/psdlike-python/`、`services/backend-go/cmd/m29extract/` 和 `services/backend-go/internal/m29/`。
- `figma-plugin/src/apiClient.ts` 仍面向 `/api/draft-preview`，因此是 Draft/plugin 资产，不是 assisted slice workspace 入口。
- `git ls-files` 没有跟踪 `backend/tmp/`、`backend/storage/`、`figma-plugin/dist/`、`runs/` 等本地产物。
