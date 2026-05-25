你是一个资深 Python 后端架构师、CV/图像处理工程师和代码重构专家。

你现在要接手一个图片转 Figma 可编辑设计稿项目。请先完整阅读我提供的《图片转 Figma 可编辑设计稿项目：代码审核报告、第一性原理分析与技术规划》，然后基于这份报告对当前代码库进行一次分阶段升级。

注意：这不是简单修 bug，也不是只写文档。你需要真实修改代码、补测试、跑测试、输出变更摘要。

============================================================
一、项目背景
============================================================

这个项目目标是做“图片 / 截图 / 后续 PSD 转 Figma 可编辑设计稿”的后端。

核心路线不是端到端黑盒 AI，而是：

M29 数学合同
+ 像素拓扑
+ source object
+ pixel ownership
+ region relation
+ replay plan
+ cleanup authorization
+ materialization permission
+ quality report
+ DSL / Renderer / Figma plugin

当前已有模块大致包括：

- FastAPI 后端
- Figma 插件
- DSL schema
- image-to-figma renderer
- OCR provider
- visual_primitive
- source_ui_physical_graph
- region_relation_kernel
- m29_replay_plan
- ownership_conservation
- hierarchy_candidate_report
- sibling_group_candidate_report
- layout_energy_report
- auto_layout_permission_report
- media_internal_decomposition
- transparent_asset_report
- internal_source_promotion
- plan_materializer
- design_token_report
- b_stage_quality_report
- dsl_visual_comparison
- batch validation scripts

请始终遵守第一性原理：

这个项目真正要解决的不是“识别图片”，而是：

从像素世界恢复设计世界。

核心问题是：

1. 这个像素属于谁？
2. 这个区域是 text / shape / image / icon / media / control / fallback 中的哪一种？
3. 什么时候可以 materialize 成 Figma 可编辑节点？
4. 什么时候只能 report-only？
5. 什么时候可以 cleanup parent raster？
6. 什么时候可以从 report 升级到 controlled materialization？
7. 什么时候可以从 confidence 升级到 evidence consistency？
8. 什么时候新依赖只是数学工具，不能成为新的判断大脑？

============================================================
二、最高优先级原则
============================================================

你可以进行破坏性重构，但必须遵守以下边界：

1. 可以重构模块结构。
2. 可以新增依赖。
3. 可以新增 image_math 层。
4. 可以替换低层纯 Python 像素循环。
5. 可以重写 report-only 内部实现。
6. 可以补充测试。
7. 可以整理重复工具函数。

但是绝对禁止：

1. 禁止让 Pillow / NumPy / scikit-image 决定 pixelOwner。
2. 禁止让 Pillow / NumPy / scikit-image 决定 replayDecision。
3. 禁止让 Pillow / NumPy / scikit-image 签发 cleanup authorization。
4. 禁止让 Pillow / NumPy / scikit-image 直接创建 DSL node。
5. 禁止让 Pillow / NumPy / scikit-image 直接改变 materialization output。
6. 禁止在 materializer、Renderer、Figma plugin 里写颜色、文案、固定 bbox、行业主题、单张截图特化规则。
7. 禁止绕过 M29.5 replay plan 直接擦图。
8. 禁止把 report-only 模块悄悄改成 materialization。
9. 禁止直接生成 Auto Layout、Component、Variant、Figma Variables。
10. 禁止为了“看起来效果好”破坏 source truth / ownership / replay plan 边界。

一句话：

Pillow / NumPy / scikit-image 是 image math execution layer，不是 source truth layer。

============================================================
三、当前任务目标
============================================================

请按审计报告执行第一轮升级，目标是：

P0：审计与防护
P1：引入小依赖
P2：建立 image_math 执行层
P3：将 report-only 图像数学热点迁移到 image_math
P4：补充 evidence consistency / local visual validation 的基础结构
P5：确保现有 DSL / materialization 行为不被无意改变

第一轮升级重点不是做 Codia 级最终能力，而是：

1. 建立安全的 image_math 层。
2. 引入 Pillow / NumPy / scikit-image。
3. 引入 orjson。
4. rich 只作为 dev/scripts 依赖。
5. 不改变现有 DSL 输出。
6. 不改变 materialization 行为。
7. 提升 report-only 模块的性能、可测性和边界清晰度。
8. 补充 import-boundary 测试，防止未来代码越权。

============================================================
四、依赖引入要求
============================================================

请修改 backend 的依赖配置，引入：

runtime:
- Pillow
- numpy
- scikit-image
- orjson

dev only:
- rich

要求：

