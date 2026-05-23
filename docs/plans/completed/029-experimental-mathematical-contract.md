# M29 Experimental Mathematical Contract

- 状态：completed
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

把 `experiment/m29-direct-replay` 分支里的 M29 实验链路按第一性原理整理成一个可审计的数学合同文档，明确当前代码真正实现的对象、公式、阈值、信息流和非目标。

## Scope

包含：

- 梳理 raw M29、M29.2、M29.3.1、M29.4、M29.5 和 M29 Direct Replay 的数学合同。
- 明确哪些输出只是 report/weak structural evidence，哪些输出会 materialize 成实验 DSL 可见节点。
- 解释外部模型关于“缺少数学定义导致局部打补丁”的说法哪里有用、哪里不符合本地代码事实。
- 更新文档索引和后端架构入口。

不包含：

- 不修改 Python 代码。
- 不新增全局优化器、Auto Layout、组件识别或响应式代码生成。
- 不改变主线 `/api/tasks/{taskId}/dsl`。
- 不创建 Figma Component/Instance。

## Steps

1. 读取 M29 相关代码事实和现有 docs map。
2. 新增 `docs/architecture/m29-experimental-mathematical-contract.md`。
3. 更新 `docs/index.md` 与 `docs/architecture/backend.md` 的链接。
4. 跑文档级校验。

## Acceptance

- 文档给出 bbox、intersection、IoU、gap、relation、ownership、cluster、replay plan 和 direct materialization 的公式。
- 文档明确当前系统不是全局优化器，也不是响应式组件编译器。
- 文档列出当前数学薄弱点和下一步应补的合同位置。
- docs map 能从 Architecture 找到该文档。

## Validation

```bash
git diff --check
git status --short --branch
```

## Notes

本阶段是文档合同冻结，不是算法阶段。后续如果要把 M29.4 role hint 推进到真正 component/layout 层，必须另开计划并先定义图同构、误差函数、owner 约束和 materialization 边界。
