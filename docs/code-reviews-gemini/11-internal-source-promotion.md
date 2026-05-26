# 11 Internal Source Promotion

## 1. source truth
本层认定的“物理事实”是：
* **原始 M29.2 源物理对象列表**。
* **M29.6、M29 透明资产和证据合同三层报告的合规性事实**。
本层是整个“物理提取/抠图”链条的物理落地点。它是从诊断、分析、报告面，过渡到正式**变更源所有权事实**（Source Ownership Mutation）的唯一桥梁。所有通过了合规性证据合同审计的内部候选图标，在此处被赋予正式的物理地位，写入晋升后的 `source_ui_physical_graph.promoted.json` 文档中，成为新主线中的 Source Objects。

## 2. input artifacts
本层读取的输入文件包括：
* **M29.2 源 UI 物理图**：`m292_document`（提供基础 `sourceObjects`，对应 `source_ui_physical_graph.json`）。
* **M29.6 媒体内部分解报告**：`media_internal_report`（获取候选人基础坐标与置信度）。
* **M29 透明资产报告**：`transparent_asset_report`（获取分析后生成的 `assetPath` 与分析用包围框 `analysisBbox`）。
* **M29 证据合同报告**：`evidence_contract_report`（核验 `promotionAllowed` 的合规决策）。

## 3. output artifacts
本层写入的输出报告与变动文档：
* **晋升修改后的 M29.2 源图文档**：`source_ui_physical_graph.promoted.json`（将晋升图标加入其中，该文档在后继管线中将替代原 M29.2 文档被 M29.3/M29.4/M29.5 消费）。
* **晋升阶段审查报告**：`internal_source_promotion_report.json`（记录晋升的详细对照表与被剔除的冗余项）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **流水线主入口**：[extract_m29_internal_source_promotion_report](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L13)
* **晋升装配引擎**：[build_promoted_objects](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L74)
  * 对每个候选人执行合规预检过滤 [reject_reason](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L157)。
  * 生成晋升对象结构 [promoted_object](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L183)。
* **空间去重过滤器**：[dedupe_promoted_objects](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L118)
  * 对坐标冲突节点进行排序和过滤，排序依据为证据评分 [promotion_rank](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L136)。

## 5. decision authority
* **决策权**：**有（关键写入权）**。
* **说明**：本层是决策变动层。它决定了哪些内部提取的小图标会正式拥有 `sourceObjectId`，决定了 `pixelOwner = "raster_icon"` 与 `replayDecision = "icon_replay"` 等所有权身份，物理改写了 M29.2 文档，并驱动后继重新运行 M29.3 拓扑计算、M29.4 组聚类及 M29.5 计划生成。

## 6. report-only surfaces
* **报告面**：**有**。
结果写入 `internal_source_promotion_report.json`。但注意，该阶段在 meta 中声明为促销专用（`meta.promotionOnly = True`），依然不直接操作公共 API 返回值或正式物化结果，所有的物理改写都是以副本文件（`.promoted.json`）的形式落地于临时 Task 目录中。

## 7. allowed facts
本层允许判定并记录的物理晋升事实：
* 正式晋升的 `raster_icon` 源对象。
* 携带的证据溯源事实：包括原始 rawNode 来源、抠图分析框（`transparentAssetBbox`）、抠图 PNG 物理文件相对路径（`transparentAssetPath`）以及对应证据网得分。
* 冗余扣留事实：因坐标重复而被丢弃的候选项及其 `reason = "duplicate_promoted_internal_bbox"`。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止偏置坐标**：不能直接在此层改变图标的中心坐标。
* **禁止提升非 raster_icon 类型**：此阶段不允许凭空创建文本（`editable_text`）或大块的 preservation 媒体节点，只能提升 `role == "internal_icon_candidate"` 类型的节点。

## 9. main formulas / gates
核心判定与过滤门控：
* **晋升一票否决预检门控 (`reject_reason`)**：
  若满足以下任一条件，无条件拒绝晋升：
  1. 缺少 M29.6 候选事实、或者其角色不是 `internal_icon_candidate`，或者决策为被丢弃的碎屑。
  2. 候选人声明的母媒体对象 ID 在底册 `base_ids` 中不存在。
  3. 包围框 `bbox` 格式非法。
  4. 缺少透明资产分析结果、或者是抠图决策为 `reject`，或者缺少生成的切片 PNG 文件。
  5. 缺少证据审查合同、或者合同模式判定不是 `allow_visible_replay`。
