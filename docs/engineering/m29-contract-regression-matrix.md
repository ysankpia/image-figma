# M29 Contract Regression Matrix

本文档把 M29 数学合同转成回归验收矩阵。它不是第三份数学解释文档，而是测试和 review 的执行清单。

状态定义：

```text
covered: 已有 pytest 明确保护该合同。
weak: 有相邻测试，但没有直接钉住该合同。
missing: 当前没有有效测试；下一阶段必须补。
```

| Case ID | Contract Area | Source Truth | Expected Owner / Relation / Plan / Materialization | Must Not Happen | Current Coverage | Pytest Target |
| --- | --- | --- | --- | --- | --- | --- |
| M29-CR-001 | Owner Boundary | 高置信 OCR text 在稳定 UI 背景上 | `editable_text` + `text_replay` | 被保留在 raster 或 diagnostic | covered | `test_source_ui_physical_graph.py::test_high_confidence_ocr_text_becomes_editable_text_replay` |
| M29-CR-002 | Owner Boundary | OCR text 位于大 textured media 内部且像 display text | `preserve_raster` + `preserve_in_parent_raster` | 错误生成 editable text 并擦 fallback | covered | `test_source_ui_physical_graph.py::test_ocr_text_inside_large_textured_media_is_preserved_as_raster` |
| M29-CR-003 | Owner Boundary | 小型 media overlay label | `editable_text` + `text_replay` | 因 media containment 被一刀切 preserve | covered | `test_source_ui_physical_graph.py::test_small_media_overlay_label_remains_editable_text` |
| M29-CR-004 | Owner Boundary | 相邻 symbol fragments | 合并为一个 `raster_icon` + `icon_replay` | 输出多个碎片 visible nodes | covered | `test_source_ui_physical_graph.py::test_adjacent_symbol_fragments_merge_into_one_raster_icon` |
| M29-CR-005 | Owner Boundary | 低纹理低颜色数 UI shape | `shape_geometry` + `shape_replay` | 被当成 blur/diagnostic | covered | `test_source_ui_physical_graph.py::test_simple_shape_replays_but_complex_shape_is_diagnostic` |
| M29-CR-006 | Owner Boundary | 高颜色数/高纹理小 circle/ellipse foreground，raw geometry 可能像圆 | `raster_icon` 或 fallback/diagnostic | 仅凭 `geometry.kind=circle` 进入 `shape_geometry` | covered | `test_source_ui_physical_graph.py::test_geometry_circle_fit_does_not_override_complex_foreground_ownership` |
| M29-CR-007 | Owner Boundary | 低纹理 badge/background | `shape_geometry` + `shape_replay` | 因小尺寸被误当成 raster icon | covered | `test_source_ui_physical_graph.py::test_low_texture_badge_shape_still_replays_as_shape` |
| M29-CR-008 | Owner Boundary | blocked 小型复杂 foreground，无 OCR/media overlap | 恢复为 `raster_icon` + `icon_replay` | 永久丢到 diagnostic-only | covered | `test_source_ui_physical_graph.py::test_blocked_complex_small_foreground_recovers_as_raster_icon` |
| M29-CR-009 | Owner Boundary | blocked foreground 与 OCR overlap | `diagnostic_only` + `skip` | 恢复成 icon 并盖住/重复文字 | covered | `test_source_ui_physical_graph.py::test_blocked_complex_foreground_overlapping_ocr_stays_diagnostic` |
| M29-CR-010 | Owner Boundary | symbol 完整在 media 内部 | 不单独 replay | media 内部碎片变成独立 icon layer | covered | `test_source_ui_physical_graph.py::test_symbol_inside_media_is_not_separately_replayed` |
| M29-CR-011 | Finite Support | OCR text + 同线 foreground + 闭合低对比 support | raw M29 输出 `low_contrast_support` | 低对比 support 完全不可见 | covered | `test_visual_primitive_graph.py::test_low_contrast_support_region_is_detected_from_text_evidence` |
| M29-CR-012 | Finite Support | low-contrast support rect geometry | rect/unknown 不写 radius | bbox 半高被当成 radius truth | covered | `test_visual_primitive_graph.py::test_low_contrast_support_rect_geometry_does_not_emit_radius` |
| M29-CR-013 | Finite Support | 贴顶部 open band，无完整外环 | 不生成 replay-safe `low_contrast_support` | open band 被 replay 成闭合输入框 | covered | `test_visual_primitive_graph.py::test_low_contrast_support_rejects_top_edge_open_band` |
| M29-CR-014 | Finite Support | 深色主题低对比 support | 仍可由物理证据检测 | 只支持浅色主题 | covered | `test_visual_primitive_graph.py::test_low_contrast_support_region_is_detected_on_dark_theme` |
| M29-CR-015 | Finite Support | 纯背景文字，无同线 foreground evidence | 不强造 support | 文本附近凭空生成 support | covered | `test_visual_primitive_graph.py::test_low_contrast_support_region_is_not_for_plain_page_background` |
| M29-CR-016 | Finite Support | textured media/banner | 不被 low-contrast support detector 吞掉 | 大 media 被误当输入框 support | covered | `test_visual_primitive_graph.py::test_low_contrast_support_region_does_not_swallow_textured_media` |
| M29-CR-039 | Finite Support / Owner Boundary | OCR text `T` 被有限浅色 pill/background `S` 包住，且无侧边 icon/foreground | raw M29 输出 `shape subtype=text_support_background`，包含 `finite_outer_ring` 和 sampled fill | 因缺少同线 foreground evidence 丢掉标签背景 | covered | `test_visual_primitive_graph.py::test_text_support_background_region_is_detected_from_text_only_pill` |
| M29-CR-040 | Finite Support / Owner Boundary | 纯页面文字或纹理 media 上的文字 | 不创建 `text_support_background` | 凭文字内容、颜色或 padding 伪造 pill | covered | `test_visual_primitive_graph.py::test_text_support_background_region_is_not_for_plain_page_text`, `test_visual_primitive_graph.py::test_text_support_background_region_does_not_swallow_textured_media`, `test_visual_primitive_graph.py::test_text_support_background_region_rejects_accepted_media_overlap` |
| M29-CR-041 | Finite Support / Owner Boundary | support-like band 贴 canvas 边界，缺少完整 outer ring | 不创建 replay-safe text support background | open band 被当成闭合 pill/input support | covered | `test_visual_primitive_graph.py::test_text_support_background_rejects_edge_open_band` |
| M29-CR-017 | Region Relation | 两 bbox 近似同一证据 | `primarySetRelation=near_equal` | 下游重新定义 duplicate 判断 | covered | `test_region_relation_kernel.py::test_near_equal_for_almost_same_ocr_and_m29_bbox` |
| M29-CR-018 | Region Relation | 大框包含小框 | `contains` / `contained_by` 方向稳定 | cleanup 方向反了 | covered | `test_region_relation_kernel.py::test_left_contains_right_when_right_is_mostly_inside_left` |
| M29-CR-019 | Region Relation | 相邻 row item | `disjoint + near + left_of + aligned_center_y` | 被误判成 containment 或 random near | covered | `test_region_relation_kernel.py::test_close_row_text_and_icon_have_near_left_and_center_alignment` |
| M29-CR-020 | Region Relation | 细 separator | near threshold thin-aware 且 capped | 细线 near 阈值塌缩或长条无限吸附 | covered | `test_region_relation_kernel.py::test_thin_separator_six_pixels_away_is_still_near` |
| M29-CR-021 | Relation Graph | M29.3.1 只输出 pairwise report | `createdVisibleNodeCount=0` | relation graph 创建 DSL/assets | covered | `test_region_relation_graph_report.py::test_m2931_empty_and_single_graphs_are_report_only` |
| M29-CR-022 | Weak Cluster | containment relation cluster | `background_anchor_like` weak evidence | 被提升成 component/materialization | covered | `test_stable_design_cluster.py::test_m294_containment_chain_becomes_stable_background_anchor_cluster` |
| M29-CR-023 | Weak Cluster | row/column geometry | `row_like` / `column_like` | 创建 group、Auto Layout 或组件 | covered | `test_stable_design_cluster.py::test_m294_row_and_column_clusters_keep_directionality` |
| M29-CR-024 | Weak Cluster | repeated size local subgraph | `repeated_item_like` report-only | 自动生成 repeated component | covered | `test_stable_design_cluster.py::test_m294_repeated_local_subgraph_scores_repeatability` |
| M29-CR-025 | Weak Cluster | media/text pair near or overlaps | 当前产出不是 `media_text_group_like`，且 report-only | 任何下游依赖 `media_text_group_like` 当已实现组件 | covered | `test_stable_design_cluster.py::test_m294_media_text_pair_remains_background_anchor_not_media_text_component` |
| M29-CR-026 | Replay Plan | M29.2 replay decisions | 映射到 M29.5 final actions | diagnostic/low confidence 被可见 replay | covered | `test_m29_replay_plan.py::test_m295_maps_m292_replay_decisions_to_plan_actions` |
| M29-CR-027 | Replay Plan | shape/image/icon/text 同时可见 | plan sort 为 `shape -> image -> icon -> text` | image 盖住 text | covered | `test_m29_replay_plan.py::test_m295_plan_items_are_sorted_for_replay_layer_order` |
| M29-CR-028 | Replay Plan | preserve raster text | 无 target role，无 cleanup targets | preserve text 被擦 fallback | covered | `test_m29_replay_plan.py::test_m295_preserve_raster_text_has_no_cleanup_targets` |
| M29-CR-029 | Replay Plan | editable text contained by media | fallback cleanup + copied image asset cleanup target | 无授权擦 copied asset 或漏擦 | covered | `test_m29_replay_plan.py::test_m295_editable_text_inside_media_declares_fallback_and_asset_cleanup` |
| M29-CR-030 | Replay Plan | near_equal duplicate source objects | suppress lower-priority duplicate | 同一像素画两遍 | covered | `test_m29_replay_plan.py::test_m295_near_equal_duplicate_keeps_one_replay_owner` |
| M29-CR-031 | Replay Plan | M29.4 cluster support enters plan | 只记录 `clusterIds`，不改 target role | cluster role hint 变成语义组件 | covered | `test_m29_replay_plan.py::test_m295_records_cluster_support_without_semantic_role_promotion` |
| M29-CR-032 | Replay Plan | node budget 超限 | over-budget visible item -> `suppress_duplicate` | flat layer 爆炸 | covered | `test_m29_replay_plan.py::test_m295_node_budget_suppresses_low_priority_visible_items` |
| M29-CR-033 | Plan-Driven Materialization | M29.5 plan items | 只 materialize accepted visible actions | suppressed/preserve/diagnostic 仍可见 | covered | `test_m29_plan_materializer.py::test_m29_plan_items_are_the_only_visible_materialization_order` |
| M29-CR-034 | Plan-Driven Materialization | plan cleanup targets | copied image asset cleanup 仅由 plan 授权 | 关系不明也擦 copied image asset | covered | `test_m29_plan_materializer.py::test_copied_media_cleanup_requires_m295_cleanup_target` |
| M29-CR-035 | Plan-Driven Materialization | plan 无 copied image cleanup target | copied image asset 不擦 | fallback cleanup 权限扩散到 copied asset | covered | `test_m29_plan_materializer.py::test_copied_media_cleanup_requires_m295_cleanup_target` |
| M29-CR-036 | Plan-Driven Materialization | raw geometry radius | 只有 geometry fit radius 可写 DSL radius | bbox-derived radius 被当 style truth | covered | `test_m29_plan_materializer.py::test_shape_replay_uses_only_source_geometry_fit_radius`, `test_m29_plan_materializer.py::test_shape_replay_does_not_invent_radius_without_geometry_fit` |
| M29-CR-037 | Plan-Driven Materialization | preserve raster text | 不创建 visible node，不擦 fallback | 不可编辑 text 被擦掉 | covered | `test_m29_replay_plan.py::test_m295_preserve_raster_text_has_no_cleanup_targets`, `test_m29_plan_materializer.py::test_fallback_erasure_requires_m295_fallback_cleanup_target` |
| M29-CR-038 | Upload Pipeline | M29.3.1/M29.4/M29.5/materializer stages | `/dsl` 来自 M29 plan-driven materializer | branch experiment 或 legacy M30 污染主线 `/dsl` | covered | `test_m30_upload_pipeline.py::test_upload_m30_preview_completes_and_serves_m29_plan_driven_dsl`, `test_m30_upload_pipeline.py::test_upload_m30_preview_uses_production_artifact_profile_by_default` |
| M29-CR-042 | Owner Boundary | raw `text_support_background` source node | M29.2 source object 为 `visualKind=control_background`、`pixelOwner=shape_geometry`、`replayDecision=shape_replay` | support shape 因 text overlap 被降成 text noise，或不经 finite support 证据直接 replay | covered | `test_source_ui_physical_graph.py::test_text_support_background_shape_replays_as_control_background` |
| M29-CR-043 | Plan-Driven Materialization | source-proven support shape 与 text member 重叠 | M29.5 排序为 shape below text；materializer 只消费 plan | 全局放宽 ordinary shape/text overlap 或从 text bbox 伪造背景 | covered | `test_source_ui_physical_graph.py::test_text_support_background_shape_replays_as_control_background`, `test_m29_replay_plan.py::test_m295_plan_items_are_sorted_for_replay_layer_order`, `test_m29_plan_materializer.py::test_m29_plan_items_are_the_only_visible_materialization_order` |
| M29-CR-044 | Owner Boundary / Raster Preservation | 大面积复杂 image-like low-confidence raw M29 unknown | M29.2 升级为 `media_region` + `preserve_raster` + `image_replay` | fallback-off 时复杂图表/照片/卡片区域消失或被白底替代 | covered | `test_source_ui_physical_graph.py::test_large_image_like_unknown_becomes_preserved_media_region`, `test_m30_upload_pipeline.py::test_upload_m30_preview_samples_dark_source_background` |
| M29-CR-045 | Plan-Driven Materialization / Background | 深色、浅色或混合源图 | root/page background 来自 source PNG 样本 | fallback-off 暴露固定 `#F7F8FA` 白底 | covered | `test_m29_plan_materializer.py::test_m29_plan_materializer_samples_source_background_instead_of_fixed_white`, `test_m30_upload_pipeline.py::test_upload_m30_preview_samples_dark_source_background` |

## Review Rule

任何后续 M29 改动都必须先回答：

```text
改动影响哪些 Case ID？
现有 pytest 是否覆盖？
如果没有覆盖，是否先补 test？
是否仍保持 M29.4 report-only、M29.5 plan-only、materializer 只消费 plan？
```

如果答案不清楚，不要直接改阈值或 materialization 逻辑。
