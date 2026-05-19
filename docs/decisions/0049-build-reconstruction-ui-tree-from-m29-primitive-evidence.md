# ADR: Build Reconstruction UI Tree From M29 Primitive Evidence

- 状态：accepted
- 日期：2026-05-20

## Context

PNG 设计图不是原始设计稿，而是所有图层绘制、透明混合和遮挡之后的压扁像素结果。M29 当前已经能从像素和 OCR 中提取可审计 primitive evidence，包括 text、shape、image、symbol、unknown 和 blocked evidence。

问题不在 M29 拆得碎。碎 evidence 是正确中间层。真正的问题是把这些 primitive evidence 直接推向 M30 DSL 会缺少三个核心事实：

```text
primitive 属于哪个视觉单元
这个视觉单元如何回退
拆分结果能否重新合成回原图
```

没有这层组织结构，局部证据可能正确，但全局重建会散。

## Decision

新增 M31 Reconstruction UI Tree，作为 M29 primitive evidence 和后续 layer recovery/materialization 之间的组织层。

M31.0 只做 script-only diagnostic：

```text
source PNG + OCR JSON + M29 nodes.json
-> primitive refs
-> reconstruction units
-> fallback unit crops
-> ownership/report/overlay
```

M31 不把 M29.0.2、M29.0.3、M29.0.4、M29.0.5 或 M30 DSL 作为主输入。它们可以作为历史 audit reference，但不能成为 tree 结构事实来源。

M31 不接插件上传主链路，不替换 M30 DSL，不删除 M29.0.x object-refinement chain。当前产品 runtime 仍保持：

```text
/api/upload-m30-preview
-> OCR + M29 + M29.0.x + M30
-> DSL
-> Renderer
```

## Consequences

好处：

- 把 M29 固定为 primitive evidence supplier，不再继续把 M29.0.x 规则堆成最终对象层。
- 引入 ownership、fallback crop 和 tree structure，开始解决“拆得碎但回不去”的根因。
- 为 M32 layer recovery plan、M33 recomposition validator、M34 DSL materializer 提供正确上游。

代价：

- M31.0 不改善插件可见输出。
- M29.0.2-M29.0.5 暂时仍保留，因为 M30 当前 runtime 仍依赖它们。
- 需要新增 tree/report/fallback crop 诊断产物，并用 ownership/fallback coverage 指标验证质量。

后续：

```text
M31.1 将 M31 诊断挂到 upload pipeline，但仍不作为 visible output
M32 从 reconstruction units 生成 layer recovery plan
M33 做 unit-level recomposition validation
M34 从 validated units 生成 DSL
M35 在 M34 替代 M30 供料后删除过时 M29.0.x object-refinement chain
```
