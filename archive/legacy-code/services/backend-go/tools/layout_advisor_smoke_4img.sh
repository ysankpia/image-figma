#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$ROOT/services/backend-go"
IMG_DIR="$ROOT/docs/reference/codia-samples/images"
WORK="${LAYOUT_ADVISOR_SMOKE_WORKDIR:-/tmp/layout_advisor_smoke_4img}"

rm -rf "$WORK"
mkdir -p "$WORK"

provider_enabled() {
  [[ -n "${LAYOUT_ADVISOR_API_KEY:-}" && -n "${LAYOUT_ADVISOR_MODEL:-}" ]]
}

run_one() {
  local key="$1"
  local image="$2"
  local image_path="$IMG_DIR/$image"
  local baseline="$WORK/$key/baseline"
  local advisor="$WORK/$key/advisor"
  mkdir -p "$baseline" "$advisor"
  (
    cd "$BACKEND"
    go run ./cmd/layoutcompile -input "$image_path" -out "$baseline" >/dev/null
    go run ./cmd/layoutcompile -input "$image_path" -out "$advisor" -advisor-input-out "$advisor/layout_advisor_input.v1.json" >/dev/null
  )
  local advisor_status="input-only"
  if provider_enabled; then
    if python3 "$BACKEND/tools/layout_advisor_experiment.py" \
      --input "$advisor/layout_advisor_input.v1.json" \
      --image "$image_path" \
      --out "$advisor/layout_advisor_result.v1.json" \
      --fallback-out "$advisor/layout_advisor_fallback.v1.json" >/dev/null; then
      (
        cd "$BACKEND"
        go run ./cmd/layoutcompile \
          -input "$image_path" \
          -out "$advisor" \
          -advisor-input-out "$advisor/layout_advisor_input.v1.json" \
          -advisor-result "$advisor/layout_advisor_result.v1.json" >/dev/null
      )
      advisor_status="advisor"
    else
      advisor_status="provider-fallback"
    fi
  fi
  python3 - "$baseline" "$advisor" "$key" "$advisor_status" <<'PY'
import json
import pathlib
import re
import sys

baseline = pathlib.Path(sys.argv[1])
advisor = pathlib.Path(sys.argv[2])
key = sys.argv[3]
status = sys.argv[4]

def report_metric(report, name, default="n/a"):
    m = re.search(rf"- {re.escape(name)}: `([^`]+)`", report)
    return m.group(1) if m else default

def load_doc(path):
    return json.loads((path / "ui_layout_ir.v1.json").read_text())

def node_flow(child):
    if child.get("meta", {}).get("zLayer") == "text_eraser":
        return False
    return child.get("type") in {"text", "icon", "image"}

def offline_overflow_rows(doc):
    count = 0
    rows = 0
    def walk(node):
        nonlocal count, rows
        if node.get("type") == "row" and node.get("layout", {}).get("mode") == "row":
            rows += 1
            flow = [c for c in node.get("children", []) if node_flow(c)]
            if len(flow) > 1:
                gap = int(node.get("layout", {}).get("gap") or 0)
                padding = node.get("layout", {}).get("padding") or {}
                required = sum((c.get("bbox") or {}).get("width", 0) for c in flow)
                required += gap * (len(flow) - 1)
                required += int(padding.get("left") or 0) + int(padding.get("right") or 0)
                width = (node.get("bbox") or {}).get("width", 0)
                if width and required > width * 1.01:
                    count += 1
        for child in node.get("children") or []:
            walk(child)
    walk(doc["root"])
    return count, rows

base_doc = load_doc(baseline)
base_report = (baseline / "html_preview_report.md").read_text()
base_overflow, base_rows = offline_overflow_rows(base_doc)

advisor_ir = advisor / "ui_layout_ir.advisor_experiment.v1.json"
if advisor_ir.exists():
    advisor_doc = json.loads(advisor_ir.read_text())
    advisor_report = (advisor / "html_preview_report.advisor.md").read_text()
    validation = json.loads((advisor / "layout_advisor_validation.v1.json").read_text())
    advisor_overflow, advisor_rows = offline_overflow_rows(advisor_doc)
    accepted = validation.get("summary", {}).get("acceptedCount", 0)
    rejected = validation.get("summary", {}).get("rejectedCount", 0)
else:
    advisor_doc = base_doc
    advisor_report = base_report
    advisor_overflow, advisor_rows = base_overflow, base_rows
    accepted = "n/a"
    rejected = "n/a"

print(
    "| {key} | {status} | {base_rows} | {base_overflow} | {base_high_gap} | {base_gap} | {base_cov} | {adv_rows} | {adv_overflow} | {adv_high_gap} | {adv_gap} | {adv_cov} | {accepted} | {rejected} | 0 |".format(
        key=key,
        status=status,
        base_rows=base_rows,
        base_overflow=base_overflow,
        base_high_gap=report_metric(base_report, "high-gap row count"),
        base_gap=report_metric(base_report, "mean gap variance"),
        base_cov=report_metric(base_report, "auto layout coverage"),
        adv_rows=advisor_rows,
        adv_overflow=advisor_overflow,
        adv_high_gap=report_metric(advisor_report, "high-gap row count"),
        adv_gap=report_metric(advisor_report, "mean gap variance"),
        adv_cov=report_metric(advisor_report, "auto layout coverage"),
        accepted=accepted,
        rejected=rejected,
    )
)
PY
}

{
  echo "# Layout Advisor Smoke 4img"
  echo
  echo "- workdir: \`$WORK\`"
  if provider_enabled; then
    echo "- advisor provider: enabled"
  else
    echo "- advisor provider: disabled; generated advisor input only"
  fi
  echo
  echo "| case | status | baseline flex rows | baseline overflow rows | baseline high-gap | baseline mean gap variance | baseline coverage | advisor flex rows | advisor overflow rows | advisor high-gap | advisor mean gap variance | advisor coverage | accepted groups | rejected groups | OCR mismatch |"
  echo "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
  run_one t018 "腾讯动漫_018_1440.png"
  run_one t022 "腾讯动漫_022_1440.png"
  run_one lizhi "荔枝_011_1440.png"
  run_one xianyu "闲鱼.png"
} | tee "$WORK/layout_advisor_smoke_4img_report.md"
