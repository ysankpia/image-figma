# 150 Mainline Legacy Code Inventory And Cleanup

Status: completed

## Summary

当前 `main` 已经收敛到 assisted slice workspace：

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

本轮处理“死代码”和“暂时不用但未来可能有价值的代码”。原则不是粗暴删除，而是建立清晰的主线边界和冷冻归档口径：

```text
current mainline code
-> explicit diagnostic/eval code
-> frozen legacy/research asset
-> generated/local artifact candidate
```

有复用价值的 Codia-like、Draft、M29、PSD-like、historical preview、旧 Pencil 路线代码应保留为 legacy/eval/research asset，但不能继续出现在当前产品默认阅读路径、默认交付路径或新功能落点里。

## Key Decisions

- 不删除 `services/pencil-python-backend` 当前主线。
- 不恢复 Codia Beta、Go Draft、Python upload-preview、`services/pencil-go` 为产品路径。
- 不把 YOLO、M29、PSD-like、OCR 或 foreground ownership 自动裁判重新变成最终 visible owner。
- 先做清晰归档和文档隔离，再考虑物理移动或删除。
- 对代码目录的处理分四类：
  - `current`: 当前 assisted slice 主线，继续维护。
  - `diagnostic`: 当前主线可能调用或调试仍需要，例如 M29 extractor。
  - `legacy-research`: 未来若恢复 Codia-like / Draft 自动化有价值，但当前不用。
  - `generated-local`: 运行产物、缓存、历史 tmp、dist、storage、runs，不应进入主线文档和提交。

## Implementation Scope

- 用 Repomix 打包分析仓库代码和文档，不把 `node_modules`、`.venv`、`dist`、`storage`、`tmp`、`runs` 等产物作为代码事实。
- 用 `rg` 做真实引用审计，确认入口、路由、测试、文档导航是否仍引用旧路径。
- 新增或更新 legacy/code inventory 文档，明确每个主要目录的当前状态、保留原因、禁止事项和后续恢复条件。
- 更新 `docs/index.md`、`docs/engineering/current-code-map.md` 等当前导航，避免旧路径看起来仍是当前产品主线。
- 如发现 repo-tracked 的明显临时产物或无引用样例，可单独列为删除候选；默认不在本轮大规模删除代码目录。
- 完成后移动本计划到 `docs/plans/completed/`。

## Out Of Scope

- 不重构当前 assisted slice 工作台前端。
- 不改 assisted slice API、artifact contract 或导出行为。
- 不删除有历史研究价值的 Draft/M29/Codia-like/PSD-like 代码。
- 不引入新的归档仓库或 git subtree。
- 不做 Codia-like 自动化复活。

## Validation

必须跑：

```bash
cd services/pencil-python-backend
make check
make slice-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-150/tencent
cd ../..
git diff --check
git status --short --branch
```

如果本轮只改文档，`make check` 和 acceptance 仍要作为主线未被破坏的证据。

## Completion Evidence

Repomix audit:

- Packed code/docs output id: `e71452412a118565`.
- Packed 1006 source/doc files.
- Included `AGENTS.md`, `README.md`, `docs/**/*.md`, `backend/**/*.py`, `services/**/*.py`, `services/**/*.go`, `packages/**/*`, `figma-plugin/src/**/*`, tests and tools.
- Excluded `node_modules`, `.venv`, `dist`, `storage`, `tmp`, `runs`, image files, ZIP, `.pen`, and logs.

Current code facts:

- `services/pencil-python-backend/` remains current product delivery surface.
- `services/psdlike-python/` is still a current dependency because `services/pencil-python-backend/app/psdlike_runner.py` invokes `tools/run_one.py`.
- `services/backend-go/cmd/m29extract/` and `services/backend-go/internal/m29/` remain current diagnostic/dependency code because Pencil backend supports `boundarySource=m29/hybrid` and the deploy bundle includes them.
- `backend/`, `services/backend-python/`, `services/pencil-go/`, Draft packages, Renderer, Plugin, historical Codia-like docs and plans are retained as legacy/research/deferred runtime assets.
- `git ls-files` showed no tracked files under `backend/tmp/`, `backend/storage/`, `figma-plugin/dist/`, `runs/`, or similar generated local artifact directories.

Document updates:

- Added `docs/engineering/legacy-code-inventory.md`.
- Updated `docs/engineering/current-code-map.md` to describe `main`, current PSD-like/M29 dependencies, and frozen research assets.
- Updated `docs/index.md`, `README.md`, and `AGENTS.md` to route non-mainline delete/revive decisions through the inventory.
- Downgraded `backend/README.md` from current product wording to historical `/api/upload-preview` wording.
- Added directory READMEs for `services/backend-go/`, `services/backend-python/`, and `services/pencil-go/`.

Deletion decision:

- No large code directory was deleted.
- Legacy/research code remains in place because it is useful for future Codia-like, Draft, model, plugin, or Pencil research.
- Only generated/local artifacts are deletion candidates; none were tracked in Git in this audit.

Validation:

- `cd services/pencil-python-backend && make check`: passed, `35 passed`.
- Initial `make slice-acceptance` failed because no server was listening on `127.0.0.1:8100`; this was environment state, not a code failure.
- Started local server with `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike OCR_PROVIDER=none uv run uvicorn app.main:app --host 127.0.0.1 --port 8100`.
- `make slice-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-150/tencent PROJECT_NAME='Pencil 150 Legacy Cleanup Acceptance'`: passed.
- Acceptance report: `/Volumes/WorkDrive/pencil-exports/slice-acceptance-150/tencent/acceptance_report.md`.
- Acceptance metrics: `passed=1 failed=0 missingSample=0 pages=1 candidates=63 selected=3 rejected=1 preview=3 exported=3 pngs=3 badRefs=0 missingRefs=0`.
- Local uvicorn server was shut down after acceptance.
- `git diff --check`: passed.
- `git status --short --branch`: dirty only with this documentation/inventory change set before commit.
