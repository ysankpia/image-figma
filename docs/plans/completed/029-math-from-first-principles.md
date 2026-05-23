# M29 Math From First Principles

- 状态：completed
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

新增一份面向只学过初中数学、但能理解工程问题的 M29 数学推演文档。它不替代 M29 实验链路数学合同，而是把合同背后的坐标、面积、比例、像素归属、关系、聚类和重放边界讲清楚。

## Scope

包含：

- 从矩形 bbox、面积、中心点开始推导 M29 的基础几何。
- 用小数字例子解释 intersection、IoU、contains、near_equal、pixel owner、shape replay safe、region relation、weak cluster 和 replay plan。
- 明确当前代码事实、启发式阈值和未来方向之间的边界。
- 更新 `docs/index.md` 和 M29 数学合同互链。

不包含：

- 不修改 Python 代码。
- 不新增测试、算法、全局优化器、组件化、Auto Layout 或 Figma Component/Instance。
- 不把 layout energy、graph isomorphism 写成当前实现。
- 不提交 git commit。

## Steps

1. 新增 `docs/architecture/m29-math-from-first-principles.md`。
2. 在 `docs/architecture/m29-experimental-mathematical-contract.md` 增加简短互链。
3. 更新 `docs/index.md` 的 Start Here 和 Architecture 入口。
4. 运行文档级校验。

## Acceptance

- 文档读者不需要大学数学背景，也能理解 M29 为什么从 bbox、面积和比例开始。
- 每个关键公式都有大白话解释和小数字例子。
- 文档明确说明 `geometry fit`、`pixelOwner`、`replayDecision` 三者不是同一件事。
- 文档明确说明 M29.4 cluster 是弱证据，不是组件。
- 文档明确说明全局优化和组件化是未来方向，不是当前事实。

## Validation

```bash
git diff --check
rg -n "全局优化|组件|media_text_group_like|pixelOwner|region relation" docs/architecture/m29-math-from-first-principles.md
git status --short --branch
```

## Notes

本文档是学习型推演，不是工程合同。工程合同仍以 `docs/architecture/m29-experimental-mathematical-contract.md` 为准。
