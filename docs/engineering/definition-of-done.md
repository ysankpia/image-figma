# Definition of Done

一个任务完成必须同时满足实现、验证、文档三件事。构建、类型检查、单元测试通过只是 baseline，不等于用户功能已经交付。

## Documentation Work

文档任务完成条件：

- 文档放在正确目录。
- `docs/index.md` 可导航到它。
- 相对链接可用。
- 没有模板占位符残留。
- 不和当前 direction contract、code map、validation docs 冲突。
- 如果替代旧草稿，旧草稿仍在 legacy、archive、reference 或 completed plan 中可追踪。
- `PROGRESS.md` 和 active/completed plan 状态已同步。

## Slice Studio Implementation Work

当前产品实现任务完成条件：

- 代码落在正确层：默认 `apps/slice-studio`，不是旧 Python Pencil、Go Draft、Renderer 或 plugin。
- 保存后的 SliceRecord 仍是编辑和导出的 truth source。
- AI/OCR/M29 仍是候选或证据，不绕过保存路径。
- API、数据模型、环境变量、用户流程或导出合同变化已更新文档。
- 相关测试或验证证据已记录到 plan 或 `PROGRESS.md`。
- 没有把样例名、固定文案、固定坐标、固定尺寸写成规则。
- 没有提交 storage、数据库、zip、`.pen`、provider raw output、密钥或 dist 产物。

## User-Visible Validation

涉及 UI、AI 画框、OCR/M29、导出、Pencil handoff 或项目存储的任务，完成前必须至少有一种真实验收：

```text
real project upload/save/refresh
AI 当前页或 AI 全部页 smoke
assets.zip inspection
project.zip/design.pen inspection
OCR/M29 diagnostics inspection
import/export round trip where applicable
```

`pnpm --dir apps/slice-studio run check` 和 `build` 不能替代这些真实验收，只能说明代码 baseline 没坏。

## 阶段提交纪律

非平凡阶段工作必须按阶段提交，不能把多个阶段塞进一个提交。

阶段完成顺序固定为：

1. 完成本阶段计划内代码、测试、文档和计划更新。
2. 确认 staged 内容只属于当前阶段，不包含下一阶段探索、临时调试、`apps/slice-studio/storage/`、旧服务 storage、插件 `dist/`、密钥或无关本地改动。
3. 创建独立 git commit。提交信息应描述阶段能力，而不是笼统写 `update` 或 `misc`。
4. 在该提交之上运行阶段要求的验证命令。
5. 验证通过后才能开始下一阶段；验证失败时，用同阶段 fix commit 修正并重新验证。

如果用户本地已有无关未提交改动，必须识别并隔离；除非用户明确要求，不得把它们并入阶段提交。

## Bug Work

Bug 修复完成条件：

- 有 bug 记录或 active plan 说明问题。
- 有复现说明，除非不可复现原因已记录。
- 有根因。
- 修在 owning layer。
- 有回归保护或明确说明为什么不能加。
- 有验证证据。

## MVP / Delivery Work

交付阶段完成条件：

- 主链路可跑通。
- P0 验收通过。
- 真实样例或产物验收记录完整。
- 失败能定位到 owning layer。
- 阻塞和跳过项记录清楚。
- `PROGRESS.md` 记录当前 checkpoint。
- 当前阶段已有独立 commit，下一阶段开始前工作区干净或无关改动已明确隔离。
