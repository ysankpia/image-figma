# 图片转 Figma 可编辑设计稿项目：代码审核报告、第一性原理分析与技术规划

> Superseded reference. This report was written before the Go Codia Beta backend became the active `Generate Beta` path. Its Python-first recommendations are historical context only. Current Codia Beta work belongs to `services/backend-go`, `docs/plans/active/090-openai-compatible-ui-detector-short-pass.md`, `docs/bugs/open/017-codia-like-beta-ui-role-detector-gap.md`, and `docs/engineering/current-mainline-code-map.md`.

本报告旨在从第一性原理出发，对 `image-figma` 项目进行全链路代码审计，评估当前架构阶段，识别潜在风险，并为下一步迈向 "Codia 级" 图片转 Figma 可编辑设计稿产品制定严密的演进路线与可靠性体系规划。

---

一、 <!--总判断-->

### 1. 当前代码库处在什么阶段？
当前代码库处于 **“B 阶段（B-stage）Report-only 智能诊断 + 早期 C 阶段结构化物化（Controlled Structure Materialization）试验期”**。
* **物理证据链（Evidence Pipeline）已跑通**：系统具备从 raw M29 Primitives 到 M29.2 Pixel Ownership，再到 M29.5 Replay Plan 的完整数学合同。
* **诊断与物化已分层**：绝大多数高阶能力（如布局能量、Auto Layout 许可、兄弟组与层级候选、媒体内部二次分解）目前均采用 `report-only: true` 模式运行，不会越权污染可见 DSL 树；
* **物化器行为克制**：目前的 `plan_materializer` 为 flat 结构，且内置了 `materialize_controlled_structure_groups`，可以安全地根据 sibling group 与 hierarchy 候选产生透明无效果的结构组（C Group），同时锁死了 Auto Layout、组件、Token、变量与 Variant 等物化逻辑，符合 B 阶段防错控险的安全边界。

### 2. 当前项目最大的优势是什么？
* **极具前瞻性的“数学合同（Mathematical Contract）”地基**：基于像素拓扑、包容关系（Containment Ratio）、IoU 与外环差值（Boundary Delta）等物理证据来推演所有权，而不是用纯黑盒 AI 端到端直接生成 DSL。这使得生成的设计稿具有物理可追溯性与确定性。
* **清晰的模块边界与分层**：
  * **DSL v0.1 契约所有者**：[packages/dsl-schema/](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/packages/dsl-schema) 负责 DSL 验证，确保 Renderer 与 Backend 严格解耦。
  * **纯物理层决策分离**：`raw M29` 仅提出 Primitive（形状/文字/图像/符号碎片），而 `M29.2` 决策所有权，`M29.5` 负责重放规划与清理授权（Cleanup Authorization），物化器 `plan_materializer` 仅作被动执行。
* **高标准的工程回归纪律**：全链路具备 325 个覆盖面广、反应灵敏的自动化测试，每一次对 Pixel Ownership、Dedupe、Relation Kernel 的修改都能得到快速回归验证。

### 3. 当前项目最大的风险是什么？
* **隐性特化逻辑的萌芽**：在 [detectors.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive/detectors.py) 中，依然存在部分硬编码启发式分类，如根据面积硬判 ellipse 是 `badge_background` 还是 `small_ellipse`，以及基于文本包含硬编码分类 unknown。这类规则虽然简单高效，但若缺乏对“有限控件背景数学模型”的提炼，容易退化为特化逻辑。
* **缺少真正的置信度概率校准（Calibration）**：系统在各阶段（如 `score_image_candidate` 与 `score_symbol_candidate`）所采用的 confidence 实际上只是**手工加权评分（Heuristic Scoring）**，并非真正的统计学概率置信度，更缺少对抗背景噪声、文字覆盖与复杂纹理的校准机制。
* **全图 Visual Diff 的粗颗粒度局限**：目前的 `dsl_visual_comparison` 主要做全图级的像素级差分，容易因微小偏移（Shift）导致整图 diff 报错，缺乏基于局部候选节点（Candidate Candidate BBox）局部渲染比对、结构边缘差异（SSIM/Edge Diff）的多维门禁审计。

### 4. 当前代码是否适合全面重构成 Go？
**不适合，当前全面重构成 Go 是一个“高风险且违背迭代规律”的非第一性原理决策。**
* **算法快速上演化期尚未结束**：像素归属、复合媒体分解、布局能量以及 Auto Layout 许可决策仍属于高速迭代的启发式与局部数学模型阶段。Python 具备极佳的开发敏捷度、算法库生态以及交互式调试性，是目前快速收敛逻辑的最佳媒介。
* **性能瓶颈在计算层而非工程编排层**：目前的性能痛点主要集中在“双重像素遍历查找局部背景”、“大图连通域打标（Connected Component Labeling）”等图像数学计算。在 Python 中引入 C 语言绑定的 `Pillow`、`NumPy` 与 `scikit-image` 即可将此类计算缩短至数毫秒级，无需付出全面重构 Go 导致的算法演进停滞代价。
* **未来的 Go 化演进路线（外围 Go化，核心留 Python）**：
  * **可 Go 化的外围模块**：FastAPI REST 路由与高并发任务队列调度（`routes/`）、任务持久化存储层（SQLite/DB 管理）、OCR 第三方 API 异步分发层、物化 DSL 输出的压缩与打包逻辑。
  * **不该动的 Python 核心算法**：`visual_primitive/`、`source_ui_physical_graph/`、`media_internal_decomposition/`、`m29_replay_plan/` 等包含密集拓扑几何运算、阈值调优和决策引擎的模块。

---

## 二、 按 Pipeline 审核代码结构

以下是针对从“输入图片”到“视觉对比”完整链路的逐层审计报告：