1. Pillow / NumPy / scikit-image 只能直接出现在 backend/app/image_math/ 内。
2. 其他 domain 模块如 visual_primitive、source_ui_physical_graph、media_internal_decomposition、transparent_asset_report、plan_materializer 如果需要使用图像数学能力，必须 import backend.app.image_math.*，不能直接 import numpy、PIL、skimage。
3. rich 只能用于 scripts、dev tooling 或 batch validation，不得进入 backend/app runtime。
4. orjson 必须通过统一 json 工具封装使用，不得到处散落 import。

请新增或修改：

backend/app/json_tools.py

封装：

- dumps_pretty(data) -> str
- dumps_compact(data) -> str
- loads(text_or_bytes) -> Any

要求：

- 默认使用 orjson。
- 保持中文不转义。
- 不改变 DSL schema。
- 不改变 API response 语义。
- 如有必要可提供标准库 json fallback，但生产依赖应使用 orjson。

============================================================
五、新增 image_math 模块
============================================================

请新增：

backend/app/image_math/
  __init__.py
  arrays.py
  background.py
  masks.py
  morphology.py
  components.py
  alpha.py
  debug.py
  metrics.py

每个文件职责如下。

------------------------------------------------------------
1. arrays.py
------------------------------------------------------------

职责：

- PIL Image <-> NumPy array 转换
- RGB / RGBA normalize
- uint8 shape validation
- crop array by bbox
- clamp bbox to image bounds

允许 import:

- PIL.Image
- numpy

禁止：

- 禁止 import M29 domain types
- 禁止判断 pixelOwner
- 禁止判断 visualKind
- 禁止创建 DSL node

------------------------------------------------------------
2. background.py
------------------------------------------------------------

职责：

- local background estimation
- edge / ring sampling
- median RGB
- RGB variance
- local blur background map
- foreground difference map

允许 import:

- numpy
- PIL.ImageFilter 可通过 arrays 或内部函数使用

禁止：

- 禁止决定 preserve_raster / shape_geometry
- 禁止决定 cleanup
- 禁止直接返回 allow/reject

输出只能是：

- rgb
- variance
- distance map
- background map
- metrics dict

------------------------------------------------------------
3. masks.py
------------------------------------------------------------

职责：

- binary mask 创建
- mask AND / OR / SUBTRACT
- mask area
- mask bbox
- mask overlap
- mask IoU
- mask containment
- text mask expansion

允许 import:

- numpy

禁止：

- 禁止决定这个 mask 是 icon / text / component
- 禁止签发 cleanup authorization

------------------------------------------------------------
4. morphology.py
------------------------------------------------------------

职责：

- remove small objects
- binary open / close
- dilate / erode
- fill small holes
- optional smooth mask

允许 import:

- skimage.morphology
- numpy

禁止：

- 禁止把 morphology 结果直接解释成 design object

------------------------------------------------------------
5. components.py
------------------------------------------------------------

职责：

- connected component labeling
- regionprops extraction
- bbox / area / centroid / fill ratio
- filter tiny components
- return pure component metrics

允许 import:

- skimage.measure
- numpy

禁止：

- 禁止决定 icon candidate 是否 materialize
- 禁止返回 DSL node

------------------------------------------------------------
6. alpha.py
------------------------------------------------------------

职责：

- mask -> alpha channel
- soft alpha
- RGBA PNG bytes
- apply alpha to crop
- compute alpha coverage
- foreground bbox from alpha

允许 import:

- PIL.Image
- numpy

禁止：

- 禁止决定是否采用该 alpha asset
- 禁止写文件路径
- 禁止创建 materialized image node

------------------------------------------------------------
7. debug.py
------------------------------------------------------------

职责：

- draw bbox overlay
- draw mask overlay
- preview sheet
- diagnostic images

允许 import:

- PIL.Image
- PIL.ImageDraw

禁止：

- 禁止在 runtime 关键路径强制执行
- 禁止影响 pipeline output
- 禁止改变任何 report/materialization 结果

------------------------------------------------------------
8. metrics.py
------------------------------------------------------------

职责：

- luma
- edge strength
- texture score
- color distance
- variance
- simple SSIM-like helper 或为后续 local visual diff 留接口
- pixel difference metrics

允许 import:

- numpy
- skimage.filters / skimage.metrics 可选

禁止：

- 禁止直接输出 accept/reject
- 禁止替代 EvidenceScore 决策层

============================================================
六、必须新增 import boundary 测试
============================================================

请新增测试，确保依赖不会越权。

例如：

backend/tests/test_image_math_import_boundaries.py

测试内容：

