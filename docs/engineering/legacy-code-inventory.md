# Legacy Code Inventory

本文件回答一个具体问题：哪些代码是当前主线，哪些代码还有价值但已经不该出现在默认产品路径里。

当前产品主线：

```text
1..N UI screenshots/design images
-> repository root
-> saved SliceRecord boxes
-> assets.zip
-> project.zip / design.pen
```

旧代码不能按“没用”粗暴删除。这个仓库里很多旧代码是 Pencil、Codia-like、Draft、M29、PSD-like、Renderer、Plugin 和模型实验路线的研究资产。正确状态是标注、隔离、限制权威，而不是让它们继续伪装成当前产品。

## Classification

| Path | Status | Keep Reason | Current Rule |
| --- | --- | --- | --- |
| `app/`, `components/`, `server/`, `shared/`, `tests/` | `current` | 当前本地项目制 UI 切图、AI 画框、三种 cut mode、SQLite 状态、`assets.zip`、`project.zip/design.pen`、OCR/M29 text handoff 都在这里。 | 新产品交付和 P0/P1 修复默认落这里。 |
| `archive/legacy-code/services/pencil-python-backend/` | `superseded-product-reference` | 曾是 Pencil assisted slice delivery surface，仍保留大量 API、导出、部署和验收经验。 | 不再作为默认产品主线。只在显式维护旧 Python Pencil route 时修改。 |
| `archive/legacy-code/services/pencil-asset-backend/` | `superseded-reference` | 瘦 image/icon handoff 服务，保留 YOLO/M29/PSD-like/OCR 资产候选经验。 | 参考其设计，不默认接回 Slice Studio。 |
| `archive/legacy-code/services/pencil-handoff-studio/` | `superseded-reference` | 批量 handoff prototype，保留 Konva review 和 export 经验。 | 参考，不作为当前运行面。 |
| `archive/legacy-code/services/backend-go/cmd/m29extract/` and `archive/legacy-code/services/backend-go/internal/m29/` | `reference/fallback` | Slice Studio 曾用 Go M29 no-OCR physical kernel；当前 TS port 已成为默认。Go 保留为对照和显式 fallback。 | 不再是默认部署依赖。只在 `SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=go_m29extract` 或 M29 研究任务中使用。 |
| `server/m29-physical-evidence/` | `current` | TypeScript M29 physical evidence kernel，服务 OCR text bbox placement。 | 当前默认使用。它只提供 physical evidence，不创建 visible layers。 |
| `server/ai-slice-boxes/` | `current` | AI 画框模块，输出 transient bbox，再由前端转成普通 slices。 | 只能服务 batch drawing，不持久化 proposal，不改变 export truth source。 |
| `archive/legacy-code/services/backend-go/internal/draft/`, `archive/legacy-code/services/backend-go/cmd/draft*`, `archive/legacy-code/services/backend-go/internal/vision/`, `archive/legacy-code/services/backend-go/internal/app/` | `legacy-research/deferred-runtime` | Draft runtime、vision review、DSL export 和旧 `/api/draft-preview` 仍有研究价值。 | 不作为 Slice Studio 新功能入口。恢复前必须新建 active plan 和验收标准。 |
| `archive/legacy-code/backend/` | `legacy-research` | 历史 Python/FastAPI `/api/upload-preview`、M29/M30+ 研究链、source ownership 和 materialization 代码仍有研究价值。 | 除非任务明确点名 `/api/upload-preview`，否则不要从这里修当前产品。 |
| `archive/legacy-code/services/backend-python/` | `legacy-research` | OmniParser/VLM/PSD-like 早期实验和测试仍可作为未来模型/候选策略参考。 | 冷冻为实验代码。不要接成当前默认服务。 |
| `archive/legacy-code/services/psdlike-python/` | `legacy-reference` | PSD-like 研究和旧 Python services 的候选依赖。 | 不进入 Slice Studio 默认 runtime。 |
| `archive/legacy-code/services/pencil-go/` | `legacy-research` | Go 版 Pencil export/server 的 superseded experiment。 | 不复活为产品路径。 |
| `archive/legacy-code/packages/dsl-schema/` | `deferred-runtime-asset` | Draft runtime DSL TypeScript contract 和 validator。 | 只在插件/Renderer/Draft 任务中维护。 |
| `archive/legacy-code/packages/image-to-figma-renderer/` | `deferred-runtime-asset` | Draft DSL 到 Figma adapter 的 renderer。 | 只渲染 DSL contract，不修 Slice Studio export 问题。 |
| `archive/legacy-code/figma-plugin/` | `deferred-runtime-asset` | Figma 插件仍是旧 Draft/plugin 资产。 | 不作为 Slice Studio delivery path。若恢复插件交付，必须先定义新 runtime contract。 |
| `archive/legacy-code/Figma-design/` | `prototype/reference` | 早期 UI/design reference。 | 只作参考。 |
| `docs/reference/legacy/`, `docs/plans/archive/`, historical ADRs | `historical-docs` | 保存旧路线、逆向、计划和决策来源。 | 只能作背景，不能覆盖当前 direction contract。 |
| `docs/code-reviews*/`, `docs/reports/`, `docs/prototypes/` | `research-evidence` | 保留审计、样例、视觉证据和问题追溯。 | 不作为当前产品规范。 |

