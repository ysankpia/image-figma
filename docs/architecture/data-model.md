# 数据模型

v0.1 使用 SQLite 记录任务、资产、DSL 结果和调试信息。

## Tables

当前已实现表：

- `tasks`
- `assets`
- `dsl_results`
- `error_logs`
- `primitive_results`
- `ocr_results`
- `dsl_patch_results`
- `text_replacement_results`
- `text_binding_results`
- `component_structure_results`
- `component_annotation_results`
- `layer_separation_results`
- `asset_slice_results`
- `icon_candidate_results`
- `icon_coverage_audit_results`
- `icon_gap_candidate_results`
- `icon_placement_plan_results`
- `icon_visible_fallback_results`
- `icon_business_candidate_results`
- `perception_benchmark_results`

后续建议表：

- `model_call_logs`

可选表：

- `render_logs`

## tasks

用途：记录上传和处理任务。

核心字段：

- `id`
- `status`
- `stage`
- `progress`
- `message`
- `original_filename`
- `mime_type`
- `file_size`
- `upload_path`
- `created_at`
- `updated_at`
- `completed_at`
- `failed_at`

`status` 枚举：

- `completed`
- `failed`

M26 当前任务主链路仍同步写入 `completed` 或 `failed`。各阶段旁路结果表可以写入 `completed`、`failed` 或 `skipped`。后续接真实处理管线再补任务级 `pending`、`uploaded`、`processing`。

## assets

用途：记录原图、裁切图、fallback、头像、商品图、Banner 等资产。

核心字段：

- `id`
- `asset_id`
- `task_id`
- `role`
- `path`
- `url`
- `mime_type`
- `width`
- `height`
- `created_at`

常见 `role`：

- `original`
- `original_reference`
- `image`
- `avatar`
- `product`
- `banner`
- `fallback`
- `icon`
- `asset_slice_candidate`
- `asset_slice_filled_candidate`
- `asset_icon_candidate`
- `asset_icon_coverage_overlay`
- `asset_icon_gap_candidate`
- `asset_icon_gap_overlay`
- `asset_icon_placement_overlay`
- `asset_icon_visible_fallback_overlay`
- `asset_icon_business_candidate`
- `asset_icon_business_overlay`
- `asset_perception_overlay_rules`
- `asset_perception_overlay_opencv`
- `asset_perception_overlay_sam2`
- `asset_perception_overlay_uied`

M9 写入真实 PNG 宽高到 `assets.width` 和 `assets.height`。

当前上传成功路径会写入：

- `asset_original`：原始上传 PNG。
- `asset_banner`：兼容旧查询的 full-image fallback 资产，M9 成功切分时不进入 DSL。
- `asset_region_header`：顶部 region crop。
- `asset_region_content`：中部 region crop。
- `asset_region_bottom`：底部 region crop。
- `asset_slice_*`：M19 生成的实验 slice PNG，只通过 `/asset-slice-candidates` 暴露，不进入 DSL `assets`。
- `asset_icon_candidate_*`：M20 生成的 icon PNG 候选资产，只通过 `/icon-candidates` 暴露，不进入 DSL `assets`。
- `asset_icon_coverage_overlay`：M21 生成的 debug overlay PNG，只通过 `/icon-coverage-audit`、`/api/assets/{assetId}` 或静态文件访问，不进入 DSL `assets`。
- `asset_icon_gap_*`：M22 生成的 gap icon PNG 候选资产，只通过 `/icon-gap-candidates` 暴露，不进入 DSL `assets`。
- `asset_icon_gap_overlay`：M22 生成的 debug overlay PNG，只通过 `/icon-gap-candidates`、`/api/assets/{assetId}` 或静态文件访问，不进入 DSL `assets`。
- `asset_icon_placement_overlay`：M23 生成的 placement decision debug overlay PNG，只通过 `/icon-placement-plan`、`/api/assets/{assetId}` 或静态文件访问，不进入 DSL `assets`。
- `asset_icon_visible_fallback_overlay`：M24 生成的 visible fallback replay debug overlay PNG，只通过 `/icon-visible-fallback`、`/api/assets/{assetId}` 或静态文件访问，不进入 DSL `assets`。
- `asset_icon_business_*`：M25 生成的 business icon PNG 候选资产，只通过 `/icon-business-candidates` 暴露，不进入 DSL `assets`。
- `asset_icon_business_overlay`：M25 生成的 debug overlay PNG，只通过 `/icon-business-candidates`、`/api/assets/{assetId}` 或静态文件访问，不进入 DSL `assets`。
- `asset_perception_overlay_*`：M26 生成的 provider benchmark debug overlay PNG，只通过 `/perception-benchmark`、`/api/assets/{assetId}` 或静态文件访问，不进入 DSL `assets`。

