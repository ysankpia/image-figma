#!/usr/bin/env bash
# Role-aware Codia compiler smoke gate for the two Tencent golden samples.
#
# This validates the Go Codia-like compiler path:
#   PNG + OCR -> M29 evidence -> Codia leaves -> controls -> tree -> diff/audit
#
# Golden Codia IR is used only for structural diff, never for generation.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$ROOT/services/backend-go"
WORK="${CODIA_SMOKE_WORK:-/tmp/codia_smoke_2img}"

OCR_T018="${CODIA_OCR_T018:-/tmp/eval_4img/t018/ocr.json}"
OCR_T022="${CODIA_OCR_T022:-/tmp/eval_4img/t022/ocr.json}"

rm -rf "$WORK"
mkdir -p "$WORK"

require_file() {
  local path="$1" label="$2"
  if [[ ! -f "$path" ]]; then
    echo "missing $label: $path" >&2
    echo "set CODIA_OCR_T018/CODIA_OCR_T022 or run services/backend-go/tools/eval_4img.sh to refresh OCR artifacts" >&2
    exit 2
  fi
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
  local key="$1" image="$2" ocr="$3"
  local out="$WORK/compile-$key"
  mkdir -p "$out"
  (cd "$BACKEND" && go run ./cmd/codiacompile -input "$image" -ocr "$ocr" -golden "$WORK/golden-$key/codia_ir.v1.json" -out "$out" >/dev/null)
}

require_file "$OCR_T018" "Tencent 018 OCR"
require_file "$OCR_T022" "Tencent 022 OCR"

run_analyze t018 "$ROOT/docs/reference/codia-samples/tencent-comic-018.canvas.json" tencent-comic-018
run_analyze t022 "$ROOT/docs/reference/codia-samples/tencent-comic-022.canvas.json"

run_compile t018 "$ROOT/docs/reference/codia-samples/images/腾讯动漫_018_1440.png" "$OCR_T018"
run_compile t022 "$ROOT/docs/reference/codia-samples/images/腾讯动漫_022_1440.png" "$OCR_T022"

python3 - "$WORK" <<'PY'
import json
import pathlib
import sys

work = pathlib.Path(sys.argv[1])
expected = {
    "t018": {"matched_min": 94, "extra_max": 55, "missed_max": 52},
    "t022": {"matched_min": 92, "extra_max": 16, "missed_max": 28},
}

failed = False
print("sample generated matched extra missed edgeP edgeR topAction")
for key in ("t018", "t022"):
    diff_path = work / f"compile-{key}" / "diff" / "codia_structure_diff.v1.json"
    audit_path = work / f"compile-{key}" / "audit" / "codia_failure_audit.v1.json"
    diff = json.loads(diff_path.read_text())
    audit = json.loads(audit_path.read_text())
    summary = diff["summary"]
    edges = diff["edges"]
    actions = audit.get("actions") or []
    top = actions[0] if actions else {}
    top_action = ":".join(
        str(top.get(part, ""))
        for part in ("ownerLayer", "diagnosis", "role", "count")
    )
    print(
        key,
        summary["generatedNodeCount"],
        summary["matchedNodeCount"],
        summary["extraNodeCount"],
        summary["missedNodeCount"],
        f"{edges['precision']:.3f}",
        f"{edges['recall']:.3f}",
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

if failed:
    sys.exit(1)
PY

echo "artifacts: $WORK"
