# Bug: M22 多个 blocked hints 导致文档校验失败

- 状态：resolved
- 创建日期：2026-05-17
- 影响范围：M22 `icon-gap-candidates` 真实图 smoke，间接影响 M23 placement plan 吸收 M22 gap icon

## Summary

七张学生端真实 PNG smoke 中，M21 能正常生成 missed icon hints，但 M22 在 2-7 张图上返回 `failed`，错误为 `ICON_GAP_CANDIDATE_VALIDATION_FAILED`，校验信息是 `blocked hint ids must be unique`。这会让 M22 已经生成的 gap overlay 或中间 crop 不能进入正式报告，M23 也只能消费 M20 icon candidates，导致真实补漏效果被低估。

## Reproduction

复现步骤：

1. 使用 `.env.local` 启动后端，开启 M20-M23 默认链路。
2. 上传学生端真实 PNG，例如 `02_学生端-楼层选择.png`。
3. 请求 `/api/tasks/{taskId}/icon-gap-candidates`。
4. 接口返回成功响应但 document status 为 `failed`，error code 为 `ICON_GAP_CANDIDATE_VALIDATION_FAILED`，warning message 为 `blocked hint ids must be unique`。

## Root Cause

M22 构造 gap probe 结果时，`build_gap_icon_for_probe()` 只接收一个 `index`，调用方传入的是 `len(gap_icons) + 1`。当连续多个 probe 都被 blocked，`gap_icons` 数量不变，所以多个 `BlockedGapHint` 会得到相同的 `blocked_gap_hint_001` id。随后 `validate_icon_gap_candidate_document()` 正确地拒绝重复 id，导致整个 M22 文档失败。

## Fix

把 M22 的 candidate icon 编号和 blocked hint 编号拆开：

- `icon_index = len(gap_icons) + 1` 只用于 `icon_gap_###` 和 failed gap icon。
- `blocked_index = len(blocked_hints) + 1` 只用于 `blocked_gap_hint_###`。

这样连续 blocked 不再依赖 candidate 数量变化，文档 id 稳定且唯一。

## Regression Guard

新增 `test_icon_gap_multiple_blocked_hints_keep_unique_ids`，构造两个都会 blocked 的 M21 field hints，断言：

- M22 document 仍为 `completed`。
- `blockedHints` 数量为 2。
- 所有 blocked hint id 唯一。

## Validation Evidence

已验证：

```bash
uv run pytest backend/tests/test_icon_gap_candidate.py
```

结果：

```text
11 passed in 23.66s
```

修复后重新跑七张学生端真实 PNG smoke，M22 全部返回 `completed`：

```text
01 M22 completed 1 cropped / 1 blocked
02 M22 completed 1 cropped / 2 blocked
03 M22 completed 2 cropped / 2 blocked
04 M22 completed 2 cropped / 3 blocked
05 M22 completed 0 cropped / 5 blocked
06 M22 completed 0 cropped / 3 blocked
07 M22 completed 0 cropped / 2 blocked
```

## Prevention Notes

候选数组和 blocked 数组不能共用“候选数量”作为 id 来源。后续类似旁路合同层如果同时输出 `items[]` 和 `blocked[]`，必须分别维护稳定编号，或者在最终 append 前统一分配 id。
