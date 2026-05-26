# 08 M29.6 Media Internal Decomposition

## 1. source truth
本层认定的“物理事实”是：
* **复合 preserve_raster 媒体区域内的原始图像像素值**（RGB 字节通道数据）。
* **OCR 文字边界框与空间锚定拓扑**（OCR 识别出的节点在媒体内的相对偏移）。
* **底册中粗筛出的原始符号/形状节点（Raw Nodes）**。
本层旨在解决大块 preserver_raster 栅格媒体图像（如一个复杂的卡片背景、带有图标的按钮、或整排底部 Tab 栏）将内部的矢量 Icon 或可交互按钮背景“整吞”的物理问题。它通过非 OCR 像素前背景扫描和 OCR 邻近几何锚定，把媒体内部潜在的 UI 控件片区分解为“内部候选节点”与“内部组”。

## 2. input artifacts
本层读取的输入文件包括：
* **源 PNG 二进制数据**：`source_png`（用以提取像素值 `PngPixels`）。
* **M29.0 原始图**：`m29_document`（提取 `nodes` 与 `blocked`）。
* **OCR 结果文档**：`ocr_document`（提取 `blocks` 文字区域）。
* **M29.2 源 UI 物理图**：`m292_document`（提取已归类为 `preserve_raster` 的大媒体节点）。

