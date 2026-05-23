# AGENTS.md

本项目采用 agent-first 文档工作流。仓库文件是事实来源，不依赖聊天记录。

## 读取顺序

1. 先读本文件。
2. 再读 [docs/index.md](docs/index.md)。
3. 根据任务类型只读相关文档。
4. 非平凡实现先创建或更新 `docs/plans/active/` 中的计划。
5. 改动完成前同步更新产品、架构、工程、计划、bug 或 ADR 文档。

## 项目边界

- 项目名：Image-to-Figma Design。
- 当前状态：M29/M30 主链收口阶段。当前 source truth 主链是 raw M29 primitive graph -> M29.2 source ownership -> M29.3 region relation -> M29.4 weak cluster -> M29.5 replay plan -> M29 Direct compare / M30 materialization。
- 项目类型：`multi-end-frontend`。
- 一期目标：单张 PNG 上传后生成 DSL v0.1，并由 Figma Renderer 写入可编辑 Figma 设计稿。
- 一期硬边界：不做代码生成、Figma Component/Instance、Auto Layout、批量上传、账号、支付、额度、质量看板、多模型平台。

## 当前主链

当前产品入口是 Figma 插件上传 PNG 到后端的 M30 preview path：

```text
Figma Plugin
-> POST /api/upload-m30-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural cluster report
-> M29.5 replay plan
-> M29 Direct compare variant
-> M30 evidence-grounded DSL materialization
-> M31/M37/M38/M39 downstream diagnostics/materialization gates
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma Canvas
```

M29 是 source truth 层。它负责从 PNG/OCR/source evidence 中固定 bbox、mask、pixel ownership、region relation、weak cluster evidence 和 replay plan。

M30 是 materialization consumer。它只能消费已经通过 M29/source 合同的证据，把可信 text、shape、image/composite media 转成 DSL v0.1；不能反向决定 M29 owner。

M29 Direct 是 compare/experiment variant。它通过 `GET /api/tasks/{taskId}/m29-direct-dsl` 暴露，不替代主线 `/api/tasks/{taskId}/dsl`。

M31-M39 是 downstream structure、audit、diagnostic 或 controlled materialization 层。它们可以审计、组织、标记、保护或有限分组 M30 输出，但不能反向修改 raw M29/M29.2 的 source ownership。

## Legacy 边界

M20-M28、SAM2 相关实验、perception provider benchmark、旧 icon/slice/provider harness 只作为历史证据和 ADR 背景保留。它们不得重新进入当前 upload/replay 的 source truth，也不得绕过 M29 owner/relation/replay 合同。

旧 M8-M28 debug endpoints 和 pre-M29 upload chain 已被 M30.2.2 移出 active runtime。不要通过环境变量、兼容 route 或旧诊断链路把它们恢复成产品路径。

## 任务路由

- 产品范围和验收：读 `docs/product/`。
- 当前主链架构和代码地图：读 `docs/architecture/` 与 [docs/engineering/current-mainline-code-map.md](docs/engineering/current-mainline-code-map.md)。
- DSL、Renderer、后端、插件边界：读 `docs/architecture/`。
- 测试、验证、代码风格、文档维护：读 `docs/engineering/`。
- 运行、发布、调试、迁移：读 `docs/runbooks/`。
- 外部接口、环境变量、术语、历史草稿：读 `docs/reference/`。
- 重大技术决策：读 `docs/decisions/`。ADR 是历史决策记录，不等于全部仍是 active runtime。
- 执行计划：读 `docs/plans/`。
- 缺陷复盘和回归保护：读 `docs/bugs/`。

## 计划规则

以下任务必须先写计划：

- 影响多个模块或目录。
- 修改 DSL、API、数据模型或运行方式。
- 增加依赖或工程脚本。
- 实现插件、Renderer、后端、识别管线中的任一核心能力。
- 修复会影响主链路的缺陷。

计划生命周期必须和目录一致：

