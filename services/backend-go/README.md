# Go M29 And Deferred Draft Backend

This directory has two different statuses.

Current diagnostic/dependency surface:

```text
cmd/m29extract/
internal/m29/
```

`services/pencil-python-backend` can use `m29extract` for `boundarySource=m29` and `boundarySource=hybrid`, and the deploy bundle includes the Go M29 extraction code. This part is not dead code.

Deferred legacy/research surface:

```text
cmd/draftcompile/
cmd/draftdetect/
cmd/draftserver/
internal/app/
internal/draft/
internal/vision/
```

Those packages belong to the historical Go Draft runtime and model-assisted Draft experiments. They are not the current product delivery route on `main`.

Rules:

- Do not treat Go Draft as the default product route.
- Do not restore Codia Beta generation paths here.
- Do not read Codia golden samples from generation code.
- If Draft is resumed, create a new active plan and define the contract and acceptance gate first.

See:

```text
docs/engineering/legacy-code-inventory.md
docs/engineering/current-code-map.md
```