如果 cropper 不支持该 PNG 格式，DSL 只使用 `asset_original` 和 `asset_banner`，并在 `meta.qualityFlags` 标记 `region_crop_unsupported`。

## dsl_results

用途：记录 DSL 结果文件和校验状态。

核心字段：

- `id`
- `task_id`
- `dsl_path`
- `version`
- `validation_status`
- `validation_errors`
- `created_at`

`validation_status`：

- `valid`
- `repaired`
- `invalid`

## error_logs

用途：记录任务失败和可追踪错误。

核心字段：

- `id`
- `task_id`
- `stage`
- `error_code`
- `message`
- `detail`
- `severity`
- `created_at`

## primitive_results

用途：记录 M8 visual primitive candidate 文件和 provider 状态。

核心字段：

- `id`
- `task_id`
- `provider`
- `model`
- `status`
- `primitive_path`
- `primitive_count`
- `relation_count`
- `error_code`
- `error_message`
- `created_at`

`status`：

- `completed`
- `partial`
- `failed`
- `skipped`

primitive payload 本体写入 `backend/storage/primitives/{taskId}.json`，SQLite 只保存索引和摘要，避免大 JSON 塞进数据库。

primitive extraction 失败时仍写入一条 `primitive_results`，`status` 为 `failed`，并在 `error_logs` 记录 `primitive_extract` 阶段错误。这样上传主链路能继续返回 DSL，同时调试端能看到失败原因。

## ocr_results

用途：记录 M9 OCR candidate 文件和 provider 状态。

核心字段：

- `id`
- `task_id`
- `provider`
- `model`
- `status`
- `ocr_path`
- `block_count`
- `error_code`
- `error_message`
- `created_at`

OCR payload 本体写入 `backend/storage/ocr/{taskId}.json`。

## dsl_patch_results

用途：记录 M9 DSL patch 文件、模式和状态。

核心字段：

- `id`
- `task_id`
- `mode`
- `status`
- `patch_path`
- `patch_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Patch payload 本体写入 `backend/storage/patches/{taskId}.json`。

## text_replacement_results

用途：记录 M14 visible text replacement 文件、模式和状态。

核心字段：

- `id`
- `task_id`
- `mode`
- `status`
- `replacement_path`
- `accepted_count`
- `rejected_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Replacement payload 本体写入 `backend/storage/text_replacements/{taskId}.json`。默认 `debug` 只保存 accepted/rejected decisions、sampling strategy 和 quality/application 报告；`apply` 把非 high-risk 的 accepted replacement 合并进最终 DSL。SQLite 不单独保存 applied/blocked/rescued/strategy 计数，这些统计写在 JSON `meta` 中。

## text_binding_results

用途：记录 M15 text-primitive binding 文件和状态。

核心字段：

- `id`
- `task_id`
- `status`
- `binding_path`
- `container_count`
- `binding_count`
- `unbound_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Binding payload 本体写入 `backend/storage/text_bindings/{taskId}.json`。它保存 `containers`、`bindings`、`unboundTextIds` 和统计 meta。`inferred_from_text_cluster` containers 只存在于 binding payload，不回写 M8 visual primitives。

## component_structure_results

用途：记录 M16 component structure 文件和状态。

核心字段：

- `id`
- `task_id`
- `status`
- `structure_path`
- `component_count`
- `group_count`
- `unstructured_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Component structure payload 本体写入 `backend/storage/component_structures/{taskId}.json`。它保存 `components`、`groups`、`unstructuredContainerIds` 和统计 meta。M16 只消费 M15 binding facts，输出 component candidates 和 layout groups；不会把 inferred components 写回 M8 visual primitives，也不会创建 Figma Component/Instance。

## component_annotation_results

用途：记录 M17 component annotation 文件和状态。

核心字段：

