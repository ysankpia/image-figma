# 149 Assisted Slice Mainline Merge Readiness

Status: active
Created: 2026-06-05 21:50 +0800

## Objective

把 `feat/pencil-assisted-slice-review` 作为当前 Pencil Assisted Slice 主产品线合流到 `main`，并在合流前后用真实验收确认主线没有退化。

当前产品主线不变：

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

## Scope

Allowed:

- 检查 `feat/pencil-assisted-slice-review`、`main`、`origin/main` 的关系。
- 跑合流前 Pencil backend 检查和真实样例 acceptance。
- 如果 `main` 可 fast-forward，则执行：

```bash
git switch main
git merge --ff-only feat/pencil-assisted-slice-review
```

- 在 `main` 上复跑最小验收。
- 推送 `main` 到 `origin/main`。
- 记录合流证据并把本计划移到 `completed/`。

Forbidden:

- 不清理旧代码。
- 不删除 Codia/Draft/Go/Pencil legacy/eval 目录。
- 不做 React/Vue 前端重构。
- 不恢复自动 ownership 裁判。
- 不引入 YOLO/model 作为最终裁判。
- 不修改 Figma plugin 产品路线。
- 不把候选质量问题当作本轮合流阻塞，除非它导致保存、预览、导出、ZIP 合同失败。

## Current Facts

Before starting merge:

```text
current branch: feat/pencil-assisted-slice-review
working tree: clean
active plans: none except README
origin/main -> main: local main ahead 18
main -> feat/pencil-assisted-slice-review: feature ahead 159
origin/main -> feat/pencil-assisted-slice-review: feature ahead 177
main has no commits missing from feature branch
```

This means a local fast-forward from `main` to `feat/pencil-assisted-slice-review` should be possible if no new commits appear during the run.

## Validation Plan

Pre-merge on `feat/pencil-assisted-slice-review`:

```bash
cd services/pencil-python-backend
make check
make slice-acceptance \
  IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-149/premerge-tencent \
  PROJECT_NAME="Slice Acceptance 149 Premerge Tencent"
git diff --check
git status --short --branch
```

Post-merge on `main`:

```bash
cd services/pencil-python-backend
make check
make slice-acceptance \
  IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-149/main-tencent \
  PROJECT_NAME="Slice Acceptance 149 Main Tencent"
git diff --check
git status --short --branch
```

Push:

```bash
git push origin main
```

## Acceptance Criteria

- `docs/plans/active/` has no unfinished plan other than this one during execution.
- Pre-merge `make check` passes.
- Pre-merge slice acceptance passes with `failed=0`, `missingSample=0`, `badRefs=0`, `missingRefs=0`.
- `main` fast-forwards to `feat/pencil-assisted-slice-review`.
- Post-merge `make check` passes.
- Post-merge slice acceptance passes with `failed=0`, `missingSample=0`, `badRefs=0`, `missingRefs=0`.
- `git push origin main` succeeds.
- Working tree is clean after final plan completion commit or push.

## Stop Conditions

- `main` is no longer an ancestor of `feat/pencil-assisted-slice-review`.
- `origin/main` receives new commits that are not in local `main` or the feature branch.
- Pre-merge or post-merge acceptance fails with a P0/P1 issue.
- Push is rejected because remote changed.
- Any required fix would exceed merge readiness scope.
