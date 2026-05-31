#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$ROOT/services/backend-go"
IMG_DIR="$ROOT/docs/reference/codia-samples/images"
WORK="${UNIFIED_VISION_SMOKE_WORKDIR:-/tmp/unified_vision_smoke_4img}"

if [[ "${IMAGE_FIGMA_LOAD_LOCAL_ENV:-true}" != "false" && -f "$ROOT/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env.local"
  set +a
fi

rm -rf "$WORK"
mkdir -p "$WORK"

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
  mkdir -p "$out"
  (
    cd "$BACKEND"
    go run ./cmd/layoutcompile -input "$IMG_DIR/$image" -out "$out" -unified-vision >/dev/null
  )
python3 - "$out" "$key" <<'PY'
import json
import pathlib
import re
import sys

out = pathlib.Path(sys.argv[1])
key = sys.argv[2]
required = [
    "ui_layout_ir.v1.json",
    "ui_layout_ir.unified_experiment.v1.json",
    "html_preview_report.md",
    "html_preview_report.unified.md",
    "unified_vision/unified_vision_input.v1.json",
    "unified_vision/unified_vision_result.v1.json",
    "unified_vision/unified_vision_validation.v1.json",
]
missing = [name for name in required if not (out / name).exists()]
if missing:
    raise SystemExit(f"{key}: missing artifacts {missing}")

def metric(report, label, default="n/a"):
    text = report.read_text()
    match = re.search(rf"- {re.escape(label)}: `([^`]+)`", text)
    return match.group(1) if match else default

baseline_report = out / "html_preview_report.md"
unified_report = out / "html_preview_report.unified.md"
validation = json.loads((out / "unified_vision/unified_vision_validation.v1.json").read_text())
summary = validation.get("summary") or {}
result = json.loads((out / "unified_vision/unified_vision_result.v1.json").read_text())
batches = result.get("batches") or []
repair_attempts = sum(1 for b in batches if b.get("repairAttempt"))
provider_errors = sum(1 for b in batches if b.get("error") and b.get("attempt", 0) > 0)

ocr_mismatch = summary.get("ocrMismatchCount", 0)
bbox_drift = summary.get("bboxDriftCount", 0)
duplicate = summary.get("duplicateOwnershipCount", 0)
zero_flow = metric(unified_report, "zero-flow row count", "n/a")
if ocr_mismatch != 0 or bbox_drift != 0 or duplicate != 0:
    raise SystemExit(f"{key}: hard invariant failed ocr={ocr_mismatch} bbox={bbox_drift} duplicate={duplicate}")
if zero_flow != "0":
    raise SystemExit(f"{key}: zero-flow rows = {zero_flow}")

print(
    "| {key} | {b_cov} | {u_cov} | {b_fallback} | {u_fallback} | {b_high_gap} | {u_high_gap} | {accepted} | {rejected} | {fallback_batches} | {provider_errors} | {repair_attempts} | {ocr} | {bbox} | {dup} | {zero_flow} |".format(
        key=key,
        b_cov=metric(baseline_report, "auto layout coverage"),
        u_cov=metric(unified_report, "auto layout coverage"),
        b_fallback=metric(baseline_report, "absolute fallback ratio"),
        u_fallback=metric(unified_report, "absolute fallback ratio"),
        b_high_gap=metric(baseline_report, "high-gap row count"),
        u_high_gap=metric(unified_report, "high-gap row count"),
        accepted=summary.get("acceptedGroupCount", 0),
        rejected=summary.get("rejectedGroupCount", 0),
        fallback_batches=summary.get("fallbackBatchCount", 0),
        provider_errors=provider_errors,
        repair_attempts=repair_attempts,
        ocr=ocr_mismatch,
        bbox=bbox_drift,
        dup=duplicate,
        zero_flow=zero_flow,
    )
)

baseline_cov = float(metric(baseline_report, "auto layout coverage", "0"))
unified_cov = float(metric(unified_report, "auto layout coverage", "0"))
baseline_high_gap = int(metric(baseline_report, "high-gap row count", "0"))
unified_high_gap = int(metric(unified_report, "high-gap row count", "0"))
improved = unified_cov > baseline_cov or unified_high_gap < baseline_high_gap
(out / "unified_vision_smoke_case_status.json").write_text(json.dumps({
    "case": key,
    "improved": improved,
    "baselineCoverage": baseline_cov,
    "unifiedCoverage": unified_cov,
    "baselineHighGap": baseline_high_gap,
    "unifiedHighGap": unified_high_gap,
}, ensure_ascii=False, indent=2))
PY
}

provider_env

{
  echo "# Unified Vision Smoke 4img"
  echo
  echo "- workdir: \`$WORK\`"
  echo "- model: \`${UNIFIED_VISION_MODEL:-}\`"
  echo "- provider host: \`${UNIFIED_VISION_BASE_URL:-}\`"
  echo
  echo "| case | baseline coverage | unified coverage | baseline fallback | unified fallback | baseline high-gap | unified high-gap | accepted groups | rejected groups | fallback batches | provider call errors | repair attempts | OCR mismatch | bbox drift | duplicate ownership | zero-flow rows |"
  echo "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
  run_one t018 "腾讯动漫_018_1440.png"
  run_one t022 "腾讯动漫_022_1440.png"
  run_one lizhi "荔枝_011_1440.png"
  run_one xianyu "闲鱼.png"
} | tee "$WORK/unified_vision_smoke_4img_report.md"

python3 - "$WORK" <<'PY'
import json
import pathlib
import sys

work = pathlib.Path(sys.argv[1])
statuses = []
for path in sorted(work.glob("*/unified_vision_smoke_case_status.json")):
    statuses.append(json.loads(path.read_text()))
failed = [s for s in statuses if not s.get("improved")]
summary_path = work / "unified_vision_smoke_4img_quality.json"
summary_path.write_text(json.dumps({
    "version": "unified_vision_smoke_quality.v1",
    "caseCount": len(statuses),
    "improvedCount": len(statuses) - len(failed),
    "failedCases": failed,
    "pass": len(statuses) > 0 and not failed,
}, ensure_ascii=False, indent=2))
if failed:
    print(f"\nQUALITY GATE FAILED: {len(failed)}/{len(statuses)} cases did not improve. See {summary_path}")
    raise SystemExit(1)
print(f"\nQUALITY GATE PASSED: all cases improved. See {summary_path}")
PY
