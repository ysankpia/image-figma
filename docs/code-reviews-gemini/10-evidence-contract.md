# 10 Evidence Contract

## 1. source truth
本层认定的“物理事实”是：
* **复合媒体检测与连通域置信度 (M29.6)**：图标作为几何候选的本体置信度。
* **透明资产抠图可行性报告 (M29 透明资产)**：该组件从大背景图里能否以物理色差切图分离的真实可行性。
本层扮演了“最高证据链法庭”的角色。任何媒体内部候选节点在晋升（Promotion）并真正影响 DSL 之前，必须在本层通过“正向证据”与“负向证据/风险惩罚”的数学代数模型检验，确认抠图成功且重放风险在可控范围内，以解决特化规则过多和单样本特例的脆弱性。

## 2. input artifacts
本层读取的输入文件包括：
* **M29.2 源 UI 物理图文档**：`m292_document`（提供原始物理对象）。
* **M29.6 媒体内部物理分解报告**：`media_internal_report`（提供检测到的内部候选图标 `internalCandidates`）。
* **M29 透明资产生成报告**：`transparent_asset_report`（提供每个候选人的透明分析记录 `items`）。

## 3. output artifacts
本层写入的输出报告/数据：
* **证据合同合规性审查报告**：`evidence_contract_report.json`。
包含 `contractItems`（列出每个候选人的证据网评分及晋升决策 `promotionAllowed`）与 `summary`。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **流水线主入口**：[extract_m29_evidence_contract_report](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/pipeline.py#L14)
* **合同项构建引擎**：[build_contract_items](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/pipeline.py#L65)
  * 对分解出来的内部图标候选运行 [build_m296_contract_item](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/scoring.py#L17)。
  * 对已在物理图中但具有遮挡标记的对象运行 [build_label_anchored_blocked_contract_item](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/scoring.py#L113)。
* **多维证据算分函数**：[score_evidence](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/scoring.py#L175)
* **最终晋升决策门控**：[decision_mode](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/scoring.py#L192)

## 5. decision authority
* **决策权**：**无/报告层面**。
* **说明**：本层是决策前置的审计把关层，输出 `promotionAllowed: true`。尽管字段取名为“允许晋升”，但此层依然属于 report-only 边界（`meta.reportOnly = True`），它并不物理将节点插入 M29.2，该动作由后继的 `internal_source_promotion` 消费并执行。

## 6. report-only surfaces
* **报告面**：**完整**。
结果详细生成并记录在 `evidence_contract_report.json` 中。

## 7. allowed facts
本层允许判定并记录的物理事实：
* `allow_visible_replay`：判定该候选图标可以且必须作为独立矢量重放，同时其背景需实施擦除。
* `report_only`：证据不够充分，不予物理重放，但保留在报告中作诊断。
* `reject`：存在严重的物理冲突风险（如文本压盖、尺寸异常），予以拒判。
* `promotionAllowed`：标示该候选人是否通过合同审计，允许物理晋升。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止回写 M29.2 物理图**：在此层运行时，不能直接更改 `m292_document` 字典内容。
* **禁止修改 PNG 切片**：不能因为评分低去物理删除 `assets/transparent/` 下的 PNG 切片。

## 9. main formulas / gates
核心检测与判定门控逻辑：
* **正向证据算分公式 (`positive`)**：
  $$\text{pos} = \text{candidate\_score} \times 0.20 + \text{size\_compact} \times 0.12 + \text{text\_anchor} \times 0.16 + \text{containment} \times 0.12 + \text{repetition} \times 0.10 + \text{relation} \times 0.10 + \text{transparent\_allowed} \times 0.20$$
* **负向证据/风险惩罚算分公式 (`negative`)**：
  $$\text{neg} = \text{text\_overlap\_penalty} \times 0.20 + \text{hero\_penalty} \times 0.16 + \text{cleanup\_risk} \times 0.12 + \text{repair\_cost} \times 0.08$$
* **总分计算**：
  $$\text{evidence\_score} = \text{clamp01}(\text{pos} - \text{neg})$$
* **晋升条件判定门控 (`allow_visible_replay`)**：
  必须同时满足以下条件：
  1. $\text{hard\_reasons}$ 列表为空。
  2. $\text{evidence\_score} \ge 0.68$ （满足可见度评分要求）。
  3. $\text{transparent\_allowed}$ 为真（抠图切片文件成功生成）。
  4. $\text{execution\_supported}$ 为真（即候选人置信度为 high，或得到对齐行动行的 group_supported 强力支持）。
  5. $\text{media\_containment} \ge 0.95$ （基本完全被包含在母媒体内，无外溢破损）。
  6. $\text{text\_overlap} \le 0.20$ （与文本无严重覆盖遮挡）。
  7. $\text{hero\_penalty} \le 0.42$ （无主视觉背景误判风险）。
  不满足以上任一条件，但 $\text{evidence\_score} \ge 0.42$ 时判定为 `report_only`；否则判定为 `reject`。

## 10. thresholds and heuristic rationale
启发式阈值设定：
* `0.68` (ALLOW_VISIBLE_THRESHOLD)：晋升为矢量独立节点的评分门限。rationale：此值设定反映了对“不要轻易擦除”的防御性立场，必须至少有 $68\%$ 的正面物理证据，且没有任何严重风险项，才能授权下游擦除原图背景并晋升。
* `0.95` (MIN_MEDIA_CONTAINMENT_FOR_VISIBLE)：完全包含比例阀值。rationale：如果一个图标与母媒体卡片只有 80% 的包含关系，说明它在边缘半进半出，若强行擦除背景，会在卡片边缘抠出一个难看的半圆锯齿，因此必须要求 $\ge 95\%$ 的包含度。

## 11. known information loss
* **物理特征数值退化损失**：将精细的像素灰度变化、文字对齐偏角、空间微小的 overlap 面积等，降解、退化为了一个由固定权重相加的线性浮点数（`evidence_score`），在边界值上有可能发生“正负项强行拉平”的信息损失。

## 12. known failure symptoms
* **孤立图标无法点选（不晋升）**：若界面中存在单独悬浮的图标（如卡片右上角的关闭 'x' 叉号、单独的 settings 齿轮），因周围没有 OCR 文本锚定，无法获得 `textAnchorScore` 分数，会直接触发 `is_unanchored_generic_foreground` 判定为硬拒绝 `generic_foreground_not_visible_replay`，导致该 icon 沦为 reject 不允许晋升，使得 Figma 中该图标只能跟着大图一起栅格化，无法编辑。
* **高价值图标被 alpha 牵连拒绝**：如果图标自身物理特征极佳（`evidence_score` 高达 0.85），但由于其压盖的卡片背景色极难抠图导致 `transparent_allowed` 为假，该节点依然会被一票否决降级为 `report_only`。

## 13. tests / guards
* **测试用例**：[backend/tests/test_m29_evidence_contract.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_m29_evidence_contract.py)
* **覆盖范围**：
  * `test_high_evidence_internal_icon_allows_visible_replay`（标准晋升成功流）
  * `test_transparent_reject_keeps_candidate_report_only`（透明度一票否决）
  * `test_high_text_overlap_rejects_internal_icon_contract`
  * `test_generic_non_ocr_foreground_is_not_promoted_even_with_alpha`（无锚定前景色硬拒绝）
  * `test_anchored_group_supported_non_ocr_foreground_can_pass_evidence_contract`（组支持下的非 OCR 前景通过）
  * `test_label_anchored_blocked_icon_is_audit_only_not_promotion_contract`

## 15. findings
* **P1 (evidence_contract)**: 无锚定图标硬拒绝设计缺陷。在 [hard_rejection_reasons](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/scoring.py#L209) 中，任何无 OCR 文本锚定的小图标（`is_unanchored_generic_foreground`）都会直接被 `reject`。这违背了真实样本中“界面中常常存在无字独立图标”的物理第一性原理，限制了该系统的通用性。
* **P2 (evidence_contract)**: 色彩渐变大背景导致连锁被否。由于正向证据中 `transparentAsset` 具有绝对否决权（`transparent_allowed == True`），卡片或按钮的轻微渐变造成抠图拒绝，会无条件抹杀掉一切几何特征完全正确的图标。

## 16. recommended next action
* **解耦无锚定硬拒绝条件**：对没有临近 OCR 的小前景连通域，如果其在视觉重复性（`repetition`）或对齐组（`group_supported`）中表现优异，应当允许晋升，取消在无文本锚定时的无条件硬拒。
* **引入非透明重置降级**：对于无法生成透明切图的高置信度图标候选人，提供“无需擦除背景、但依然单独导出矢量占位框”的重放方案，替代简单粗暴的无条件废弃。
