# 083 Go M29 VisualTree 结构对齐 Codia(空间聚类 1:1)

- 状态:completed
- 创建日期:2026-05-29
- 负责人:未指定(可交由 Codex 执行)
- 所属链路:`services/backend-go` 的 M29 VisualTree 编译层

> 历史说明：本计划记录的是旧 Go M29 VisualTree / XY-cut 对齐阶段。后续 raw Codia canvas 审计和 Codia-like compiler 工作已经替代了“纯几何空间聚类可接近 Codia 1:1”的判断。Go Codia-like compiler 目前暂停在 `docs/plans/archive/deferred/089-go-codia-like-compiler-rebuild.md` 的 Beta checkpoint；当前 Beta 质量瓶颈和 detector 后续路径见 `docs/bugs/open/017-codia-like-beta-ui-role-detector-gap.md`。本文保留作历史追溯，不作为新实现合同。

## 一、任务背景

本项目目标:截图 PNG → 可编辑 Figma 设计树(类似 Codia AI Design)。正式后端为 Go(`services/backend-go`)。链路:

```
PNG → m29extract(连通域primitive) → m29tokens(evidence token)
   → m29relations(关系图) → m29visualtree(编译成可编辑树) → visual_tree.v1.json
```

**历史核心认知(后续已降级):** 当时判断 Codia pipeline = 感知(切图 + OCR + 元件定位)→ **编译(纯几何空间聚类成嵌套树,无语义)** → 机械命名 → 像素测量样式。后续多样本 raw canvas 审计和 Xianyu tiny ImageView 证据显示，当前主线不能继续把纯几何聚类当作 Codia-like 质量上限。旧 `.fig` / canvas 解析笔记已归档到 `docs/reference/legacy/codia-exploration/codia-fig-reverse-engineering.md`，raw Codia `.canvas.json` samples 仍是 golden truth。

**关键事实:** Codia 只用 4 种节点 `FRAME(容器,命名 Groups / 可点 Button) / TEXT / ROUNDED_RECTANGLE(Image 或 Background)`。层级完全靠**空间包含 + 聚类**算出来,不是语义识别。

## 二、当前现状(已完成)

1. **对比工具(标尺)已建好**:`services/backend-go/tools/compare_trees.py`。加载 Codia 真实树与 Go 输出树,归一化到绝对坐标,计算结构相似度。
   ```bash
   python3 services/backend-go/tools/compare_trees.py
   ```
   核心指标:**分组召回率**(Codia 容器组里 Go 有多少也聚成组 IoU≥0.6)、**综合相似度**(0.7×召回 + 0.3×深度比;1.0=完全 1:1)。

2. **编译层已重写**:`services/backend-go/internal/m29/visualtree/spatial_group.go` 实现 **XY-cut 递归空间聚类 + 邻近连通兜底**,替换旧的"找行 + 魔法阈值"逻辑(旧逻辑在 `group.go` 的 `applyVisualGroups`,已不再被调用)。

3. **已提交基线**:`03b99f6 feat: align go m29 visual tree closer to codia structure` 把综合相似度推进到 **0.761**,分组召回 **0.659**。该阶段已包含:
   - `contained_pair_group` / `text_background_group` / `vertical_pair_group` 这类 Codia-like 机械几何配对。
   - 物理背景叶子沉底,避免大背景参与前景 XY-cut。
   - `visual_element.v1.json` 输出雏形,用于后续对齐 Codia `VisualElement` envelope。

4. **已提交 surface evidence 阶段**:`f581d88 feat: emit codia-like visual element and recover surface foreground evidence` 已进一步放开 M29.0 surface evidence:
   - 允许有 OCR 锚点的贴边大 surface,例如顶部/底部大 UI band,不再因触碰图片边缘被无条件拒绝。
   - 对每个 surface 在排除 OCR mask 后做局部背景残差提取,把 surface 内部 icon / foreground component 保留为物理 primitive。
   - Tencent Codia 样本验证:primitive **252**,token **151**,VisualTree node **268**,分组召回 **0.756**,综合相似度 **0.829**。
   - 已尝试 `horizontal_lane_group`,但真实样本降到 **0.812**,因此按证据驱动原则撤回,不进入本阶段。

