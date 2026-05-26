# 062 M29 First-Principles Source Chain Code Audit

- 状态：active
- 创建日期：2026-05-26
- 负责人：Codex

## Goal

从 M29.0 开始，对当前 `image-figma` 主线做一次只读、代码事实驱动、第一性原理的 source-chain code audit。目标不是立刻修某个图、某个按钮、某个 icon、某个 tab，也不是接受外部审核报告或历史计划的结论；目标是把当前 M29 链路里每一层到底保存了什么事实、丢了什么事实、谁有决策权、谁只有报告权、哪里有特化倾向、哪里有错误抽象和信息损失全部讲清楚。

审计最终要回答：

```text
1. 当前 M29 主链每一层的 source truth 是什么？
2. 每一层允许新增什么事实，不允许新增什么事实？
3. 每一层的输入、输出、artifact、代码入口和测试覆盖在哪里？
4. 哪些启发式阈值是合理数学参数，哪些已经变成隐性特化？
5. 哪些错误必须在 raw M29 / M29.2 / evidence chain 修，不能在 materializer / Renderer / plugin 修？
6. 哪些 report-only surface 实际上正在被当成 decision 使用，或反过来只 report 没有形成可执行证据链？
7. 为什么真实样本里会出现“文字可选但图标/按钮/底部 tab/小 marker 仍不可选”的断点？
8. 下一步要按什么顺序修，才能接近 Codia-like usable design draft，而不是继续单样本补丁？
```

本计划的输出是一套审计报告，不是运行时行为变更。

## Mode

Use `stage-gated-dev-agent` in Harnessed Repository Mode, with `first-principles-analysis` as the judgment gate.

Execution mode for this plan:

```text
read current repo truth
-> define audit contract
-> inspect code and artifacts by source-chain layer
-> write durable code-review reports
-> produce prioritized fix roadmap
-> stop for user review before implementation
```

This plan is deliberately **audit-first**. It does not authorize broad refactor or bugfix implementation.

## Standards Read

Required standards for this audit:

```text
AGENTS.md
docs/index.md
docs/engineering/current-mainline-code-map.md
docs/architecture/m29-experimental-mathematical-contract.md
docs/architecture/m29-math-from-first-principles.md
docs/architecture/image_math_boundary.md
docs/engineering/m29-contract-regression-matrix.md
docs/engineering/testing-strategy.md
docs/bugs/index.md
docs/bugs/open/009-specialization-prone-m29-internal-asset-gates.md
docs/plans/active/056-m29-525-real-sample-batch-hardening.md
docs/plans/active/057-m29-525-editable-control-quality-hardening.md
docs/plans/active/058-m29-evidence-contract-for-internal-ui-icons.md
docs/plans/active/060-gemini-review-first-principles-audit.md
docs/plans/completed/061-codia-like-real-sample-hardening.md
```

External audit/reference inputs may be read, but they are not source truth:

```text
docs/reference/code_review_first_principles_Gemini.md
docs/reference/code_review_first_principles_technical_plan.md
/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma-gemini
```

## Scope

包含：

- 按当前主线，从 upload-preview 入口到 Figma-visible DSL 输出，逐层审计 M29 source chain。
- 对 M29.0/raw primitive graph、M29.2 ownership、M29.3 relation、M29.4 weak structure、M29.5 replay plan、ownership conservation、M29.6、transparent asset、evidence contract、internal source promotion、final replay、materializer、quality reports 做代码事实核验。
- 对当前历史 M29 audit packages 做 dead-path / compatibility / current-dependency 分类。
- 对真实 artifact 断点做 source-chain tracing，重点包括：
  - 文字可编辑但 icon 不可选；
  - media 内部 button/control 背景被大 raster 吞掉；
  - bottom tab icon / selected marker / table marker / small circular dot 丢失；
  - internal candidate report-only 但不能 promotion；
  - transparent asset 有 assetPath 门禁、edge alpha、alpha coverage、background stability 风险；
  - copied media cleanup 的授权和执行是否仍有双影/破洞风险。
- 输出 code review 报告目录和优先级修复路线。
- 必要时运行只读搜索命令、artifact jq 检查、targeted pytest 来验证代码事实。

不包含：

- 不直接改 runtime 行为。
- 不调整 threshold、confidence、EvidenceScore、alpha gate、cleanup gate。
- 不新增依赖。
- 不改 DSL schema、API response、Renderer、Figma plugin protocol、task state、database schema。
- 不恢复 M29 Direct、legacy M30、M31-M39/M39.1、ONNX proposer 或旧 product paths。
- 不以单张图片、单个 Figma URL、固定文案、固定坐标、固定 bbox 作为修复依据。

## Audit Output Directory

最终审计报告写入：