| 阶段 / 层级 | 当前模块 | 当前状态 | 主要问题 | 是否越权 | 建议 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. 输入图片** | `backend/app/routes/upload_preview.py` | 已实现 | 入口主要处理上传 PNG，不支持 PSD/PDF 等源物理图。 | 否 | 保持 entry 纯净，不要在此做任何像素或文件预处理。 |
| **2. OCR** | `backend/app/ocr.py`, `ocr_baidu.py` | 已实现 | 强依赖百度等外部 API，高并发与弱网下可能抖动。 | 否 | 将 OCR 输出的 `M29TextBox` 建立独立模型缓冲以防请求失效。 |
| **3. Primitive / Mask / CC** | `visual_primitive/` | 已实现 | 连通域打标由纯 Python 栈式遍历实现，对于超高分辨率图有栈溢出风险且耗时过长。 | 否 | 引入 NumPy/scikit-image 的 labeling，极大提升性能与可靠性。 |
| **4. Physical Graph** | `source_ui_physical_graph/` | 已实现 | `controls.py` 中对有限控件的规则存在零散分布。 | 否 | 提取统一的 `finite_control_background` 判定。 |
| **5. Pixel Ownership** | `source_ui_physical_graph/` | 已实现 | 像素归属只是针对 SourceObject 内部作标记，未建立全局像素覆盖与争夺模型。 | 否 | 应该将 `pixelOwner` 的分配做全局互斥约束，禁止多重前景。 |
| **6. Region Relation** | `region_relation_kernel.py`, `region_relation_graph_report.py` | 已实现 | 二值关系判定完善，但缺失三元或局部网格布局约束。 | 否 | 引入 `secondaryGeometryRelations` 作为布局约束输入。 |
| **7. Replay Plan** | `m29_replay_plan/` | 已实现 | 只处理去重和 flat 重放，预算分配是硬约束，缺乏多维代价加权。 | 否 | 严格保持其作为“DSL 物化许可唯一签发机关”的地位。 |
| **8. Ownership Conservation** | `ownership_conservation/` | 已实现 | 属于 `report-only`。仅对比了 Claims 和 Actions，没有计算精确到像素级错擦率。 | 否 | 升级为“像素映射矩阵守恒审计”，进入回归测试门禁。 |
| **9. Media Internal Decomposition** | `media_internal_decomposition/` | 已实现 | 属于 `report-only`。内部 foreground 搜索使用朴素的双循环相对差，性能较弱。 | 否 | 提取局部背景图模型时，利用形态学开闭运算做性能加速。 |
| **10. Transparent Asset Report** | `transparent_asset_report/` | 已实现 | 属于 `report-only`。分析 dominant_rgb 时使用简易 bucket，易受边缘半透明渐变干扰。 | 否 | 边缘采样区域可自适应向外扩张 2px 以消除干扰。 |
| **11. Internal Source Promotion** | `internal_source_promotion/` | 已实现 | 仅对 `action_row` 中的 icon 提升，忽略了通用独立高置信 internal icon。 | 否 | 建立 promotion 准入白名单，防范误升引发的 cleanup 链条失控。 |
| **12. Hierarchy Candidate** | `hierarchy_candidate_report/` | 已实现 | 属于 `report-only`。未改变 DSL。基于 bbox containment 的选择对 padding 不对称包容过度敏感。 | 否 | 引入相对位置重心偏差作为父子从属关系的惩罚项。 |
| **13. Sibling Group Candidate** | `sibling_group_candidate_report/` | 已实现 | 属于 `report-only`。未改变 DSL。聚类只用了 stable_design_cluster 弱特征。 | 否 | 引入以 text-width / gap 共同构筑的 action_row Isomorphism。 |
| **14. Layout Energy** | `layout_energy_report/` | 已实现 | 属于 `report-only`。仅有 Row/Column/Grid 数学草案，无动态规划重排求解。 | 否 | 未来可以引入弹性形变能量模型，不要用硬编码对齐。 |
| **15. Auto Layout Permission** | `auto_layout_permission_report/` | 已实现 | 属于 `permission-only`。无可见变动。 | 否 | 严防物化器在此阶段注入 Auto Layout 逻辑。 |
| **16. Plan Materializer** | `plan_materializer/` | 已实现 | Flat 重放与 C-stage 结构化控制组物化（C Group）已经跑通，物化不改变可见节点数量。 | 否 | **绝对禁止**在此物化阶段直接判断或生成新 owner。 |
| **17. DSL v0.1** | `packages/dsl-schema/` | 已实现 | 作为 Backend/Renderer 的公共 schema契约。规范性高。 | 否 | 在物化时用 pydantic 进行严格 schema 运行时拦截。 |
| **18. Renderer / Figma** | `packages/image-to-figma-renderer/` | 已实现 | 接收 DSL v0.1 并还原设计。当前版本只识别 flat 结构。 | 否 | 在 Figma 侧接收 C Group 并原样打组，暂不配置 layout 属性。 |
| **19. Quality Report** | `b_stage_quality_report/` | 已实现 | 属于 `report-only`。仅作 counts 和 repair-cost 计算，无法自动化打回。 | 否 | 后续可将此报告的 `repair_cost` 加入 CI 自动化合并门禁。 |

---

## 三、 置信度之外的可靠性体系审核

仅靠 AI 或 OCR 算出来的原始 Confidence 根本无法确保生成 Figma 稿的可编辑可用性。以下针对 8 项高阶可靠性体系进行审计并提出缺口改善方案：

