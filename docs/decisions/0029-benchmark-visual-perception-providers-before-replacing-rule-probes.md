# 0029. Benchmark Visual Perception Providers Before Replacing Rule Probes

- 状态：Accepted
- 日期：2026-05-18

## Context

M25 七张学生端 smoke 共裁出 22 个 business icon candidate，但 blocked `edge_clipped_unresolved` 达 65。这个结果说明 region-guided probe 能补业务 icon 覆盖，但继续按固定比例和局部窗口堆规则会越来越脆弱。换一个分辨率、字体大小、滚动位置或页面构图，规则成本都会继续上涨。

问题不在 `png_tools.py`。它只是底层 PNG metadata、decode、crop、encode、sampling 和 overlay 工具。真正脆弱的是上层候选发现逻辑。

SAM2、OpenCV、UIED 都可能有用，但不能直接进生产主链路。SAM2 是 mask proposal engine，不是 UI parser；OpenCV 是快速 bbox proposal engine，不是语义引擎；UIED 是 GUI detection 方向参考，但不能不经改造 vendoring 进项目。

## Decision

M26 新增 visual perception provider benchmark harness：

- 默认关闭，显式开启后才随 upload 生成 `/perception-benchmark` 报告。
- `current_rules` provider 读取 M20/M22/M25 已有候选作为 baseline。
- `opencv` provider 是可选 benchmark provider；依赖缺失或未启用时 status 为 `unavailable`。
- `sam2` provider 是可选/offline provider；启用且 checkpoint、torch、sam2 可用时运行 automatic mask generation；缺 checkpoint、torch 或 sam2 时 status 为 `unavailable`。
- `uied` provider 只支持外部 command adapter，不复制 UIED 源码，不把其依赖塞进 backend。
- 所有 provider 输出统一 candidates、blocked、overlay、elapsedMs 和误检代理指标。
- M26 不修改 DSL，不新增可见节点，不修改 DSL assets，不裁新 icon asset，不影响 Renderer。

## Consequences

好处：

- 把“感觉 SAM/OpenCV 更好”变成可对比数据。
- 保留当前规则 baseline，避免无证据推翻已有可用成果。
- 避免 torch/SAM2/checkpoint 冷启动和安装复杂度污染主链路。
- 为 M27 是否采用 SAM2 candidate filtering、OpenCV baseline 或 UIED adapter 提供证据。

代价：

- M26 本身不提升 Figma 可见效果。
- OpenCV provider 第一版仍只是 bbox proposal，不解决 UI 语义。
- SAM2 provider 已能执行 automatic mask，但依赖、checkpoint 和设备差异仍使其不适合默认主链路。
- 需要额外跑 smoke 才能获得完整 provider 对比。

实测证据：

- OpenCV restored high-recall 在 01 图上 124 candidates、59 blocked、277ms。它快，但噪声大。
- SAM2 tiny 在 01 图上 21 candidates、10 blocked、9268ms。它慢一些，但候选更干净，更符合下一阶段过滤实验方向。
- UIED adapter 在 01 图上 75 candidates、35 blocked、724ms。它不值得 vendoring，只保留外部 adapter。

M27 推荐路线是 SAM2 visual candidate filtering harness，而不是继续扩张 M25 式固定区域规则，也不是直接把 SAM2 输出写入 DSL。

## Non-Goals

- 不做 production replacement。
- 不改变 DSL/Figma 输出。
- 不裁新 icon PNG。
- 不做 Codia 式全量拆层。
- 不默认下载模型。
- 不默认引入 torch/sam2/opencv-python 到主生产依赖。
- 不把 SAM2/OpenCV/UIED 输出直接当 DSL 权威。
