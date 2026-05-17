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
- 当前状态：M26 工程阶段，已完成 DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路、真实 PNG deterministic region fallback DSL、visual primitive contract harness、OCR/DSL patch harness、百度 PP-OCRv5 异步 OCR provider、文字替换覆盖率扩展 harness、text replacement 质量控制、UI-aware text replacement sampling、text-primitive binding harness、component structure harness、DSL component annotation/layer naming harness、component-aware layer separation candidate harness、local asset slice/simple fill experiment harness、icon candidate extraction/crop harness、icon coverage audit/placement readiness harness、region-guided icon gap candidate harness、icon placement plan/layering readiness harness、visible icon fallback replay experiment harness、region-guided business icon candidate harness，以及 visual perception provider benchmark harness。
- 项目类型：`multi-end-frontend`。
- 一期目标：单张 PNG 上传后生成 DSL v0.1，并由 Figma Renderer 写入可编辑 Figma 设计稿。
- 一期硬边界：不做代码生成、Figma Component/Instance、Auto Layout、批量上传、账号、支付、额度、质量看板、多模型平台。

## 任务路由

- 产品范围和验收：读 `docs/product/`。
- DSL、Renderer、后端、插件边界：读 `docs/architecture/`。
- 测试、验证、代码风格、文档维护：读 `docs/engineering/`。
- 运行、发布、调试、迁移：读 `docs/runbooks/`。
- 外部接口、环境变量、术语、历史草稿：读 `docs/reference/`。
- 重大技术决策：读 `docs/decisions/`。
- 执行计划：读 `docs/plans/`。
- 缺陷复盘和回归保护：读 `docs/bugs/`。

## 计划规则

以下任务必须先写计划：

- 影响多个模块或目录。
- 修改 DSL、API、数据模型或运行方式。
- 增加依赖或工程脚本。
- 实现插件、Renderer、后端、识别管线中的任一核心能力。
- 修复会影响主链路的缺陷。

## 实现约束

- 先保持 DSL -> Figma 稳定，再逐步增强 PNG -> DSL。
- 保持模块边界清楚，不把后端识别、Renderer 和插件 UI 混在一起。
- 优先小而稳定的实现，不为未来功能提前加抽象。
- 复杂区域优先 fallback，不能让局部失败拖垮整页生成。
- 当前默认使用 fake OCR；可选接入百度 PP-OCRv5 异步 OCR，并在 `TEXT_REPLACEMENT_MODE=apply` 时对 quality gate 通过的 accepted 文字做可见替换；high-risk replacement 阻断，medium-risk replacement 记录风险但仍可应用。M14 通过 UI-aware sampling 减少 `complex_background` 误杀。M15 生成 text binding 报告，M16 生成 component structure 报告，M17 只把 M16 结构以 DSL element `meta/name` annotation 形式挂回 DSL，M18 只生成 layer separation candidate 报告和 simple fill candidate，M19 基于 M18 低风险候选生成本地 slice PNG 和 filled slice PNG 实验资产，M20 在 component 内部寻找高置信 icon bbox 并生成 icon PNG 候选资产，M21 审计 M20 icon 覆盖、漏裁 hints 和 future placement readiness，并生成 debug overlay，M22 把可靠 M21 missed hints 和少量 header/bottom-nav/trailing 局部 probe 补裁成本地 gap icon PNG 并生成 gap overlay，M23 把 M20/M22 icon 统一成 placement plan，判断 dedupe、fallback mask、slice coordination、blocked 和 futureDslNodeHint。M15-M23 都不改变 Figma 可见输出、不重组图层、不删除 fallback、不创建 Figma Component/Instance、不把 inferred containers/components 写回 primitives。M24 默认 `ICON_VISIBLE_FALLBACK_ENABLED=false`；显式开启后只消费 M23 placement plan，把 M20/M22 已裁出且低风险的 nav/header/leading icon 通过 `icon_fallback_cover` shape + `visible_icon_fallback` image node 小范围回放，并只把实际使用的 icon asset 追加进 DSL assets。M25 默认开启，基于稳定区域 probe 裁 bottom nav、primary button trailing arrow、shortcut tile、metric card、room card、trailing、tip/info 等业务 icon 候选 PNG；M25 只追加 DSL 顶层 meta，不新增可见节点，不修改 DSL assets，不把 icon 放进画布。M25 不做全图无边界 detection，不做 Codia 式全量拆层，不处理插画、头像、建筑或床位平面图复杂资产，不做 SVG/icon 语义识别、图标库匹配、AI inpainting，不引入 Pillow/OpenCV。M26 默认 `PERCEPTION_BENCHMARK_ENABLED=false`，只在显式开启或 smoke 脚本中生成 visual perception benchmark report，把 `current_rules`、可选 OpenCV、可选 SAM2 automatic mask 和可选 UIED command adapter 放到统一指标/overlay 下比较；M26 不修改 DSL/Figma 输出、不裁新 icon asset、不把 provider 输出当 Renderer 输入，也不把 torch/sam2/opencv-python 作为生产依赖。M27 应基于 M26 证据做 SAM2/OpenCV 候选过滤实验，不能继续盲目扩张固定区域规则。AI/OCR/视觉 provider 输出不能直接成为 DSL 权威，必须经过合同、决策、采样策略、质量门禁、绑定、结构聚合、annotation、分层候选、切片候选、icon 候选、coverage audit、gap candidate、placement plan、visible fallback replay、business icon candidate、perception benchmark 和校验。
- 上传主链路默认返回带 hidden `candidate_text` 的 enhanced DSL，但 fallback 视觉输出必须保持稳定。
- 任何行为、接口、数据模型、环境变量、运行步骤变化都必须更新文档。

## 验证要求

- DSL 变更必须有 schema 或等价校验。
- Renderer 变更必须能用假 DSL 验证。
- 后端 API 变更必须有接口级验证。
- 插件 UI 或浏览器可见行为变更必须做本地可视化验证。
- Bug 修复必须有回归保护；无法自动化时必须在 bug 记录里说明。

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