| 可靠性方法 | 当前代码支持情况 | 关键工程缺口 | 推荐落地模块 | 优先级 |
| :--- | :--- | :--- | :--- | :--- |
| **1. Calibration / 概率校准** | 仅使用 raw_confidence 或启发式分数（0~1 截断值） | 缺失 ECE 统计学表；没有结合区域大小、前景对比度和局部纹理度对置信度进行数学期望校准（例如小文本 OCR 极易退化，应受更严厉的惩罚）。 | `visual_primitive/metrics.py` | **P1** |
| **2. IoU / containment / overlap-based validation** | 已在 `bbox.py` 与 `region_relation_kernel.py` 稳定实现 | containment 判定阈值在多处硬编码（如 0.95, 0.88），未对不同类型（如 Text 与 Media）引入阶梯准入容差。 | `region_relation_kernel.py` | **P2** |
| **3. NMS / duplicate suppression** | `dedupe.py` 实现 IoU >= 0.88 的过滤 | 当 icon fragment 与 alpha candidate 相互重合时，只使用 simple priority rank，容易因微弱 bbox 大小差异错删主视觉。 | `m29_replay_plan/overlap.py` | **P1** |
| **4. 多证据一致性 / evidence consistency** | 部分引入（如 text-mask 对 image/symbol 检测的阻断，`score_one_candidate` 对 anchor 和 compact 的综合判定） | 缺乏全局的 `EvidenceScore`。对于“控件”和“小图标”的决定，依然有单一机制“一票否决”或“一票放行”的安全隐患。 | `source_ui_physical_graph/pipeline.py` | **P1** |
| **5. Test-time augmentation (TTA) / 扰动稳定性** | 空白 | 轮播图内部的细微前景、半透明背景图标等在稍微模糊、对比度变化（blur/contrast perturbation）下是否能稳定检测无评估。 | `visual_primitive/validation.py` | **P3** |
| **6. Layout / geometry consistency** | `media_internal_decomposition` 内实现了 anchor matching 与 action row 间距稳定性 | 仅限于 CompositeMedia 内部，对于 root 级的多列、多行对齐和排布一致性校验尚未覆盖到 Ownership 分配上。 | `stable_design_cluster/scoring.py` | **P2** |
| **7. Render-back / visual regression** | `dsl_visual_comparison` 实现了简易的全图渲染差异比对 | 缺乏**局部候选节点（Candidate Render-back）**的提取比对。整图差分在大偏差下无效，需要计算局部区域的 SSIM 与边缘算子差异。 | `dsl_visual_comparison/render.py` | **P2** |
| **8. Benchmark metrics** | 有 `tests/` 和 `/Users/luhui/Downloads/m29` 评测脚本 | 缺少 ground truth 级别的精确 pixel-level 标签集，对于“修复代价（Repair Cost）”的度量指标还未在 pipeline 中拦截落地。 | `b_stage_quality_report/quality.py` | **P1** |

---

## 四、 引入 Pillow / NumPy / scikit-image 等依赖的决策

为解决图像处理的性能与召回缺陷，引入小依赖是可行的，但必须严守“数学工具层与决策所有权层”的纯净边界，严防外部工具对 M29 source truth 的越权控制。

### 1. 依赖决策表
| 依赖 | 是否建议引入 | 核心用途 | 潜在风险 | 边界红线 | 推荐模块 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pillow** | **建议** | 负责图像的 Decode、自适应裁切（Crop）、背景颜色采样与 RGBA 遮罩合并输出。 | 读写文件引发的 OS 资源耗尽。 | 严禁根据 PIL 导出的直方图直接判定 `pixelOwner` 决策。 | `image_math/arrays.py` |
| **NumPy** | **建议** | 替代手写双重循环像素遍历，快速进行 RGBA 矩阵化变换、局部背景差分计算与 Luma 向量化。 | 内存占用过大（超大图的 float 矩阵）。 | 严禁使用 Numpy 阵列的直接归属作为 replay 判定，矩阵只做物理指标映射。 | `image_math/background.py` |
| **scikit-image** | **建议** | 快速连通域标记（`label`）、特征提取（`regionprops`）与形态学腐蚀/膨胀（Morphology Open/Close）。 | API 较重、多维参数调节混乱导致召回率漂移。 | 严禁利用 regionprops 的特征直接映射 DSL 结构体或 Auto Layout 判定。 | `image_math/components.py` |
| **orjson** | **建议** | 提升 API 返回体及大型 nodes.json 文件序列化性能。 | 部分不支持自定义类的快速 dump。 | 绝对不允许改动 API 的 schema 输出结构和 DSL v0.1 JSON 语义定义。 | `upload_preview/task_state.py` |
| **rich** | **建议** | 仅用于开发期、批验证脚本、CI pipeline 的可视化诊断与 stdout 格式化输出。 | 不恰当的终端 buffer 捕获导致 runtime 堵塞。 | **红线**：严禁进入线上 runtime 管线（即不许进入 `backend/app/` 的生产代码）。 | `scripts/` (仅限脚本) |

### 2. 依赖引入的 ADR 边界红线（Must & Must Not）
所有第三方图像数学库的引入必须严格遵守以下守恒红线：
* **Pillow/NumPy/scikit-image 可以（May）**：
  * 解码、归一化像素点（Decode and normalize pixels）；
  * 计算局部 binary mask、支持区域 mask 以及前景矩阵；
  * 执行高效的连通域标记（Connected Component Labeling）与形态学清理；
  * 计算局部图像的方差、亮度和边缘梯度算子（Sobel/Canny）；
  * 生成供调试比对（Overlay Sheet）的预览图与 alpha RGBA 抠图。
* **Pillow/NumPy/scikit-image 绝对禁止（Must Not）**：
  * 判定 `pixelOwner` 分类决策；
  * 做出 `replayDecision` 重放判定；
  * 签发 `cleanup authorization` 擦除授权；
  * 直接推定组件分类（Component Identity）或 Auto Layout 许可决策；
  * 直接实例化任何 DSL 节点或修改最终 DSL 的拓扑层次；
  * 针对特定截图特化规则，以绕过数学合同。

---

## 五、 重点审核：Media Internal Decomposition (复合媒体内部像素分解)

在复杂的轮播图（Composite Media）中，包含各种前景元素（文字、矢量点、小图标），如果只重放为一个整体的 `image_replay`，设计稿的还原度与编辑度将大打折扣。以下对这套逻辑进行第一性原理深度审计：

### 1. 核心问题解答
1. **当前是否只是 report-only？**
   * **是**。在 `upload_preview/pipeline.py` 中，`media_internal_decomposition_stage` 产生的 report 带有 `reportOnly: true`，不改变 DSL 输出，仅供 promotion 决策消费。
2. **是否有 internal UI label 判断？**
   * **是**。通过对 `TextInside(M)` 集合过滤，识别出完全处于 media 范围内部的文本块，这符合物理包含的第一性原理。