```text
docs/code-reviews/m29-first-principles-source-chain-audit/
```

目录建议结构：

```text
README.md
00-task-contract.md
01-current-runtime-chain.md
02-m290-raw-primitive-graph.md
03-m292-source-ownership.md
04-m293-region-relation.md
05-m294-weak-structure.md
06-m295-replay-plan.md
07-ownership-conservation.md
08-m296-media-internal-decomposition.md
09-transparent-asset-report.md
10-evidence-contract.md
11-internal-source-promotion.md
12-final-replay-and-materializer.md
13-post-materialization-quality.md
14-legacy-dead-path-inventory.md
15-specialization-and-heuristic-ledger.md
16-real-artifact-source-traces.md
17-prioritized-fix-roadmap.md
```

每个模块报告必须包含：

```text
source truth:
input artifacts:
output artifacts:
code entrypoints:
decision authority:
report-only surfaces:
allowed facts:
forbidden facts:
main formulas / gates:
thresholds and heuristic rationale:
known information loss:
known failure symptoms:
tests / guards:
artifact evidence:
findings:
recommended next action:
```

报告可以非常详细，但不要用图。若需要表达链路，使用分层文本和代码块。

## Audit Method

每一层都按同一套第一性原理问题审计：

```text
Real goal:
  这一层存在是为了降低什么用户修复成本，或保护什么视觉/ownership 正确性？

Primitive facts:
  如果删掉历史模块名、计划编号、外部报告和当前 threshold，哪些事实仍然成立？

Source truth:
  这一层从哪些像素、OCR、source object、relation、plan、asset 或 report 读事实？

Information loss:
  哪些像素事实、结构事实、关系事实、alpha 信息、cleanup 权限在这里被丢掉或合并？

Decision authority:
  这一层是否允许决定 visible replay、source ownership、cleanup、asset replacement、DSL mutation？

Wrong-abstraction risk:
  有没有把 report 当 decision、把 confidence 当 proof、把 materializer 当 owner、把 visual diff 当 source truth？

Specialization risk:
  有没有依赖文案、品牌、文件名、task id、路径、主题色、固定坐标、固定 bbox、单样本结构、单方向 anchor？

Verification:
  用什么代码、测试、artifact、真实样本或搜索结果证明这个判断？
```

审计深度分两级：

```text
line-referenced audit:
  所有改变 source ownership、candidate acceptance、execution support、transparent allow/reject、evidence decision、promotion、cleanup authorization、materialization 的函数。

interface-level audit:
  纯 report formatting、path layout、stage timing、summary 统计、类型薄封装等不改变事实或权限的代码。
```

如果审计过程中发现某个 interface-level 文件实际藏着决策逻辑，升级为 line-referenced audit。

## Source Chain Layers To Audit

### 1. Upload Preview Orchestration

Primary files:

```text
backend/app/upload_preview/pipeline.py
backend/app/upload_preview/stages.py
backend/app/upload_preview/paths.py
backend/app/upload_preview/types.py
backend/app/upload_preview/timings.py
backend/app/upload_preview/task_state.py
backend/app/routes/upload_preview.py
backend/app/routes/tasks.py
backend/scripts/run_upload_preview_batch_validation.py
```

Audit focus:

```text
stage order
which M29.2 document is used before/after promotion
where final reports replace pre-promotion reports
which artifacts are authoritative
whether route output can bypass plan-driven materializer
whether batch validation records enough artifact evidence
```

### 2. M29.0 Raw Primitive Graph

Primary files:

```text
backend/app/visual_primitive_graph.py
backend/app/visual_primitive/
backend/app/image_math/
backend/app/png_tools/
```

Audit focus:

```text
text mask construction
foreground mask
connected components
shape/image/symbol/unknown classification
low-contrast support detection
finite control background evidence
image protection mask
large media swallowing internal UI
threshold size classes that may act like hidden specialization
```

### 3. M29.2 Source Ownership

Primary files:

```text
backend/app/source_ui_physical_graph/
```

Audit focus:

```text
visualKind / pixelOwner / replayDecision authority
editable text vs preserve_raster_text
media_region vs control_background
raster_icon source ownership
diagnostic_only leakage
blocked foreground recovery
dedupe priority
sourceEvidence completeness
```

### 4. M29.3 Region Relation

Primary files:

```text
backend/app/region_relation_kernel.py
backend/app/region_relation_graph_report.py
```

Audit focus:

```text
single geometry kernel
contains / contained_by / overlap / near / alignment consistency
relation graph completeness for cleanup and grouping
no duplicate relation logic in downstream modules
```

### 5. M29.4 Weak Structure

Primary files:

```text
backend/app/stable_design_cluster/
```

Audit focus:

