# 00 Task Contract

## Objective

按 `docs/plans/active/062-m29-first-principles-source-chain-code-audit.md` 执行 M29 source-chain 只读代码审计。审计目标是把 M29.0 到 DSL/Figma 的当前主链事实讲清楚，并输出后续修复路线。当前阶段不改运行行为。

## Mode

```text
stage-gated-dev-agent: Harnessed Repository Mode
first-principles-analysis: judgment gate
```

本阶段不是 bugfix mode。真实样本如 `task_33428579a6f7` 可用于 source trace，但不能把单样本现象变成生产规则。

## Standards Read

已读或本阶段约束来源：

```text
AGENTS.md
docs/index.md
docs/plans/active/062-m29-first-principles-source-chain-code-audit.md
docs/engineering/current-mainline-code-map.md
docs/architecture/m29-experimental-mathematical-contract.md
docs/bugs/open/009-specialization-prone-m29-internal-asset-gates.md
docs/plans/active/056-m29-525-real-sample-batch-hardening.md
docs/plans/active/057-m29-525-editable-control-quality-hardening.md
docs/plans/active/058-m29-evidence-contract-for-internal-ui-icons.md
docs/plans/active/060-gemini-review-first-principles-audit.md
docs/plans/completed/061-codia-like-real-sample-hardening.md
```

用户明确说 `docs/reference/code_review_first_principles_Gemini.md` 不用管。本审计不修改该文件，也不把它当 source truth。

## Affected Layers

```text
source input:
  source PNG pixels, OCR boxes

intermediate data:
  raw M29 nodes, M29.2 source objects, relation graph, replay plan, internal candidates, transparent assets, evidence contract, promotion report

decision point:
  M29.2 source ownership, M29.5 replay/cleanup plan, evidence contract allow/report/reject, internal source promotion

output surface:
  materialized_design/design.dsl.json, materialization_report.json, /api/tasks/{taskId}/dsl, Renderer/Figma

validation surface:
  tests, stage_timings, batch ledger, artifact JSON, dsl_visual_comparison
```

## Allowed Scope

Audit/write docs only:

```text
docs/code-reviews/m29-first-principles-source-chain-audit/
docs/plans/active/062-m29-first-principles-source-chain-code-audit.md
docs/index.md
```

Read-only inspection of:

```text
backend/app/
backend/tests/
backend/scripts/
docs/architecture/
docs/engineering/
docs/bugs/
backend/storage/upload_previews/
backend/tmp/validation/
```

## Forbidden Scope

本审计阶段禁止：

```text
runtime behavior changes
threshold changes
new dependencies
DSL schema changes
API response changes
Renderer changes
Figma plugin changes
database/task-state contract changes
materializer owner inference
cleanup outside M29.5 cleanupTargets
single-sample or brand/text/path/coordinate-specific logic
```

## Commands

Read-only / documentation checks:

```bash
git status --short --branch
git diff --check
rg --files backend/app
rg --files backend/tests
rg -n "cleanupTargets|copied_image_asset|pixelOwner|replayDecision|allow_visible_replay|groupSupportedExecution|candidateAllowedForAlpha|assetPath|internal_candidate_not_execution_supported" backend/app backend/tests -S
rg -n "SearchBar|Card|充值|提币|划转|买币|Google|Facebook|Snapchat|Phone|filename|taskId|theme|brand|fixed|hack|special|coordinate|bbox" backend/app packages figma-plugin -S
```

Targeted pytest is allowed only when a finding depends on current test behavior:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py -q
```

## Acceptance Criteria

审计完成需要证明：

```text
1. 每个 M29 主链层都有独立报告。
2. 每个报告都包含 source truth、input/output artifact、entrypoints、decision authority、information loss、tests、findings。
3. 所有 P0/P1/P2/P3 finding 都有 owner layer、文件引用、证据、禁止修复路径、推荐下一步。
4. 合理数学阈值与隐性特化被明确分开。
5. 最终 roadmap 给出按阶段修复顺序和每阶段验证方式。
6. 没有 runtime 行为在审计阶段被改动。
```

## Git Policy

当前 repo 在 `main`，工作树已有：

```text
main...origin/main [ahead 1]
docs/index.md modified
docs/plans/active/062-m29-first-principles-source-chain-code-audit.md untracked
docs/reference/code_review_first_principles_Gemini.md untracked, user said do not touch
```

审计文件可以后续作为文档阶段提交，但提交必须只包含本审计相关 docs，不包含 storage/tmp/generated artifacts，也不包含用户指定不用管的 Gemini reference 文件。

## Stop Conditions

停止并报告：

```text
1. 审计发现必须改 public contract 才能继续。
2. 当前文档与代码冲突到无法判断 active runtime。
3. 关键 artifact 不存在，且无法在不依赖外部 OCR 的情况下复现。
4. dirty tree 无法隔离审计文档。
5. 用户要求暂停。
```
