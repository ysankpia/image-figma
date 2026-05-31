#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$ROOT/services/backend-go"
IMG_DIR="$ROOT/docs/reference/codia-samples/images"
WORK="${LAYOUT_SMOKE_WORKDIR:-/tmp/layout_smoke_4img}"

rm -rf "$WORK"
mkdir -p "$WORK"

run_one() {
  local key="$1"
  local image="$2"
  local out="$WORK/$key"
  mkdir -p "$out"
  (
    cd "$BACKEND"
    go run ./cmd/layoutcompile -input "$IMG_DIR/$image" -out "$out" >/dev/null
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
    "ui_layout_ir_validation.v1.json",
    "layout_compile_report.md",
    "preview.html",
    "preview_debug.html",
    "html_preview_report.md",
]
missing = [name for name in required if not (out / name).exists()]
if missing:
    raise SystemExit(f"{key}: missing artifacts {missing}")

validation = json.loads((out / "ui_layout_ir_validation.v1.json").read_text())
if validation.get("errorCount") != 0:
    raise SystemExit(f"{key}: validation errors {validation}")

doc = json.loads((out / "ui_layout_ir.v1.json").read_text())
html = (out / "preview.html").read_text()
refs = re.findall(r'\bsrc="([^"]+)"', html)
asset_missing = [
    ref for ref in refs
    if not ref.startswith(("http://", "https://", "data:")) and not (out / ref).exists()
]
if asset_missing:
    raise SystemExit(f"{key}: missing html assets {asset_missing[:5]}")

root_children = len(doc.get("root", {}).get("children") or [])
rows = sum(len(section.get("children") or []) for section in doc.get("root", {}).get("children") or [])
summary = doc.get("summary") or {}
report = (out / "html_preview_report.md").read_text()
warning_match = re.search(r"- warnings: `([0-9]+)`", report)
warnings = int(warning_match.group(1)) if warning_match else -1
print(
    "| {key} | {nodes} | {sections} | {rows} | {evidence} | {assets} | {warnings} |".format(
        key=key,
        nodes=summary.get("nodeCount", 0),
        sections=root_children,
        rows=rows,
        evidence=summary.get("evidenceCount", 0),
        assets=len(refs),
        warnings=warnings,
    )
)
PY
}

{
  echo "# Layout Smoke 4img"
  echo
  echo "- workdir: \`$WORK\`"
  echo
  echo "| case | nodes | sections | rows | evidence | html assets | warnings |"
  echo "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"
  run_one t018 "腾讯动漫_018_1440.png"
  run_one t022 "腾讯动漫_022_1440.png"
  run_one lizhi "荔枝_011_1440.png"
  run_one xianyu "闲鱼.png"
} | tee "$WORK/layout_smoke_4img_report.md"