1. backend/app/image_math/ 内允许 import numpy、PIL、skimage。
2. backend/app 其他模块不得直接 import skimage。
3. backend/app 其他模块不得直接 import numpy，除非在白名单里。
4. backend/app 其他模块不得直接 import PIL，除非在白名单里。
5. rich 不得出现在 backend/app 下。
6. image_math 不得 import:
   - source_ui_physical_graph
   - m29_replay_plan
   - plan_materializer
   - dsl schema
   - renderer
   - upload_preview pipeline
7. image_math 下不得出现以下字符串：
   - pixelOwner
   - replayDecision
   - cleanupAuthorization
   - materialize
   - autoLayout
   - componentIdentity

如果现有代码中已有直接 import，可以先保留白名单，但必须在测试注释里说明迁移计划。

============================================================
七、先不改变行为
============================================================

第一轮提交必须尽量 behavior-invariant。

要求：

1. 不改变现有 design.dsl.json 结构。
2. 不改变 plan_materializer 输出。
3. 不改变 M29.5 replay plan 输出。
4. 不改变 Figma Renderer 行为。
5. 不启用新的 Auto Layout。
6. 不启用新的 Component。
7. 不启用新的 cleanup 路径。
8. 不让 image_math 的结果直接进入 visible node。

如果你必须改变行为，请单独列出：

- 改了什么
- 为什么必须改
- 影响哪些测试
- 是否可通过 feature flag 关闭

============================================================
八、优先重构的目标模块
============================================================

请优先审查并逐步重构这些模块：

1. backend/app/media_internal_decomposition/candidates.py
   - 目标：将手写 connected component / foreground mask / local background 逻辑逐步迁移到 image_math。
   - 第一轮只允许 report-only 输出不变。
   - 保留旧实现作为 fallback 或 feature flag。

2. backend/app/transparent_asset_report/alpha.py
   - 目标：将 alpha coverage、foreground bbox、mask -> RGBA PNG 迁移到 image_math.alpha。
   - 不改变 transparent_asset_report 的决策语义。

3. backend/app/visual_primitive/components.py
   - 目标：将连通域基础算法抽象到 image_math.components。
   - 第一轮不要改变 detected components 的结果；可以先并行跑新旧实现，输出 debug diff。

4. backend/app/png_tools/sampling.py
   - 目标：将 sampling 的底层像素循环逐步替换为 image_math.background / arrays。
   - 保留旧实现。

5. backend/app/dsl_visual_comparison/
   - 目标：为 local candidate visual diff 留接口。
   - 第一轮可以只新增 metrics helper，不启用 gate。

6. backend/app/ownership_conservation/
   - 目标：为后续像素级 owner heatmap / wrong cleanup area 留接口。
   - 第一轮只做数据结构准备，不改变报告主逻辑。

============================================================
九、EvidenceScore 初始设计
============================================================

请不要一上来大改所有 confidence。

但请新增一个轻量的 EvidenceScore 结构或 helper，为后续迁移做准备。

例如：

backend/app/evidence_score/
  __init__.py
  types.py
  scoring.py

或者放在更合适的位置。

第一轮只提供工具，不强行改现有模块。

建议字段：

- source_confidence
- geometry_consistency
- pixel_consistency
- relation_consistency
- anchor_consistency
- repetition_consistency
- render_back_consistency
- ownership_conflict_penalty
- cleanup_risk_penalty
- texture_penalty
- repair_cost_penalty
- final_score
- decision: report | review | allow | reject
- reasons
- risks

注意：

1. EvidenceScore 第一轮只作为 report helper。
2. 不替代 M29.5 replay plan。
3. 不直接改变 materializer。
4. 后续可逐步用于 media_internal_decomposition、transparent_asset_report、finite control background。

============================================================
十、Media Internal Decomposition 后续规划
============================================================

请不要直接把轮播图内部元素全部 materialize。

按阶段规划：

Phase 1: report-only
- 保持当前内部候选报告
- 使用 image_math 提升 foreground mask / connected component 性能
- 不改变 DSL

Phase 2: internal UI text report/promotion split
- 先区分 internal UI label 与 artistic text
- 先 report，再 promotion
- 不 cleanup

Phase 3: internal icon alpha candidate
- 使用 image_math.alpha 生成透明 asset candidate
- 不 cleanup parent media

Phase 4: cleanup authorization
- 只有 M29.5 replay plan 明确授权后，才允许 copied media cleanup
- 必须经过 ownership conservation 和 render-back check

Phase 5: action row / group candidate
- icon + text anchor matching
- repetition / gap stability
- sibling group candidate
- 不生成 Auto Layout

