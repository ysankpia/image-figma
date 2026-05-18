# M29.1 Symbol Fragment Grouping And Asset Integrity Audit

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29.1 是 M29 visual primitive graph 的后处理 harness。它只读取 M29.0.1 输出的 accepted symbol nodes 和 eligible blocked primitives，把碎片候选保守合并成 grouped visual object candidates。

M29.1 不重新扫描整图、不重新跑 foreground mask、不重新跑 connected components、不重新做 detector、不回写 M29 `nodes.json`、不覆盖原始 symbol assets、不接 OCR/SAM2/SVG/Figma/DSL、不进入上传主链路。

## Implementation

新增：

```text
backend/app/symbol_fragment_grouping.py
backend/scripts/run_m29_1_symbol_grouping.py
backend/tests/test_symbol_fragment_grouping.py
```

M29.1 要求输入 M29 `meta.blockedEvidenceVersion == "0.2"`。如果不是 M29.0.1 evidence，脚本直接失败，不允许用旧的 `symbol_metrics_rejected` 结果偷跑 grouping。

Candidate universe 固定为：

```text
accepted symbol nodes
+ eligible blocked primitives
```

Interactive shape 可以作为 `icon_button_group` 的 background member，但不是 foreground fragment detector 来源。

## Output

M29.1 默认输出到 M29 output 下的 `m29_1/`：

```text
group_nodes.json
symbol_asset_audit.json
symbol_asset_audit.md
edge_audit.json
preview_sheet.png
assets/symbol_groups/*.png
overlays/09_symbol_fragment_risks.png
overlays/10_symbol_groups.png
overlays/11_grouped_vs_original.png
```

`preview_sheet.png` 是人工审计入口，必须同时展示源图、group overlay、父级 M29 已保留的 `assets/images/*.png` 和 M29.1 新增的 `assets/symbol_groups/*.png`。M29.1 不处理 image，但 preview 不能让 retained image asset 看起来像在 M29.1 消失。

CLI：

```bash
cd backend
uv run python scripts/run_m29_1_symbol_grouping.py \
  --m29-output storage/m29_visual_primitive_graph \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png"
```

## Acceptance

合成测试必须严格覆盖：

```text
拒绝 legacy blocked evidence
eligible blocked primitive 准入门槛
hard-block reasons 不进入 graph
edge accepted/weak/rejected/hard reject audit
搜索圆+柄、购物车车身+轮子、定位外圈+中心点合并
红色圆按钮+白色加号形成 icon_button_group 且 member role 正确
相邻 tab icon 不误合并
文字碎片不进入 accepted group
image 内部纹理不进入 graph
uncertain/rejected 不导出 accepted asset
原始 M29 nodes.json 不被修改
overlay PNG 可读
```

真实图 smoke 只作为人工诊断证据，不用 group 数量作为质量目标。验收重点是 grouped asset 是否更完整、是否出现明显误合并、edge audit 是否解释得通、原始 symbol 是否保留。

Preview 验收还要确认父级 M29 image assets 仍在 M29.1 sheet 中可见，避免把“未参与 symbol grouping”误读为“被 M29.1 删除或拆没”。

验证命令：

```bash
cd backend && uv run pytest tests/test_symbol_fragment_grouping.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```
