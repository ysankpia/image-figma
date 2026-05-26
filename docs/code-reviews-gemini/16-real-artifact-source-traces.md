# 16 Real Artifact Source Traces

## 1. source truth
本层认定的“物理事实”是：
* **真实任务 `task_33428579a6f7` 中物理输出的各阶段 JSON 报告与错误标记**。
本层通过对线上真实还原失败样本（Google 登录图标未被提取、文字可编辑但按钮无法拖拽、底部 Tab 栏图标丢失等典型断点）进行全链路物理追溯（Source Tracing），定位整个 Pipeline 中各层物理阀门对证据链的具体拦截行为，解释断点产生的核心机理。

## 2. input artifacts
本层读取的输入文件包括：
* `backend/storage/upload_previews/task_33428579a6f7/` 下的所有报告目录：
  * `m29_media_internal_decomposition/media_internal_decomposition_report.json`
  * `m29_transparent_assets/transparent_asset_report.json`
  * `m29_evidence_contract/evidence_contract_report.json`
  * `m29_internal_source_promotion/internal_source_promotion_report.json`

## 3. output artifacts
本层写入的输出报告/数据：
* **真实样本链路追溯报告**：`real-artifact-source-traces`（即本报告文档）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* 各检测层报告的预检和过滤规则判断分支点。

## 5. decision authority
* **决策权**：**无/纯追溯记录**。
* **说明**：只做数据溯源，不修改任何后端代码。

## 6. report-only surfaces
* **报告面**：**完整**。
结果呈现在本文件中。

## 7. allowed facts
本层判定并记录的物理事实：
* **总晋升图标数为 0**：在 `task_33428579a6f7` 中，`promotedSourceObjectCount` 为 0，而 `rejectedCandidateCount` 高达 146。
* **主要拒判原因**：
  * $89$ 个候选人因为 `internal_candidate_not_execution_supported` 被拒。
  * $27$ 个候选人因为 `internal_candidate_not_accepted` 被拒。
  * $10$ 个候选人因为 `unstable_background` 被拒。
  * $12$ 个候选人因为 `edge_alpha_risk` 被拒。

## 8. forbidden facts
本层绝对禁止判定或干预的事使：
* **禁止手动修复该 Task**：不在此处人工合成或强制晋升该 task 中的任何图标。

## 9. main formulas / gates
物理拦截过程中的关键控制门：
* **门控 1**：透明资产预检中 `confidence == "high"` 或 `groupSupportedExecution == True`。
* **门控 2**：抠图分析中 `variance <= 18.0`（背景稳定门控）。
* **门控 3**：边界泄露 `edgeAlphaMean <= 12.0`（截断风险门控）。

## 10. thresholds and heuristic rationale
拦截阈值设定：
* 参见第 15 篇阈值台账。例如，`variance > 18.0` 和 `edgeAlphaMean > 12.0` 在这起 Trace 任务中直接击落了 22 个候选人。

## 11. known information loss
* **无信息损失**：本篇为纯追溯分析。

## 12. known failure symptoms (典型故障 Trace 还原)

### 故障 A: Google 图标未被提取（“文字可编辑但图标沦为栅格背景”）
* **物理事实表现**：在最终 Figma 设计中，Google Button 上的 `"Google"` 文字是矢量可编辑的，但其旁边的 Google "G" 彩色图标无法独立点选，只能作为一个大 Preserved image 背景。
* **管线物理拦截追溯 (Trace)**：
  1. **M29.6 连通域检测**：Google 图标作为 `pixel_anchor` 前景块被成功扫出，但由于其属于中值对比度且旁边文字锚定分不高，被判定为 `"confidence": "medium"`。由于该图标不是横向排列的 Bottom Tab bar 成员，无法获得 Repetitive 对齐行群组支持，`groupSupportedExecution` 标记保持为 `False`。
  2. **M29 透明资产预检**：因为 `confidence == "medium"` 且 `groupSupportedExecution == False`，触发准入风险 `internal_candidate_not_execution_supported`（89例中的一员），导致**该图标被一票否决**，直接跳过了抠图处理，`assetPath` 置为空 `null`。
  3. **证据合同判定**：因为 `transparentAssetPath` 为 `null`，正向证据中的 `transparentAsset` 评分降为 `0.0`，最终得分低于 0.68，决策被判定为 `report_only` / `reject`，不被允许晋升 (`promotionAllowed = False`)。
  4. **物化还原**：物化器未收到该图标的 `icon_replay` 晋升指令，只能将其残留在母媒体大卡片中，仅将 label 重放为文本。