Phase 6: controlled materialization
- 只生成 transparent group / C group
- 不生成 Auto Layout
- 不生成 Component
- 不生成 Variant
- 不绑定 token

请确保代码或文档中体现这个阶段策略。

============================================================
十一、有限控件 / button / search box
============================================================

请审查 source_ui_physical_graph/controls.py 和相关代码。

目标：

不要继续增加 searchbox/button/badge 等样例特化。

请逐步抽象为：

finite_control_background evidence model

它可以使用这些证据：

- OCR containment
- finite bbox
- stable local fill
- raw shape overlap
- outer ring boundary delta
- low texture score
- low image-like penalty
- reasonable aspect ratio
- foreground text/icon relation
- render-back consistency，后续

不要根据：

- 文案
- 页面行业
- 颜色主题
- 固定坐标
- 某张截图的 bbox
- 某个文件名

来判断控件。

第一轮可以只做审计报告或 TODO，不要冒然大改 controls.py。

============================================================
十二、需要新增/更新文档
============================================================

请新增或更新以下文档：

1. docs/decisions/0074-introduce-image-math-execution-dependencies.md

内容包括：

- Context
- Decision
- Allowed usage
- Forbidden usage
- Consequences
- Validation
- Non-goals

核心句子：

Pillow / NumPy / scikit-image are image math execution dependencies.
They are not source truth dependencies.
They must not decide ownership, replay, cleanup, materialization, component identity, or Auto Layout permission.

2. docs/architecture/image_math_boundary.md

说明：

- image_math 的职责
- 允许 import
- 禁止 import
- 哪些模块可以使用 image_math
- 哪些模块必须保持 domain decision authority
- 迁移策略

3. docs/plans/active/058-image-math-dependencies-and-evidence-gates.md

写清：

- P0
- P1
- P2
- P3
- P4
- P5
- 每阶段目标、改动、测试、风险、回滚

4. docs/checklists/m29-runtime-fact-check.md

检查：

- report-only 是否真的 report-only
- materializer 是否越权
- cleanup 是否只有 M29.5 签发
- renderer 是否没有补丁特化
- image_math 是否没有 domain 决策

============================================================
十三、测试要求
============================================================

请至少新增：

1. test_image_math_arrays.py
2. test_image_math_masks.py
3. test_image_math_components.py
4. test_image_math_alpha.py
5. test_image_math_import_boundaries.py
6. test_json_tools.py

如果修改了 media_internal_decomposition 或 transparent_asset_report，请新增/更新：

7. test_media_internal_decomposition_image_math_parity.py
8. test_transparent_asset_alpha_image_math_parity.py

测试重点：

- 新旧实现结果一致或差异在可解释范围内
- 不改变 DSL
- 不改变 materializer
- 不改变 replay plan
- alphaCoverage 正确
- component bbox 正确
- mask IoU 正确
- orjson 输出 schema 不变
- import boundary 通过

============================================================
十四、验证命令
============================================================

请完成后运行：

backend:
cd backend
uv sync
uv run pytest -q

如项目有前端/插件：
cd ..
pnpm install
pnpm run check

如有 batch validation：
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir <本地样本目录> --poll-timeout 300

如果某些命令无法运行，请说明原因，不要假装通过。

============================================================
十五、输出格式
============================================================

完成后请输出：

1. 总体变更摘要
2. 新增依赖
3. 新增文件
4. 修改文件
5. 行为是否改变
6. 是否改变 DSL 输出
7. 是否改变 materialization
8. 是否改变 replay plan
9. 测试结果
10. 未完成项
11. 风险
12. 下一阶段建议

请特别标注：

- Behavior invariant: yes/no
- DSL changed: yes/no
- Materialization changed: yes/no
- Replay plan changed: yes/no
- Cleanup behavior changed: yes/no
- New dependencies isolated: yes/no
- Import boundary tests added: yes/no

============================================================
十六、破坏性重构许可
============================================================

你可以进行破坏性重构，但只能破坏：

- 文件组织
- 内部工具函数
- 重复底层像素算法
- 无领域语义的 helper
- report-only 内部实现
- 测试结构
- 文档结构

你不能破坏：

- DSL schema
- public API
- upload_preview 主行为
- M29.5 replay plan 语义
- cleanup authorization 语义
- materializer 的许可边界
- Figma renderer 输出语义

如果你认为必须破坏这些，请先输出 RFC，不要直接改。


第一轮 PR 只允许做到 P0–P1，不允许直接进入 P3–P6。也就是说：先加依赖、建 image_math、补测试、写 ADR、保证 behavior invariant。等我审核通过后，再继续把 media_internal_decomposition 和 transparent_asset_report 迁移到 image_math。
