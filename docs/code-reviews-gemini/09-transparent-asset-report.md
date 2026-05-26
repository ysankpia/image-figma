# 09 Transparent Asset Report

## 1. source truth
本层认定的“物理事实”是：
* **源 PNG 的二进制原始 RGB 像素数据**。
* **OCR 文本边界框与 M29.6 内部候选节点边界框**。
本层旨在评估候选图标/按钮是否能够从其周围背景中“干净、独立地抠图提取出来”。它读取原始像素值，评估背景色是否足够稳定一致（即不存在大范围渐变或复杂图像背景纹理），生成透明通道（Alpha Mask），并验证提取后是否会产生边缘截断或过度碎裂风险。

## 2. input artifacts
本层读取的输入文件包括：
* **源 PNG 二进制数据**：`source_png`（用以提取像素值 `PngPixels`）。
* **OCR 结果文档**：`ocr_document`（提供 `blocks` 用以评估文本遮罩）。
* **M29.2 源 UI 物理图**：`m292_document`（提供 `sourceObjects` 中已有的图标对象）。
* **M29.6 媒体内部物理分解报告**：`media_internal_report`（提供 `internalCandidates` 内部候选图标）。

## 3. output artifacts
本层写入的输出报告与资源：
* **透明资产生成报告**：`transparent_asset_report.json`（详细记录每个候选人的抠图决策、背景色和物理属性指标）。
* **透明 RGBA 图像切片**：`assets/transparent/{candidateId}.png`（在 `allow` 决策下，将生成的透明通道同像素数据合成写出的 RGBA PNG 切片文件）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **流水线总入口**：[extract_m29_transparent_asset_report](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/pipeline.py#L17)
* **预检收集器**：[collect_transparent_asset_candidates](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/candidates.py#L19)
  * 对 M29.2 中的已识别 raster_icon [is_m292_icon_candidate](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/candidates.py#L37) 以及 M29.6 的 internal_icon_candidate 进行收集预检，生成 `candidateAllowedForAlpha` 标记。
* **抠图与质量分析器**：[analyze_transparent_asset_candidate](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/alpha.py#L20)
  * 执行背景色采样估值 [dominant_background_sample](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/alpha.py#L183)。
  * 执行像素差二值化构建 Alpha 掩码 [build_alpha_mask](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/alpha.py#L219)。
  * 进行边缘 alpha 泄露和完整度过滤。

## 5. decision authority
* **决策权**：**部分/诊断**。
* **说明**：本层拥有判定“抠图动作是否允许（`allow` / `reject`）”的决策权，并物理输出抠图后的 RGBA PNG 文件。然而，本层本身依然属于 report-only 层面（`meta.reportOnly = True`，`meta.materializerConsumesAssets = False`）。即使本层产出了 `allow` 的透明切片，物化器此时也不会直接读取它，必须通过后继 `evidence_contract` 进行合规性促进后，才具有真正覆盖大图擦除的重放效力。

## 6. report-only surfaces
* **报告面**：**完整**。
结果写入 `transparent_asset_report.json`。为调试提供大量数值指标，如 `edgeAlphaMean`、`edgeAlphaCoverageGt32`、`largestComponentRatio`、`bgVariance` 等。

## 7. allowed facts
本层允许判定并记录的物理事实：
* `allow` / `reject`：该节点是否可以通过简单的色差抠图法进行提取。
* `backgroundRgb`：抠图提取所使用的背景色中值。
* `alphaProfile`：抠图的配置策略（普通图标为 `default_icon`，强锚定且高对比度的发光/软边缘图标为 `anchored_soft_edge_icon`）。
* `transparent_candidate_too_large` / `too_thin`：几何特征不符事实。
* `unstable_background`：卡片背景多色、复杂渐变或含有图片，无法定准抠图基底事实。
* `edge_alpha_risk`：像素主体触碰了截取边界，抠图会导致生硬的直线切边事实。
* `fragmented_foreground_mask`：图标主体抠出来后呈星散状碎裂，预示着有穿孔或大面积像素空缺事实。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止主动将大媒体剔除**：不能判定去删除或清空母媒体的重放。
* **禁止修改 DSL 的图源**：不能在此层直接强行替换正式的 DSL Image 节点属性。

## 9. main formulas / gates
核心检测与判定门控逻辑：
* **预检准入限制**：
  * 最大面积：$\text{area} \le 12000\text{px}^2$。
  * 文本重叠：$\text{text\_overlap} \le 0.20$。
  * 对于 M29.6 内部候选：要求 `confidence == "high"` 或具有 `groupSupportedExecution` 保护，且 `heroGraphicPenalty` $\le 0.42$。
* **背景稳定判定门控 (`dominant_background_sample`)**：
  * 主导背景覆盖率：$\text{coverage} \ge 0.36$ 且 $\text{cluster\_variance} \le 18.0$。
  * 或者是全局边缘中值差：$\text{all\_edge\_variance} \le 38.0$。
  满足以上任一条件，背景才被判定为 `stable`。
* **软边缘背景稳定判定门控 (`soft_edge_background_is_stable`)**：
  * 针对 `anchored_soft_edge_icon` 配置文件，要求更严格的覆盖率与变异系数：
    $$\text{coverage} \ge 0.32 \text{ 且 } \text{cluster\_variance} \le 8.0$$
* **对比度门控**：
  * 前景像素（到背景欧氏色差 $\ge 72$）比例 $\text{foreground\_ratio}$ 必须落入区间：
    $$0.04 \le \text{foreground\_ratio} \le 0.88$$
* **边缘 Alpha 溢出判定 (`edge_alpha_is_risky`)**：
  * 对于 `default_icon`（硬边缘图标）：若满足以下条件则拒判：
    $$\text{edgeAlphaMean} > 12.0 \text{ 或 } \text{edgeAlphaCoverageGt32} > 0.08$$
  * 对于 `anchored_soft_edge_icon`（发光/软边缘图标）：放宽到：
    $$\text{edgeAlphaMean} > 48.0 \text{ 或 } \text{edgeAlphaCoverageGt32} > 0.30$$
* **碎裂度判定**：
  * 抠出出的前景最大单连通域面积比例：
    $$\text{largest\_ratio} \ge 0.35 \text{（普通）} \text{ 或 } \ge 0.90 \text{（软边缘）}$$
    低于此门限判定为碎裂，予以拒判。

## 10. thresholds and heuristic rationale
启发式阈值设定：
* `12000` (MAX_TRANSPARENT_ASSET_AREA)：允许转换透明图标的最大像素面积。rationale：常见的 App 状态栏图标、动作栏小按钮面积通常在 16x16 到 80x80 之间，若超过 12000（相当于 110x110），极可能是一个整块的大插画或功能卡片，直接用色差法抠图会造成灾难性的画质破损。
* `12.0` (edgeAlphaMean)：默认硬边缘图标在边界处允许的最大 alpha 平均值。rationale：非透明边缘平均 Alpha 小于 12 代表图标像素与截图边界没有物理粘连，可以干净切出。若超过 12 甚至 32，说明图标已被边界截断，强行切出会出现一道整齐切平的白边/黑边。

## 11. known information loss
* **色彩细节损失 (Color Matting Loss)**：本层的 Alpha Mask 生成模型是基于“像素颜色距背景色的欧氏距离”来进行插值的非物理通道反褶算法。如果图标前景部分本身含有与背景极度接近的像素，这些区域的透明度会被强行算为接近 0，造成抠出后的图标内部出现不可预期的“空洞”。

## 12. known failure symptoms
* **渐变背景图标缺失**：当图标位于具有明显彩色渐变（如金黄色按钮、炫彩 banner 卡片）的 preserve_raster 媒体内部时，背景采样会因为 `variance > 18.0` 从而判定背景不稳定（`unstable_background`），直接拒判该图标的透明化处理，导致图标保留在大背景里不可点选。
* **发光图标被切边**：若发光图标（如发光蓝色小钩、带有渐变外阴影的 icon）未被判定为 `anchored_soft_edge_icon` 而是误用 `default_icon` 进行分析，其边缘阴影的 alpha 会触发 `edgeAlphaMean > 12.0` 门限被判定为 `edge_alpha_risk` 拒绝，导致无法抠图。

## 13. tests / guards
* **测试用例**：[backend/tests/test_transparent_asset_report.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_transparent_asset_report.py)
* **覆盖范围**：
  * `test_raster_icon_on_stable_background_allows_rgba_debug_asset`
  * `test_ocr_overlap_rejects_transparent_asset`
  * `test_unstable_background_rejects_asset`
  * `test_edge_alpha_risk_rejects_background_block_asset`
  * `test_group_supported_medium_internal_icon_uses_alpha_gate`
  * `test_anchored_group_supported_internal_icon_allows_soft_edge_glow`（软发光测试）
  * `test_internal_icon_uses_context_bbox_for_stable_action_strip_background`（扩展边界采样）

## 14. artifact evidence
* 在 Task 输出的 `assets/transparent/` 目录中生成实际的 RGBA PNG 图像。
* 并在 `transparent_asset_report.json` 中详细记录：
  ```json
  "items": [
    {
      "candidateId": "m29_media_internal_0001:internal_candidate_0002",
      "decision": "allow",
      "assetPath": "assets/transparent/m29_media_internal_0001:internal_candidate_0002.png",
      "backgroundRgb": [255, 255, 255],
      "bgVariance": 0.04,
      "alphaCoverage": 0.384,
      "edgeAlphaMean": 2.41,
      "edgeAlphaCoverageGt32": 0.02
    }
  ]
  ```

## 15. findings
* **P1 (transparent_asset)**: RGB 色彩空间评估的物理局限。使用直观的 RGB 欧氏距离在判断亮色、高亮发光边缘与渐变卡片时极易造成过度惩罚或过度松懈（由于人眼对绿、红、蓝敏感度不同，RGB 空间色差不能代表视觉上的一致性）。需要引入更优的感知色彩空间（如 CIELAB/HSV）进行色差判断。
* **P2 (transparent_asset)**: 诊断资产与生产脱节。虽然在 `assets/transparent/` 下物理生成了切图 PNG，但该模块作为 report-only 层，生成的资源对于 materializer 来说是“不可触达”的，除非中转层能够重新回写 DSL 并把资源路径重映射到这个 transparent 目录中。

## 16. recommended next action
* **升级色彩差值函数**：在 [foreground_pixel](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L883) 和 [dominant_background_sample](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/alpha.py#L183) 中引入 CIELAB 空间色彩差异公式，提升提取复杂控件时的稳定度。
* **生产路径穿透**：配置 `plan_materializer` 使其具备有条件读取并消费 `transparent_asset_report.json` 中 `assetPath` 的能力，实现真正意义上的透明切片上传。
