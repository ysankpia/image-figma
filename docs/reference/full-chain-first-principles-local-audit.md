# Superseded Full-Chain First-Principles Audit

This file intentionally keeps only a tombstone summary.

The original audit described an older Python upload-preview / M29 materialization chain. That chain is not the current product runtime on this branch.

Current product work must start from:

- [../../AGENTS.md](../../AGENTS.md)
- [../index.md](../index.md)
- [../architecture/overview.md](../architecture/overview.md)
- [../architecture/runtime.md](../architecture/runtime.md)
- [../engineering/current-code-map.md](../engineering/current-code-map.md)
- [../plans/active/093-editable-draft-layer-pipeline-rebuild.md](../plans/active/093-editable-draft-layer-pipeline-rebuild.md)

Current architecture:

```text
PNG
-> Go /api/draft-preview
-> OCR + M29 physical evidence + optional vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

Use git history if the full superseded audit is needed for archaeology.