## What Not To Delete

这些目录现在看起来“不在主线”，但不是死代码：

```text
archive/legacy-code/backend/
archive/legacy-code/services/backend-python/
archive/legacy-code/services/pencil-python-backend/
archive/legacy-code/services/pencil-asset-backend/
archive/legacy-code/services/pencil-handoff-studio/
archive/legacy-code/services/pencil-go/
archive/legacy-code/services/backend-go/internal/draft/
archive/legacy-code/services/backend-go/internal/vision/
archive/legacy-code/services/psdlike-python/
archive/legacy-code/figma-plugin/
archive/legacy-code/packages/dsl-schema/
archive/legacy-code/packages/image-to-figma-renderer/
docs/reference/legacy/
docs/plans/archive/
docs/code-reviews*/
```

原因：如果以后重新做 Codia-like 自动树、Draft 可编辑图层、插件渲染、模型辅助识别或对照测试，这些代码和文档就是历史证据和实现资产。删掉只会丢知识，不会让当前 Slice Studio 更稳定。

## What Can Be Deleted

可删除的是本地运行产物，不是 legacy source：

```text
.next/
storage/
archive/legacy-code/backend/tmp/
archive/legacy-code/backend/storage/
archive/legacy-code/services/backend-go/storage/
archive/legacy-code/services/backend-go/tmp/
archive/legacy-code/services/backend-go/bin/
archive/legacy-code/services/*/storage/
archive/legacy-code/figma-plugin/dist/
runs/
node_modules/
.venv/
*.log
*.zip
*.pen
*.sqlite
*.db
```

删除前仍要检查是否被 Git 跟踪。不要删除用户当前正在使用的 local project storage，除非用户明确要求。

## Recovery Rules

以后如果要恢复旧能力，不能从旧目录直接继续堆代码。先回答三件事：

1. 恢复目标是什么：Pencil Python route、Codia-like tree、Draft editable graph、plugin rendering、model candidate，还是 deployment reference。
2. 当前真相源是什么：Slice Studio saved slices、`manual_slices.v1.json`、`editable_layer_graph.v1.json`、DSL，还是新的 contract。
3. 验收门是什么：真实样例、artifact ref 检查、Pencil/Figma visual inspection、plugin render，还是 Codia eval 指标。

没有新的 active plan 和验收门，不允许把 `legacy-research` 目录重新接到当前产品默认路径。

## Current Documentation Rule

When docs conflict, authority order is:

```text
current code at repository root
-> docs/product/direction-contract.md
-> AGENTS.md / PROGRESS.md / docs/index.md
-> docs/engineering/current-code-map.md
-> completed Slice Studio plans 159-183
-> older plans / ADRs / legacy docs
```
