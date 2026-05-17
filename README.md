# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路、真实 PNG deterministic region fallback DSL、M8 visual primitive contract harness、M9 OCR/DSL patch harness，M10 百度 PP-OCRv5 异步 OCR provider、M11 低风险可见文字替换 harness、M12 文字替换覆盖率扩展、M13 text replacement 质量控制、M14 UI-aware text replacement sampling、M15 text-primitive binding harness、M16 component structure harness、M17 DSL component annotation 和 layer naming harness、M18 component-aware layer separation candidate harness、M19 local asset slice/simple fill experiment harness、M20 icon candidate extraction/crop harness、M21 icon coverage audit/placement readiness harness、M22 region-guided icon gap candidate harness、M23 icon placement plan/layering readiness harness、M24 visible icon fallback replay experiment harness、M25 region-guided business icon candidate harness、M26 visual perception provider benchmark harness，以及 M27 SAM2-guided visual candidate filtering harness。

一期 MVP 只验证一条主链路：

```text
单张 PNG
-> 后端识别
-> visual primitive candidates
-> OCR / DSL patch candidates
-> DSL v0.1
-> Figma Renderer
-> Figma 可编辑设计稿
```

当前 M27 默认仍使用 fake OCR 和 `TEXT_REPLACEMENT_MODE=debug`；显式设置 `OCR_PROVIDER=baidu_ppocrv5` 和百度 token 后，上传链路会生成真实 OCR candidates。`TEXT_REPLACEMENT_MODE=apply` 会写入通过 quality gate 的 accepted visible text replacement；M14 在 M13 quality gate 前增加 UI-aware sampling。M15-M18 生成 binding、structure、annotation 和 layer separation 报告，M19 生成本地 slice PNG 实验资产，M20 生成 text/component-guided icon PNG 候选资产，M21 审计 icon 覆盖和漏裁 hints，M22 补裁可靠 gap icon，M23 把 M20/M22 icon 统一成 placement plan，M24 默认关闭但可做小范围 visible icon fallback replay。M25 默认开启，绕开 M16 业务组件识别不足，使用 region-guided probes 裁高价值业务 icon 候选 PNG。M26 默认关闭，只生成 `/perception-benchmark` 报告比较 current_rules、可选 OpenCV、可选 SAM2 和可选 UIED adapter。M27 默认关闭；显式开启后，它只生成 `/sam-visual-candidates` 报告和 SAM2 visual candidate overlay，把 SAM2 automatic masks 过滤成候选/blocked，不修改 DSL/Figma 输出、不裁新 icon asset、不把 SAM2 输出直接当 DSL 权威。调试接口包括 `/ocr`、`/primitives`、`/dsl-patch`、`/text-replacements`、`/text-bindings`、`/component-structures`、`/component-annotations`、`/layer-separation-candidates`、`/asset-slice-candidates`、`/icon-candidates`、`/icon-coverage-audit`、`/icon-gap-candidates`、`/icon-placement-plan`、`/icon-visible-fallback`、`/icon-business-candidates`、`/perception-benchmark` 和 `/sam-visual-candidates`。

下一步执行顺序：

1. 保持文档、ADR 和计划与实现同步。
2. 继续验证插件上传链路和 Figma 手动烟测。
3. 用固定样例目录持续验证三段 region fallback。
4. 持续用样例图验证 `TEXT_REPLACEMENT_MODE=debug/apply` 的 accepted/rejected/blocked 决策。
5. 下一步基于 M27 输出做 M25 rules + M27 SAM 候选池合并，统一 dedupe、collision 和 placement plan；仍不要盲目做全局 icon detection 或直接 visible replay。

从 [docs/index.md](docs/index.md) 开始阅读。