- `id`
- `task_id`
- `status`
- `annotation_path`
- `annotation_count`
- `group_hint_count`
- `unannotated_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Component annotation payload 本体写入 `backend/storage/component_annotations/{taskId}.json`。它保存 `annotations`、`groupHints`、`unannotatedElementIds`、`unresolvedComponentIds` 和统计 meta。M17 只消费 M15/M16 的 binding/component facts，通过确定性 ID join 给已有 DSL element 添加 `name` 和 `meta`；不会切图、不会创建 Figma group/component、不会删除 fallback region，也不会把 annotation 写回 visual primitives。

## layer_separation_results

用途：记录 M18 layer separation candidate 文件和状态。

核心字段：

- `id`
- `task_id`
- `status`
- `separation_path`
- `candidate_count`
- `fill_candidate_count`
- `repair_required_count`
- `embedded_text_count`
- `blocked_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Layer separation payload 本体写入 `backend/storage/layer_separation_candidates/{taskId}.json`。它保存 `candidates`、`fallbackContexts`、`blockedComponentIds` 和统计 meta。M18 只消费 M14/M15/M16/M17 facts 和已有 PNG 采样能力，输出分层策略候选与 simple fill candidate；不会切图、不会生成填充 PNG、不会删除 fallback、不会修改已有 DSL element，也不会引入 Pillow/OpenCV。

## asset_slice_results

用途：记录 M19 local asset slice candidate 文件和状态。

核心字段：

- `id`
- `task_id`
- `status`
- `slice_path`
- `slice_count`
- `filled_slice_count`
- `blocked_count`
- `failed_slice_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Asset slice payload 本体写入 `backend/storage/asset_slice_candidates/{taskId}.json`。它保存 `slices`、`blockedComponentIds` 和统计 meta。生成的 PNG 写入 `backend/storage/assets/{taskId}/slices/`，并以 `asset_slice_candidate` 或 `asset_slice_filled_candidate` role 登记到 `assets` 表。M19 不把这些实验 slice 写入 DSL `assets` 数组，不改变 Figma 可见输出。

## icon_candidate_results

用途：记录 M20 icon candidate extraction 文件和状态。

核心字段：

- `id`
- `task_id`
- `status`
- `icon_path`
- `icon_count`
- `cropped_icon_count`
- `blocked_count`
- `failed_crop_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Icon candidate payload 本体写入 `backend/storage/icon_candidates/{taskId}.json`。它保存 `icons`、`blockedComponentIds` 和统计 meta。生成的 PNG 写入 `backend/storage/assets/{taskId}/icons/`，并以 `asset_icon_candidate` role 登记到 `assets` 表。M20 不把这些 icon 候选写入 DSL `assets` 数组，不改变 Figma 可见输出，不声明 icon 语义。

## icon_coverage_audit_results

用途：记录 M21 icon coverage audit 文件、overlay 资产和 placement readiness 摘要。

核心字段：

- `id`
- `task_id`
- `status`
- `audit_path`
- `overlay_asset_id`
- `placement_count`
- `missed_hint_count`
- `ready_count`
- `needs_fallback_coordination_count`
- `needs_slice_coordination_count`
- `blocked_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Icon coverage audit payload 本体写入 `backend/storage/icon_coverage_audits/{taskId}.json`。它保存 `placements`、`missedIconHints`、`coverageOverlay`、`blockedIconCandidateIds` 和统计 meta。overlay PNG 写入 `backend/storage/assets/{taskId}/debug/icon_coverage_overlay.png`，并以 `asset_icon_coverage_overlay` role 登记到 `assets` 表。M21 不把 overlay 或 icon 候选写入 DSL `assets` 数组，不改变 Figma 可见输出，不声明 icon 语义。

## icon_gap_candidate_results

用途：记录 M22 region-guided icon gap candidate 文件、overlay 资产和漏裁补齐摘要。

核心字段：

- `id`
- `task_id`
- `status`
- `gap_path`
- `overlay_asset_id`
- `gap_icon_count`
- `cropped_gap_icon_count`
- `blocked_count`
- `failed_crop_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Icon gap candidate payload 本体写入 `backend/storage/icon_gap_candidates/{taskId}.json`。它保存 `gapIcons`、`blockedHints`、`gapOverlay`、`warnings` 和统计 meta。gap icon PNG 写入 `backend/storage/assets/{taskId}/icons_gap/`，并以 `asset_icon_gap_candidate` role 登记到 `assets` 表。overlay PNG 写入 `backend/storage/assets/{taskId}/debug/icon_gap_overlay.png`，并以 `asset_icon_gap_overlay` role 登记到 `assets` 表。M22 不把 gap icon 或 overlay 写入 DSL `assets` 数组，不改变 Figma 可见输出，不声明 icon 语义。

## icon_placement_plan_results

用途：记录 M23 icon placement plan 文件、overlay 资产和分层就绪摘要。

核心字段：

