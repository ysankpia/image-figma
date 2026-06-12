#!/usr/bin/env bash
# 4 图回归评测:用当前 Go 代码对固定的 4 张图生成 VisualTree,
# 与仓库内 Codia 标准答案树批量对比,输出平均分 + 最低分。
#
# 用法(在仓库根执行):
#   bash services/backend-go/tools/eval_4img.sh
#
# 最低分是防过拟合的核心指标:单图刷分会被最低分拉下来。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

IMG_DIR="docs/reference/codia-samples/images"
JSON_DIR="docs/reference/codia-samples"
WORK="/tmp/eval_4img"
rm -rf "$WORK"; mkdir -p "$WORK"

run_one() {
  local key="$1" img="$2"
  local out="$WORK/$key"; mkdir -p "$out"
  mkdir -p "$out/masks" "$out/crops"
  ( cd services/backend-go
    go run ./cmd/m29extract   -input "../../$IMG_DIR/$img" -out "$out" >/dev/null
    go run ./cmd/m29tokens    -input "$out/m29_physical_evidence.v1.json" -out "$out" >/dev/null
    go run ./cmd/m29relations -input "$out/evidence_tokens.v1.json" -out "$out" >/dev/null
    go run ./cmd/m29visualtree -tokens "$out/evidence_tokens.v1.json" -relations "$out/relation_graph.v1.json" -out "$out" >/dev/null )
}

run_one t018   "腾讯动漫_018_1440.png"
run_one t022   "腾讯动漫_022_1440.png"
run_one lizhi  "荔枝_011_1440.png"
run_one xianyu "闲鱼.png"

cat > "$WORK/manifest.txt" <<EOF
$JSON_DIR/tencent-comic-018.canvas.json|$WORK/t018/visual_tree.v1.json|腾讯动漫018
$JSON_DIR/tencent-comic-022.canvas.json|$WORK/t022/visual_tree.v1.json|腾讯动漫022
$JSON_DIR/lizhi-011.canvas.json|$WORK/lizhi/visual_tree.v1.json|荔枝011
$JSON_DIR/xianyu.canvas.json|$WORK/xianyu/visual_tree.v1.json|闲鱼
EOF

python3 services/backend-go/tools/compare_trees.py --batch "$WORK/manifest.txt" --trace-dir "$WORK/eval_trace"
