# Superseded Full-Chain First-Principles Audit

This file intentionally keeps only a tombstone summary.

The original audit described an older Python upload-preview / M29 materialization chain. That chain is not the current product runtime on this branch.

Current product work must start from:

- [../../AGENTS.md](../../AGENTS.md)
- [../index.md](../index.md)
- [../../services/pencil-python-backend/README.md](../../services/pencil-python-backend/README.md)
- [../reference/pencil-python-backend-api.md](pencil-python-backend-api.md)
- [../runbooks/pencil-python-backend-handoff.md](../runbooks/pencil-python-backend-handoff.md)
- [../engineering/current-code-map.md](../engineering/current-code-map.md)
- [../plans/completed/145-assisted-slice-workspace-acceptance-hardening.md](../plans/completed/145-assisted-slice-workspace-acceptance-hardening.md)

Current architecture:

```text
1..N images
-> Pencil assisted slice workspace
-> candidates.v1.json
-> manual_slices.v1.json
-> project.zip + selected-assets.zip
```

Use git history if the full superseded audit is needed for archaeology.