- `id`
- `task_id`
- `status`
- `plan_path`
- `overlay_asset_id`
- `placement_count`
- `ready_count`
- `needs_fallback_mask_count`
- `needs_slice_coordination_count`
- `needs_fallback_coordination_count`
- `review_required_count`
- `blocked_count`
- `deduped_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Icon placement plan payload 本体写入 `backend/storage/icon_placement_plans/{taskId}.json`。它保存 `placements`、`dedupedIcons`、`blockedIcons`、`placementOverlay`、`warnings` 和统计 meta。overlay PNG 写入 `backend/storage/assets/{taskId}/debug/icon_placement_overlay.png`，并以 `asset_icon_placement_overlay` role 登记到 `assets` 表。M23 不把 placement plan、futureDslNodeHint 或 overlay 写入 DSL `assets` 数组，不改变 Figma 可见输出，不声明 icon 语义，也不创建可见 icon node。

## icon_visible_fallback_results

用途：记录 M24 visible icon fallback replay 文件、overlay 资产和可见回放摘要。

核心字段：

- `id`
- `task_id`
- `status`
- `fallback_path`
- `overlay_asset_id`
- `selected_count`
- `applied_count`
- `blocked_count`
- `skipped_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Icon visible fallback payload 本体写入 `backend/storage/icon_visible_fallbacks/{taskId}.json`。它保存 `visibleIcons`、`blockedPlacements`、`visibleFallbackOverlay`、`warnings` 和统计 meta。overlay PNG 写入 `backend/storage/assets/{taskId}/debug/icon_visible_fallback_overlay.png`，并以 `asset_icon_visible_fallback_overlay` role 登记到 `assets` 表。M24 默认关闭时不生成 result；开启后只把实际 applied 的 icon asset 追加进 DSL `assets`，并 append `icon_fallback_cover` / `visible_icon_fallback` 节点，不修改已有 assets 或已有 elements。

## icon_business_candidate_results

用途：记录 M25 region-guided business icon candidate 文件、overlay 资产和业务 icon 候选摘要。

核心字段：

- `id`
- `task_id`
- `status`
- `business_path`
- `overlay_asset_id`
- `business_icon_count`
- `cropped_business_icon_count`
- `blocked_count`
- `failed_crop_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Icon business candidate payload 本体写入 `backend/storage/icon_business_candidates/{taskId}.json`。它保存 `businessIcons`、`blockedCandidates`、`businessOverlay`、`warnings` 和统计 meta。business icon PNG 写入 `backend/storage/assets/{taskId}/icons_business/`，并以 `asset_icon_business_candidate` role 登记到 `assets` 表。overlay PNG 写入 `backend/storage/assets/{taskId}/debug/icon_business_overlay.png`，并以 `asset_icon_business_overlay` role 登记到 `assets` 表。M25 不把 business icon 或 overlay 写入 DSL `assets` 数组，不改变 Figma 可见输出，不声明 icon 语义。

## perception_benchmark_results

用途：记录 M26 visual perception provider benchmark 文件、provider overlay 资产和汇总指标。

核心字段：

- `id`
- `task_id`
- `status`
- `benchmark_path`
- `rules_overlay_asset_id`
- `opencv_overlay_asset_id`
- `sam2_overlay_asset_id`
- `uied_overlay_asset_id`
- `provider_count`
- `candidate_count`
- `blocked_count`
- `recommended_provider`
- `elapsed_ms`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Perception benchmark payload 本体写入 `backend/storage/perception_benchmarks/{taskId}.json`。它保存 `providers`、`comparison`、`warnings` 和统计 meta。overlay PNG 写入 `backend/storage/assets/{taskId}/debug/perception_overlay_*.png`，并以 `asset_perception_overlay_*` role 登记到 `assets` 表。M26 不把 provider candidates、blocked 或 overlay 写入 DSL，不追加 DSL meta，不改变 Figma 可见输出。

## model_call_logs

用途：记录 OCR/AI 调用摘要，不默认保存完整模型输入输出。M9 不创建该表；OpenAI provider 当前只把 primitive extraction 的结果摘要写入 `primitive_results`，失败细节写入 `error_logs`。

核心字段：

- `id`
- `task_id`
- `stage`
- `model`
- `status`
- `input_summary`
- `output_summary`
- `latency_ms`
- `created_at`

## Explicit Non-Models

v0.1 不建：

- users。
- organizations。
- teams。
- billing。
- quota。
- permissions。
- full history。
- quality score dashboard。

这些表会制造假的产品复杂度。
