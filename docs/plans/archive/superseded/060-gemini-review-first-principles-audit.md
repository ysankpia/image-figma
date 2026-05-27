# Gemini Review First-Principles Audit

- 状态：superseded
- 创建日期：2026-05-26
- 负责人：未指定

归档说明：Gemini 审核已作为参考输入使用，后续主线由 062/063/068 及当前 model-first 代码地图收口。本文不再代表 active work。

## Goal

对 `/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma-gemini` 中的 Gemini 审核报告做代码事实核验，区分：

- 已被当前代码和仓库文档证明的正确结论；
- 已过期、路径错误、事实错误或推断过度的结论；
- 真实存在但需要另开阶段处理的架构风险；
- 不应立即执行的重写、依赖、Go 化、模型化或下游补丁建议。

本计划的核心不是接受外部审核结论，而是把它还原成当前 `image-figma` 主线代码、M29 合同和测试证据能够证明或反驳的事实。

## Scope

包含：

- 读取 Gemini 审核报告并提取核心主张、风险和建议。
- 对照 `AGENTS.md`、`docs/index.md`、当前主线代码地图、M29 contract regression matrix 和实际代码。
- 核验 materializer、M29.6、transparent asset、evidence contract、internal source promotion、image_math 边界和测试覆盖。
- 输出需要保留、修正、删除、延后或转成 bug/plan 的结论。
- 形成后续阶段执行顺序，但不在本计划内直接重构主链。

不包含：

- 不经代码核验就接受 Gemini 的架构建议。
- 修改 public API、DSL schema、Renderer、Figma plugin protocol 或 upload-preview runtime 行为。
- 为单张图片、固定文案、固定坐标、主题色、文件名或样本路径添加特化。
- 直接执行 Go 重写、SAM/ONNX 引入、Poisson/Inpainting 引入或大规模删除历史包。
- 在 materializer、Renderer 或 plugin 下游补 source ownership 问题。

## The 5 Audit Tasks

1. **Report Fact-Check**
   - 逐项核验 Gemini 报告中的路径、模块名、测试数量、依赖边界、主链顺序和阻断级别。
   - 输出 `correct / stale / wrong / unverified` 分类。

2. **Runtime Boundary Audit**
   - 核验 M29.6、transparent asset report、M29 evidence contract、internal source promotion 和 M29.5 replay/materializer 的权限边界。
   - 重点确认 report-only 层是否越权创建 visible node、asset replacement、cleanup authorization 或 DSL mutation。

3. **Math Contract Simplification Audit**
   - 找出 bbox、containment、overlap、confidence、EvidenceScore、Z-order、cleanup risk、alpha risk 等数学公式是否重复、分散或语义混乱。
   - 判断哪些应保留为纯 kernel，哪些应上升为合同，哪些只是历史阶段遗留。

4. **Legacy / Dead Path Inventory**
   - 盘点 M29 历史审计包、未被主链调用的 package、legacy routes、legacy report surfaces 和文档残留。
   - 只输出删除/归档候选，不在本阶段直接删除。

5. **Next-Stage Refactor Plan**
   - 根据前四项事实核验，形成最小可验证的后续阶段计划。
   - 每个阶段必须有 owner layer、禁止修复方式、targeted pytest、真实样本/产物核验和 commit boundary。

## Acceptance

- 本计划文件归档于 `docs/plans/archive/superseded/`，作为 Gemini 审核参考输入的历史记录。
- Gemini 报告的结论不会被直接当成事实；所有判断必须指向当前代码、docs 或测试。
- 输出包含提交紧急性判断：哪些需要现在提交，哪些应等审计完成后再提交。
- 输出包含真实风险优先级：P0/P1/P2/P3 必须基于当前代码证据，而不是报告措辞。
- 输出包含后续执行建议，但不越过用户确认直接开始大规模重构。

## Validation

- `git diff --check`
- `git status --short --branch`
- 只读核验命令，包括但不限于：

```bash
rg --files backend/app
rg -n "import (numpy|PIL|skimage|orjson|rich)|from (numpy|PIL|skimage|orjson|rich)" backend/app backend/tests -S
rg -n "SearchBar|Card|充值|提币|划转|买币|filename|taskId|theme|brand|fixed|hack|special|coordinate|bbox" backend/app packages figma-plugin -S
rg -n "cleanupTargets|copied_image_asset|pixelOwner|replayDecision|allow_visible_replay|materialize_controlled_structure|contiguous|positions" backend/app -S
```

必要时再运行 targeted pytest。只读审计阶段不需要全量 `uv run pytest -q`，除非审计结论依赖当前测试状态。

## Notes

- 当前 `image-figma-gemini` 是外部审核输入，不是本仓库 source truth。
- `AGENTS.md`、`docs/index.md`、当前主线代码、M29 contract regression matrix 和测试才是本仓库可执行事实源。
- 若审计发现 source ownership 缺陷，修复层仍必须是 raw M29 / M29.2 / evidence chain，不允许在 materializer、Renderer 或 plugin 下游补丁。