3. **是否有 text mask 保护？**
   * **是**。在 `candidates.py` 中，基于 OCR 文本块创建带 padding（x=3, y=3）的 `TextMask`，并在前景提取时执行过滤，避免了中文字符或标点连通域对小图标识别的污染。
4. **是否有 local background model？**
   * **否（工程缺口）**。当前代码没有实现自适应局部背景图，而是用了简易的窗口边界中位数（`median_edge_rgb`）。在背景存在强烈光晕或复杂渐变时，该模型表现粗糙。
5. **是否有 connected component / foreground mask？**
   * **是**。在 `connected_pixel_components` 中，手写了基于 mask 的双重 BFS 连通域查找。
6. **是否有 icon-text anchor matching？**
   * **是**。在 `directional_anchor_score` 里通过高斯核函数公式对“图标与文本相对位置（above/below/left/right）”以及理想 gap 距离进行空间能量建模，为 icon-text 的结合提供了优美的数学描述。
7. **是否有 repetition / action row validation？**
   * **是**。在 `apply_repetition_scores` 与 `build_matched_internal_groups` 里，对 accepted 的内部候选进行了水平/垂直轴对齐（Row alignment）与间距方差计算，有效识别出了“充值/提币/划转/买币”等成排的 action row。
8. **是否有 hero graphic penalty？**
   * **是**。在 `hero_graphic_penalty` 中对面积占比高、质心居中、纹理度极高的内部碎片进行了惩罚，防止把轮播图中心的主视觉海报大图误判成 icon。
9. **是否有 art text penalty？**
   * **否（工程缺口）**。缺乏对“艺术字/装饰性非结构化字母”的专门惩罚因子。
10. **是否有 copied media cleanup authorization？**
    * **是**。当 promoted 的内部前景成功提升为 `raster_icon` / `icon_replay` 时，重新运行的 M29.5 会自动分析并在 `cleanup.py` 中授权擦除母媒体（Parent Media）对应区域的前景像素。
11. **是否有 materializer 消费权限？**
    * **是**。物化器会读取 `m295_report` 中的 cleanup targets，执行擦除并把 promoted internal icon 挂载到扁平设计树中。

### 2. 复合媒体内部可编辑化落地路线图（Phase 1 至 Phase 6）

为了稳步提升这一能力并彻底规避“退化特化与乱擦母图”的灾难，必须分阶段平滑推进：

```text
Phase 1: Report-Only --> Phase 2: Text Promotion --> Phase 3: Icon Alpha Asset --> Phase 4: Copied Media Cleanup --> Phase 5: Layout Candidate --> Phase 6: Controlled Materialization
```

#### Phase 1: Report-Only (当前已跑通)
* **目标**：以绝对安全的形式，仅生成内部复合结构分析，验证 precision & recall。
* **输入**：Source PNG, OCR blocks, Raw M29.
* **输出**：`media_internal_decomposition_report.json`
* **修改模块**：无（只增加 regression test）。
* **新增测试**：测试 action row 的 alignment score 与 gap stability score 在多重样例下的收敛性。
* **不允许**：不允许任何 promoted 节点进入 DSL，也不许擦除原图。
* **验收指标**：Icon anchor 匹配准确率 >= 90%，无错判。

#### Phase 2: Internal Text Promotion (正在落地中)
* **目标**：将复合媒体内部的可编辑文本正式提升至 DSL 节点，还原设计稿的文本编辑能力。
* **输入**：Media decomposition report, M29.2 source objects.
* **输出**：在 `source_ui_physical_graph.promoted.json` 中，原属于 parent media 的内部 text 变更为 `editable_text` + `text_replay`。
* **修改模块**：`internal_source_promotion/pipeline.py`。
* **新增测试**：验证在 `media_region` 下多个文本同时编辑时，重新生成的 relation 保持拓扑一致。
* **不允许**：此阶段不允许提取内部 icon。
* **验收指标**：内部文本漏判率 < 5%，误判率 < 1%。

#### Phase 3: Internal Icon Alpha Asset
* **目标**：提取高置信内部 icon 候选，并利用 alpha 分析器将其转为透明 RGBA 资产，脱离原轮播图。
* **输入**：Promoted M29.2, pixels, transparent asset report.
* **输出**：RGBA PNG transparent assets.
* **修改模块**：`transparent_asset_report/alpha.py`。
* **新增测试**：输入带有复杂模糊背景的 icon，验证 `unstable_background` 触发阈值的稳定性。
* **不允许**：不允许从母图中擦除该 icon，仅做提取输出。
* **验收指标**：透明资产提取召回率 >= 80%，边缘无明显毛刺或溢色。

#### Phase 4: Copied Media Cleanup
* **目标**：在 M29.5 签发 cleanup 授权，并在物化时使用 alpha mask 从母图中精确擦除被提升的前景，使其不再双重呈现（母图带 icon，又生出独立 icon 节点重叠）。
* **输入**：Final M29.5 Replay Plan (containing promoted icons + cleanup authorizations).
* **输出**：被擦除后的母图素材（已修补的前景）。
* **修改模块**：`plan_materializer/cleanup.py`。
* **新增测试**：测试擦除边界是否会出现“错位漏擦”或“过度擦除文字”。
* **不允许**：不允许在没有 M29.5 明确 cleanup 授权下，由物化器自主修改像素。
* **验收指标**：错擦率 (Wrong Cleanup Area Ratio) < 1.5%。

#### Phase 5: Action Item Group / Layout Candidate
* **目标**：根据 action row 等多列结构，在 report 中推荐将该复合区域拆解为 sibling group 候选。
* **输入**：Promoted relations, Layout energy, Auto layout permission reports.
* **输出**：`sibling_group_candidate_report.json`
* **修改模块**：`sibling_group_candidate_report/candidates.py`。
* **新增测试**：构造 gap 不均匀的 row 实例，验证聚类是否被正确剔除。
* **不允许**：不许在 DSL 中建立组节点。
* **验收指标**：Action Row 组候选生成率 >= 85%。

