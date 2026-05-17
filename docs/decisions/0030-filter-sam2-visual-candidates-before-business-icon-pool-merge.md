# ADR 0030: Filter SAM2 Visual Candidates Before Business Icon Pool Merge

## Status

Accepted.

## Context

M25 proved that business icon candidate extraction is useful, but fixed region probes are brittle and expensive to keep extending. M26 compared current rules, OpenCV, SAM2 and UIED under one benchmark. The evidence showed OpenCV is fast but noisy, SAM2 tiny is slower but cleaner, and UIED is not worth vendoring.

The next useful step is not visible replay and not more hard-coded region probes. We need a cleaner visual candidate pool that can feed a later merge/placement stage.

## Decision

M27 introduces a SAM2-guided visual candidate filtering harness. It runs SAM2 automatic mask generation only when explicitly enabled and a local checkpoint is configured. It maps masks back to original image coordinates, filters them with existing DSL/text/cover/existing-icon/exclusion facts, and writes `SamVisualCandidateDocument v0.1`, a debug overlay and SQLite summary.

M27 does not modify DSL or Figma output. It does not crop icon assets or generate transparent PNG. It does not make SAM2 output authoritative. The output is evidence for M28, where M25 rule candidates and M27 SAM candidates can be deduped and planned together.

The local development environment may install SAM2 runtime in a uv dependency group and keep the checkpoint on the external work drive. Checkpoints remain outside tracked files.

## Consequences

- We stop expanding M25 fixed-window rules blindly.
- SAM2 runtime and checkpoint cost stay explicit and opt-in.
- Upload remains stable when dependencies or checkpoint are missing.
- M28 can compare and merge M25 and M27 candidates with actual evidence.
- Renderer and DSL contracts remain stable in M27.
