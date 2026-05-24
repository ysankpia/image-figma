# ADR: Solve Pixel Ownership At M29 Source Layer

- 状态：proposed
- 日期：2026-05-22

## Context

Figma Compare 证明 M29 Direct Replay 可以用很短链路生成接近主线的 flat draft，但也暴露了源头问题：

```text
艺术字被普通 text 重画
小图标碎成色块
media 内部纹理和文字被过早拆出来
fallback 擦除和 replay 决策没有统一归属来源
```

继续在 M39/M40 后面补规则会把问题留在下游。真正的源头对象是 PNG 像素归属：哪些像素应该成为可编辑文字，哪些应该保留在 raster，哪些是 icon，哪些是 UI 背景或分割线。

## Decision

新增 M29.2 Source-Level UI Physical Graph，作为 M29 Direct Replay 的源头 ownership gate。

M29.2 读取：

```text
source PNG
OCR document
M29 primitive graph
```

输出：

```text
m29_2/source_ui_physical_graph.json
m29_2/source_ui_physical_graph_overlay.png
```

每个 source object 同时记录：

```text
visualKind
pixelOwner
replayDecision
sourceEvidence
confidence
reasons
risks
```

M29 Direct Replay 优先消费 M29.2 的 `replayDecision`。没有 M29.2 或 M29.2 失败时，保留旧 direct replay 路径作为实验 fallback。主线 `/api/tasks/{taskId}/dsl` 不变。

## Consequences

好处：

- 源头统一决定 text/media/icon/shape/fallback ownership，减少 downstream 补丁。
- `preserve_raster_text` 不会被错误重画成普通 Figma text。
- 合并后的 icon bbox 可以作为一个 raster icon replay，减少碎片和色块。
- fallback 擦除只跟随安全 replay 决策。

代价：

- 上传任务多一个可选诊断阶段，耗时和产物增加。
- 第一版规则仍是启发式，只能解决通用物理归属，不保证恢复原始 Figma 层级。
- M29.2 如果规则过严，左侧 direct draft 会更保守；如果规则过松，会重新引入重影或错误 replay。

## Boundaries

- 不接新模型，不引入新依赖。
- 不把 OCR、模型或单个 M29 primitive 当 truth source。
- 不写样图固定坐标、固定文本、固定元素规则。
- 不做 Auto Layout、Component/Instance、代码生成。
- 不替换 mainline M30/M37/M38/M39；M29.2 只增强 compare mode 左侧实验输出。
