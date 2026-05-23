# M29 Direct Source Support And Layer Order Fix

- 状态：active
- 创建日期：2026-05-23
- 负责人：未指定

## Goal

修复 M29 Direct 左侧实验路径里的两个物理问题：

```text
1. replay 层级顺序错误导致 image 盖住 text。
2. raw M29 看不见低对比支撑区域，导致输入框/搜索框这类 support shape 无法进入后续 ownership/replay。
```

这不是 UI 语义 detector。目标是让 source primitive graph 能产生低对比 support region，并让 replay 顺序符合可见物理层级。

## Scope

包含：

- M29.5 replay plan 和 M29 Direct replay 使用统一可见层级顺序：
  ```text
  shape/support/background -> image -> icon -> text
  ```
- raw M29 增加 `low_contrast_support` shape 检测。
- M29.2 将 `low_contrast_support` 当作可 replay 的 support geometry 消费。
- 低对比 support 检测同时支持浅色和深色主题，只依赖局部稳定填充、内外环颜色差异、内部 OCR text 和同线 foreground evidence。

不包含：

- 不做 OCR-symbol leakage cleanup。
- 不处理头像、底部 tab、小纹理 foreground ownership。
- 不新增 SearchBar/Card/TabBar 这类语义规则。
- 不改主线 `/api/tasks/{taskId}/dsl`。
- 不新增 route，不改插件 UI。

## Steps

1. 调整 M29.5 plan 的 visible order 和 node budget priority，保证 shape/image/icon/text 顺序稳定。
2. 在 raw M29 source extraction 中加入低对比 support detector。
3. 让 detector 只从 OCR text + 同线 foreground evidence 的 bbox 并集生成候选，避免固定宽度吞整行。
4. 删除浅色主题假设，不用亮度作为通过条件。
5. M29.2 消费 `low_contrast_support` 为 `shape_geometry + shape_replay`。
6. 增加浅色、深色、纯背景文字、textured media 和 replay 层级回归测试。

## Acceptance

- 商品图或 media 下方的 text replay 不被 image replay 盖住。
- raw M29 对低对比输入支撑区域输出 `shape` subtype `low_contrast_support`。
- 用户验收图中搜索区域能产生接近真实输入框主体的 support bbox，并穿过 M29.2、M29.5、M29 Direct DSL。
- 深色主题低对比 support region 也能被检测。
- 纯背景文字不会强造 support region。
- 大 textured media/banner 不会被低对比 support detector 吞掉。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_direct_replay.py -q
uv run pytest tests/test_visual_primitive_graph.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_region_relation_kernel.py tests/test_region_relation_graph_report.py tests/test_stable_design_cluster.py -q
cd ..
git diff --check
git status --short --branch
```

手工验收样本：

```text
/Users/luhui/Downloads/m29/ChatGPT Image 2026年5月17日 14_47_13 (4).png
```

验收点：

- M29 Direct 左侧搜索框背景出现，并能作为 shape 选中。
- 搜索框文字仍在 shape 上方。
- 商品图上的 editable text 不再被 image 盖住。
- 右侧 Current Mainline 不变。

## Notes

- `Q春日穿搭灵感` 里的 leading `Q` 属于 OCR-symbol leakage，本阶段明确不修。
- 头像和底部 tab icon 成块属于小型纹理 foreground ownership，本阶段明确不修。
- 低对比 support detector 的 source truth 是像素区域的稳定填充和局部关系，不是“搜索框”这个语义名。