#### Phase 6: Controlled Materialization
* **目标**：在物化阶段，将已提取 of internal icons + internal texts 在 DSL 根节点下包裹进一个透明的 `m29_controlled_structure_group`。
* **输入**：Plan materializer, Hierarchy/Sibling candidates.
* **输出**：修改后的可见 DSL 树，包含 group 嵌套结构。
* **修改模块**：`plan_materializer/structure.py`。
* **新增测试**：测试嵌套的 C Group 重构后在 Figma 插件侧是否能一键打组，且 z-order 保持物理一致。
* **不允许**：**严禁在此阶段生成 Auto Layout 或 Component。**
* **验收指标**：结构打组成功率 >= 95%，不丢失任何扁平元素。

---

## 六、 重点审核：有限控件（Finite Control / Button / Search Box）

### 1. 质量问题清单与现状评估
在移动端截图或 Web UI 中，搜索框、圆角按钮、胶囊徽标等“有限控件”常有以下表现缺陷：
* **误判为 Media**：当按钮中带有渐变、阴影或小图标时，其 Primitive 容易被误断为 `image`，进而物化为 `preserve_raster` 图片，这属于降级灾难。
* **规则泛滥风险**：当前代码里包含针对 `search_field_background`、`badge_background`、`icon_button_background` 的 subtype 细分。目前这些 subtype 仅作为 Evidence Label 使用，但容易诱导开发人员针对不同圆角大小、不同背景高度特化定制 rules，导致规则坍塌。
* **物化器注入补丁**：目前在 Figma plugin 或 Renderer 层，有时会出现为了修复特定按钮还原度而硬编码修正 padding/margin 的越权行为。

### 2. 改进规划与统一判定公式
我们将以上特化的 subtype 合并定义为 **“有限控件背景数学模型（Finite Control Background Formula）”**。判定该区域为有限控件背景必须满足以下证据链条：

$$Score(S) = w(S) \times h(S) \times Containment(T) \times ShapeOverlap(F)$$

具体证据判定公式如下：

* **OCR 包含度约束（Containment）**：
  必须包含至少一个文本块且文本框面积不超过控件面积的 65%，

  $$\frac{I(T, S)}{area(T)} \ge 0.95, \quad \frac{area(T)}{area(S)} \le 0.65$$

* **几何边界有限度约束（Finite BBox）**：
  高度在 24px 至 110px 之间，纵横比大于等于 1.5。

  $$24 \le h(S) \le 110, \quad \frac{w(S)}{h(S)} \ge 1.5$$

* **稳定局部填充度（Stable Local Fill）**：
  该区域的外环像素色差波动小且整体纹理度低，说明是干净的 UI 面板而非自然图像。

  $$Variance(Edge(S)) \le 28, \quad TextureScore(S) \le 0.08$$

* **外环隔离特征（Outer Ring Boundary Delta）**：
  内外边界具备高对比度的隔离边缘（如按钮有边线或与底色不同）。

  $$\Delta_{boundary} = \left\| Mean(Inner(S)) - Mean(Outer(S)) \right\| \ge 12$$

### 3. 落地建议
* **修在哪一层**：必须且仅能修在 `source_ui_physical_graph/controls.py` (M29.2 阶段)里。将符合上述有限控件特征的 `unknown` 或 `image_like_low_confidence` 提升为 `shape_geometry`，允许作为 Shape 被安全重放。
* **不能修在哪一层**：绝对不允许在 `plan_materializer`、Renderer 或者 Figma 插件里根据文字内容（例如“搜索”、“确定”）去特化或修改 bbox 形状。

---

## 七、 具体改造规划路线图

本项目演进应严格遵循“先安全诊断、后有限物化”的软件工程纪律，分 7 个阶段逐步落地：

| 阶段 / 优先级 | 核心目标 | 修改文件 / 模块 | 新增文件 / 模块 | 新增测试 | 验证命令 | 运行风险 | 回滚策略 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **P0: 审计与防护** | 引入无行为变更的 Ownership 严格像素级守恒断言，拦截非法擦除。 | `m29_replay_plan/cleanup.py`, `plan_materializer/cleanup.py` | | `tests/test_p0_protection.py` | `uv run pytest -k test_p0` | 无任何业务逻辑破坏风险。 | Git revert 即可。 |
| **P1: 引入小依赖** | 引入 Pillow/NumPy，升级连通域标记和像素采样，提升效率。 | `visual_primitive/components.py`, `png_tools/sampling.py` | `image_math/arrays.py`, `image_math/components.py` | `tests/test_image_math_integration.py` | `uv run pytest -k test_png_tools` | 阈值浮动导致极少部分小碎片被剔除。 | 本地保留老版 BFS 代码作为开关 fallback 开关。 |
| **P2: 增强一致性** | 引入 `EvidenceScore` 机制，升级 OCR 概率校准与重叠去重。 | `source_ui_physical_graph/dedupe.py`, `visual_primitive/detectors.py` | `image_math/metrics.py` | `tests/test_evidence_score.py` | `uv run pytest -k test_evidence` | 低置信度 UI 节点被退化为 preserve_raster 增多。 | 调整准入阈值 `min_text_confidence`。 |
| **P3: 二次分解** | 落实 CompositeMedia 内部的 editable text 二阶段正式物化。 | `internal_source_promotion/pipeline.py` | | `tests/test_media_internal_editability.py` | `uv run pytest -k test_media_internal` | 母图提取擦除区域边缘出现半透明白条或断片。 | 关闭 `enable_media_internal_promotion` 开关。 |
| **P4: 局部 Render-back** | 引入局部 Candidate SSIM / Edge Diff，形成诊断回归门禁。 | `dsl_visual_comparison/pipeline.py` | `dsl_visual_comparison/local_diff.py` | `tests/test_local_render_back.py` | `uv run pytest -k test_render_back` | 多一轮像素级绘制，本地 CPU 计算时间拉长 1~2 秒。 | 可将 Render-back 设置为异步后台计算或非阻塞模式。 |
| **P5: 有限物化** | 将 promoted 的 internal icon 在 M29.5 授权后参与 DSL flat 物化与母图精确擦除。 | `plan_materializer/replay.py`, `m29_replay_plan/cleanup.py` | | `tests/test_p5_materialization.py` | `uv run pytest -k test_p5` | icon 抠图错误引发 Figma 侧可见素材缺角。 | 关闭 `enable_icon_cleanup_authorization`。 |
| **P6: 结构打组** | 消费 sibling & hierarchy 候选，在扁平 DSL 上包裹透明 `m29_controlled_structure_group`。 | `plan_materializer/structure.py` | | `tests/test_p6_group_structure.py` | `uv run pytest -k test_p6` | Z-Order 拓扑错乱导致原本浮于上层的元素沉到底部。 | 彻底关闭 `enable_controlled_structure_materialization`。 |