```text
weak structural evidence only
row/column/repeated/background-anchor evidence
whether weak clusters incorrectly imply visible group, Auto Layout, or component authority
```

### 6. M29.5 Replay Plan

Primary files:

```text
backend/app/m29_replay_plan/
```

Audit focus:

```text
finalReplayAction
targetRole
visible replay order
node budget
dedupe / suppress_duplicate
fallback cleanup authorization
copied_image_asset cleanup authorization
visible overlap suppression
whether cleanup permission is solely plan-owned
```

### 7. Ownership Conservation

Primary files:

```text
backend/app/ownership_conservation/
```

Audit focus:

```text
double ownership
invalid cleanup
promoted internal icon copied-image cleanup
text cleanup vs icon cleanup
report-only vs blocking behavior
whether it can catch wrong owner / wrong erase / unexplained erase
```

### 8. M29.6 Media Internal Decomposition

Primary files:

```text
backend/app/media_internal_decomposition/
```

Audit focus:

```text
composite media selection
TextMask protection
OCR-anchor windows
non-OCR foreground scanning
connected component scoring
anchor relations: above/below/left/right/near
internal group formation
groupSupportedExecution
matchedInternalGroupCount failure modes
button/control background missing path
internal marker/dot/table/tab evidence gaps
```

### 9. Transparent Asset Report

Primary files:

```text
backend/app/transparent_asset_report/
```

Audit focus:

```text
candidate source set
background estimation
alpha generation
edge alpha risk
unstable background
weak contrast
execution support
assetPath requirement
medium confidence gate drift
whether diagnostic asset generation is wrongly treated as ownership
```

### 10. Evidence Contract

Primary files:

```text
backend/app/m29_evidence_contract/
```

Audit focus:

```text
positive evidence
negative evidence
risk/cost penalty
transparent asset dependency
execution_supported definition
allow_visible_replay / report_only / reject
promotionAllowed correctness
whether EvidenceScore is decomposed proof or just another confidence number
```

### 11. Internal Source Promotion

Primary files:

```text
backend/app/internal_source_promotion/
```

Audit focus:

```text
only bridge back into M29.2
required transparent asset
required evidence contract allow
promoted sourceEvidence
dedupe against base source objects
whether promotion can create only raster_icon or also needs future control_background path
```

### 12. Final Replay And Materializer

Primary files:

```text
backend/app/plan_materializer/
backend/app/m29_plan_materializer.py
```

Audit focus:

```text
plan consumer only
no owner inference
no cleanup authorization invention
text/image/icon/shape replay
copied media cleanup execution
alpha-mask cleanup
fallback cleanup
DSL node output traceability
```

### 13. Post-Materialization Reports

Primary files:

```text
backend/app/hierarchy_candidate_report/
backend/app/sibling_group_candidate_report/
backend/app/layout_energy_report/
backend/app/auto_layout_permission_report/
backend/app/design_token_report/
backend/app/b_stage_quality_report/
backend/app/dsl_visual_comparison/
```

Audit focus:

```text
report-only boundaries
whether C-stage controlled structure creates only transparent groups
no Auto Layout / Component / variables / vectors
quality score meaning
visual diff as validation, not source truth
repair cost metric correctness
```

### 14. Legacy / Compatibility Packages

Primary files:

```text
backend/app/text_masked_media_audit/
backend/app/visual_evidence_normalization/
backend/app/visual_object_candidate_audit/
backend/app/text_aware_visual_object_refinement/
backend/app/text_visual_ownership_gate/
backend/app/symbol_fragment_grouping/
backend/app/member_boundary_quality_audit.py
backend/app/pre_ocr_symbol_lineage_audit.py
backend/app/mixed_symbol_text_conflict_audit.py
```

Audit focus:

```text
active dependency
test-only dependency
historical compatibility export
dead path
deleted route residue
whether old M29.0.x assumptions still bias current runtime
```

## Finding Categories

Every finding must be categorized:

```text
P0 architecture violation:
  downstream layer invents ownership, cleanup, visible nodes, or public contract behavior.

P1 source-chain correctness defect:
  real UI element evidence is present but lost, swallowed, blocked, or cannot reach M29.5.

P2 evidence quality gap:
  report exists but proof is incomplete, gate is over/under-strict, or validation lacks independent evidence.

P3 cleanup / documentation / dead-path debt:
  stale docs, misleading names, dead compatibility package, duplicate formula, weak comments.
```

Every finding must also include an owner layer:

```text
raw_m29
m29_2_source_ownership
m29_3_relation
m29_4_structure
m29_5_replay_plan
ownership_conservation
m29_6_internal_decomposition
transparent_asset
evidence_contract
internal_source_promotion
plan_materializer
post_materialization_quality
renderer_or_plugin
docs_or_tests
```

