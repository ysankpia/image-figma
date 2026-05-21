# ADR: Nested Multi-Level Hierarchy Materialization

- 状态：accepted
- 日期：2026-05-22

## Context

在 M38 (Controlled Hierarchy Materialization) 阶段中，系统只能将平铺的 M30 节点物化为单层的 `group` 容器，直接放置在 Page 根节点下。任何嵌套或重叠的重建单元（例如卡片内的列表项，或者列表项内的按钮组）都会在平铺的 Z-order 碰撞检查或所有权冲突检查中被直接跳过。

真实的 UI 界面天然是多级嵌套的（如 Card -> Row -> Button/Text/Icon）。如果无法物化多级嵌套的 `group` 容器，将会极大限制设计稿的可编辑性与结构化质量。同时，当容器嵌套时，子节点在 DSL 中的坐标必须从绝对页面坐标转换成相对于其直接父容器的相对坐标，以便 Figma 能够正确渲染并支持拖拽。

因此，我们需要在 M38 的基础之上进行增强，设计并实现 M40 阶段，支持多级嵌套的容器物化和递归坐标变换。

## Decision

1. **确定下一阶段为 M40 (Nested Multi-Level Hierarchy Materialization)**：
   - 替换或在 M38 之后重构物化逻辑，支持多级嵌套的容器结构。
   - 默认启用嵌套物化开关 `M40_NESTED_HIERARCHY_ENABLED=true`，并将最大容器限制从 8 提升至 24，最大嵌套深度控制为 4。

2. **树形包容性判别与父子关系解析**：
   - 从 M37 审计通过的 safe 容器候选中，解析所有容器的 bounding box。
   - 通过几何包含关系（如 $Area(Parent \cap Child) / Area(Child) \ge 0.98$）判定父子关系。
   - 对容器进行面积降序排列（大容器在前），构建一个容器树/森林。若容器 B 包含在 A 中，且不存在中间容器 C，则 B 成为 A 的子容器。

3. **子节点深度归属分配**：
   - 对于每个 M30 可见节点，计算其归属的最小（最深层）容器。
   - Z-order 碰撞检查在同级容器或同级子节点间进行，不再执行全局平铺的冲突检测。若存在部分交叉重叠（而非完全包含），则判定为不安全并跳过该容器。

4. **递归坐标变换与 DSL 构建**：
   - 从根级 children 开始，递归遍历容器树。
   - 对于每个被移入父容器的子节点（无论是叶子节点还是子容器），将其 layout 坐标转换为父容器局部坐标：
     - $x_{local} = x_{absolute} - x_{parent\_absolute}$
     - $y_{local} = y_{absolute} - y_{parent\_absolute}$
   - 在节点的 `meta` 中记录 `m40ParentContainerId`、`m40OriginalPageBBox`，并保留 `rawLayout` 用于诊断和校验。

5. **硬性安全边界**：
   - `original_reference` 和 `fallback_region` 等根部 fallback 节点必须保持在 Page 根节点下，绝对不能被移入任何嵌套组中。
   - 必须在物化完成后执行绝对坐标漂移校验（`absolutePositionViolations`），确保在 Figma 中渲染出的绝对位置与原始位置完全一致，零漂移。

## Consequences

### 好处

- 完美还原了 Figma 设计稿中的嵌套组件结构，极大提高了图层目录的可读性和移动性。
- 通过允许完全包含的嵌套关系，消除了 M38 因为“重叠”而误杀嵌套单元的痛点，显著提高了安全容器的召回率。
- 坐标相对化后，直接拖拽父级卡片时，子级文本和图片会随之正确移动，完全符合 Figma 用户的操作直觉。

### 代价

- 坐标变换和 z-order 检查的逻辑从一维平铺升级为了树状递归，复杂度增加。
- 对 Renderer 提出了兼容性要求（必须能正确处理多级嵌套的透明 fill group）。
- 若绝对坐标计算错误，将导致渲染位置出现整体偏移，因此必须配有极其严格的绝对坐标漂移自动化校验。

## 显式非目标

- 不主动去识别新的 BBox，只消费 M37 readiness 已经审计为 safe 的候选。
- 不引入自动布局（Auto Layout）或 Figma 组件/实例（Component/Instance）。
- 不把 fallback 节点塞进嵌套组，fallback 必须始终平铺在最底层。
