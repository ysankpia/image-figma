# 发布 Runbook

当前默认产品是仓库根目录的 Slice Studio。

正式多用户发布前遵循 active plan：

```text
docs/plans/completed/190-slice-studio-prelaunch-codebase-hardening.md
docs/plans/active/189-slice-studio-multi-user-production-launch.md
```

不要从当前 live working directory 直接复制部署包。这个仓库包含 `.env.local`、storage、`.next`、node_modules、venv、tmp、output、runs 和历史服务产物。发布必须来自干净 checkout 或显式 release package。

## Release Targets

未来可能存在：

- Slice Studio private/self-use deployment.
- Slice Studio public web product.
- Historical Figma plugin / Pencil services only when explicitly targeted.

## Release Checklist

Slice Studio 发布前必须确认：

- `storage/` 已备份，或生产环境有独立持久 storage。
- `.env.local`、SQLite、ZIP、`.pen`、`.next`、`output`、`tmp`、`runs` 没有进入发布包。
- `pnpm run check` 通过。
- `pnpm run build` 通过。
- `git diff --check` 通过。
- `bun run smoke` 对 running Slice Studio API 通过。
- 真实样例能上传、保存 slices、导出 `assets.zip` 和 `project.zip`。
- 如果 AI provider 改动过，真实 provider smoke 已记录，或明确写明缺少 key。
- 回滚方式明确。

## Pre-Deploy Artifact Check

```bash
git status --short --branch
git ls-files | rg "\\.zip$|\\.pen$|\\.sqlite$|\\.db$|\\.env\\.local$|(^|/)\\.next/|(^|/)dist/|(^|/)storage/"
```

Only intentional tracked placeholders such as `storage/.gitkeep` may appear.