5. **当前完成阶段**:VisualTree contained foreground grouping 已补齐:
   - `contained_foreground_group`:保留紧凑 text/background 配对,并允许高一些的 image tile 包住靠下文本。
   - `contained_slice_group`:当同一可信 parent scope 中,一个宽 Image 内包含多段同基线文本时,按文本中心线生成 source-referenced background slice groups。原始 Image 仍保留,不会被移动或删除。
   - VisualElement 输出移除 `Button` 机械命名,Layer 统一命名为 `Groups`,语义只保留在 `processingMeta.groupKind`。
   - Tencent Codia 样本最终验证:primitive **252**,token **151**,VisualTree node **267**,分组召回 **0.829**,综合相似度 **0.880**。

## 三、最终目标

让 `services/backend-go` 对测试图的输出树与 Codia 官方输出树结构 1:1。量化:`compare_trees.py` 综合相似度逼近 1.0(当前验证 **0.880**,目标 **0.85+**),其中**分组召回率是主要瓶颈**(当前验证 **0.829**,目标 **0.8+**)。

## 四、要做的事(按优先级)

### 任务 A(最高优先级):补 "文字+背景=Button" 包含配对

当前未匹配的 Codia 组**约一半是 `Button`**(模式:一个 TEXT + 一个紧紧包住它的圆角色块 ROUNDED_RECTANGLE)。两 bbox **完全重叠**,XY-cut 和邻近连通都切不出,需要第三种规则:**bbox 包含配对**。

- 思路:当一个 Text 被一个尺寸相近(背景面积不超过文字面积约 4 倍)的 Image/Layer 紧紧包含时,把两者配成一个组(synthetic 容器)。
- 数据已确认:对测试图,Go token 里有 11 处"文字被相近色块包含"。
- 注意:部分可能已在 `containment.go` 阶段建立父子关系,先排查哪些已配对、哪些仍是兄弟未配对。
- 完成状态:已实现 `contained_pair_group` / `contained_foreground_group` / `contained_slice_group`。仍不引入 Button 节点类型或 Button 命名。

### 任务 B:对齐分组边界(IoU≈0.5 的 Groups)

另一半未匹配是 IoU≈0.5 的 `Groups`(边界接近但差一点)。调查 XY-cut 切分边界为何与 Codia 差一截:可能 `spatialGapRatio`(当前常量 0.15)需更自适应,或切分点策略改为"每层只切最显著的一条缝"递归。

### 任务 C:大背景图沉底

部分区域一张大背景图(如 665×346)与上面小前景元素重叠,使 XY-cut 当一簇切不开。Codia 会把大背景图沉为 Background 层、不参与前景切分。需识别"覆盖大部分区域的大 Image",空间聚类时排除它(当背景),只对前景元素聚类。参考 token 已有的 `CompileHints.CanContainForeground`。

### 任务 D:修复 3 个过时单元测试

`internal/m29/visualtree/compiler_test.go` 中以下测试断言旧 `row_group` GroupKind(已被 `spatial_group` 取代)而失败:

- `TestCompileGroupsLocalProjectionRowAsSyntheticLayer`
- `TestCompileLetsSyntheticLayerParentContainedChildByBBox`
- `TestCompileCompletesRowGroupWithLocalProjectionSibling`

把断言更新为验证新的 XY-cut/spatial_group 行为(不是删除,是改成反映新逻辑的正确契约)。

### 任务 E:放开 M29.0 surface-local foreground evidence

当前已实现并验证。它解决的是上游“surface 内 icon / foreground 被背景同化后无法进入树”的问题,不是下游语义补丁:

- `detectSurfaceCandidates` 允许 OCR 锚定的贴边大 surface,但仍要求 surface 包含 OCR、面积受限、比例受限。
- `detectSurfaceForegroundComponents` 在 surface 内以局部背景色为基准提取残差前景,并继续排除 OCR text mask。
- 该阶段不引入 OpenCV / GoCV;用现有 Go mask + connected components 即可验证收益。
- CV 依赖只能作为后续 measurement backend 引入,必须证明它解决的是现有纯 Go kernel 无法稳定解决的测量问题,不能混入本阶段收益判断。

## 五、硬约束(必须遵守)

