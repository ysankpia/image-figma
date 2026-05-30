#!/usr/bin/env bash
# Role-aware Codia compiler smoke gate for the four Codia golden samples.
#
# This validates the Go Codia-like compiler closure:
#   PNG + OCR + optional detector candidates
#   -> M29 evidence -> tokens -> raw leaves -> assembly -> controls -> tree
#   -> Figma-like tree -> Codia-like canvas JSON -> codiaanalyze read-back
#
# Golden Codia IR is used only for structural diff, never for generation.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$ROOT/services/backend-go"
WORK="${CODIA_SMOKE_4IMG_WORK:-/tmp/codia_smoke_4img}"

OCR_T018="${CODIA_OCR_T018:-/tmp/eval_4img/t018/ocr.json}"
OCR_T022="${CODIA_OCR_T022:-/tmp/eval_4img/t022/ocr.json}"
OCR_LIZHI="${CODIA_OCR_LIZHI:-/tmp/eval_4img/lizhi/ocr.json}"
OCR_XIANYU="${CODIA_OCR_XIANYU:-/tmp/eval_4img/xianyu/ocr.json}"

DETECTOR_T018="${CODIA_DETECTOR_T018:-}"
DETECTOR_T022="${CODIA_DETECTOR_T022:-}"
DETECTOR_LIZHI="${CODIA_DETECTOR_LIZHI:-}"
DETECTOR_XIANYU="${CODIA_DETECTOR_XIANYU:-}"

rm -rf "$WORK"
mkdir -p "$WORK"

require_file() {
  local path="$1" label="$2"
  if [[ ! -f "$path" ]]; then
    echo "missing $label: $path" >&2
    echo "run services/backend-go/tools/eval_4img.sh to refresh OCR artifacts, or set the matching CODIA_OCR_* variable" >&2
    exit 2
  fi
}

optional_detector_args() {
  local path="$1" label="$2"
  if [[ -z "$path" ]]; then
    return 0
  fi
  if [[ ! -f "$path" ]]; then
    echo "missing optional detector candidates for $label: $path" >&2
    exit 2
  fi
  printf '%s\n' "-detector-candidates"
  printf '%s\n' "$path"
}

run_analyze() {
  local key="$1" json="$2" expect="${3:-}"
  local out="$WORK/golden-$key"
  mkdir -p "$out"
  if [[ -n "$expect" ]]; then
    (cd "$BACKEND" && go run ./cmd/codiaanalyze -input "$json" -out "$out" -expect "$expect" >/dev/null)
  else
    (cd "$BACKEND" && go run ./cmd/codiaanalyze -input "$json" -out "$out" >/dev/null)
  fi
}