## 3. output artifacts
本层写入的输出报告/数据：
* **媒体内部物理分解报告**：`media_internal_decomposition_report.json`。
包含 `compositeMediaItems`（被分解的母媒体）、`textMasks`（文字遮罩）、`internalCandidates`（分解出的 icon/shape 候选）、`matchedInternalGroups`（组合出的行动栏/Tab 组）、`rejectedFragments`（被排除的碎屑）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **阶段主入口**：[extract_m29_media_internal_decomposition_report](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/pipeline.py#L16)
* **核心解析器**：[build_composite_media_items](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L26)
  * 对每个符合条件的媒体对象：
    * 提取内部 OCR 文字构建文字遮罩 [build_text_mask](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L110)。
    * 综合评分原始 raw nodes 及像素扫描出的前景连通域 [score_internal_candidates](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L133)。
    * 过滤、融合碎屑 [merge_anchor_icon_fragments](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L398)。
    * 横向扫描并合成行级行动组 [build_matched_internal_groups](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L548)。

## 5. decision authority
* **决策权**：**无**。
* **说明**：此层也是纯只读诊断报告面（`meta.reportOnly = True`）。在此层所生成的 `internalCandidates` 候选人，其决定是 `accepted_report_candidate`，但这只表示“它是一个合格的前景图标候选人”。本层不能批准将此候选人恢复为正式的 Source Object。它只产生供后继 `m29_evidence_contract` 与 `internal_source_promotion` 消费的诊断事实。

## 6. report-only surfaces
* **报告面**：**完整**。
其产生的所有候选对象均标有 `"reportOnly": true`，且最终写入 `media_internal_decomposition_report.json`。

## 7. allowed facts
本层允许判定并记录的物理事实：
* `composite_media`：大媒体内部含有子结构的物理判定。
* `text_mask`：可编辑文本区域周围 $3\text{px}$ 范围的遮罩（用于保护文本不被误识别为图标碎片）。
* `internal_icon_candidate` / `internal_shape_candidate`：媒体内部检测出的图标与背景板候选对象。
* `action_row` / `row`：通过多路锚定确认的对齐行动行（如一行按钮、一排 Bottom Tabs）。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止创建 Source Object**：不能直接将发现的像素连通域写进 M29.2 的 `sourceObjects` 列表。
* **禁止删除母媒体**：不能将 `preserve_raster` 的母媒体直接置为 `skip`，必须原样保留。

## 9. main formulas / gates
核心判定与计算公式：
* **候选人综合评分公式**：
  $$\text{score} = \text{size} \times 0.18 + \text{compact} \times 0.16 + \text{color} \times 0.12 + \text{anchor} \times 0.34 - \text{hero\_penalty} \times 0.20$$
* **碎屑排除门控 (Reject Gate)**：
  满足以下任一条件时，判定决策设为 `rejected_fragment`：
  1. $\text{text\_overlap} > 0.30$ （与文本遮罩高度重合）。
  2. $\text{area\_ratio} > 0.18$ （占用母媒体面积太大，可能为非图标大图）。
  3. $\text{separator\_not\_icon}$ （宽高比过于极端的分割线）。
  4. $\text{hero\_penalty} \ge 0.62 \text{ 且 } \text{anchor} < 0.35$ （纹理背景或主视觉中心大插图）。
  5. $\text{score} < 0.36 \text{ 且 } \text{anchor} < 0.35$ （总分过低且无强文本锚定）。
* **行动组评分与接受门控**：
  $$\text{confidence} = 0.40 + \text{row\_align} \times 0.25 + \text{gap\_stable} \times 0.20 + \min(N, 4) \times 0.035$$
  其中 $N$ 为行内项数。若 $\text{confidence} \ge 0.50$ 则组通过（`accepted`）。
* **前景像素二值化分类器 (`foreground_pixel`)**：
  满足以下全部条件判定为前景像素：
  1. $\text{color\_distance}(\text{pixel}, \text{bg}) \ge 55$ （与背景中值色差足够大）。
  2. $\text{saturation} \ge 15$ （不是极弱的噪声过渡像素）。
  3. $\text{luma} \ge 18$ （亮度在暗色背景下有可分辨对比度）。

## 10. thresholds and heuristic rationale
启发式阈值设定：
* `55` (color_distance)：提取图标等前景元件的色彩阀值。rationale：此距离在 RGB 空间能滤除卡片背景的普通渐变噪点，但保留彩色 icon 和白色控件边缘。
* `20` - `5200` (PIXEL_COMPONENT_AREA)：像素连通域的面积限制。rationale：小于 20 像素的块多为文字边角料或噪点；大于 5200 像素则属于大文本框或卡片边框，非独立图标。
* `10.0` (MAX_ASPECT_RATIO)：限制候选图标的长宽比。rationale：图标通常是近似方正的（如 24x24，32x32），如果长宽比超过 10 倍，大概率是表格横线、分割线或扫描边线，不应视为 icon。

## 11. known information loss
* **多组件截断损失**：在 `connected_pixel_components` 阶段，对每个窗口提取的前景连通域做面积排序后，强制执行了 `[:6]` 截断，**每个扫描窗口最多只保留前 6 个最大连通域**。如果大媒体内有密集的表格点、大量的小点，后面的节点将被无条件抛弃。
* **非文本锚定候选漏检**：因无 OCR 文本锚定而生成的 `generic_foreground_candidates` 的综合评分公式中，文本锚定占比低但基准要求分高达 `0.58`，相比 OCR 锚定的 `0.36` 门限严苛许多，这会导致无临近文本说明的独立悬浮图标（如卡片角落的关闭 'x' 号、未识别 OCR 的图形图标）很难被接受。

## 12. known failure symptoms
* **卡片内按钮/图标不可编辑**：若 `heroGraphicPenalty` 算式对带有大量渐变和背景花纹的卡片算出较高的惩罚值，导致卡片内部合格的图标被误判为 `hero_or_texture_fragment` 碎屑而拒绝，最终该图标无法被提升（promoted），无法编辑。
* **Tab栏/按钮行破损**：由于对齐行聚类器 `row_pair_clusters` 对 Y 轴漂移极为敏感（`center_y` delta 限制在 `text_threshold` 或 `icon_threshold`），若 OCR 行高或小图标有轻微像素偏移（如 2~3px），会分裂为不同的 rows，导致 `gap_score` 崩塌而丢掉整个 matched group，致使部分 icon 无法获得 group support 保护。

## 13. tests / guards
* **测试用例**：[backend/tests/test_media_internal_decomposition.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_media_internal_decomposition.py)
* **覆盖范围**：
  * `test_composite_media_with_internal_ocr_and_symbol_reports_candidate`
  * `test_text_mask_rejects_raw_component_overlapping_internal_ocr`
  * `test_repeated_icon_label_row_builds_matched_group_without_text_literal_rule`
  * `test_ocr_anchor_foreground_uses_multiple_relations_not_only_above_text`（多向扫描）
  * `test_non_ocr_foreground_component_inside_media_reports_candidate`（非 OCR 锚定前景）
  * `test_fragmented_icon_parts_with_same_text_anchor_get_union_candidate`（碎片融合）

## 14. artifact evidence
* **日志与文件证据**：
在 Task 输出目录下生成的 `media_internal_decomposition_report.json` 中，包含如下检测出的子候选记录：
```json
"internalCandidates": [
  {
    "candidateId": "media_01:internal_candidate_0001",
    "role": "internal_icon_candidate",
    "bbox": [100, 45, 24, 24],
    "candidateDecision": "accepted_report_candidate",
    "score": 0.72,
    "matchedOcrBoxId": "ocr_text_01",
    "anchorRelation": "above_text",
    "reasons": ["ocr_anchor_foreground_component", "local_pixel_foreground"]
  }
]
```

## 15. findings
* **P1 (raw_m29 / m29_6_internal_decomposition)**: 性能与架构违背风险。`connected_pixel_components` 采用纯 Python 手写 BFS/DFS 栈双循环去扫二值化 `bytearray`，在大分辨率图片和多个 preserve_raster 卡片并存的场景中，引发严重的 CPU 算力损耗，属严重的底层计算模式设计错误，应转移到 `image_math` 库调用 NumPy 或 C 加速的连通域标签化接口。
* **P2 (m29_6_internal_decomposition)**: 连通域上限截断缺陷。`[:6]` 硬截断逻辑在表格、复杂面板、具有很多小徽章/小圆点的复杂大媒体场景中会导致候选节点直接遗漏，属于特化写法的后遗症。

## 16. recommended next action
* **连通域算法加速重构**：将 [connected_pixel_components](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L893) 重构为矢量化计算，提取到隔离的 `image_math` 包中，利用 NumPy 或外部的高效连通域库替换。
* **扩展扫描机制**：将固定 5 向（上下左右近）的空间扫描框升级为辐射形多向投影，解决非标准偏角下的图标检测缺失问题。
* **废除硬截断**：使用与媒体区域面积正相关的动态上限阈值替换硬编码的 `[:6]`。
