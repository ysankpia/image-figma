# 07 Ownership Conservation

## 1. source truth
本层认定的“物理事实”是：
* **源 UI 物理图 (M29.2)** 中所有 Source Object 的物理存在（坐标 `bbox`、类别 `visualKind`、所有权决策 `pixelOwner` 与 `replayDecision`）。
* **空间区域关系图 (M29.3)** 中两两对象之间的拓扑关系事实（如包含 `contains`、重叠 `overlaps`、等价 `near_equal` 等）。
* **重放计划图 (M29.5)** 中最终计划重放决策（`finalReplayAction`、`targetRole` 与 `cleanupTargets` 擦除指令）。
本层通过比对以上三者，检验“重放节点的所有权”与“被擦除图像的所有权”在空间与拓扑上是否守恒、一致，是否存在“未擦除的重影（双影）”或“非法越权擦除（破洞）”。

## 2. input artifacts
本层读取的输入文件包括：
* **M29.2 源 UI 物理图文档**：`m292_document`（包含 `sourceObjects`，对应 `source_objects_*.json`）。
* **M29.3.1 空间关系报告**：`m2931_report`（包含 `edges`，对应 `region_relation_graph_report.json`）。
* **M29.5 重放计划报告**：`m295_report`（包含 `planItems`，对应 `replay_plan.json`）。

