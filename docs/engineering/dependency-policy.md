# 依赖策略

依赖不是免费午餐。每个依赖都会增加安装、升级、调试和 agent 理解成本。

## Rules

- 优先使用当前项目已经采用的框架和标准能力。
- 不为少量代码引入大型依赖。
- 不引入无人维护或冷门依赖。
- 不在没有计划的情况下引入新包管理器。
- 新依赖必须说明用途、替代方案和验证方式。
- 新依赖如果影响构建、运行、部署、环境变量或 artifact，必须更新对应文档。

## Current Default Stack

当前默认产品栈是 Slice Studio：

- App：repository root
- Web：Next.js + React
- Canvas：Konva / React Konva
- API：Elysia on Bun
- Storage：SQLite + local project files
- Image processing：Sharp
- Icons：lucide-react
- Tests：Vitest + TypeScript
- Package checks：`pnpm run check` / `build`

Workspace 仍使用 pnpm。Slice Studio 本地开发使用 Bun。

## Current Slice Studio Dependencies

主要依赖：

- `next`, `react`, `react-dom`：Web UI。
- `elysia`, `@elysiajs/cors`：本地 API。
- `konva`, `react-konva`：Review Workbench canvas。
- `sharp`：PNG/JPEG decode、crop、resize、cutout、AI tile compression、TS M29 physical evidence image access。
- `lucide-react`：UI icon buttons。
- `typescript`, `vitest`, `@types/*`：类型检查和测试。
- `concurrently`：同时启动 API 和 Web dev server。

Do not add a second frontend state manager, ORM, queue, object storage SDK, or browser automation dependency unless an active plan proves it is needed.

## AI/OCR Dependencies

AI slice boxes are provider-boundary code under `server/ai-slice-boxes/`.

Rules:

- provider config comes from `SLICE_STUDIO_AI_SLICE_*`;
- images must be tiled/compressed before provider calls;
- provider output is parsed and validated server-side;
- boxes are transient until saved as normal SliceRecord entries;
- raw provider request/response data must not be committed or printed with secrets.

OCR is provider-boundary code under Slice Studio text modules:

- `SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5` is the normal configured path when a token exists;
- Tesseract is diagnostic-only when explicitly configured;
- OCR owns text content, not visible asset ownership.

M29 physical evidence:

- default is TypeScript `server/m29-physical-evidence/`;
- Go `m29extract` is explicit fallback/reference only;
- M29 evidence only affects text bbox placement.

## Historical Dependencies

Old dependency groups remain for historical routes only:

- Go Draft backend under `archive/legacy-code/services/backend-go`.
- Python Pencil backend under `services/pencil-python-backend`.
- Python upload-preview under `backend`.
- PSD-like and model experiments under `services/*`.
- Renderer and Figma plugin under `archive/legacy-code/packages/*` and `archive/legacy-code/figma-plugin/`.

Do not add dependencies to those routes for current Slice Studio work unless the task explicitly targets that route.

## Review Requirement

Any new dependency must update:

- this file;
- [validation.md](validation.md);
- [../runbooks/local-setup.md](../runbooks/local-setup.md) when it changes setup or commands;
- [../reference/env-vars.md](../reference/env-vars.md) when it introduces environment variables;
- the active plan and final validation evidence.
