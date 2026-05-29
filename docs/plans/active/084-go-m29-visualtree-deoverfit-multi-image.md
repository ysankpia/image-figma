# 084 Go M29 VisualTree 瘦身去过拟合(多图稳健化)

- 状态:active (A/C/D 完成,B 部分完成)
- 创建日期:2026-05-29
- 前置:083(已让综合分从 0.22 提到单图 0.88)
- 负责人:未指定(可交由 Codex 执行)

## 进度记录

### 当前评测结果(2026-05-29)

```
图            召回     Codia容器  Go容器   综合分
腾讯动漫018    0.829      41        86      0.880
腾讯动漫022    0.714      28        60      0.800
荔枝011        0.844      32        46      0.891
闲鱼           0.714      35        57      0.800
------------------------------------------------
平均综合分                                  0.843  ✅ (目标 ≥0.792)
最低综合分                                  0.800  ✅ (目标 ≥0.78)
```

### 任务完成情况

- ✅ **任务 A**: 删除写死像素阈值。`canUseTextBBoxAsBackground` 中 `Height>34`/`Width<40` 已替换为纯相对判据(宽高比 ≥ 2.5)。
- ⚠️ **任务 B**: 容器灌水未达标(Go/Codia 比 1.44~2.14,目标 ≤1.2)。主要来源是 TEXTBG 为每个宽型文本创建容器。禁用 TEXTBG 会降低召回率,与分数目标冲突。需要更精细的策略(如只在有物理背景证据时才创建 TEXTBG)。
- ✅ **任务 C**: 死代码清理完成。`group.go` 从 429 行缩减到 ~80 行,删除了全部废弃的 relation-based grouping 逻辑(applyVisualGroups/candidateGroups/rowProjectionGroups/connectedGroups/buildGroupNode 等)。`spatial_group.go` 删除了 `xycut` 的未使用参数 `parentBox`,修复了 range-over-int lint 警告。
- ✅ **任务 D**: 测试更新完成。`TestCompileLetsSyntheticLayerParentContainedChildByBBox` 改用 `findDescendant`(适配 XY-cut 嵌套行为)。`TestCompileSlicesWideContainedForegroundByTextBaseline` 更新为验证 TEXTBG 新行为。`go test ./...` 全绿。

### 新增功能

- **Straggler absorption**(仅 Body 层级):XY-cut 后,孤立叶节点被吸收进最近的相邻组(距离 < 目标组最大维度/2)。通过 `ABL_ABSORB` 环境变量可禁用。为 t022 和 lizhi 各增加 2 个匹配。

## 一、背景:083 达标了,但分数有水分

083 让 `services/backend-go` 的 VisualTree 编译层从单图综合相似度 0.22 提升到 0.88。但用 **4 张不同的图** 批量复核后,真实情况是:

```
图            召回     Codia容器  Go容器   综合分
腾讯动漫018    0.829      41        80      0.880   ← 083 调参用的图(过拟合高点)
腾讯动漫022    0.571      28        43      0.700
荔枝011        0.781      32        43      0.847
闲鱼           0.629      35        52      0.740
------------------------------------------------
平均综合分                                  0.792
最低综合分(防过拟合)                       0.700
```

**两个确诊问题:**

1. **单图过拟合**:0.88 只在 083 调参那张图上成立,真实平均是 0.792,最低 0.700。

2. **系统性容器灌水**:**4 张图的 Go 容器数全部超过 Codia**(41→80、28→43、32→43、35→52,普遍 1.3~2 倍)。说明编译层在到处"多包组"刷 IoU 召回,造出比 Codia 碎得多的树。这虽然能编辑,但层级冗余、不好用。

3. **写死像素阈值(违反 083 硬约束)**:`internal/m29/visualtree/spatial_group.go` 的 `canUseTextBBoxAsBackground` 里有 `if node.BBox.Height > 34 || node.BBox.Width < 40`。`34`/`40` 是绝对像素值,针对特定图调出,换高分屏大字图必崩。这正是项目历史失败的"手写视觉模型"模式(见 066)。

## 二、目标(从"追单图最高"转为"稳健 + 干净")

- **核心目标:提高最低综合分**(当前 0.700),目标 **≥0.78**;同时平均分不低于当前 0.792。
- **消除容器灌水**:让每张图的 Go 容器数接近 Codia(目标:Go 容器数 / Codia 容器数 ≤ 1.2,当前最坏 ~2.0)。
- **删除所有写死像素阈值**,改为相对判据(相对元素尺寸/中位数/父容器尺寸)。
- **代码瘦身**:`spatial_group.go` 当前 737 行、28 个函数,大量是为刷单图分加的细分规则。在不降低最低分的前提下尽量精简。

**重要:这是一次以"减规则"为主的任务,不是"加规则"。** 宁可单图分略降,换取最低分上升和泛化稳定。

## 三、唯一评测方式(考卷,不许改)

仓库已固化 4 图回归数据集和一键评测脚本:

```bash
bash services/backend-go/tools/eval_4img.sh
```