1. **历史约束：纯几何/通用规则,严禁语义特化。** 不许写 `bottom_nav`/`tab`/`card`/固定文案/固定坐标/主题色/文件名 等特化。只用通用空间关系:bbox 包含、投影空白带、局部密度、邻近连通、递归切分。这是旧 VisualTree 阶段的约束；当前 Go Codia-like compiler 已转向 role-aware pipeline 且暂停在 Beta checkpoint，见 `docs/plans/archive/deferred/089-go-codia-like-compiler-rebuild.md` 和 `docs/bugs/open/017-codia-like-beta-ui-role-detector-gap.md`。
2. **不分裂主线。** 改进直接写进 Go(`services/backend-go`),不在 Python 另起炉灶;Python 仅用于对比标尺。
3. **证据驱动,每次改动都用对比工具验证。** 改完跑 `compare_trees.py`,分数升才保留,降就回滚。不要在单一指标上调参陷入局部最优(历史失败模式)。
4. **节点类型收口在 `Body/Layer/Text/Image`**,不引入语义节点类型(`TestCompileDoesNotCreateSemanticNodeTypes` 必须始终通过)。
5. **`go test ./services/backend-go/...` 最终必须全绿。**

## 六、验证方式(完整复现命令)

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go

# 1. 跑完整链路生成 Go 输出树(测试图已压缩到 1440 以内)
IMG="/Users/luhui/Downloads/腾讯动漫_018_1440.png"   # 若不存在,用任意测试图重新走链路
OUT="/tmp/go_run"; mkdir -p "$OUT"
go run ./cmd/m29extract   -input "$IMG" -out "$OUT"
go run ./cmd/m29tokens    -input "$OUT/m29_physical_evidence.v1.json" -out "$OUT"
go run ./cmd/m29relations -input "$OUT/evidence_tokens.v1.json" -out "$OUT"
go run ./cmd/m29visualtree -tokens "$OUT/evidence_tokens.v1.json" -relations "$OUT/relation_graph.v1.json" -out "$OUT"

# 2. 对比打分(核心标尺)
cd .. && python3 services/backend-go/tools/compare_trees.py

# 3. 单元测试必须全绿
cd services/backend-go && go test ./internal/m29/visualtree/...
```

**当前验收标准:** 综合相似度保持 **0.880** 量级且高于目标 0.85;分组召回率保持 **0.829** 量级且高于目标 0.8;`visual_element.v1.json` 生成;`go test ./...` 全绿;不违反任何硬约束。

本阶段已验证:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go
go test ./...

OUT=/tmp/go_run_083_final_verify
rm -rf "$OUT" && mkdir -p "$OUT"
IMG='/Users/luhui/Downloads/腾讯动漫_018_1440.png'
go run ./cmd/m29extract -input "$IMG" -out "$OUT"
go run ./cmd/m29tokens -input "$OUT/m29_physical_evidence.v1.json" -out "$OUT"
go run ./cmd/m29relations -input "$OUT/evidence_tokens.v1.json" -out "$OUT"
go run ./cmd/m29visualtree -tokens "$OUT/evidence_tokens.v1.json" -relations "$OUT/relation_graph.v1.json" -out "$OUT"
test -f "$OUT/visual_element.v1.json"
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
python3 services/backend-go/tools/compare_trees.py docs/reference/codia-samples/tencent-comic-018.canvas.json "$OUT/visual_tree.v1.json"
```

## 七、关键文件清单

| 文件 | 作用 |
|---|---|
| `services/backend-go/internal/m29/visualtree/spatial_group.go` | **主战场**:XY-cut 空间聚类(任务 A/B/C) |
| `services/backend-go/internal/m29/visualtree/compiler.go` | 建树主流程(`buildTree` 顺序:containment → spatial grouping) |
| `services/backend-go/internal/m29/visualtree/containment.go` | bbox 包含建父子(任务 A 需了解,避免重复) |
| `services/backend-go/internal/m29/visualtree/compiler_test.go` | 单元测试(任务 D) |
| `services/backend-go/tools/compare_trees.py` | 对比标尺(不改其评分逻辑,只用它验证) |
| `docs/reference/legacy/codia-exploration/codia-fig-reverse-engineering.md` | 历史 Codia 结构分析(只作追溯) |
| `docs/reference/codia-samples/tencent-comic-018.canvas.json` | Codia 标准答案树 |

## 八、可选增强(行有余力)

- 再导出 2~3 张不同 App 的 Codia `.fig` 作对照集,扩展 `compare_trees.py` 支持多图平均分,避免只对单图过拟合。
- XY-cut 切分点策略可参考 ChatGPT 提议的"每层只切最大空白缝 + 邻近连通兜底"的双阶段思路(已部分吸收)。
