# 095 Unified Vision: Section-Based Layout Relationship Experiment

- 状态：active
- 创建日期：2026-06-01
- 分支：`feat/editable-draft-layer-pipeline`
- 负责人：Codex
- 前置依赖：094 Stage 8A（materialize + HTML flex preview）已完成

## Problem Statement

当前 HTML preview 已能用 flex 暴露 row 结构错误。问题已经从“渲染层遮住错误”降级为“布局关系归属层质量不足”：M29/OCR 给出精确 bbox 和文字，现有 vision detector 给出单元素角色，但它们都没有可靠回答“哪些 evidence 属于同一组”。纯几何 `cluster.BuildRows` 只能按 y-center、gap、bbox union 猜测关系，因此会产生 mega-row、过大 gap、重复/错误 row 归属。

Unified Vision 的目标不是让模型生成 HTML、Figma 或最终树，而是让模型只提出“关系分组建议”和少量文本样式建议。bbox、OCR text、asset crop、materialize 分类仍由 Go 确定性 pipeline 掌权。

## Current Evidence

旧 095 中的两个判断已经被复测推翻：

- `<=45 items` 不是稳定安全线；39、36、21、14 items 的 batch 都可能出现错误。
- errors 不主要是 unknown id；更常见的是 duplicate ownership、single-member group、局部 overflow，以及模型试图表达嵌套关系但 v1 flat 合同无法承载。

最新四图 Python smoke 复测结果：

| case | sections | calls | groups | overflow | validation errors | coverage | time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| t018 | 4 | 6 | 34 | 2 | 6 | 59% | 184s |
| t022 | 6 | 6 | 30 | 0 | 7 | 87% | 157s |
| lizhi | 8 | 8 | 26 | 0 | 1 | 85% | 187s |
| xianyu | 4 | 5 | 26 | 0 | 1 | 59% | 161s |
| total | 22 | 25 | 116 | 2 | 15 | - | - |

结论：方案有强信号，但还不是稳定产品路径。Go 主线必须以实验 artifact 并列输出，默认关闭，不覆盖 baseline。

## Architecture Contract

当前阶段实现 Go v1 flat experiment：

```text
M29/OCR/optional detector
-> segment.Build()              # 几何稳定分区
-> cluster.BuildRows()          # baseline，保持不变
-> materialize.Build()          # baseline visible leaves
-> Unified Vision experiment    # 只重组 accepted flat groups
-> deterministic validation
-> advisor/unified preview artifacts
```

产物并列输出，不覆盖 baseline：

```text
ui_layout_ir.v1.json
preview.html
html_preview_report.md
unified_vision/unified_vision_input.v1.json
unified_vision/unified_vision_result.v1.json
unified_vision/unified_vision_validation.v1.json
ui_layout_ir.unified_experiment.v1.json
preview.unified.html
html_preview_report.unified.md
```

## Batching Contract

第一层仍使用现有 section 分区。每个 section 内只发送 flow evidence：`text`、`textview`、`icon`、`image`、`imageview`。不发送 shape、line、substrate、texture fragment。

batch 不是只按数量切，而是按复杂度切。复杂度至少包含：

- item count
- y-band count
- role mix
- evidence density
- overlap/containment pairs
- horizontal gap variance
- large-gap count
- vertical span
- neighbor density

拆分顺序：

1. section 内真实垂直空白带；
2. y-band 分割；
3. y-center median；
4. 最后才按 hard item cap 切 chunk。

默认：`UNIFIED_VISION_MAX_ITEMS_PER_BATCH=30`，`UNIFIED_VISION_HARD_MAX_ITEMS_PER_BATCH=45`，`UNIFIED_VISION_MAX_COMPLEXITY=110`。这些是 provider 保护和注意力保护，不是质量保证。

## Prompt And Output Contract

模型输入：section crop、全局 bbox、crop-local bbox、evidence id、role、OCR text（只读参考）。

模型输出严格 JSON：

```json
{
  "version": "unified_vision_result.v1",
  "groups": [
    {
      "id": "group_1",
      "name": "short_name",
      "direction": "horizontal",
      "gap": 12,
      "members": ["evidence_id_1", "evidence_id_2"],
      "confidence": 0.8,
      "reason": "short reason"
    }
  ],
  "elementStyles": {
    "evidence_id_1": {"fontSize": 16, "fontWeight": 600, "color": "#111111"}
  },
  "ungrouped": [],
  "warnings": []
}
```

禁止模型输出 HTML/CSS/Figma、禁止新增 bbox、禁止新增或改写 text、禁止新增 asset、禁止嵌套 group。v1 是 flat contract；tree 是后续 Python 实验。

## Deterministic Validator

硬门：

- result version 必须正确；
- evidence id 必须存在；
- group 至少 2 个成员；
- 同一 evidence 只能被一个 accepted group 拥有；
- direction 只能是 `horizontal` 或 `vertical`；
- confidence 默认 `>=0.70`；
- fit ratio 默认 `<=1.01`，并且按 group union bbox 计算，不按整个 section 宽度放水；
- gap 默认 `<=96`；
- cross-axis spread、actual max gap、gap variance 必须过阈值；
- text style 只允许作用于 text evidence，fontSize/color 范围必须合法。