---

## 八、 建议新增的 ADR (ADR 0074 草案)

```markdown
# ADR 0074: Introduce Image Math Execution Dependencies Without Changing Source Truth

## Status
Proposed

## Context
Our M29 pipeline relies heavily on pixel-level operations, including connected component labeling, dominant color border sampling, and mask intersection calculations. The current pure Python implementations (e.g., stack-based BFS in `visual_primitive` and pixel-by-pixel loops in `png_tools/sampling.py`) are hitting performance limits on high-resolution mockups (often taking >1.2 seconds per upload) and are prone to stack overflow errors.
To scale, we need to introduce dedicated image math libraries (`Pillow`, `NumPy`, and `scikit-image`) to accelerate computation. However, introducing these libraries presents a high risk of "feature creep", where algorithmic decision logic (like pixel ownership, clean-up authorization, or Auto Layout permission) gets hardcoded into image math utility layers, bypassing the M29 mathematical contract.

## Decision
We will introduce `Pillow`, `NumPy`, and `scikit-image` strictly as an **Image Math Execution Layer**. A clear boundary will be enforced between math helpers and the M29 source truth layer:

1. All calculations using these libraries must reside inside a new dedicated package `backend/app/image_math/`.
2. Core domain packages (`visual_primitive`, `source_ui_physical_graph`, `m29_replay_plan`, and `plan_materializer`) are permitted to import from `backend/app/image_math/` to obtain raw metrics (arrays, labels, masks, and bounding boxes), but `image_math` is strictly forbidden from importing any M29 domain types or policies.
3. No file outside `backend/app/image_math/` (except for test configurations) is allowed to import `scikit-image` or raw `numpy` directly, keeping dependencies localized and auditable.

## Allowed Usage
* **Pillow**: Used for raw image decoding, cropping pixel regions, applying composite alpha channels, and exporting RGBA assets.
* **NumPy**: Used for vectorizing RGB/RGBA distance math, computing channel variance, and performing fast element-wise array operations.
* **scikit-image**: Used for connected component labeling via `skimage.measure.label` and extracting bounding boxes via `regionprops`.

## Forbidden Usage
* **No Ownership Decisions**: `image_math` must not decide `pixelOwner` or map a component to a `visualKind`.
* **No Replay Planning**: `image_math` must not decide whether a candidate is materialized or skipped, nor authorize a parent raster cleanup.
* **No Direct DSL Generation**: `image_math` must not construct or mutate DSL node JSON payloads.
* **No Hardcoded Layout Rules**: `image_math` must not propose spacing tokens, auto-layout directions, or component isomorphism slots.
* **No Color/Theme/Text Patching**: The library must not be used to bypass regular detection logic using hardcoded color, text contents, or mockup-specific bounding boxes.

## Consequences
* **Performance**: Pipeline execution times are expected to drop below 350ms for typical mobile screenshots.
* **Maintainability**: Image math bugs can be isolated and debugged independently in `tests/test_image_math.py`.
* **Auditing**: The strict separation guarantees that M29.5 remains the single source of truth for all design-generation decisions.

## Validation
* **Linting Rules**: CI will enforce that no file under `backend/app/` (outside `image_math/` and `png_tools/`) imports `numpy` or `skimage`.
* **Behavior Invariance**: All 325 existing unit and integration tests must pass without changes to their expected output nodes.
```

---

## 九、 建议新增的模块结构

建议在 `backend/app/` 下创建独立的 `image_math` 库：

```text
backend/app/image_math/
├── __init__.py
├── alpha.py
├── arrays.py
├── background.py
├── components.py
├── debug.py
├── masks.py
├── metrics.py
└── morphology.py
```

### 每个文件的职责、允许的依赖与限制条件：

#### 1. `arrays.py`
* **职责**：执行 PIL Image 与 NumPy Array 之间的极速双向转换，处理 RGB / RGBA 通道的规整与重排。
* **允许 import 的依赖**：`PIL.Image`, `numpy`.
* **禁止做的事情**：不允许在此承载任何关于坐标相交或包含等业务几何逻辑。

#### 2. `background.py`
* **职责**：构建局部背景估计。接收 BBox，提取该区域周边的外环颜色分布，利用 NumPy 快速求解三通道颜色的中位数与方差，输出局部背景 RGB 值。
* **允许 import 的依赖**：`numpy`.
* **禁止做的事情**：不允许决定该背景是否属于 `preserve_raster` 或者 `shape_geometry`。

#### 3. `masks.py`
* **职责**：根据连通域或 bounding box 生成 binary mask。执行 mask 之间的布尔运算（AND/OR/SUBTRACT），计算 mask 之间的精确 Overlap 像素面积。
* **允许 import 的依赖**：`numpy`.
* **禁止做的事情**：禁止自主做出“是否擦除背景”的物理指令。

#### 4. `morphology.py`
* **职责**：执行二值图像形态学操作，通过膨胀（Dilate）、腐蚀（Erode）或开闭运算清理边缘噪点，分离粘连连通域。
* **允许 import 的依赖**：`scikit-image (skimage.morphology)`.
* **禁止做的事情**：禁止利用形态学特征去推论该前景元素是不是一个 Icon 还是文本笔画。

