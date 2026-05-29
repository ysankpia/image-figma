#!/usr/bin/env python3
"""
Codia vs Go 树结构对比工具。

目标:量化我们 Go 后端输出树 与 Codia 官方输出树 的结构差距,作为改进 Go 编译层的标尺。

用法:
  python3 compare_trees.py [codia.canvas.json] [go_visual_tree.v1.json]

默认路径:
  codia = docs/reference/codia-samples/tencent-comic-018.canvas.json
  go    = /tmp/go_run/visual_tree.v1.json

对比维度:
  1. 规模:节点总数、各类型计数、最大/平均深度、顶层直接子节点数
  2. 容器结构:容器(有children)节点数、叶子数、平均扇出
  3. 空间包含一致性:Codia 的每个容器,在 Go 树里是否有对应的"把同一批叶子聚在一起"的容器
"""
import json
import sys
from collections import Counter

CODIA_DEFAULT = "/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/reference/codia-samples/tencent-comic-018.canvas.json"
GO_DEFAULT = "/tmp/go_run/visual_tree.v1.json"


# ---------- 归一化:把两种格式统一成 {type,name,x,y,w,h,children} 绝对坐标 ----------

def norm_codia(node, px=0, py=0):
    """Codia: transform.m02/m12 相对父;size.x/y。返回绝对坐标节点。"""
    t = node.get("transform") or {}
    s = node.get("size") or {}
    x = px + (t.get("m02") or 0)
    y = py + (t.get("m12") or 0)
    w = s.get("x") or 0
    h = s.get("y") or 0
    out = {
        "type": node.get("type", "?"),
        "name": node.get("name", ""),
        "x": x, "y": y, "w": w, "h": h,
        "children": [norm_codia(c, x, y) for c in (node.get("children") or [])],
    }
    return out


def norm_go(node):
    """Go: bbox 绝对坐标。"""
    b = node.get("bbox") or {}
    out = {
        "type": node.get("type", "?"),
        "name": node.get("name", ""),
        "x": b.get("x", 0), "y": b.get("y", 0),
        "w": b.get("width", 0), "h": b.get("height", 0),
        "children": [norm_go(c) for c in (node.get("children") or [])],
    }
    return out


def load_codia(path):
    d = json.load(open(path))
    root = d["root"]
    # 找到 "Figma design" -> "Root" 那棵真正的设计树
    def find(n, sub):
        if sub in (n.get("name") or ""):
            return n
        for c in n.get("children") or []:
            r = find(c, sub)
            if r:
                return r
        return None
    dz = find(root, "Figma design")
    rt = find(dz, "Root") if dz else None
    if rt is None:
        # 退而求其次:最大的 FRAME
        rt = root
    return norm_codia(rt)


def load_go(path):
    d = json.load(open(path))
    root = d.get("root", d)
    return norm_go(root)


# ---------- 度量 ----------

def walk(n, depth=0):
    yield n, depth
    for c in n["children"]:
        yield from walk(c, depth + 1)


def metrics(tree):
    types = Counter()
    depths = []
    container = 0
    leaf = 0
    fanouts = []
    for n, d in walk(tree):
        types[n["type"]] += 1
        depths.append(d)
        if n["children"]:
            container += 1
            fanouts.append(len(n["children"]))
        else:
            leaf += 1
    return {
        "total": sum(types.values()),
        "types": dict(types),
        "max_depth": max(depths) if depths else 0,
        "avg_depth": round(sum(depths) / len(depths), 2) if depths else 0,
        "top_children": len(tree["children"]),
        "containers": container,
        "leaves": leaf,
        "avg_fanout": round(sum(fanouts) / len(fanouts), 2) if fanouts else 0,
    }


# ---------- 空间包含一致性 ----------

def leaves_of(n):
    """返回子树下所有叶子的 (x,y,w,h) 集合。"""
    out = []
    for m, _ in walk(n):
        if not m["children"]:
            out.append((m["x"], m["y"], m["w"], m["h"]))
    return out


def containers_of(tree, min_leaves=2):
    """返回所有容器节点(有 >=min_leaves 个后代叶子的)。"""
    res = []
    for n, d in walk(tree):
        if n["children"]:
            lv = leaves_of(n)
            if len(lv) >= min_leaves:
                res.append((n, lv))
    return res


def bbox_of_leaves(lvs):
    xs = [l[0] for l in lvs]; ys = [l[1] for l in lvs]
    xe = [l[0] + l[2] for l in lvs]; ye = [l[1] + l[3] for l in lvs]
    return (min(xs), min(ys), max(xe), max(ye))


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    aa = (ax2 - ax1) * (ay2 - ay1)
    ba = (bx2 - bx1) * (by2 - by1)
    return inter / (aa + ba - inter)


