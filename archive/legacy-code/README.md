# Legacy Code Archive

This directory keeps superseded implementation paths as reference material.

The active product is Slice Studio at the repository root. Code under this
archive is not part of the default runtime, workspace, build, or validation
path. Use it only when an active plan explicitly revives a component or when
you need to inspect historical implementation ideas.

Archived areas:

- `backend/`: older Python service and analysis pipelines.
- `services/`: Go, Python, Pencil, PSD-like, and handoff experiments.
- `figma-plugin/`: historical Figma plugin surface.
- `packages/`: deferred renderer and schema packages.
- `Figma-design/`: early plugin and manual slicing prototypes.
- `tests/`: old root-level test placeholders.

Do not write new product code here. If archived code is revived, move the
smallest required part back into an active module through a documented plan.
