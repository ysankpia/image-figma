# 071 M29 Control Radius Pixel Evidence Fix

- 状态：completed
- 创建日期：2026-05-27
- 负责人：Codex

## Goal

修复 model-first interactive 主链中 control background 被错误 materialize 成半高圆角/胶囊的问题。

## Root Cause

圆角被错误绑定在 bbox 比例上：

```text
wide finite control -> radius = height / 2
```

这不是 source truth。模型候选只说明“这里可能是 UI object/control”，不能证明按钮角半径。角半径必须由 source PNG 的边界像素证明。

## Changes

- `perception_source_compiler` 不再按宽高比例给 control 写 `shapeRadiusOverride`。
- raw M29.2 low-confidence unknown control path 不再按 `fillRatio/aspect` 推断 radius。
- 新增像素边界半径估计：矩形角点填满时不写 radius；圆角/胶囊由四角边界进入填充色的位置证明。
- `claimMaskKind` 跟随 radius 证据：无 radius 用 `bbox`，有 radius 用 `rounded_rect`。
- M29.5 cleanup target 为 rounded rect 携带 `maskRadius`。
- materializer cleanup 使用 `maskRadius`，不再默认半高圆角擦除。

## Acceptance

- 方形/微圆角不足以证明的按钮不会被输出成胶囊。
- 真实圆角按钮仍能输出 radius。
- residual copied image cleanup 使用同一个 radius 合同，不和 visible shape 分叉。
- 不修改 public API、DSL schema、Renderer、Figma plugin protocol。
- 不引入文件名、坐标、文案、主题色、任务 id 特化。

## Validation

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_source_ui_physical_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
# 95 passed

git diff --check
# pass
```

## Notes

第一性原理结论：shape radius 是像素几何事实，不是 bbox 形状先验。模型发现候选，source ownership 层验证几何，M29.5 授权 replay/cleanup，materializer 只执行。