run_compile() {
  local key="$1" image="$2" ocr="$3" detector_path="$4"
  local out="$WORK/compile-$key"
  mkdir -p "$out"
  local detector_args=()
  while IFS= read -r item; do
    detector_args+=("$item")
  done < <(optional_detector_args "$detector_path" "$key")
  if ((${#detector_args[@]} > 0)); then
    (cd "$BACKEND" && go run ./cmd/codiacompile \
      -input "$image" \
      -ocr "$ocr" \
      "${detector_args[@]}" \
      -golden "$WORK/golden-$key/codia_ir.v1.json" \
      -out "$out" >/dev/null)
  else
    (cd "$BACKEND" && go run ./cmd/codiacompile \
      -input "$image" \
      -ocr "$ocr" \
      -golden "$WORK/golden-$key/codia_ir.v1.json" \
      -out "$out" >/dev/null)
  fi
}

run_canvas_readback() {
  local key="$1"
  local out="$WORK/canvas-$key"
  mkdir -p "$out"
  (cd "$BACKEND" && go run ./cmd/codiaanalyze \
    -input "$WORK/compile-$key/codia_canvas_like.v1.canvas.json" \
    -out "$out" >/dev/null)
}

require_file "$OCR_T018" "Tencent 018 OCR"
require_file "$OCR_T022" "Tencent 022 OCR"
require_file "$OCR_LIZHI" "Lizhi OCR"
require_file "$OCR_XIANYU" "Xianyu OCR"

run_analyze t018 "$ROOT/docs/reference/codia-samples/tencent-comic-018.canvas.json" tencent-comic-018
run_analyze t022 "$ROOT/docs/reference/codia-samples/tencent-comic-022.canvas.json"
run_analyze lizhi "$ROOT/docs/reference/codia-samples/lizhi-011.canvas.json"
run_analyze xianyu "$ROOT/docs/reference/codia-samples/xianyu.canvas.json"

run_compile t018 "$ROOT/docs/reference/codia-samples/images/腾讯动漫_018_1440.png" "$OCR_T018" "$DETECTOR_T018"
run_compile t022 "$ROOT/docs/reference/codia-samples/images/腾讯动漫_022_1440.png" "$OCR_T022" "$DETECTOR_T022"
run_compile lizhi "$ROOT/docs/reference/codia-samples/images/荔枝_011_1440.png" "$OCR_LIZHI" "$DETECTOR_LIZHI"
run_compile xianyu "$ROOT/docs/reference/codia-samples/images/闲鱼.png" "$OCR_XIANYU" "$DETECTOR_XIANYU"

run_canvas_readback t018
run_canvas_readback t022
run_canvas_readback lizhi
run_canvas_readback xianyu

python3 - "$WORK" <<'PY'
import json
import pathlib
import sys

work = pathlib.Path(sys.argv[1])

# These gates lock the current deterministic four-image no-detector closure.
# Detector-enhanced runs may improve these numbers, but must not fall below the
# same structural floor unless the plan document is deliberately updated.
expected = {
    "t018": {"matched_min": 95, "extra_max": 54, "missed_max": 51},
    "t022": {"matched_min": 92, "extra_max": 14, "missed_max": 28},
    "lizhi": {"matched_min": 61, "extra_max": 28, "missed_max": 32},
    "xianyu": {"matched_min": 64, "extra_max": 52, "missed_max": 68},
}

failed = False
print("sample generated golden matched extra missed edgeP edgeR canvasNodes rootChildren topAction")
for key in ("t018", "t022", "lizhi", "xianyu"):
    diff_path = work / f"compile-{key}" / "diff" / "codia_structure_diff.v1.json"
    audit_path = work / f"compile-{key}" / "audit" / "codia_failure_audit.v1.json"
    readback_path = work / f"canvas-{key}" / "codia_canvas_analysis.v1.json"
    diff = json.loads(diff_path.read_text())
    audit = json.loads(audit_path.read_text())
    readback = json.loads(readback_path.read_text())
    summary = diff["summary"]
    edges = diff["edges"]
    actions = audit.get("actions") or []
    top = actions[0] if actions else {}
    top_action = ":".join(
        str(top.get(part, ""))
        for part in ("ownerLayer", "diagnosis", "role", "count")
    )
    node_count = readback.get("nodeCount", 0)
    root_children = readback.get("rootChildCount", 0)
    print(
        key,
        summary["generatedNodeCount"],
        summary["goldenNodeCount"],
        summary["matchedNodeCount"],
        summary["extraNodeCount"],
        summary["missedNodeCount"],
        f"{edges['precision']:.3f}",
        f"{edges['recall']:.3f}",
        node_count,
        root_children,
        top_action,
    )
    gate = expected[key]
    if summary["matchedNodeCount"] < gate["matched_min"]:
        print(f"{key}: matched below gate {summary['matchedNodeCount']} < {gate['matched_min']}", file=sys.stderr)
        failed = True
    if summary["extraNodeCount"] > gate["extra_max"]:
        print(f"{key}: extra above gate {summary['extraNodeCount']} > {gate['extra_max']}", file=sys.stderr)
        failed = True
    if summary["missedNodeCount"] > gate["missed_max"]:
        print(f"{key}: missed above gate {summary['missedNodeCount']} > {gate['missed_max']}", file=sys.stderr)
        failed = True
    if node_count <= 0 or root_children <= 0:
        print(f"{key}: generated canvas read-back is empty", file=sys.stderr)
        failed = True

if failed:
    sys.exit(1)
PY

echo "artifacts: $WORK"