## Anti-Specialization Audit

Search and inspect active mainline code for:

```bash
rg -n "SearchBar|Card|充值|提币|划转|买币|Google|Facebook|Snapchat|Phone|filename|taskId|theme|brand|fixed|hack|special|coordinate|bbox" backend/app packages figma-plugin -S
rg -n "sample|fixture|TODO|hack|filename|brand|theme|coordinate|fixed|magic|only|Google|充值|提币|划转|买币" backend/app backend/tests docs -S
```

These terms are inspection prompts, not automatic proof. A threshold is not invalid merely because it is numeric. It becomes a bug when its only justification is one sample, one fixed geometry, one direction, one text, one theme, one brand, or one path.

Threshold review must distinguish:

```text
valid mathematical parameter:
  area ratio, containment, overlap, compactness, edge alpha, contrast, texture, fill ratio, cleanup risk.

specialization smell:
  fixed y band, one icon direction only, literal label, brand, file name, exact image size, exact bbox, upload order, task id, theme color.

contract smell:
  confidence alone decides promotion, report-only layer changes output, materializer invents owner, cleanup without M29.5 target.
```

## Real Artifact Tracing

Use existing artifacts first. Do not commit storage artifacts.

Primary recent traces:

```text
backend/storage/upload_previews/task_33428579a6f7
latest real upload where text is editable but Google icon/button is not promoted
```

Known trace questions:

```text
1. Where does Google icon first appear?
2. Is it missing in M29.6, or detected then blocked?
3. Which transparent asset gate rejected it?
4. Why did evidence contract stay report_only?
5. Why did promotion reject?
6. Why does the button background have no source object?
7. Which layer owns the future fix?
```

Use batch ledgers where they already exist:

```text
backend/tmp/validation/upload_preview_batch_*
```

If current evidence is stale or insufficient, rerun a representative batch only after the audit task contract is accepted.

## Validation

Because this plan is audit-only, validation is mostly structural and evidence based:

```bash
git diff --check
git status --short --branch
```

Required read-only commands:

```bash
rg --files backend/app
rg --files backend/tests
rg -n "cleanupTargets|copied_image_asset|pixelOwner|replayDecision|allow_visible_replay|groupSupportedExecution|candidateAllowedForAlpha|assetPath|internal_candidate_not_execution_supported" backend/app backend/tests -S
rg -n "SearchBar|Card|充值|提币|划转|买币|Google|Facebook|Snapchat|Phone|filename|taskId|theme|brand|fixed|hack|special|coordinate|bbox" backend/app packages figma-plugin -S
rg -n "import (numpy|PIL|skimage|cv2|torch)|from (numpy|PIL|skimage|cv2|torch)" backend/app backend/tests -S
```

Targeted pytest is optional during audit and required only when a finding depends on current test behavior:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py -q
```

No full real-image batch is required to create the audit report. A batch run becomes required only if the audit claims current sample-level acceptance or regression state.

## Acceptance

This plan is accepted when:

- `docs/plans/active/062-m29-first-principles-source-chain-code-audit.md` exists and defines the audit contract.
- The audit output directory exists and contains the final report set listed above.
- Reports are based on current code, current docs, current tests, and current artifacts, not chat memory.
- Every M29 layer from raw primitive graph through materializer has a source-truth / decision-authority / information-loss section.
- All P0/P1/P2/P3 findings have file references, owner layer, evidence, forbidden fix path, and recommended next action.
- Specialization risks are explicitly separated from valid mathematical thresholds.
- The final roadmap gives stage-scoped fixes with validation commands and real artifact acceptance criteria.
- No runtime behavior is changed as part of the audit unless a separate user-approved implementation plan supersedes this plan.

## Stop Conditions

Stop and report before implementation if the audit finds:

- public DSL/API/plugin/task-state/database contract change is necessary;
- current docs contradict current code in a way that changes product behavior;
- source ownership defect cannot be fixed without a broader M29 contract rewrite;
- required local artifacts are missing and cannot be regenerated without unavailable external services;
- dirty worktree prevents safe isolation of audit documents.

## Notes

The motivating failures include current real cases such as:

```text
text becomes editable, but icon remains raster
button label is editable, but whole button is not draggable
bottom tab icon / selected marker is missing
media-contained internal UI candidate is report-only but not promoted
large media swallows finite control backgrounds
medium-confidence candidate is detected but fails execution support
```

These are not to be fixed one by one in this audit. They are source-chain symptoms used to locate contract gaps.

The current architectural suspicion is:

```text
M29 has accumulated several locally reasonable gates.
Some gates are valid mathematical filters.
Some gates now behave like hidden specialization by size, confidence, direction, or available evidence source.
The audit must identify which is which before the next implementation stage.
```