#### 5. `components.py`
* **职责**：调用 `skimage.measure.label` 实现高速连通域标记，利用 `regionprops` 提取每个连通分量的 BBox 与精确像素面积，淘汰低于极值尺寸的噪点。
* **允许 import 的依赖**：`numpy`, `skimage.measure`.
* **禁止做的事情**：禁止决定该 component 在重放时映射为什么 `subtype`，更不允许在此产生 DSL node。

#### 6. `alpha.py`
* **职责**：提取透明资产。基于给定的前背景阈值，将组件的原始 RGB 像素扣出，并使用 NumPy 生成柔和的 alpha 半透明通道，输出 RGBA 二进制流以供保存。
* **允许 import 的依赖**：`PIL.Image`, `numpy`.
* **禁止做的事情**：禁止越权获取文件存储路径，只返回二进制流；不允许自行决定是否将该抠图提升为设计可见图标。

#### 7. `debug.py`
* **职责**：利用 Pillow 在源图上绘制多彩的 BBox 检测框、在前景上绘制半透明蒙版以生成诊断用的 Overlay 图像或 Sheet 排版预览图。
* **允许 import 的依赖**：`PIL.Image`, `PIL.ImageDraw`.
* **禁止做的事情**：**此文件不允许在生产环境路由下被导入执行**，仅用于生成 debug 静态图。

#### 8. `metrics.py`
* **职责**：计算区域的高阶物理指标，包括计算局部高频纹理度（Texture Score）以及基于像素梯度（Sobel）的边缘度。
* **允许 import 的依赖**：`numpy`, `skimage.feature` (可选).
* **禁止做的事情**：不允许在此判断置信度的高低。

---

## 十、 当前代码中最值得优先审查的文件（Top 20）

| 优先级 | 文件 / 目录 | 为什么要审计 | 潜在主要问题 | 建议改造方向 |
| :---: | :--- | :--- | :--- | :--- |
| **1** | [backend/app/source_ui_physical_graph/controls.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/controls.py) | 承载了搜索框等有限控件的复杂判断，极易退化成规则特化。 | 阈值分散在 `options`，判断缺乏统一几何公式。 | 合并 subtype 判断，重构为前述统一有限控件公式。 |
| **2** | [backend/app/media_internal_decomposition/candidates.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py) | 复合媒体内部分解的核心，长达 929 行，承载极重的 BFS 双循环像素扫描。 | 运算性能极低，局部背景采样粗糙，文字保护带生硬。 | 引入 `skimage.measure.label` 重构连通域。 |
| **3** | [backend/app/transparent_asset_report/alpha.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/alpha.py) | 负责抠图及透明资产合法性检查。 | 手写 Dominant color 桶排序极慢，抗噪点差。 | 引入 NumPy 矩阵计算前背景欧氏距离差。 |
| **4** | [backend/app/visual_primitive/detectors.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive/detectors.py) | 从连通域中探测 text/shape/image 的核心决策点。 | `subtype` 的硬编码映射过多，圆角信息粗糙。 | 将 geometry_radius 与 shape 分类完全解耦。 |
| **5** | [backend/app/m29_replay_plan/decisions.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/decisions.py) | 决定重放行为和优先去重的裁判所。 | 去重算法对 large/small 的相对包含判定制约较弱。 | 引入基于 EvidenceScore 校准后的多维度去重。 |
| **6** | [backend/app/plan_materializer/structure.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/structure.py) | 决定是否在物化时打组（C Group）的受控层。 | 若判断宽松，可能引入 Z-Order 非 contiguous 组。 | 严厉维持 contours 连通性，防止乱打组导致图层错乱。 |
| **7** | [backend/app/ownership_conservation/claims.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/claims.py) | 物理归属断言的验证机制。 | 缺少对擦除像素重叠度的矩阵验证。 | 改造为基于 binary mask 叠加热图的守恒检查。 |
| **8** | [backend/app/internal_source_promotion/pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py) | 内部候选重新提升为 source object 的唯一回流网关。 | 提升条件过于粗放，可能把垃圾碎片升为 visible。 | 设定严格的 repeatability / layout 结构门禁。 |
| **9** | [backend/app/region_relation_kernel.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/region_relation_kernel.py) | 几何关系判定的地基工具。 | 边界差值缺乏浮点归一化，抗极小漂移差。 | 为 near_equal 设定相对宽高比例容差。 |
| **10** | [backend/app/png_tools/sampling.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/png_tools/sampling.py) | 前背景色彩采样的最底层。 | 多次手写逐行读取 RGB byte 慢。 | 用 PIL + NumPy 的 array slicing 改写。 |
| **11** | [backend/app/upload_preview/pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/upload_preview/pipeline.py) | 后端总编排控制器。 | stage 错综复杂，双重重算容易导致 timing 统计错乱。 | 保持 no-behavior，禁止在此添加业务决策。 |
| **12** | [backend/app/visual_primitive_graph.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/visual_primitive_graph.py) | raw M29 入口编排。 | 属于 thin orchestration，职责需要彻底向域模块分散。 | 无行为拆分，保持稳定。 |
| **13** | [backend/app/dsl_visual_comparison/pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/dsl_visual_comparison/pipeline.py) | visual comparison 比对器。 | 目前使用全图级比对，极易受局部偏置噪点干扰。 | 引入局部 candidate-level 的 SSIM 比对逻辑。 |
| **14** | [backend/app/auto_layout_permission_report/permission.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/auto_layout_permission_report/permission.py) | 决定是否许可 Auto Layout。 | 没有真正阻断物理生成，容易被未来开发者滥用。 | 在 pipeline 注入强制检查，防止物化器越权。 |
| **15** | [backend/app/layout_energy_report/energy.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/layout_energy_report/energy.py) | 布局能量度量。 | 目前只是理论公式占位，缺乏对 Gap 方差的惩罚项。 | 实装基于 gap_stability_score 的能量计算。 |
| **16** | [backend/app/sibling_group_candidate_report/candidates.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/sibling_group_candidate_report/candidates.py) | 兄弟组候选提取。 | 重叠度校验未包含 Z-Order 的断言。 | 增加 contiguous z-order 排序校验。 |
| **17** | [backend/app/hierarchy_candidate_report/candidates.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/hierarchy_candidate_report/candidates.py) | 层级结构候选提取。 | 贪婪包含可能引发巨大的嵌套树错乱。 | 加入 best-parent 相对 padding 分布惩罚。 |
| **18** | [backend/app/b_stage_quality_report/quality.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/b_stage_quality_report/quality.py) | 质量评分。 | 没有针对 false editable 给予足够严厉的惩罚。 | 提高 false editable area 的扣分比重。 |
| **19** | [backend/app/database.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/database.py) | 数据库层。 | json serialization 频繁调用原生 json，速度慢。 | 将底层序列化库替换为 orjson。 |
| **20** | [backend/app/config.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/config.py) | 全局配置项。 | 各阶段阈值写死在 dataclass，未通过环境变量透出。 | 为关键物理阈值映射 `.env` 参数并写入环境文档。 |

