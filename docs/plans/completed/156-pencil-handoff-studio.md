# 156 Pencil Handoff Studio

## Summary

新建 `services/pencil-handoff-studio/`，把当前交付路线收敛为：

```text
1..N UI images
-> originals
-> image/icon/basic candidates
-> Konva Review
-> manual_slices.v1.json
-> assets.zip
-> project.zip
```

`manual_slices.v1.json` 是最终交付真相源。自动证据只生成候选和 warning，失败不阻断人工画框。

## Scope

- 新 FastAPI 服务，默认端口 `8120`，环境变量前缀 `PENCIL_HANDOFF_`。
- 新 React/Vite/Konva 前端，构建后由后端托管。
- 输出 `assets.zip` 和 `project.zip`，均包含 originals 和 slices。
- Pencil `design.pen` 底层包含可见锁定 source reference，上层包含 selected slices 和安全基础元素。
- 不修改旧 Pencil、Draft、Codia、Figma plugin 路线。

## Validation

```bash
cd services/pencil-handoff-studio
make check
make handoff-acceptance IMAGE=/absolute/path/or/dir OUT=/Volumes/WorkDrive/pencil-exports/handoff-acceptance

cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
pnpm --filter @image-figma/pencil-handoff-studio-web run typecheck
git diff --check
git status --short --branch
```
