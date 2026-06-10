# 169 Slice Studio Cut Mode UI Cleanup

## Summary

修 Review 右侧资产面板里透明裁切模式的交互位置和列表视觉问题。

当前问题：

- `透明形状` 只在 active asset 面板里，像是只能改一个资产。
- 资产列表里额外显示 `透明` 胶囊，和输入框/active 卡片叠在一起，看起来像双层。
- 用户真实工作流需要两层控制：
  - 全局模式：接下来画框默认用矩形还是透明底，并能批量切换当前页已有资产。
  - 单项覆盖：导出检查后，某个透明效果不好的资产可以单独改回矩形。

## Scope

- 只改 `apps/slice-studio` Review UI 和保存逻辑。
- 不改透明裁切算法。
- 不改 API。
- 不改导出 ZIP 合同。

## Behavior

- 右侧 Inspector 顶部新增 `裁切模式` 分段按钮：`矩形` / `透明底`。
- 点击全局模式：
  - 更新当前页所有 slices 的 `cutMode`。
  - 设置后续新建 slice 的默认 `cutMode`。
  - 自动保存。
- 新建 slice 使用当前全局默认模式。
- 资产列表每行显示一个紧凑的 `矩形/透明` 小切换，可单独覆盖该 slice。
- active asset 面板不再单独放 `透明形状` 开关。
- 删除资产行里的 `透明` 胶囊，避免双层/溢出。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- 浏览器确认：
  - 顶部能看到 `矩形/透明底`。
  - 切到透明底后当前页所有资产变成 shape。
  - 新画的资产默认 shape。
  - 单个资产能改回 rect。
  - 资产列表不再出现双层胶囊和溢出。
  - Console 无 error/warn。
