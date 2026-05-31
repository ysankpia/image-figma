# Reliability

Draft runtime reliability means task state is correct, failure is explicit, and completed output satisfies the Draft contract.

## Task States

```text
queued
running
completed
failed
```

Draft stages:

```text
draft_queued
ocr
m29_physical_evidence
vision_detector
vision_review
draft_assemble
draft_assets
draft_validate
draft_export
draft_completed
draft_failed
```

## Failure Strategy

Request-level failures reject upload immediately:

```text
invalid MIME
invalid PNG signature
unreadable image dimensions
file too large
```

Pipeline-level failures update the task:

```text
status = failed
stage = failing stage
message = concrete error
```

The server must recover from panics inside task goroutines and mark the task failed. A task must not remain permanently `running`.

## Required Evidence

M29 physical evidence and Draft assembly/export are required. If they fail, the task fails.

OCR may be required depending on configured provider and product mode. If OCR is required and fails, the task fails.

Vision detector/review is best-effort by default. Provider TLS, timeout, 5xx, empty response, or JSON parse failure should write a fallback artifact and continue with M29/OCR unless the request explicitly requires vision.

## Completion Requirements

A task may be marked completed only when:

- `editable_layer_graph.v1.json` exists;
- `draft_runtime.dsl.v1.json` exists;
- visible RasterLayer assets resolve;
- Draft validation has no blocking violations;
- task state points to the completed artifact paths.

Do not return fake DSL after a required evidence stage fails.