拒绝的 group 不进入 experiment IR，必须记录 rejection reason。provider 失败或 batch 缺结果时，该 batch 保持 baseline/fallback，不阻塞 baseline compile。

## Retry Contract

重试分两类：

- transport retry：HTTP/断连/429/5xx/520 等 provider 问题，默认 3 次；
- semantic repair retry：JSON 可解析但 validator 拒绝时，把失败 batch 和 rejection summary 发回模型修复，默认 1 次。

第一轮全绿不走 repair。repair 后仍失败则拒绝/fallback，不能静默接受。

## Style Scope

第一阶段只消费 text style：

- `fontSize`、`fontWeight` 写入 text node meta；
- `color` 写入 text node `Style.Fill`；
- HTML preview 渲染这些 text style。

container background、borderRadius、shadow 暂时只保留在 raw result/validation，不作为可见背景权威，避免制造新的 ownership 重叠。

## 095B Python Tree Experiment

Go v1 flat 已经证明安全边界可跑通，但四图质量门槛未过。主要失败不是 provider 或 renderer，而是 flat contract 不能表达真实 UI 的嵌套关系。因此 095B 进入 Python tree P0 实验，不直接回迁 Go。

tree contract 允许 group 引用 group，也允许 group 引用 evidence。validator 必须检查：group id 唯一、child ref 存在、无环、无 self reference、leaf evidence 最终单 ownership、group 不能多父引用、每层 bbox 从 children 计算、每层 fit ratio/cross-axis/gap/gap-variance 通过。

P0 只输出 `unified_vision_tree_result.v1.json`、`unified_vision_tree_validation.v1.json` 和四图 Markdown 指标，不生成 IR。P0 明显优于 flat 后，才做 P1 tree preview；P1 四图和额外样本通过后，再决定是否回迁 Go。不要直接把 tree 写进 Go。

095B v2 稳定化结果：

- `missing_roots` 改为 deterministic root normalization，不再把 roots 漏写当成模型结构失败。
- 低 confidence node 改为 ignored，不计入 rejection，不占用 ownership，不触发 repair；模型 confidence 不是物理事实源，物理安全仍由 bbox/fit/gap/ownership validator 负责。
- Python tree provider runner 支持 batch 并发，默认复用 `UNIFIED_VISION_CONCURRENCY=3`。
- `tools/unified_vision_tree_smoke_4img.sh` 支持 `UNIFIED_VISION_TREE_FAST_INPUT=true`，用于只导出 Go input/fallback、不重复运行 Go flat provider。

v2 四图 fast 结果：hard invariants 全绿，tree repair 从 v1 的 55 次降到 3 次。`t018/t022/lizhi/xianyu` tree coverage 分别为 `0.4331 / 0.5139 / 0.7241 / 0.4810`。额外复杂样本 hard pass，tree coverage 从 v1 的 `0.3670` 提升到 `0.4312`，repair 从 `18` 降到 `1`，但仍低于 baseline auto-layout coverage，说明 tree 方向有效但不能回迁 Go。

当前判断：tree P0 的安全性和执行成本已经可控；剩余瓶颈是 accepted coverage 不足和部分 parent 物理 overflow。下一步如果继续，应做 P1 preview/apply 的最小实现或继续优化 tree coverage，而不是恢复 flat prompt 调参。

## Do Not

- 不要删除 `cluster.BuildRows`；它是 baseline 和 fallback。
- 不要删除 Python experiment scripts。
- 不要恢复 Python `/api/upload-preview` 为 Draft runtime。
- 不要恢复 Codia generation route。
- 不要让 Codia golden JSON 进入 generation runtime。
- 不要按样本名、品牌、文案、固定 bbox、固定坐标、固定屏幕尺寸写规则。
- 不要让模型成为 bbox/text/asset/materialize 分类权威。
- 不要让 Python tree 读取 Codia golden JSON；Codia 只能作为结构参考或离线 eval。

## Acceptance

最低验收：

- `UNIFIED_VISION_ENABLED=false` 或未传 `-unified-vision` 时 baseline 行为不变；
- `-unified-vision` 会生成并列 unified artifacts，不覆盖 baseline；
- provider 缺失/失败时 baseline compile 成功，unified validation 记录 fallback batch；
- Go validator 单测覆盖 unknown id、duplicate ownership、single-member、overflow、high spread、bad gap、bad style、horizontal/vertical accepted group；
- 四图 smoke 输出 baseline vs unified 对比：rows、overflow/high-gap、coverage、fallback、OCR mismatch、bbox drift、duplicate ownership、zero-flow rows、provider calls、repair attempts；
- OCR mismatch = 0，bbox drift = 0，accepted duplicate ownership = 0，zero-flow rows = 0；
- 四图都必须相对 baseline 改善，不能靠错误 group 虚高 coverage。
- Python tree P0 必须输出 baseline/flat/tree 三方对比，硬门为 OCR mismatch = 0、bbox drift = 0、duplicate leaf ownership = 0、cycle = 0；质量门为 tree coverage 不低于 flat，且物理拒绝不高于 flat。
