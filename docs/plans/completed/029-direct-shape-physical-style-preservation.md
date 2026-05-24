# M29 Direct Shape Physical Style Preservation

- 状态：completed
- 创建日期：2026-05-23
- 负责人：未指定

## Goal

把 raw M29 shape 的物理样式证据传到 M29 Direct 左侧实验 DSL：

```text
raw M29 shape style
-> M29.2 source object
-> M29.5 replay plan
-> M29 Direct shape DSL
```

当前搜索 support shape 变成直角方块的根因是 M29 Direct 的 M29.2/M29.5 shape replay 路径只传 `fill`，没有恢复 raw M29 source node 的 `style.radius`。

## Scope

包含：

- M29 Direct shape replay 从 raw M29 source node 恢复合法 `style.radius`。
- `low_contrast_support` 使用半高 radius 作为通用 support 物理估计，并 clamp 到 bbox 可表达范围。
- M29.2 fallback path 和 M29.5 plan path 共用同一套 shape replay style 构造。
- DSL node `meta` 写入 radius/style source 审计字段。

不包含：

- 不做 OCR-symbol leakage cleanup。
- 不处理头像、底部 tab、小型纹理 foreground ownership。
- 不把稳定低纹理 support 改成图片裁片。
- 不新增 SearchBar/Card/TabBar 语义 detector。
- 不改主线 `/api/tasks/{taskId}/dsl`、DSL schema、Renderer 或插件 UI。

## Acceptance

- M29.5 plan replay 的 shape source node 带 `style.radius` 时，M29 Direct DSL shape 保留 radius。
- `low_contrast_support` replay 成 shape 时，radius 接近 `min(width,height)/2`。
- 没有 raw radius evidence 的普通 shape 不凭空加 radius。
- 搜索 support shape 在 Figma 左侧不再退化成直角方块。
- 商品图文字层级、M29.2 ownership、M29.5 replay plan 不回归。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_direct_replay.py tests/test_visual_primitive_graph.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m30_upload_pipeline.py -q
cd ..
git diff --check
git status --short --branch
```

手工验收样本：

```text
/Users/luhui/Downloads/m29/ChatGPT Image 2026年5月17日 14_47_13 (4).png
```

## Notes

- `style.radius` 已被 DSL schema 和 Figma Renderer 支持，本阶段只修后端 M29 Direct style evidence 传递。
- 如果 raw M29 没有产生 support shape，本阶段不会在 M29.2/M29.5 下游硬造。