* **空间精准坐标去重门控**：
  在去重时，采用包围框坐标精确匹配：
  $$\text{tuple}(\text{normalize\_bbox}(A)) == \text{tuple}(\text{normalize\_bbox}(B))$$
  若匹配则判定为重复，仅保留 $\text{promotion\_rank}$ 得分最高的一个，其余判定为 `duplicate_promoted_internal_bbox` 剔除。
* **排序决策因子 (`promotion_rank`)**：
  去重时采用三元组降序排序：
  $$\text{rank} = (\text{evidenceScore}, \text{len(candidateId)}, \text{media\_id\_len})$$

## 10. thresholds and heuristic rationale
启发式阈值设定：
* 空间去重精确坐标匹配：去重算法中为了彻底消除多窗口重复扫描导致的物理冗余，引入了 bbox 精确碰撞。rationale：多路扫描窗口可能对同一个物理 icon 扫出几乎一样的坐标，若全部重放会导致 Figma 出现完全重合的多份矢量图层，拖慢 Figma 性能并造成结构混乱。

## 11. known information loss
* **亚像素/相近坐标去重漏网损失**：由于坐标碰撞采用的是**绝对精确匹配**（$x, y, w, h$ 必须完全一致），若两个扫描窗口对同一个图标定位产生哪怕 $1\text{px}$ 的漂移（例如一个是 `[10, 10, 24, 24]`，另一个是 `[11, 10, 24, 24]`），本层的去重算法将完全失效，导致两个几乎相同的图标被同时晋升，丢失了空间重叠过滤的信息。

## 12. known failure symptoms
* **矢量图层重合冗余**：Figma 导入后，可编辑图标在同一位置叠加了两层，在拖拽该图标时会拖出另一个一模一样的图标。原因正是上文所述的亚像素漂移导致 `dedupe_promoted_objects` 精准坐标去重漏判。
* **物理位置微移错位**：晋升时物理包围框使用了 `transparentAssetBbox`（通常会在原始 `candidateBbox` 基础上因背景采样而外扩数像素）。这导致最终生成的 icon 坐标比底册里的位置偏大偏下，产生视觉位置漂移。

## 13. tests / guards
* **测试用例**：[backend/tests/test_internal_source_promotion.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_internal_source_promotion.py)
* **覆盖范围**：
  * `test_internal_source_promotion_promotes_high_confidence_allowed_internal_icon`（成功晋升链）
  * `test_internal_source_promotion_rejects_medium_without_group_support_internal_icon`
  * `test_internal_source_promotion_uses_transparent_asset_analysis_bbox`（包围框外扩回写）
  * `test_internal_source_promotion_dedupes_same_promoted_bbox_by_evidence_score`（去重排序）

## 14. artifact evidence
* 在 Task 临时目录生成以下实证：
  * `source_ui_physical_graph.promoted.json`
* 打开该 JSON 可观察到 `promotedSourceObjects` 拥有完整的溯源标记：
  ```json
  "sourceEvidence": {
    "mediaSourceObjectId": "media_01",
    "mediaInternalCandidateId": "media_01:internal_candidate_0002",
    "transparentAssetPath": "assets/transparent/media_01:internal_candidate_0002.png",
    "promotionSource": "m29_6_internal_icon_candidate"
  }
  ```

## 15. findings
* **P0 (internal_source_promotion / plan_materializer)**: 去重策略过于脆弱（绝对精确匹配）。因为前端 OCR 和后端图像算法对连通域计算具有天然的不确定性，很容易产生 $1\text{px}$ 的差值，这使得目前的精确 bbox 匹配去重形同虚设，导致真实样本中大量出现重复矢量重合图层，属严重架构设计缺陷。
* **P1 (internal_source_promotion)**: 晋升类型特化限制。目前晋升硬编码只能产生 `raster_icon` 类型的对象。如果 M29.6 扫描出了母媒体内高可信度的子按钮矢量背景框（`shape`），此层无法将其晋升为 `control_background` 类型，限制了未来对矢量按钮背景的复用能力。

## 16. recommended next action
* **升级为重合度 (IoU) 去重**：将去重判断从绝对坐标相等，升级为交并比判定：
  $$\text{IoU}(A, B) \ge 0.80$$
  对 IoU 超过 80% 的候选人进行融合去重，彻底解决 1~2px 坐标偏差造成的重复图层问题。
* **解耦类型硬编码**：允许根据 M29.6 候选人的原始 `role`，自适应晋升为 `raster_icon`、`control_background` 或 `shape_geometry`，提高提取矢量组件的通用性。
