# 12 Final Replay and Materializer

## 1. source truth
本层认定的“物理事实”是：
* **重放计划中已核准的重放动作与擦除指令（M29.5 Replay Plan）**。
* **晋升后的物理图数据（M29.2 Promoted Source Objects）**。
本层是整个后端的“生产线终点”。它不进行任何所有权推导、关系判断或计划规划。它的唯一物理使命是作为一个纯粹的“计划执行者”，消费重放计划与物理图，将抽象的 `text_replay`、`image_replay`、`icon_replay`、`shape_replay` 物化为具象的 Figma DSL 树节点，并物理对底层栅格切片资产（Fallback 图像与 Copied Image 图像）执行背景擦除（像素重置）。

## 2. input artifacts
本层读取的输入文件包括：
* **源 PNG 原始文件**：`source_png`。
* **原始 M29 Primitives 图**：`m29_document`（提供底册节点）。
* **OCR 文本图**：`ocr_document`。
* **晋升修改后的 M29.2 源图**：`m292_document`（即 `source_ui_physical_graph.promoted.json`）。
* **M29.5 重放计划报告**：`m295_replay_plan`。
* **后物化阶段容器组报告**（可空）：`hierarchy_report` / `sibling_group_report` / `layout_energy_report` / `auto_layout_permission_report`。

## 3. output artifacts
本层写入的输出文件包括：
* **Figma 消费的生产级 DSL 描述文件**：`design.dsl.json`（最终用于 Figma Plugin 还原矢量的核心 DSL 交换结构）。
* **物化报告**：`materialization_report.json`（汇总重放节点数、擦除组件数与警告）。
* **物理修改后的 Fallback 与 Copied 栅格图片**：写入 `assets/m29_fallback/` 和 `assets/m29_image/` 目录中的同名 PNG 文件（已被涂抹擦除掉对应文字/图标前景像素的背景切片）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **物化器总入口**：[build_plan_driven_dsl](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/builder.py#L26)
  * 执行源背景采样与基础命名空间初始化。
* **重放循环分发器**：[replay_m295_plan_items](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/replay.py#L14)
  * 对计划项分发 `text_replay`（构建 text DSL）、`image_replay`（裁剪切片并关联）、`icon_replay`（处理透明资产关联与裁剪）、`shape_replay`（矢量背景重放）。
* **擦除与抠图执行器**：
  * [clean_text_from_copied_image_assets](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L14)：文本背景物理涂抹。
  * [clean_internal_assets_from_copied_image_assets](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L72)：图标背景物理遮罩擦除。
  * [erase_replayed_bboxes_from_fallback](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L284)：全局 Fallback 图像擦除。

## 5. decision authority
* **决策权**：**执行权/只读于计划**。
* **说明**：此层拥有**最高的 DSL 生成与图像像素修改决策权**，能够对 PNG 文件进行覆盖写入。但它在“所有权”上是**完全无决策权**的。物化器严禁发明任何擦除指令、严禁把计划中设为跳过的图标强行画出来、严禁私自修改坐标或改变字体颜色推导。它必须 100% 遵照计划进行物理拼装，任何违反计划的私自重放都是架构越权（P0 级事故）。

## 6. report-only surfaces
* **报告面**：**无**（此阶段已进入正式生产输出阶段，生成正式的交付物 `design.dsl.json`）。

## 7. allowed facts
本层允许判定并生成的物理事实：
* DSL 中的矢量节点、样式树（`fontSize`、`color`、`textAlign`、`radius` 等）。
* 图像资产依赖项（`assets` 列表中声明的切片 ID 与相对 URL）。
* 擦除后的背景像素值（在 PNG 背景切片上）。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止自行推导所有权**：不能在计划外自行识别文本或图标。
* **禁止无授权擦除**：如果在 M29.5 计划项的 `cleanupTargets` 里找不到对应被擦除媒体 ID，物化器绝对禁止去修改该媒体 PNG 的任何像素，防止造成越权擦除。

## 9. main formulas / gates
核心擦除与装配门控：
* **节点预算门控**：
  $$\text{len}(\text{replayed}) < \text{options.max\_total\_visible\_nodes}$$
  若超出预算则强制跳过重放（`node_budget_exceeded`）。
* **带 Alpha 遮罩擦除判定 (`erase_with_alpha_mask`)**：
  在擦除 Copied Image 时，如果 promoted icon 拥有 alpha 数据（即由透明资产报告抠出来的 PNG 字节流），则计算亚像素映射坐标下的 alpha 值。
  当且仅当：
  $$\text{alpha\_value} > 32$$
  时，才会将大图在该坐标处的像素涂抹为背景色中值 `fill`。这保证了擦除边界与图标轮廓精确重合。

## 10. thresholds and heuristic rationale
启发式阈值设定：
* `32` (Alpha Gate)：判定擦除与否的 alpha 边界。rationale：在透明 RGBA 图标中，边缘过渡像素的 alpha 通常在 0 到 255 之间渐变。若把 alpha 很小的半透明边缘也作为擦除依据，会导致擦除区域外溢，将大卡片背景抠出一个毛边明显的白洞。将其设为 32 可过滤掉过渡羽化边，确保抠图精准。

## 11. known information loss
* **废弃项彻底抛弃**：任何最终被设为 `suppress_duplicate`、`fallback_only` 的节点及其空间信息在 DSL 中被彻底丢弃，只在 materialization 报告的 `skippedItems` 中留存。
* **样式退化**：复杂的字体类型统一退化为了默认的 `"Inter"` 字体，复杂的阴影、内发光、多重填充在 `simple_shape_replay` 里丢弃或简化为单色 `fill`。

## 12. known failure symptoms
* **ghosting (重影)**：若擦除阶段因图片解码失败（空 try-except）被跳过，导致重放的矢量文字依然压在底图文字上，显示双层叠影。
* **Figma 物理大白洞**：若擦除授权被误算（例如将 fallback 擦除当成了 copied 擦除），会导致母媒体图片在 Figma 中呈现大面积刺眼的白色块或透明破洞。

## 13. tests / guards
* **测试用例**：[backend/tests/test_upload_preview_pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_upload_preview_pipeline.py)
* **验证能力**：在全流程集成测试中检验是否能正常生成 `design.dsl.json`，且 `materialization_report.json` 中无 error 异常。

## 14. artifact evidence
* **物理证据**：
Task 输出目录中的 `design.dsl.json` 包含矢量树，而 `assets/` 下包含已被像素级抹除的背景切片。

## 15. findings
* **P0 (plan_materializer)**: 异常悄然吞没缺陷。在 [cleanup.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L40) 等多处核心图像操作函数中，存在 `try-except Exception: continue` 的空捕捉写法。若遇到不支持的 PNG 深度或压缩块损坏，系统会彻底跳过物理擦除并不抛出任何异常，导致线上出现高频的双影 bug 却无法从日志捕获。
* **P1 (plan_materializer)**: 硬限节点预算隐患。硬编码的 `max_total_visible_nodes` 限制了重放的最大节点数。对于长截图或极其复杂的 UI 界面，超出预算的可见控件会被悄无声息地丢弃，前台无任何显式红线提示，带来极差的用户感知。

## 16. recommended next action
* **消除吞异常模式**：将 [cleanup.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L40) 等位置的空捕捉重构为带日志记录的警告，并在 `materialization_report.json` 中物理写入 `"warnings"` 列表，防止默默失败。
* **设计还原度监控**：加入设计漏重放比率统计，当跳过节点占总节点比率超过 15% 时，应自动在 B-stage 报告中计为严重低分并发出预警。
