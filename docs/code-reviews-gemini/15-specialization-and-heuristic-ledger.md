# 15 Specialization and Heuristic Ledger

## 1. source truth
本层认定的“物理事实”是：
* **当前 active 主线后端各层代码中硬编码的所有数值、布尔过滤网控和代数权重公式**。
本层扮演了项目“启发式特化总台账”的角色。第一性原理认为，真正的通用视觉还原模型应当是“分辨率无关”（Resolution-agnostic）且“无宿主特例”（Context-free）的。本层系统性梳理项目中到底埋藏了哪些依赖于“特定尺寸、固定间距或硬性面积”的特殊经验阈值，区分哪些是合理的数学比例因子，哪些是由于特化倾向埋下的隐性漏洞。

## 2. input artifacts
本层分析读取的输入文件包括：
* 后端 M29 流水线的所有核心代码（`candidates.py`、`alpha.py`、`scoring.py`、`cleanup.py`、`detectors.py`等）。

## 3. output artifacts
本层写入的输出文件包括：
* **特化与启发式阈值总账报告**：`specialization-and-heuristic-ledger`（即本报告文档）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* 各层包中的常量定义和条件分支语句（例如各层头部的常量列表）。

## 5. decision authority
* **决策权**：**无/纯审计账本**。
* **说明**：只做静态分类和风险量化评估，不修改代码。

## 6. report-only surfaces
* **报告面**：**完整**。
结果归档于本报告中。

## 7. allowed facts
本层判定并记录的物理事实：
* **主线中无明文业务特化**：物理扫描证实，当前 active 后端代码中**没有**针对具体中英文业务品牌（如 Google/Facebook、充值/提币/划转）、文件名（如 `"Google_Icon.png"`）或硬编码任务 ID 的特例分支。
* **存在大量分辨率特化数值**：存在大量依赖于绝对像素大小（如 $\le 18\text{px}$、$< 3200\text{px}^2$）的硬编码分类阀值。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止删除或更改这些阈值**：不能在没有数学重构方案前擅自调小或调大任一数值。

## 9. main formulas / gates
各层核心硬编码公式汇总：
* 参见前文各层报告（03、08、09、10）中的 $\text{score}$、$\text{pos}$、$\text{neg}$、$\text{coverage}$ 线性加权公式。

## 10. thresholds and heuristic rationale
后端核心硬编码阈值完整分类账（Ledger）：

### A. 属于“合理几何/色彩数学参数”的指标 (Valid Mathematical Parameters)
这些指标采用比例、百分比或中值色差，不依赖于截图绝对分辨率：
1. **重叠冲突率**：$\text{overlap\_ratio} \ge 0.20$。设计 rationale：控件间重合超过 $20\%$ 预示遮挡，符合空间拓扑常识。
2. **文本重叠率**：$\text{text\_overlap} \le 0.20$。设计 rationale：允许图标与标签边缘轻微贴边，但超过 20% 即为重合遮盖。
3. **连通域长宽比**：$\text{aspect\_ratio} \le 10.0$。设计 rationale：图标长宽比不可能超过 10 倍，否则即为条状分割线。
4. **主导背景覆盖率**：$\text{coverage} \ge 0.36$。设计 rationale：至少 $36\%$ 的边界像素落入主色簇，才能代表该背景为单色稳定底。
5. **背景像素灰度方差**：$\text{bg\_variance} \le 18.0$。设计 rationale：卡片单色背景允许微弱噪点，但方差超 18 即非单色背景。
6. **擦除边界 Alpha 门限**：$\text{alpha\_value} > 32$。设计 rationale：过滤边缘抗锯齿极度透明像素，防止擦除过界。