- `docs/plans/active/` 只放真实下一阶段工作。
- 已完成计划必须移入 `docs/plans/completed/`。
- 已替代计划必须移入 `docs/plans/archive/superseded/`。
- 已暂缓计划必须移入 `docs/plans/archive/deferred/`。
- 不允许 `active` 目录保留 `completed`、`deferred` 或 `superseded-by-*` 状态文件。

## 实现约束

- 先保持 DSL -> Figma 稳定，再逐步增强 PNG -> DSL。
- 保持模块边界清楚，不把后端识别、Renderer 和插件 UI 混在一起。
- 优先小而稳定的实现，不为未来功能提前加抽象。
- 复杂区域优先 fallback，不能让局部失败拖垮整页生成。
- 修复 source ownership 问题必须从 raw M29 / M29.2 source 合同修起；禁止在 M30、Renderer 或 plugin 里按文字内容、颜色名、中文语义或样式补丁伪造结果。
- `pixelOwner` 和 `replayDecision` 是回放权限门，不是视觉猜测标签。看不懂、算不准、无法证明 cleanup 安全的对象，应保留在 raster/fallback/report，而不是勉强画成 editable node。
- M29.3 relation kernel 必须保持纯 bbox/geometry 逻辑；不要在下游业务文件里再写一套 contains/near/duplicate 规则。
- M29.4 cluster 始终是 weak structural evidence。`row_like`、`column_like`、`background_anchor_like`、`repeated_item_like` 不提供组件化、Auto Layout、Figma Component/Instance 或 materialization 权限。
- M29.5 replay plan 是 M29 Direct 前的最后质量门。可见层顺序、去重、node budget、cleanup 授权必须由 plan 控制。
- M30 只能 materialize trusted M29 evidence。它不创建新 bbox，不重写 raw M29 JSON，不把 future cluster/semantic hint 当组件真值。
- AI/OCR/视觉 provider 输出不能直接成为 DSL 权威，必须经过 M29/M30 合同、质量门禁和校验。
- 上传主链路默认返回 M30 DSL；M29 Direct 只作为 compare variant。
- 任何行为、接口、数据模型、环境变量、运行步骤变化都必须更新文档。

## 验证要求

- DSL 变更必须有 schema 或等价校验。
- Renderer 变更必须能用假 DSL 验证。
- 后端 API 变更必须有接口级验证。
- 插件 UI 或浏览器可见行为变更必须做本地可视化验证。
- Bug 修复必须有回归保护；无法自动化时必须在 bug 记录里说明。
- M29 owner/relation/replay/cleanup 改动必须先映射到 [docs/engineering/m29-contract-regression-matrix.md](docs/engineering/m29-contract-regression-matrix.md)，没有覆盖就先补测试。

## 阶段提交规则

- 一个 M 阶段完成后必须形成独立 git commit，提交信息使用该阶段的实际能力描述，例如 `feat: add low-risk text replacement harness`。
- 阶段 commit 必须只包含本阶段范围内的代码、测试、文档、ADR 和计划更新；不得把下一阶段探索、临时调试、storage、dist、密钥或无关本地改动混进去。
- 阶段计划的验收项完成后，先提交阶段 commit，再在该提交之上运行完整验证命令；验证失败时用后续 fix commit 修正，不能把多个阶段攒成一个大提交。
- 开始下一阶段前必须确认 `git status --short` 干净，或者明确记录并隔离用户未提交的无关改动。
- 小的阶段内修正可以追加在同阶段 commit 前；阶段验收通过之后再出现的新问题，应按 bug fix 或下一阶段单独提交。

## 完成定义

任务完成必须满足：

- 实现或文档改动完整。
- 对应计划状态更新。
- 相关文档同步更新。
- 验证命令或人工验证记录清楚。
- 阶段级工作已经按阶段提交，且提交边界清楚。
- 如果涉及 bug，bug 记录包含根因、修复、回归保护和验证证据。
