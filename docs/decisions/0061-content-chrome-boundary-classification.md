# ADR: Content-Chrome Boundary Classification

- 状态：accepted
- 日期：2026-05-22

## Context

在 M37 (Hierarchy Readiness) 和 M38 (Controlled Hierarchy Materialization) 阶段中，系统通过 M31 物理重建单元来将平铺的 M30 节点组织到透明的 `group` 容器中。然而，如果重建单元在物理上跨越了“内容区域”（Content，如滚动卡片、列表项、文本）与“系统外壳”（Chrome，如固定页头、底部导航栏、悬浮操作按钮），将会导致它们被错误地打包在同一个 M38 容器下。这极大地破坏了可编辑设计稿的局部移动性。

我们需要在 M30 物化与 M37 审计之间，引入一个通用的 Content-Chrome 边界分类器，对 M30 DSL 中的每个节点进行性质分类，并在 M37/M38 中加以约束，避免“内容与外壳混合打包”。

## Decision

1. **引入独立阶段 `m39_boundary_classification`**：
   - 运行在 M30 `m30_asset_publish` 阶段之后，M37 `m37_hierarchy_readiness` 阶段之前。
   - 读取并修改 M30 DSL 中的节点，在其 `meta` 下写入 `"boundaryClassification": "chrome"` 或 `"boundaryClassification": "content"`。
   - 默认开启，但可通过 `M39_CONTENT_CHROME_CLASSIFICATION_ENABLED=false` 回退到 M39 前行为；关闭时不生成 `m39/` report，也不写 `boundaryClassification`。
   - 分类范围仅限已物化 M30 节点：`m30_text_member`、`m30_shape_candidate`、`m30_visual_asset`、`m30_composite_media_asset`。`fallback_region` 与 `original_reference` 永远不参与分类。

2. **分类逻辑设计**：
   - **相对几何规则（Rule-based Baseline）**：
     - Viewport 顶部 12% 区域（如状态栏、页头 Header）和底部 12% 区域（如底部导航栏 Tab Bar/Footer），且其宽度跨度较大时，判定为 `chrome`。
     - Viewport 右侧边缘悬浮物（如 `x > 0.8 * PageWidth`，且宽度与高度均小于 Viewport 尺寸的 20%），判定为 `chrome`。
     - 其它中心区域的元素默认为 `content`。
   - **模型候选提议器（YOLOv8 ONNX Proposer）**：
     - 若环境中存在 `numpy`、`Pillow`、`onnxruntime`，且模型文件存在，则动态加载本机 `/Volumes/WorkDrive/Models/model_fp16.onnx` 运行 YOLOv8 目标检测。
     - 输入尺寸强制缩放为 640x640，提取检测框（Chrome/Content 候选区域），滤除置信度低于阈值（如 0.25）的检测框并运行非极大值抑制（NMS）。
     - 将检测框映射回原始图像尺寸。如果 M30 节点与模型检测到的 chrome 候选框重叠比例超过阈值（如 0.8），且不违背核心几何安全边界（例如在屏幕正中心大面积卡片绝不能是 chrome），则分类为 `chrome`。
     - 如果依赖缺失、模型文件不存在、输出 shape 不符合预期或推理失败，则记录 `modelSkippedReason` 和 warnings，降级为纯相对几何规则，非阻塞运行。
     - 模型只能提出候选，不能绕过几何安全规则，不能直接成为 DSL 权威。

3. **M37/M38 联合约束**：
   - 在 M37 (`hierarchy_readiness.py`) 中：审计每个重建单元映射的所有 M30 子节点。如果这些子节点中既有 `chrome` 又有 `content`，则该重建单元是不安全的，在其 `unsafeReasons` 中标记 `"boundary_classification_conflict"`。
   - 在 M38 (`hierarchy_materialization.py`) 中：跳过所有存在分类冲突（即 `boundary_classification_conflict`）的重建单元，绝不将它们物化为 group。
   - `m30_composite_media_asset` 可以作为 M38 可移动 child，但仍必须先通过 M37 safe direct-match，且不得跨 content/chrome 边界。

4. **产物输出与可观测性**：
   - 在阶段运行结束时，向 `storage/m30_1_uploads/{taskId}/m39/m39_boundary_classification_report.json` 写入报告，包含分类汇总指标、`modelSkippedReason`、warnings、模型候选数量和各节点最终判定。
   - 在 `stage_timings.json` 中记录 `m39_boundary_classification` 耗时和状态。
   - 提供只读接口 `GET /api/tasks/{taskId}/m39-boundary-classification`，返回 summary、warnings、`modelSkippedReason`、classifiedNodes、report path 和 stageTimings。

## Consequences

### 好处

- 阻止了 Chrome 节点与 Content 节点被打包进同一个 Group 容器中，保证了设计稿被 Figma 消费时的合理结构。
- 通过“规则判定 + 模型提议（非真值源）”的架构，安全地利用了 YOLOv8 模型的高召回率，同时利用几何安全规则（中心卡片兜底为 content）防止误杀。
- 模型、ONNX 运行时、Pillow、numpy 都是非阻塞加载的，具备极高的鲁棒性，不会因为本地可选依赖缺失导致上传失败。
- M39 有显式开关，便于把问题定位回 M39 前后的行为差异。

### 代价

- 增加了一个新的 DSL 变动阶段和报告，略微增加了总上传管线的耗时（在有 ONNX 运行时，约增加数百毫秒的 CPU 推理时间）。
- 存在两层冲突判定开销（M37 判定 unsafe，M38 跳过），但因为都在内存中处理，开销极小。
- 可选模型路径是本机配置，默认值仅适合当前开发机；生产环境必须明确配置或关闭模型 proposer。
