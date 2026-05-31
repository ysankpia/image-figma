# Superseded Codex Prompt Snapshot

This file intentionally no longer carries an executable agent prompt.

The old prompt targeted the historical Python/M29 and later Codia Beta investigation paths. Those paths are not the current product runtime on this branch.

Current work must start from:

- [../../AGENTS.md](../../AGENTS.md)
- [../index.md](../index.md)
- [../architecture/overview.md](../architecture/overview.md)
- [../architecture/runtime.md](../architecture/runtime.md)
- [../engineering/current-code-map.md](../engineering/current-code-map.md)
- [../plans/active/093-editable-draft-layer-pipeline-rebuild.md](../plans/active/093-editable-draft-layer-pipeline-rebuild.md)

Current product path:

```text
PNG
-> Go /api/draft-preview
-> OCR + M29 physical evidence + optional vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

Use git history if the old prompt text is needed for archaeology.