def grouping_recall(codia, go):
    """
    对 Codia 的每个容器(由其叶子bbox界定),看 Go 树里有没有一个容器的 bbox IoU>=0.6 匹配。
    衡量:Codia 认为该聚成一组的东西,Go 有没有也聚成一组。
    """
    cc = containers_of(codia)
    gc = containers_of(go)
    g_boxes = [bbox_of_leaves(lv) for _, lv in gc]
    matched = 0
    misses = []
    for cn, clv in cc:
        cbox = bbox_of_leaves(clv)
        best = 0.0
        for gb in g_boxes:
            best = max(best, iou(cbox, gb))
        if best >= 0.6:
            matched += 1
        else:
            misses.append((cn["name"][:20], cbox, round(best, 2)))
    return {
        "codia_containers": len(cc),
        "go_containers": len(gc),
        "matched": matched,
        "recall": round(matched / len(cc), 3) if cc else 0,
        "misses": misses,
    }


def score_pair(codia_path, go_path):
    """对一组 (codia, go) 打分,返回指标 dict。"""
    codia = load_codia(codia_path)
    go = load_go(go_path)
    cm = metrics(codia)
    gm = metrics(go)
    gr = grouping_recall(codia, go)
    depth_ratio = min(gm["max_depth"], cm["max_depth"]) / max(cm["max_depth"], 1)
    score = round(0.7 * gr["recall"] + 0.3 * depth_ratio, 3)
    return {"cm": cm, "gm": gm, "gr": gr, "score": score, "depth_ratio": round(depth_ratio, 3)}


def print_single(codia_path, go_path):
    r = score_pair(codia_path, go_path)
    cm, gm, gr = r["cm"], r["gm"], r["gr"]
    print("=" * 64)
    print("规模对比                    Codia        Go")
    print("-" * 64)
    rows = [
        ("总节点", cm["total"], gm["total"]),
        ("最大深度", cm["max_depth"], gm["max_depth"]),
        ("平均深度", cm["avg_depth"], gm["avg_depth"]),
        ("顶层直接子节点", cm["top_children"], gm["top_children"]),
        ("容器数", cm["containers"], gm["containers"]),
        ("叶子数", cm["leaves"], gm["leaves"]),
        ("平均扇出", cm["avg_fanout"], gm["avg_fanout"]),
    ]
    for name, c, g in rows:
        print(f"{name:<22} {str(c):>10}  {str(g):>10}")
    print()
    print(f"Codia 类型: {cm['types']}")
    print(f"Go    类型: {gm['types']}")
    print()
    print("=" * 64)
    print("空间分组一致性 (Codia 的组,Go 是否也聚到了一起 IoU>=0.6)")
    print("-" * 64)
    print(f"Codia 容器数: {gr['codia_containers']}")
    print(f"Go    容器数: {gr['go_containers']}")
    print(f"匹配上:       {gr['matched']}")
    print(f"分组召回率:   {gr['recall']}  <-- 核心指标,越接近1越像Codia")
    print()
    if gr["misses"]:
        print(f"Codia 有但 Go 没聚成组的 (前15个):")
        for name, box, best in gr["misses"][:15]:
            bx = tuple(round(v) for v in box)
            print(f"  '{name}' codia_bbox={bx} 最佳IoU={best}")
    print()
    print("=" * 64)
    print(f"综合相似度: {r['score']}  (0.7*分组召回 + 0.3*深度比;1.0=结构1:1)")
    print("=" * 64)


def print_batch(manifest_path):
    """批量模式:清单每行 'codia.json|go.json|可选标签',输出每组分数+平均+最低。

    多图平均分和最低分是防过拟合的核心:单图刷分会被最低分拉下来。
    """
    pairs = []
    with open(manifest_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            codia_p, go_p = parts[0], parts[1]
            label = parts[2] if len(parts) > 2 else f"{codia_p.split('/')[-1]}"
            pairs.append((label, codia_p, go_p))

    print("=" * 78)
    print(f"{'图':<22}{'召回':>8}{'深度比':>8}{'Codia容器':>10}{'Go容器':>10}{'综合分':>10}")
    print("-" * 78)
    scores = []
    recalls = []
    for label, cp, gp in pairs:
        r = score_pair(cp, gp)
        scores.append(r["score"])
        recalls.append(r["gr"]["recall"])
        print(f"{label[:22]:<22}{r['gr']['recall']:>8.3f}{r['depth_ratio']:>8.3f}"
              f"{r['gr']['codia_containers']:>10}{r['gr']['go_containers']:>10}{r['score']:>10.3f}")
    print("-" * 78)
    if scores:
        avg = round(sum(scores) / len(scores), 3)
        worst = round(min(scores), 3)
        print(f"{'平均综合分':<22}{'':>16}{'':>20}{avg:>10.3f}")
        print(f"{'最低综合分(防过拟合)':<18}{'':>16}{'':>20}{worst:>10.3f}")
    print("=" * 78)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        print_batch(sys.argv[2])
        return
    codia_path = sys.argv[1] if len(sys.argv) > 1 else CODIA_DEFAULT
    go_path = sys.argv[2] if len(sys.argv) > 2 else GO_DEFAULT
    print_single(codia_path, go_path)


if __name__ == "__main__":
    main()
