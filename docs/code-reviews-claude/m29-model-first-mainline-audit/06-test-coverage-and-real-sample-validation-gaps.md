# 06 Test Coverage and Real-Sample Validation Gaps

## Fact: Mainline Test Coverage
The model-first pipeline has high coverage in focused unit tests:
* `test_perception_model_report.py`: Verifies report-only behavior of the model.
* `test_perception_source_compiler.py`: Verifies compilation of candidates into M29.2 objects.
* `test_m29_replay_plan.py`: Tests Visible overlap suppression, deduplication, budget constraints, and cleanup authorization rules.
* `test_m29_plan_materializer.py`: Tests plan item sorting, style overrides, and alpha/geometry erasures.
* `test_ownership_conservation.py`: Tests visible claims and conflicts.
* `test_auto_layout_permission_report.py`: Tests layout models.
* `test_upload_preview_pipeline.py`: Tests the default production profile and interactive pipeline orchestration.

## Fact: Legacy Test Execution Overhead
A large portion of the test suite (at least 11 files out of 46) targets legacyVisual discovery loops:
- `test_media_internal_decomposition.py`
- `test_transparent_asset_report.py`
- `test_m29_evidence_contract.py`
- `test_internal_source_promotion.py`
- `test_m29_bridge_fate_trace.py`
- `test_symbol_fragment_grouping.py`
- `test_text_aware_visual_object_refinement.py`
- `test_text_masked_media_audit.py`
- `test_text_visual_ownership_gate.py`
- `test_visual_evidence_normalization.py`
- `test_visual_object_candidate_audit.py`

### Inference
While these tests help verify that legacy compatibility APIs do not crash, they do not test the mainline product path. The mainline is covered by newer model-first tests.

## Inference: Validation Gaps
1. **Model path verification in integration tests**: Mainline integration tests mock out the actual model execution or use raw outputs, which is normal for unit tests. However, there is a gap in validating the model inference directly against real ONNX structures during developer validation.
2. **Aggressive suppression risk coverage**: There are no tests verifying that closely adjacent icon groups (e.g. icon-only grids or status indicators) are preserved without being suppressed by the aggressive 20% threshold.

## Recommendation
Add integration tests that explicitly check closely spaced element arrays to prevent regression on the 20% containment threshold.
