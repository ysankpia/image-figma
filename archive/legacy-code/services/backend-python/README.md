# Legacy Python Experiments

This directory is retained as legacy/research code for OmniParser, VLM, PSD-like, and model-assisted decomposition experiments.

It is not the current product delivery backend. Current assisted slice product work belongs in:

```text
services/pencil-python-backend/
```

Use this directory only when a task explicitly targets historical model experiments or when a new active plan defines how to promote a piece of this code into the current candidate-generation pipeline.

Rules:

- Do not run this as the default service for the product.
- Do not connect it directly to the current Pencil export path.
- Do not treat its automatic ownership decisions as final visible ownership.
- If a useful idea is reused, translate it into `candidates.v1.json`, debug evidence, or a separately approved contract.

See:

```text
docs/engineering/legacy-code-inventory.md
docs/engineering/current-code-map.md
```
