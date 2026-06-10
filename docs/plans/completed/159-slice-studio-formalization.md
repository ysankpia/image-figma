# 159 Slice Studio Formalization

## Summary

Build `apps/slice-studio/` as the formal product surface for manual UI asset slicing.

Main flow:

```text
1..N UI screenshots
-> local project workspace
-> source images saved to storage
-> user-confirmed image/icon slices
-> SQLite metadata
-> assets.zip
```

## Scope

- Use Next.js + React + TypeScript + Konva for the UI.
- Use Bun + ElysiaJS + bun:sqlite + sharp for the API.
- Keep `Figma-design` as prototype/reference only.
- Do not implement AI, OCR, YOLO, M29, PSD-like, Pencil export, Figma import, auth, cloud sync, or team features in this phase.

## Acceptance

- Project CRUD works.
- Multipart page upload stores PNG originals.
- Review canvas supports continuous draw, select, move, resize, delete, rename, and kind changes.
- Slices autosave and restore after refresh.
- Exported `assets.zip` contains originals, slices, `manifest.json`, and `project.json`.
- Storage artifacts are not tracked by git.
