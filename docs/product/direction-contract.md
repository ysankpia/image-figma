# Direction Contract

This document is the current project direction contract. It overrides historical Draft, Codia, and older Pencil-assisted plans when they conflict with the current code and documentation.

## Real user outcome

Users can upload one or more UI screenshots/design images, quickly create or AI-assist rectangular asset boxes, manually adjust the result, and export a package that can be opened in Pencil and continued in Figma, plus a frontend asset ZIP.

## Final artifact

The current default deliverables are produced by `apps/slice-studio`:

```text
assets.zip
project.zip
design.pen inside project.zip
manifest.json
project.json
slice PNG assets
editable OCR text nodes when OCR is configured
```

## Success signal

For a real multi-page sample project:

- pages upload and persist in the project workspace;
- manual or AI-assisted boxes save as normal slices;
- repeated AI drawing does not create large duplicated overlap;
- `assets.zip` contains confirmed slice assets by page order;
- `project.zip` contains `design.pen`, page originals, remainder layers, visible slice assets, and manifest metadata;
- Pencil can open `design.pen`;
- visible asset references are package-local and do not point to absolute paths, source files, debug crops, masks, raw fragments, or parent directories;
- optional OCR/M29 text layers improve editability without overriding confirmed slice assets.

## Truth source

The SQLite-backed Slice Studio project state is the live editing truth. Saved `SliceRecord` rows and page order are the export truth.

For exported packages, `manifest.json` with schema `manual_ui_slices.v1` is the artifact truth. AI slice boxes, M29 physical evidence, OCR output, and old automatic candidates are evidence only.

## Evidence and candidate sources

- User-drawn boxes in the Review Workbench.
- AI-generated rectangular boxes from `POST /api/projects/:projectId/pages/:pageId/ai-boxes`.
- OCR text content from the configured Slice Studio OCR provider.
- TypeScript `m29-physical-evidence` for editable text physical bbox placement.
- Go `m29extract` only when explicitly configured as a reference/fallback.
- Historical Python Pencil, Pencil Asset, Pencil Handoff Studio, Draft, Renderer, and plugin outputs as reference material only.

## Human repair path

Users repair output in the Review Workbench:

- add, move, resize, rename, or delete boxes;
- choose `rect`, `subject`, or `card` cut mode;
- page through multi-image projects;
- rename, replace, reorder, or delete pages;
- export again after corrections.

The repair path is intentionally normal slice editing, not a separate AI proposal state.

## Non-goals

Current default delivery does not aim to:

- rebuild a semantic UI tree;
- produce Codia-compatible JSON;
- infer Auto Layout or components;
- make YOLO, OCR, M29, or AI the final visible ownership judge;
- revive Go Draft or Python upload-preview as the default product route;
- depend on the Go `m29extract` binary for default Slice Studio text placement;
- turn OCR text into button/card/background reconstruction;
- perform cloud sync, auth, billing, or collaboration.

## Validation artifact

Primary validation artifacts:

- `apps/slice-studio` typecheck/test/build output;
- real project smoke using uploaded images;
- generated `assets.zip` and `project.zip`;
- package inspection of `manifest.json`, `project.json`, and visible asset paths;
- Pencil open/screenshot inspection when `.pen` visual fidelity is in scope.

## Direction risk signals

Revisit this contract if any of these appear:

- root docs again point new work to `services/pencil-python-backend` or Draft as the default route;
- AI, OCR, M29, YOLO, or legacy candidates bypass saved Slice Studio slices;
- export starts cropping from thumbnails, debug artifacts, or generated intermediates instead of source originals;
- old Draft/Renderer/plugin work is revived without a new active plan and validation gate;
- manual repair becomes impossible or secondary to automatic ownership.