### B. 存在“隐性特化风险”的绝对像素指标 (Specialization Smells)
这些指标依赖于“标准移动端 $1\text{x}$ 分辨率”的静态假设，在 $2\text{x}/3\text{x}$ 视网膜（Retina）屏幕或超高分辨率长图上极易失效：
1. **选项背景 Ellipse 判定**：$\text{area} < 3200$。来自 `detectors.py`。设计 rationale：判定选项小红点或圆角框。风险：在 3x Retina 屏上，一个正常的圆角头像面积可能轻松超过 3200 像素，导致被误判为大卡片。
2. **Tab 栏高度**：$\text{height} \le 18$。来自 `detectors.py`。设计 rationale：标准 Tab 条高度在 $18\text{px}$ 左右。风险：在高分辨率大屏上极易漏判。
3. **像素连通域面积上下限**：$\text{PIXEL\_COMPONENT\_MIN\_AREA} = 20$，$\text{PIXEL\_COMPONENT\_MAX\_AREA} = 5200$。来自 `candidates.py`。设计 rationale：假定图标通常在 20 到 5200 像素之间。风险：Retina 屏上的大图标（如 96x96 @3x，面积为 9216）会被直接作为 fragment 排除，彻底丧失晋升机会。
4. **最小短边长度**：$\text{MIN\_SHORT\_EDGE} = 8$。设计 rationale：小于 $8\text{px}$ 的为垃圾噪声像素。风险：高分图上的极细矢量线图标会因此被枪毙。
5. **文本遮罩安全边界**：固定 $3\text{px}$ 外扩。来自 [padded_bbox](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L116)。设计 rationale：为 OCR 文本添加 $3\text{px}$ 的膨胀遮罩防误切。风险：在 Retina 3x 或大粗字体图上，3px 过小，文字边缘笔画极易溢出遮罩，导致溢出部分被误识别为 icon 碎屑接受，进而触发 `text_overlap_too_high`。
6. **前景像素绝对色彩对比度**：$\text{color\_distance} \ge 55$。设计 rationale：前景与背景色差大于 55 视为有效分界。风险：在低对比度设计、极简灰白 UI 中，合法控件色差仅为 20~30，会导致大面积漏判。

## 11. known information loss
* **无损盘点**：本报告为静态分类，不损失信息。

## 12. known failure symptoms
* **高分 Retina 长图识别崩塌**：当用户上传宽度为 $1125\text{px}$ 或 $1242\text{px}$ 的 $3\text{x}$ iPhone 截图时，由于图标面积膨胀了 9 倍，绝大多数 icon 面积超过了 5200 上限，直接触发 `large_media_fragment` 被拒绝；或者短边过滤导致其长宽比错位，使得原本可以完美提取的 Google 图标全被丢弃。

## 13. tests / guards
* **测试用例**：
  在各单元测试中，所有 Mock 的 bbox 均为 $1\text{x}$ 绝对像素（如 24x24 按钮，36x36 图标）。这形成了 CI 侧的特化保护盾，反向固化了这一绝对像素依赖，阻碍了对自适应系统的重构。

## 14. artifact evidence
* **物理证据**：
  查阅 [candidates.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L15-L21) 的常量定义：
  ```python
  PIXEL_COMPONENT_MIN_AREA = 20
  PIXEL_COMPONENT_MAX_AREA = 5200
  PIXEL_COMPONENT_MIN_SHORT_EDGE = 8
  PIXEL_COMPONENT_MAX_ASPECT_RATIO = 10.0
  ```
  无任何分辨率缩放因子（`scale`）参与运算，坐实了分辨率特化事实。

## 15. findings
* **P1 (raw_m29 / m29_6_internal_decomposition)**: 绝对像素特化硬伤。后端缺乏“物理分辨率自适应”（Scale-adaptation）机制。目前的 M29 检测系统既不知道图像是 1x, 2x 还是 3x，也没有基于全局 OCR 字符平均字高进行动态尺寸换算的机制，而是采用绝对的 $5200\text{px}^2$ 面积和 $8\text{px}$ 边界对全部图片一刀切，这是导致大图和 Retina 图还原质量急剧下滑的第一根源。

## 16. recommended next action
* **引入基于全局字高的动态比例尺**：废除硬编码的 `5200`、`20`、`8` 等绝对像素阈值。在上游通过统计 OCR Blocks 的平均高度，得出基准物理单位 $1\text{rem} = \text{mean\_ocr\_height}$。以此 rem 单位为基底，将连通域大小转换为相对单位（如最小面积 $\ge 0.05\text{rem}^2$，最大面积 $\le 6.0\text{rem}^2$），使整个识别链条自适应缩放。