---

## 十一、 最终结论

### 1. 当前项目是否值得继续沿 Python 走？
**绝对值得。** 本项目处于“像素拓扑规则与启发式所有权决策”的高速演化和收敛期。Python 的敏捷开发与丰富的科学计算、CV 库支持能让开发人员将核心精力放在提炼数学公式上，而不是消耗在 Go 复杂的类型系统与重构时间里。

### 2. 是否应该现在 Go 重构？
**不应该。** 现在重构 Go 会直接腰斩算法研发进度，属于战略误判。当前所谓的性能缺陷完全是 Python 简易双循环像素比对造成的，可通过引入 C 底层加速库（Pillow/NumPy）直接抹平。Go 应该只在未来作为外部网关与并发调度器重构，不涉及核心所有权算法。

### 3. 是否应该引入 Pillow / NumPy / scikit-image？
**应该。** 它们能以原生的 C 性能运行，不仅能极大提升响应时间（从 1.5s 级压缩至 300ms 级），而且 `skimage` 内置的连通域算法能解决目前手写 BFS 带来的潜在栈溢出隐患。

### 4. 是否应该加入 orjson / rich？
* **orjson**：建议加入，大型 Task 序列化加速明显。
* **rich**：建议仅在 `tests/` 和脚本层引入，开发期友好；**红线限制**禁止进入后端 runtime 流。

### 5. 哪些依赖绝对不该现在加？
* **绝对不要引入任何大模型 CV 框架（如 PyTorch、SAM2 运行时、MMDetection 等）**。除非在未来作为独立的 RPC Provider 抽离（如现有的 OCR API 服务一样），否则引入大模型会导致代码体积暴涨、显卡环境绑定复杂化，进而掩盖基于像素拓扑和 M29 数学合同的 deterministic 所有权逻辑。

### 6. 下一步最应该做的 5 件事是什么？
1. **完成 P0-P1 阶段改造**：建立 `backend/app/image_math/`，将 Pillow/NumPy/scikit-image 引入，在不更改任何 M29 output contract 的前提下重写连通域打标和像素采样逻辑，跑通 325 个回归测试。
2. **制定并实装统一的“有限控件背景”判定数学模型**：消除 `controls.py` 中的杂乱 subtype，防止控件背景被降级误判为 preserve_raster。
3. **完成 Phase 2-Phase 3 复合媒体内部分解落地**：提升内部 text 的可编辑度，用柔和 alpha mask 抠出高置信图标。
4. **升级 Ownership Conservation 审计指标**：建立精确的像素覆盖矩阵比对，量化 wrong_cleanup 和 wrong_owner 并在 B 阶段报告中呈现。
5. **为 Visual Comparison 引入局部 Candidate-level 比对**：消除全图对齐偏差导致的 diff 失真，引入 SSIM。

### 7. 这套系统距离 Codia 级还差什么？
* **局部/全局布局能量的动态规划重排求解器**：目前只有 report，物化器尚无合并、形变、gap 对齐的最优解求解能力。
* **高精度的像素级置信度校准体系**：目前的 confidence 是手写评分，缺乏基于 ground truth 数据集的概率校准（Calibration）。
* **可量化的“修复代价（Repair Cost）”工程拦截器**：只有能自动打回并评估用户修复代价，才能确保输出质量的持续提升。

### 8. 当前最可能被低估的问题是什么？
**Z-Order 的非连续性与打组（Z-Order Contiguity）**：在 Sibling Group 聚类时，如果将物理上不连续（中间夹杂了其他浮层或背景元素）的节点打包进同一个 Figma 组，将造成图层顺序错乱或遮挡。这属于严重的视觉破坏，目前代码对 Contiguous Z-Order 的断言保护仍需加强。

### 9. 当前最可能被高估的能力是什么？
**“Weak Structural Cluster”的直接物化潜力**：很多人高估了类似 `row_like` 或 `column_like` 的 cluster 作用，试图让它们直接指导生成 Auto Layout 或 Figma Component。事实证明，如果没有经过 `Auto Layout Permission` 许可和物理背景擦除授权（Cleanup Authorization），仓促建组只会导致 Figma 设计稿不可用。

### 10. 你作为审核人最担心哪三个技术债？
1. **开发者绕过所有权合同在 Renderer 或 Plugin 中打补丁**：因为后台所有权逻辑复杂，前端开发者往往图省事，根据文字内容或位置在 Figma 端打硬编码补丁，这会导致物理证据链名存实亡。
2. **未校准的 OCR 错误信息在 Promotion 中引发擦除链崩塌**：低置信 OCR 意外提升，引发 Replay Plan 错误签发 Cleanup 授权，导致主背景图被擦除得千疮百孔。
3. **缺乏形态学保护的透明资产提取边缘残留**：对 icon 进行扣图时，由于背景复杂且缺乏形态学（Dilate/Erode）收缩保护，导致抠出来的图标边缘带有母图的底色残留，在 Figma 侧变换背景时出现严重的穿帮。
