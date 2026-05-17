# 0028. Crop Business Icon Candidates Before Visible Business Icon Replay

- 状态：Accepted
- 日期：2026-05-17

## Context

M20-M24 的真实学生端 smoke 暴露了一个架构事实：text/component-guided icon 链路没有足够的业务组件输入时，只能稳定覆盖 header 这类几何强的图标。M20 在七张图上基本没有裁出业务 icon；M21 主要发现 header hints；M22 主要补裁 header nav/action；M23 只规划这些 icon；M24 可见回放也只能回放 header。

继续在 M24 上扩大可见回放范围是错的。M24 的输入池不够，扩大 replay 只会把缺失问题伪装成可见层问题。真正的下一个瓶颈是业务 icon candidate 覆盖，而不是 icon placement 或 renderer。

## Decision

M25 引入 region-guided business icon candidate harness：

- 默认开启，因为它不改变 Figma 可见输出。
- 不依赖完整 M16 业务组件识别，不重新 OCR，不按中文文案特化。
- 基于原始 PNG 像素和稳定业务区域 probe 裁业务 icon PNG candidate。
- 优先覆盖 bottom nav、primary button trailing arrow、shortcut tile、metric card、room card、row/card trailing 和 tip/info 区域。Primary button leading 区域第一版不主动裁，因为白色按钮文字笔画太容易被误判成 icon。
- 使用 M20/M22/M23/M24 existing icon bbox 做 duplicate exclusion，避免重复裁已经进入 icon pipeline 的候选。
- 使用 visible text、text replacement cover、hidden candidate_text、状态栏、header title 和 banner/illustration 排除区阻断误裁。
- 写 `/icon-business-candidates` 报告、`icons_business/*.png`、`icon_business_overlay.png`、SQLite 摘要和 DSL 顶层 meta。
- 不把 business icon 写入 DSL `assets`，不新增可见节点，不把 icon 放进画布。

## Consequences

好处：

- 绕开当前 component structure 对业务 icon 覆盖不足的问题。
- 让业务 icon 覆盖扩展和可见回放解耦，避免 M24 变成杂乱的“找图标 + 放图标”混合阶段。
- M26 可以在一个更完整的 icon pool 上统一做 dedupe、collision 和 placement plan。
- M27 才基于 M26 计划做业务 icon visible replay，风险边界清楚。

代价：

- M25 probe 是几何启发式，第一版会漏裁，也可能产生 blocked 候选；这是可接受的候选层行为。
- Shortcut 第一版裁的是 tile/icon 候选，不保证得到纯透明 icon 图形。
- 复杂插画、头像、建筑、床位平面图主体不进入 icon pipeline，需要后续 asset slice / illustration / component image 路线处理。
- M25 不提供可拖动图层，用户在 Figma 中看不到新增 icon layer；可见价值要等 M26/M27。

## Non-Goals

- 不做 visible replay。
- 不修改 DSL `assets`。
- 不新增可见 DSL 节点。
- 不处理 M24 已回放节点。
- 不做全图无边界 detection。
- 不做 Codia 式全量拆层。
- 不处理插画、头像、建筑或床位平面图复杂资产。
- 不做 SVG/icon semantic recognition。
- 不做图标库匹配。
- 不接 AI。
- 不引入 Pillow/OpenCV。