## 3. output artifacts
本层写入的输出报告/数据：
* **M29 物理守恒检验报告**：`ownership_conservation_report.json`。
包含 `sourceObjectClaims`、`visibleReplayClaims`、`cleanupClaims`、`conflicts`（冲突详情）与 `summary`（指标摘要）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **流水线入口**：[extract_m29_ownership_conservation_report](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/pipeline.py#L17)
  * 加载、规范化数据并调用 `detect_conflicts`。
* **冲突检测主引擎**：[detect_conflicts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/conflicts.py#L12)
  * 依次触发：
    * [detect_non_visible_claims](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/conflicts.py#L30)：不可见重放节点非法申领 visible role 校验。
    * [detect_visible_overlap_conflicts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/conflicts.py#L50)：可见重放节点间的空间重叠冲突。
    * [detect_missing_copied_cleanup](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/conflicts.py#L77)：可编辑文本重放但未对底层 preserve_raster 媒体声明局部擦除的漏擦校验。
    * [detect_invalid_cleanup_claims](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/conflicts.py#L111)：擦除声明合法性（越权擦除）校验。

## 5. decision authority
* **决策权**：**无**。
* **说明**：此层是纯只读诊断报告面（`meta.reportOnly = True`）。它不能修改任何 Replay Action，不能过滤重叠节点，也不能在运行时主动补上漏掉的擦除或撤销非法的擦除。所有的不一致性只会作为 `conflicts` 输出在报告中，不会在内存中自动订正，也不会阻断后续的物化渲染（除非上层调用者显式阻断）。

## 6. report-only surfaces
* **报告面**：**完整覆盖**。
生成 `ownership_conservation_report.json`，其中 `conflicts` 数组详细列出了每次冲突的 `type`、`severity` (warning/error)、涉及的 `sourceObjectIds`、`planItemIds`、空间 `bbox` 以及具体文字原因 `reason`。

## 7. allowed facts
本层允许判定并记录的物理一致性事实：
* `visible_ownership_overlap`：两个被重放的可见元素（如文本与图、图与图）在空间上发生无合理解释的重叠，预示可能有重影。
* `missing_copied_image_asset_cleanup`：可编辑文本完全落在 preserver_raster 媒体上，却漏掉了对此媒体的 copied_image_asset 局部擦除声明。
* `non_visible_action_has_visible_claim`：重放动作声明为隐藏/跳过，但却占用了可见的角色名。
* `invalid_fallback_cleanup_claim`：重放节点不属于可见项，却声明了 fallback 擦除。
* `invalid_copied_image_asset_cleanup`：重放节点声明对某个媒体对象进行局部擦除（copied_image_asset），但找不到空间包含/覆盖关系证据、或者该重放节点不是合法的文本/icon/背景。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止重写 Replay Action**：不能因为 `visible_ownership_overlap` 而将某个节点设为 `suppress_duplicate`。
* **禁止修改 bbox**：不能通过微调坐标来规避重叠冲突。
* **禁止修剪擦除区域**：不能动态为 materializer 新增擦除坐标。

## 9. main formulas / gates
核心检测与判定门控逻辑：
* **可见冲突重叠判定**：
  $$\text{intersection\_area}(A, B) > 0 \text{ 且 } (\text{overlap\_ratio}(A, B) \ge 0.20 \text{ 或 } \text{edge\_relation} == \text{"near\_equal"})$$
  若满足且无法通过 `overlap_is_explainable` 解释，则判定为 `visible_ownership_overlap`。
* **重叠可合理解释门控 (`overlap_is_explainable`)**：
  1. 包含 `shape_replay` 且另一方为 text/icon/image 时：视为合法的背景-前景重叠。
  2. `image_replay` + `icon_replay` 解释门：
     * icon 必须是由 M29.6 internal 提升（`promotionSource == "m29_6_internal_icon_candidate"`）且指定了 `transparentAssetPath`，且归属于该 media。
     * 或者 icon 具有 `labelAnchorOcrBoxId` + `blockedIds`，并且 icon 对该 media 具有擦除指令（`has_copied_cleanup_target`）。
  3. `image_replay` + `text_replay` 解释门：文本与 media 必须有关系网中的 text 包含关系，且文本拥有对 media 的 `copied_image_asset` 擦除。
  4. `icon_replay` + `text_replay` 解释门：必须满足 `is_promoted_internal_icon_label_overlap`。
* **提升图标与标签重叠门 (`is_promoted_internal_icon_label_overlap`)**：
  * icon 为 M29.6 提升的 internal 候选，且 icon 和 text 共同指向同一个 media 进行擦除，且：
    $$\text{textOverlapRatio} \le 0.14$$
* **擦除授权验证门控**：
  * 文本的 `copied_image_asset` 擦除：必须满足 `relation_contains_text`（M29.3 拓扑关系存在）。
  * 提升 icon 的 `copied_image_asset` 擦除：必须满足 `promotionSource == "m29_6_internal_icon_candidate"` 且 `mediaSourceObjectId` 匹配，且拓扑上包含。
  * 阻挡 icon 的 `copied_image_asset` 擦除：必须满足 `labelAnchorOcrBoxId` 与 `blockedIds` 存在，且拓扑上包含。
  * 背景 shape 的 `copied_image_asset` 擦除：必须是 `shape_background_contained_by_media` 且拓扑上包含。

## 10. thresholds and heuristic rationale
启发式阈值设定：
* `0.20` (overlap_ratio)：判断普通可见节点冲突的重叠率门限。设计 rationale：允许极边缘的轻微像素重合，避免噪声导致大量无谓警告，但超过 20% 则极可能发生遮挡或重影。
* `0.14` (MAX_PROMOTED_INTERNAL_ICON_LABEL_TEXT_OVERLAP_RATIO)：限制从媒体内部提取的 icon 与其说明 label 重合的最大比例。设计 rationale：因为 internal icon 从媒体切出时可能因边缘估计不准而划过标签，少于 14% 的重合被允许，超过则判定为严重的文字被图标切片截断风险。

## 11. known information loss
* **信息损失**：无。
* **原因**：本层是纯只读校验。但需要注意的是，本层为了简化判断，通过 `claims.py` 丢弃了具体的原始图像通道信息和 OCR 文本内容，仅保留了几何 BBox、ID 与 meta 标签进行逻辑代数运算。

## 12. known failure symptoms
* **ghosting (双影/重影)**：若 overlap 校验发生漏判，下游物化器既绘制了可编辑的文本/图标，又没有在背景大图（media）上把原来的文字/图标擦除掉，导致 Figma 中出现“一层矢量文字压在一层栅格图片文字上面”的重影瑕疵。
* **hole_punching (破洞/白底)**：若越权擦除（`invalid_copied_image_asset_cleanup`）在下游被强行执行，而实际该位置并没有可见元素覆盖，背景大图会被抠出一个无意义的透明白洞。

## 13. tests / guards
* **测试用例**：[backend/tests/test_ownership_conservation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_ownership_conservation.py)
* **覆盖范围**：
  * `test_ownership_conservation_records_basic_visible_claims`
  * `test_copied_image_cleanup_is_explainable_for_text_contained_by_media`
  * `test_copied_image_cleanup_is_explainable_for_promoted_internal_icon`
  * `test_unpromoted_icon_copied_image_cleanup_is_rejected`（校验非法擦除）
  * `test_promoted_internal_icon_low_label_overlap_is_explainable_when_both_cleanup_same_media`
  * `test_shape_background_copied_cleanup_target_is_valid_when_contained_by_media`

## 14. artifact evidence
* 在真实 Task 的输出目录中生成以下证据：
  * `ownership_conservation_report.json`
* 例如，若有异常，在 JSON 中会呈现类似以下段落：
  ```json
  "conflicts": [
    {
      "type": "invalid_copied_image_asset_cleanup",
      "severity": "error",
      "sourceObjectIds": ["icon_001", "media_002"],
      "planItemIds": ["plan_icon_001"],
      "bbox": [10, 10, 20, 20],
      "reason": "copied image cleanup target must be preserve_raster image_replay media"
    }
  ]
  ```

## 15. findings
* **P1 (evidence_contract / plan_materializer)**: 本层虽然能检测出 `invalid_copied_image_asset_cleanup` 这样严重导致“抠图破洞”的 `error` 级别冲突，但由于其设计为纯 `reportOnly: true`，物化阶段并没有任何阻断机制。下游 `plan_materializer` 依然会盲目读取 `plan_items` 中的 `cleanupTargets` 去进行裁剪抠图，可能直接引发线上渲染事故。
* **P2 (ownership_conservation)**: 空间重叠冲突门限（`0.20`）是针对全局的硬编码阈值，对于极小尺寸的 UI 控件（例如 10x10 的小徽标、圆形红点），20% 的重叠面积极小，轻微偏移就会低于该门限，导致漏警告。

## 16. recommended next action
* **阻断机制接入**：在 pipeline 顶层阶段或 `app/plan_materializer` 入口，检查 `ownership_conservation_report.json` 的 `summary.errorCount`。若大于 0，必须抛出 `OwnershipConservationError` 阻断导出，或在物化时自动丢弃该非法 `cleanupTarget` 声明，防止画面出现空洞。
* **动态重叠阈值**：将 `0.20` 重叠阈值重构为与 BBox 最小边长挂钩的动态自适应算式，对小尺寸节点实施更严格的重叠判定。
