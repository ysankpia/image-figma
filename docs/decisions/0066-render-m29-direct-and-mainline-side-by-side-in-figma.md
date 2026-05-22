# ADR: Render M29 Direct And Mainline Side By Side In Figma

- 状态：proposed
- 日期：2026-05-22

## Context

M29 Direct Replay 的 CLI/report 已能说明节点数量、跳过原因和 fallback 擦除情况，但这些指标不能替代真正的 Figma 操作验收。用户要判断的是：

```text
文字能不能编辑
图标/图片能不能拖动
拖走后有没有重影
图层数量是否可操作
主线和 M29 direct 哪个更接近目标
```

这些问题必须在 Figma 画布里看，而不是继续堆更多 report。

## Decision

在 `experiment/m29-direct-replay` 分支上把 M29 Direct Replay 接入现有 `/api/upload-m30-preview` task，作为同一任务下的实验 variant：

```text
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_report.json
storage/assets/{taskId}/m29_direct/*
```

新增只读接口：

```text
GET /api/tasks/{taskId}/m29-direct-dsl
```

插件新增 `Generate Compare`。它上传一次 PNG，等待任务完成后分别获取 M29 direct DSL 和当前主线 DSL，把两份设计稿左右并排渲染到 Figma。

默认 `Generate from PNG` 保持不变，只渲染主线 `/api/tasks/{taskId}/dsl`。

M29 direct variant 是非阻塞实验产物。生成或资产发布失败时，后台任务继续走主线；compare endpoint 返回 `M29_DIRECT_DSL_NOT_FOUND`，而不是让默认上传失败。

## Consequences

好处：

- 路线选择变成实际 Figma 画布证据，而不是抽象报告争论。
- M29 direct 复用同一次 OCR/M29，不引入第二个 task 和第二次模型成本。
- 主线 `/dsl` 合同不变，可以稳定对照。

代价：

- `/api/upload-m30-preview` 在实验分支会额外生成 M29 direct variant，上传耗时和存储会增加。
- M29 direct 必须足够稳，否则会影响同一个后台 task。因此它需要单元测试、路由测试和资产发布测试保护。
- 因为它是非阻塞 variant，compare mode 可能缺失左侧实验输出；这比拖垮主线默认生成更符合实验边界。
- Compare mode 只能证明 flat draft 的可用性；它不解决 unit promotion、layout semantics 或 component/instance。

## Boundaries

- 不把模型输出当 DSL truth source。
- 不做单样图硬编码。
- 不把 M29 direct 写进 `dsl_results`。
- 不修改 Renderer schema；M29 direct 仍使用 DSL v0.1 的 `text`、`shape`、`image`。
- 不在本阶段决定默认路线切换。
