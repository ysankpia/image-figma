# Plan 208: Qwen Layered Evidence Experiment

Status: active
Started: 2026-06-26

## Objective

Evaluate whether Qwen-Image-Layered can revive the old Draft / Codia-like layer route when combined with existing evidence sources instead of relying on Slice Studio manual boxes alone.

The experiment uses the user-provided mobile UI screenshot as the first concrete sample and writes all artifacts under:

```text
docs/reports/qwen-layered-evidence-experiment/
```

Large generated PNG/JSON artifacts may live under `/private/tmp/qwen-layered-probe/`; report files must link to their exact paths and summarize the evidence so the conclusion survives chat compaction.

## Evidence Routes

1. Baseline Qwen-Image-Layered on the full screenshot.
2. M29 physical evidence on the full screenshot.
3. YOLO / Deki YOLO evidence where local model artifacts or runnable scripts are available.
4. PSD-like legacy decomposition scripts as non-model physical/texture evidence.
5. Combination tests:
   - evidence-selected ROI -> Qwen recursive decomposition;
   - Qwen alpha layers -> threshold / connected components / bbox extraction;
   - high-resolution original pixels + Qwen masks;
   - evidence post-processing to split Qwen coarse layers.

## Non-Goals

- Do not wire Qwen into the production Slice Studio runtime in this plan.
- Do not commit API tokens, generated zips, `.pen`, SQLite databases, or storage artifacts.
- Do not claim Codia parity from one screenshot.
- Do not treat M29, YOLO, PSD-like, or Qwen as final ownership authority without reviewable artifacts.

## Acceptance

- A report ranks the tested routes by layer usefulness, fidelity, granularity, runtime, and integration risk.
- The report names which route should drive a restart of the old Draft / Codia-like pipeline.
- Each tested route has reproducible input/output paths and at least one visual artifact or structured JSON summary.
- The working tree remains clean except for scoped documentation/report files unless implementation work is explicitly requested later.

## Current Hypothesis

Qwen-Image-Layered is the best coarse pixel-ownership source. M29 and YOLO should not be used as primary layer generators; they should split, validate, or select regions for recursive Qwen calls and post-process masks into candidate raster layers.