### 故障 B: 底部 Tab 栏图标丢失 / 破损（“Selected Marker 丢失”）
* **物理事实表现**：界面底部的 Tab 栏图标（例如选中的高亮蓝点、彩色圆圈）在 Figma 中完全丢失，或者抠出来后边缘残缺不齐。
* **管线物理拦截追溯 (Trace)**：
  1. **M29.6 连通域检测**：小圆点/高亮 Marker 被识别为 `accepted_report_candidate`，并且因为底栏的 Repetitive 对齐行结构，顺利获得了 `groupSupported` 保护，通过了置信度准入。
  2. **M29 透明资产分析**：在对其执行背景颜色估值和边缘分析时，由于小圆点极小且直接贴在 Tab 栏的卡片边框上，其采样的边缘像素极易把卡片边线抓进来，导致 `bgVariance` 算出高达 `23.031`（如候选人 0001 的记录）甚至是 `59.375`（候选人 0004 记录），触发 `unstable_background` 拒绝；或者在边界处的 Alpha 平均值远超 12.0（候选人 0001 的 `edgeAlphaMean` 高达 `35.218`），触发 `edge_alpha_risk` 拦截，抠图流断裂，`assetPath` 置为 `null`。
  3. **结果**：缺少 `assetPath` 导致证据合同拒绝晋升，Selected Marker 最终被大卡片背景完全吞没。

## 13. tests / guards
* **测试用例验证**：在 pipeline 单元测试中，常使用无渐变的纯色底图，使得 `bgVariance` 恒等于 0，绕过了真实的 `unstable_background` 和 `edge_alpha_risk` 门禁，因此无法暴露该真实样本断点。

## 14. artifact evidence
* **物理证据**：
  查阅 `task_33428579a6f7/m29_transparent_assets/transparent_asset_report.json` 中关于 `"rejectionReasonCounts"` 的统计，明确证实了上述阻断链条在真实环境中的分布。

## 15. findings
* **P1 (m29_6_internal_decomposition / transparent_asset)**: 中等置信度节点的物理晋升死锁。`task_33428579a6f7` 中高达 89 个候选人因为没有得到 Row Group 组对齐支持（例如它是单独悬浮在卡片一角的 Google 'G' 图标），即便其物理抠图极其稳定，也依然因为中置信度在预检时被直接丢弃。这种对 Medium 置信度的“无群组保护即丢弃”策略，是造成 Google Icon 和多数独立功能图标大面积还原失败的核心物理根源。
* **P2 (transparent_asset)**: 局部边缘方差误算。对于贴边小图标，没有进行先验包围框微调缩小（Shrink bbox），而是把周边的边界硬线条强行抓入 Edge sample 中计算方差，导致背景被误判为“不稳定”而拒绝抠图，属于启发式计算几何层面的粗糙封装。

## 16. recommended next action
* **打破 Medium 晋升死锁**：重构预检门控。对 Medium 置信度候选人，如果抠图判定为 `allow`（即物理背景极为稳定、边缘无泄露），应当免除对群组对齐支持的强制依赖，允许其参与合同审查与最终晋升。
* **引入收缩边缘采样机制**：在计算贴边极小组件（如选中 marker、徽标）的 edge samples 时，在原始 Bbox 内部向内收缩 1px 进行像素边界采样，剔除周边的背景卡片线条干扰，修正背景稳定度误判。
