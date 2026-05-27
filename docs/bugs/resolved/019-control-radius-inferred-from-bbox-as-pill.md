# Bug: Control Radius Inferred From BBox As Pill

- 状态：resolved
- 创建日期：2026-05-27
- 影响范围：M29 model-first interactive source ownership and residual cleanup

## Summary

真实上传中，部分本应接近方形或小圆角的按钮被 materialize 成半高圆角的胶囊/椭圆。该问题不是 perception model 分类错误；模型只提供候选 bbox。错误发生在 M29 source ownership 层：control background 被默认写入 `shapeRadiusOverride = height / 2`，随后 M29.5 cleanup 也用 `rounded_rect` 半高 mask。

## Root Cause

`perception_source_compiler` 的 `inferred_radius(..., role="control")` 使用了错误抽象：

```text
height <= 96 and width / height >= 1.6 -> radius = height / 2
```

raw M29.2 的 low-confidence unknown control path 也有同类逻辑，按 `fillRatio/aspect` 推断半高 radius。这把“有限控件背景”误当成“胶囊按钮”。第一性原理上，圆角是像素边界几何事实，不是 bbox 比例事实。

## Fix

- perception source compiler 不再根据宽高比例推断 control radius。
- raw M29.2 low-confidence unknown control path 不再根据 `fillRatio/aspect` 推断 radius。
- 新增像素边界半径估计：从四个角沿边界测量第一个进入控件填充色的位置；矩形角点填满时返回 `None`，真实圆角/胶囊才写 `shapeRadiusOverride`。
- `claimMaskKind` 跟随半径证据：无 radius 使用 `bbox`，有 radius 使用 `rounded_rect`。
- M29.5 cleanup target 在 `rounded_rect` 时携带 `maskRadius`；materializer cleanup 使用该 radius，不再默认半高圆角擦除。

## Regression Guard

- `tests/test_perception_source_compiler.py` 覆盖方形 model control 不得写 radius，圆角 model control 必须写像素证明 radius 和 `maskRadius`。
- `tests/test_source_ui_physical_graph.py` 覆盖 raw low-confidence unknown 方形控件不得写 radius，圆角控件必须写像素证明 radius。
- `tests/test_m29_replay_plan.py` 覆盖 rounded cleanup target 保留 `maskRadius`。

## Validation Evidence

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_source_ui_physical_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
# 95 passed

git diff --check
# pass
```

## Prevention Notes

模型候选 bbox 不是形状半径 truth。shape radius 和 cleanup geometry 必须来自像素边界证据或 upstream geometry fit，不能由 bbox aspect、固定高度、颜色主题、文案、文件名或任务 id 推断。