它对 `docs/reference/codia-samples/images/` 的 4 张图用当前 Go 代码统一生成 VisualTree,与 `docs/reference/codia-samples/*.canvas.json` 标准答案批量对比,输出**每图分 + 平均分 + 最低分**。

**铁律:每次改动后跑这个脚本。判据是【最低综合分】必须 ≥ 改动前,且平均分不下降。** 单图涨、最低分跌 = 过拟合 = 回滚。**不许修改 `compare_trees.py` 的评分逻辑或 `eval_4img.sh`(那是改考卷作弊)。**

## 四、要做的事(按优先级)

### 任务 A:删除写死像素阈值(最高优先级,硬约束修复)
定位 `spatial_group.go` 中所有绝对像素常量(如 `Height > 34`、`Width < 40`、以及其他写死的 `> 数字`/`< 数字` 比较)。改为相对判据:相对该批元素的中位尺寸、相对父容器尺寸、或相对配对对象自身尺寸。删完跑 `eval_4img.sh`,最低分不许跌。

### 任务 B:抑制容器灌水
排查哪些配对/分组规则导致 Go 容器数远超 Codia(`groupContainedForegroundSlices`、`pairVerticalForeground`、各种 `canPairAs*`/`canUse*` slice 细分)。逐个临时关掉,跑 `eval_4img.sh` 看影响:
- 关掉后**最低分不跌甚至升** → 这个规则是刷单图的,**删掉**。
- 关掉后**最低分明显跌** → 这个规则是真通用的,**保留**。
用数据决定每个规则的去留,不靠猜。目标:Go 容器数 / Codia 容器数 ≤ 1.2。

### 任务 C:代码精简
任务 A/B 删完后,清理死代码、合并重复逻辑,让 `spatial_group.go` 回归到清晰、单一职责的状态。同时删除 `group.go` 里已不再被调用的旧 `applyVisualGroups` 及其相关死代码(`candidateGroups`/`rowProjectionGroups`/`connectedGroups` 等,确认无引用后删)。

### 任务 D:修复/更新过时测试
`internal/m29/visualtree/compiler_test.go` 中断言旧 `row_group` 行为的测试需更新为反映当前 XY-cut/spatial 行为。`go test ./services/backend-go/...` 必须全绿。`TestCompileDoesNotCreateSemanticNodeTypes` 必须始终通过。

## 五、硬约束(继承 083,加强)

1. **严禁任何写死的绝对像素阈值。** 所有几何判据必须相对化(相对元素尺寸/中位数/父尺寸)。这是本任务的首要目的。
2. **严禁语义特化**(nav/tab/card/固定文案/固定坐标/主题色/文件名)。只用通用空间关系。
3. **以减规则为主。** 加规则需证明:能提升【最低分】,且不降平均分。仅提升单图分的规则一律不要。
4. **节点类型收口 `Body/Layer/Text/Image`**,不引入语义节点类型。
5. **不改评测工具**(`compare_trees.py` / `eval_4img.sh`)。
6. **`go test ./services/backend-go/...` 最终全绿。**

## 六、验收标准

```bash
# 1. 4 图回归(核心)
bash services/backend-go/tools/eval_4img.sh
#   要求:最低综合分 ≥ 0.78(当前 0.700),平均 ≥ 0.792(不下降)
#   要求:每张图 Go容器数 / Codia容器数 ≤ 1.2

# 2. 单元测试全绿
cd services/backend-go && go test ./...

# 3. 无写死像素阈值(应无输出或仅剩相对判据)
grep -nE "BBox\.(Height|Width) [<>] [0-9]+|[<>] [0-9]{2,}" internal/m29/visualtree/spatial_group.go
```

## 七、关键文件

| 文件 | 作用 |
|---|---|
| `services/backend-go/internal/m29/visualtree/spatial_group.go` | **主战场**:删写死阈值、抑制灌水、精简(任务 A/B/C) |
| `services/backend-go/internal/m29/visualtree/group.go` | 含已废弃的旧 `applyVisualGroups` 死代码(任务 C 清理) |
| `services/backend-go/internal/m29/visualtree/compiler_test.go` | 单元测试(任务 D) |
| `services/backend-go/tools/eval_4img.sh` | **一键 4 图评测(唯一考卷,不许改)** |
| `services/backend-go/tools/compare_trees.py` | 评分逻辑 + `--batch` 模式(不许改) |
| `docs/reference/codia-samples/*.canvas.json` | 4 张图的 Codia 标准答案树 |
| `docs/reference/codia-samples/images/*.png` | 4 张输入图 |
| `docs/reference/codia-fig-reverse-engineering.md` | Codia 真实结构分析 |

## 八、提醒

容器灌水的根因判断:Codia 对"并排的几个套餐/图标"通常包成一个父 Groups 再放几个子,而当前 Go 倾向于给每个小单元都额外包一层。瘦身时关注"是否在不必要处加了中间层"。Codia 的真实树普遍比当前 Go 树**浅而宽**(平均扇出更大),这是对齐方向。
