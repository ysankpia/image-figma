# ADR 0011: 先用 DSL Patch Builder，再做可见可编辑还原

- 状态：accepted
- 日期：2026-05-16

## Context

M8 已经证明 AI/CV 输出只能作为 visual primitive candidates。下一步如果直接把 OCR 文字渲染到 Figma 画布，会出现明显的双层文字：fallback 截图里已有文字，新增 Figma Text 盖上去只要有一点错位就会变差。

真正的可见文字替换需要背景重建、底板识别、文字区域清除和更细资产裁切。M9 不该把这些问题混进 OCR 合同层。

## Decision

M9 先实现 DSL patch harness：

- OCR 输出先落成 `OCRDocument v0.1`。
- OCR + visual primitives 只生成 `DSLPatchDocument v0.1`。
- patch builder 只支持添加 hidden `candidate_text`。
- 默认 `DSL_PATCH_MODE=debug`。
- `/dsl` 可返回 enhanced DSL，但 candidate text 默认 hidden。
- patch validation 失败时回退 M7 base DSL。
- 插件和 Renderer 不改。

## Consequences

好处：

- 识别结果第一次进入 DSL，但不会破坏视觉输出。
- patch 可单独查询、测试和回退。
- M10 可以在这个基础上做局部可见替换。

代价：

- M9 不会让最终 Figma 画面明显更可编辑。
- Layers 会出现 hidden candidate text。
- fake OCR 只服务合同和调试，不代表真实识别质量。

## Non-Goals

- 不接真实 OCR。
- 不做背景擦除。
- 不做可见文字替换。
- 不生成 Auto Layout。
- 不让 AI 直接输出 DSL。
