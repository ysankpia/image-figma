# M30.3 Text Font Size Harmonization

- 状态：completed
- 创建日期：2026-05-20
- 负责人：Antigravity

## Goal

解决同一排（如 Tab 栏、横向排列的菜单、卡片底部的同一行信息）字被识别出来大小不一致（由于 OCR 边界检测带来的高度微小抖动）的问题。
利用第一性原理，在生成 DSL 时自动对水平对齐、字号相近的文本进行自适应归一化（Harmonization）。

## Scope

包含：
- 在 `backend/app/evidence_grounded_dsl_materialization.py` 中重构 `harmonize_text_font_sizes` 逻辑。
- **水平对齐判定**：依据 Y 坐标中心点的距离与文本高度的比例（$\Delta y_{center} \le \max(8.0, \min(h_1, h_2) \times 0.4)$）。
- **归一化算法（自适应众数归一）**：
  1. 在单行内统计每个字号出现的频率（Frequencies）。
  2. 寻找最频出的字号（Mode）。
  3. 基于 Mode 大小自适应计算容差门限：$\text{threshold} = \max(3, \min(6, \text{round}(\text{mode\_fs} \times 0.18)))$。
  4. 将该行内所有处于 $[\text{mode\_fs} - \text{threshold}, \text{mode\_fs} + \text{threshold}]$ 范围内的文本字号全部归一为 $\text{mode\_fs}$。
  5. 对剩余文本迭代执行上述步骤，如果频率全部为 1 则退化为基于相邻差值值聚类的中位数归一策略。
- **边界与限制**：
  - 不强制对齐跨行或字号本身差异极其巨大的文本（如特大标题与极小角标）。

## Steps

1. 修改 `backend/app/evidence_grounded_dsl_materialization.py`，实现 `harmonize_text_font_sizes` 自适应众数对齐函数。
2. 在 `backend/tests/test_evidence_grounded_dsl_materialization.py` 中编写单元测试 `test_text_font_size_harmonization_mode_snapping`。
3. 运行测试并通过。
4. 在 `task_9a96ac511404` 真实数据中复核 Tab 栏对齐效果。

## Acceptance

- 同一排中由于检测高度抖动导致的类似文本（如导航 Tab 栏），生成 DSL 中的 `fontSize` 完全一致。
- 跨行或字号本就不同的文本（如大标题和小标）保持各自原有字号，不被错误合并。

## Validation

### Automated Tests
```bash
pytest backend/tests/test_evidence_grounded_dsl_materialization.py
```
- 全部 16 个测试点顺利通过（包含新加入的 `test_text_font_size_harmonization_mode_snapping`）。

### Manual Verification
在 `task_9a96ac511404` 真实测试集上，Tab 栏的实际字号输出为：
- 推荐: fs=36 (高亮选中项，保持较大字号)
- 穿搭: fs=30 (众数归一)
- 美妆: fs=30 (众数归一)
- 旅行: fs=30 (众数归一)
- 探店: fs=30 (原 fs=35 众数归一)
- 家居: fs=30 (众数归一)
- 美食: fs=30 (原 fs=25 众数归一)
- 三: fs=20 (Hamburger 图标项，保持独立字号)
结果完全满足一致性设计预期。
