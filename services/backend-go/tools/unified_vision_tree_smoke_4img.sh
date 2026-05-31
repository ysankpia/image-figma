#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$ROOT/services/backend-go"
IMG_DIR="$ROOT/docs/reference/codia-samples/images"
WORK="${UNIFIED_VISION_TREE_SMOKE_WORKDIR:-/tmp/unified_vision_tree_smoke_4img}"

if [[ "${IMAGE_FIGMA_LOAD_LOCAL_ENV:-true}" != "false" && -f "$ROOT/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env.local"
  set +a
fi

provider_env() {
  export UNIFIED_VISION_BASE_URL="${UNIFIED_VISION_BASE_URL:-}"
  export UNIFIED_VISION_WIRE_API="${UNIFIED_VISION_WIRE_API:-}"
  if [[ -z "${UNIFIED_VISION_API_KEY:-}" && -n "${LAYOUT_ADVISOR_API_KEY:-}" ]]; then
    export UNIFIED_VISION_API_KEY="$LAYOUT_ADVISOR_API_KEY"
  fi
  if [[ -z "${UNIFIED_VISION_MODEL:-}" && -n "${LAYOUT_ADVISOR_MODEL:-}" ]]; then
    export UNIFIED_VISION_MODEL="$LAYOUT_ADVISOR_MODEL"
  fi
  if [[ "${UNIFIED_VISION_BASE_URL:-}" == "" && -n "${LAYOUT_ADVISOR_BASE_URL:-}" ]]; then
    export UNIFIED_VISION_BASE_URL="$LAYOUT_ADVISOR_BASE_URL"
  fi
  if [[ "${UNIFIED_VISION_WIRE_API:-}" == "" && -n "${LAYOUT_ADVISOR_WIRE_API:-}" ]]; then
    export UNIFIED_VISION_WIRE_API="$LAYOUT_ADVISOR_WIRE_API"
  fi
  if [[ -z "${UNIFIED_VISION_API_KEY:-}" && -n "${CODIA_UI_DETECTOR_API_KEY:-}" ]]; then
    export UNIFIED_VISION_API_KEY="$CODIA_UI_DETECTOR_API_KEY"
  fi
  if [[ -z "${UNIFIED_VISION_MODEL:-}" && -n "${CODIA_UI_DETECTOR_MODEL:-}" ]]; then
    export UNIFIED_VISION_MODEL="$CODIA_UI_DETECTOR_MODEL"
  fi
  if [[ "${UNIFIED_VISION_BASE_URL:-}" == "" && -n "${CODIA_UI_DETECTOR_BASE_URL:-}" ]]; then
    export UNIFIED_VISION_BASE_URL="$CODIA_UI_DETECTOR_BASE_URL"
  fi
  if [[ "${UNIFIED_VISION_WIRE_API:-}" == "" && -n "${CODIA_UI_DETECTOR_WIRE_API:-}" ]]; then
    export UNIFIED_VISION_WIRE_API="$CODIA_UI_DETECTOR_WIRE_API"
  fi
}

run_one() {
  local key="$1"
  local image="$2"
  local out="$WORK/$key"
  local image_path="$IMG_DIR/$image"
  mkdir -p "$out"
  if [[ "${UNIFIED_VISION_TREE_FAST_INPUT:-false}" == "true" ]]; then
    (
      cd "$BACKEND"
      env UNIFIED_VISION_API_KEY= UNIFIED_VISION_MODEL= \
        go run ./cmd/layoutcompile -input "$image_path" -out "$out" -unified-vision \
          -unified-vision-api-key "" -unified-vision-model "" >/dev/null
    )
  else
    (
      cd "$BACKEND"
      go run ./cmd/layoutcompile -input "$image_path" -out "$out" -unified-vision >/dev/null
    )
  fi
  python3 "$BACKEND/tools/unified_vision_tree_experiment.py" \
    --input "$out/unified_vision/unified_vision_input.v1.json" \
    --image "$image_path" \
    --result-out "$out/unified_vision/unified_vision_tree_result.v1.json" \
    --validation-out "$out/unified_vision/unified_vision_tree_validation.v1.json" \
    --workdir "$out/unified_vision/tree_raw" >/dev/null

  python3 - "$out" "$key" <<'PY'
import json
import pathlib
import re
import sys

out = pathlib.Path(sys.argv[1])
key = sys.argv[2]

def metric(report, label, default="0"):
    text = report.read_text()
    match = re.search(rf"- {re.escape(label)}: `([^`]+)`", text)
    return match.group(1) if match else default

baseline_report = out / "html_preview_report.md"
flat_report = out / "html_preview_report.unified.md"
flat_validation = json.loads((out / "unified_vision/unified_vision_validation.v1.json").read_text())
tree_validation = json.loads((out / "unified_vision/unified_vision_tree_validation.v1.json").read_text())
flat_summary = flat_validation.get("summary") or {}
tree_summary = tree_validation.get("summary") or {}
fast_input = flat_summary.get("fallbackBatchCount", 0) > 0 and flat_summary.get("acceptedGroupCount", 0) == 0

hard_failures = {
    "ocrMismatch": tree_summary.get("ocrMismatchCount", 0),
    "bboxDrift": tree_summary.get("bboxDriftCount", 0),
    "duplicateLeafOwnership": tree_summary.get("duplicateLeafOwnershipCount", 0),
    "cycle": tree_summary.get("cycleCount", 0),
}
hard_pass = all(value == 0 for value in hard_failures.values())
tree_physical = tree_summary.get("physicalRejectedNodeCount", 0)
flat_physical = flat_summary.get("rejectedGroupCount", 0)
tree_coverage = float(tree_summary.get("coverage", 0))
flat_coverage = float(flat_summary.get("coverage", 0))
tree_better_or_equal = hard_pass and (fast_input or (tree_physical <= flat_physical and tree_coverage >= flat_coverage))

status = {
    "case": key,
    "hardPass": hard_pass,
    "hardFailures": hard_failures,
    "baselineCoverage": float(metric(baseline_report, "auto layout coverage", "0")),
    "flatCoverage": flat_coverage,
    "fastInput": fast_input,
    "treeCoverage": tree_coverage,
    "flatRejected": flat_summary.get("rejectedGroupCount", 0),
    "treeRejected": tree_summary.get("rejectedNodeCount", 0),
    "flatPhysicalRejected": flat_physical,
    "treePhysicalRejected": tree_physical,
    "flatAccepted": flat_summary.get("acceptedGroupCount", 0),
    "treeAccepted": tree_summary.get("acceptedNodeCount", 0),
    "treeFallback": tree_summary.get("fallbackBatchCount", 0),
    "treeProviderErrors": tree_summary.get("providerErrorCount", 0),
    "treeRepairAttempts": tree_summary.get("repairAttemptCount", 0),
    "treeOverflow": tree_summary.get("overflowNodeCount", 0),
    "treeHighGap": tree_summary.get("highGapNodeCount", 0),
    "treeOneChild": tree_summary.get("oneChildGroupCount", 0),
    "treeZeroChild": tree_summary.get("zeroChildGroupCount", 0),
    "treeBetterOrEqual": tree_better_or_equal,
}
(out / "unified_vision_tree_smoke_case_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2))

print(
    "| {case} | {b_cov:.4f} | {f_cov:.4f} | {t_cov:.4f} | {f_acc} | {t_acc} | {f_rej} | {t_rej} | {t_phys} | {t_over} | {t_gap} | {t_fb} | {t_rep} | {hard} |".format(
        case=key,
        b_cov=status["baselineCoverage"],
        f_cov=status["flatCoverage"],
        t_cov=status["treeCoverage"],
        f_acc=status["flatAccepted"],
        t_acc=status["treeAccepted"],
        f_rej=status["flatRejected"],
        t_rej=status["treeRejected"],
        t_phys=status["treePhysicalRejected"],
        t_over=status["treeOverflow"],
        t_gap=status["treeHighGap"],
        t_fb=status["treeFallback"],
        t_rep=status["treeRepairAttempts"],
        hard="pass" if hard_pass else "fail",
    )
)
PY
}

provider_env
rm -rf "$WORK"
mkdir -p "$WORK"

{
  echo "# Unified Vision Tree Smoke 4img"
  echo
  echo "- workdir: \`$WORK\`"
  echo "- model: \`${UNIFIED_VISION_MODEL:-}\`"
  echo "- provider host: \`${UNIFIED_VISION_BASE_URL:-}\`"
  echo
  echo "| case | baseline coverage | flat coverage | tree coverage | flat accepted | tree accepted | flat rejected | tree rejected | tree physical rejected | tree overflow | tree high-gap | tree fallback | tree repair | hard invariants |"
  echo "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
  run_one t018 "腾讯动漫_018_1440.png"
  run_one t022 "腾讯动漫_022_1440.png"
  run_one lizhi "荔枝_011_1440.png"
  run_one xianyu "闲鱼.png"
} | tee "$WORK/unified_vision_tree_smoke_4img_report.md"

python3 - "$WORK" <<'PY'
import json
import pathlib
import sys

work = pathlib.Path(sys.argv[1])
statuses = [json.loads(path.read_text()) for path in sorted(work.glob("*/unified_vision_tree_smoke_case_status.json"))]
failed_hard = [status for status in statuses if not status.get("hardPass")]
failed_quality = [status for status in statuses if not status.get("treeBetterOrEqual")]
summary = {
    "version": "unified_vision_tree_smoke_quality.v1",
    "caseCount": len(statuses),
    "hardPass": not failed_hard and len(statuses) > 0,
    "qualityPass": not failed_quality and len(statuses) > 0,
    "failedHardCases": failed_hard,
    "failedQualityCases": failed_quality,
}
(work / "unified_vision_tree_smoke_4img_quality.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
if failed_hard:
    print(f"\nHARD GATE FAILED: {len(failed_hard)}/{len(statuses)} cases. See {work / 'unified_vision_tree_smoke_4img_quality.json'}")
    raise SystemExit(1)
if failed_quality:
    print(f"\nQUALITY GATE FAILED: {len(failed_quality)}/{len(statuses)} cases. See {work / 'unified_vision_tree_smoke_4img_quality.json'}")
    raise SystemExit(1)
print(f"\nQUALITY GATE PASSED. See {work / 'unified_vision_tree_smoke_4img_quality.json'}")
PY
