package visualtree

import (
	"fmt"
	"os"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

// spatialGapRatio:判定结构性留白的相对阈值。缝隙 >= 该轴元素中位尺寸 * 比例 才切。
// 越小越爱切(树更深更碎),越大越粗(树更浅)。经单图对比工具校准。
var spatialGapRatio = func() float64 {
	if v := os.Getenv("ABL_GAP"); v != "" {
		var f float64
		fmt.Sscanf(v, "%f", &f)
		if f > 0 {
			return f
		}
	}
	return 0.15
}()

// applySpatialGrouping 递归地对每个容器节点的子节点做 XY-cut 空间聚类,
// 把扁平排列的兄弟节点收拢成嵌套的 synthetic 容器(对标 Codia 的 "Groups")。
//
// 动机:containment 只能用 token 已有的 bbox 包含关系建父子。当一批 UI 元素
// 没有任何"容器型" token 包着它们时(绝大多数情况),它们会全部平铺在 Body 下,
// 导致树很扁。Codia 的做法是纯几何:递归地沿"最大空白带"把空间切成嵌套块。
// 这就是经典的 XY-cut 版面分析算法,不依赖任何手写的语义/尺寸阈值。
func applySpatialGrouping(root *Node, counter *int) {
	regroupChildren(root, counter)
}

// regroupChildren 对 node 的直接子节点做一次 XY-cut 重组,然后递归处理每个子节点。
func regroupChildren(node *Node, counter *int) {
	if isAtomicSpatialGroup(*node) {
		refreshChildLayouts(node)
		return
	}
	// 已经是叶子或只有一个孩子:无需重组,直接递归
	if len(node.Children) <= 1 {
		for i := range node.Children {
			regroupChildren(&node.Children[i], counter)
		}
		return
	}

	backgrounds, foreground := splitBackgroundLeaves(node.Children)
	if os.Getenv("ABL_SLICES") == "" {
		foreground = groupContainedForegroundSlices(foreground, counter)
	}
	if os.Getenv("ABL_PAIRC") == "" {
		foreground = pairContainedForeground(foreground, counter)
	}
	if os.Getenv("ABL_VERT") == "" {
		foreground = pairVerticalForeground(foreground, counter)
	}
	if os.Getenv("ABL_TEXTBG") == "" {
		foreground = pairTextBackedForeground(foreground, counter)
	}
	grouped := xycut(foreground, counter, 0)
	if os.Getenv("ABL_ABSORB") == "" && node.Type == "Body" {
		grouped = absorbStragglers(grouped, counter)
	}

	// 顶层切出了多个成员:作为该节点的新子节点。
	// 若 xycut 整体切不开(返回原列表),保持平铺,不强加空壳。
	node.Children = append(backgrounds, grouped...)
	refreshChildLayouts(node)

	for i := range node.Children {
		regroupChildren(&node.Children[i], counter)
	}
}

func splitBackgroundLeaves(children []Node) ([]Node, []Node) {
	backgrounds := make([]Node, 0)
	foreground := make([]Node, 0, len(children))
	for _, child := range children {
		if isBackgroundLeaf(child) {
			backgrounds = append(backgrounds, child)
			continue
		}
		if os.Getenv("ABL_BGSPLIT") == "" && coversMostSiblings(child, children) {
			backgrounds = append(backgrounds, child)
			continue
		}
		foreground = append(foreground, child)
	}
	return backgrounds, foreground
}

// coversMostSiblings:一个真实图层叶子若在空间上罩住了同批多数兄弟(它们的中心
// 落在其 bbox 内),它是该区块的背景图,而非与兄弟平级的前景。把它从前景剥离,
// 前景元素才能按行/列被 XY-cut 正常切分,而不被这张大背景图的全尺寸投影吞掉切缝。
// 纯几何相对判据,不依赖任何绝对像素阈值。
func coversMostSiblings(child Node, all []Node) bool {
	if child.Type == "Text" || child.Meta.Synthetic || len(child.Children) > 0 {
		return false
	}
	others, covered := 0, 0
	for _, sibling := range all {
		if sibling.ID == child.ID {
			continue
		}
		others++
		cx := sibling.BBox.X + sibling.BBox.Width/2
		cy := sibling.BBox.Y + sibling.BBox.Height/2
		if cx >= child.BBox.X && cx < child.BBox.X+child.BBox.Width &&
			cy >= child.BBox.Y && cy < child.BBox.Y+child.BBox.Height {
			covered++
		}
	}
	return others >= 2 && covered*2 >= others
}

func isBackgroundLeaf(node Node) bool {
	return node.Meta.Synthetic && node.Meta.GroupKind == "background_leaf"
}

func pairContainedForeground(nodes []Node, counter *int) []Node {
	if len(nodes) < 2 {
		return nodes
	}
	used := map[int]bool{}
	pairsByFirst := map[int]Node{}
	for textIdx, text := range nodes {
		if used[textIdx] || text.Type != "Text" {
			continue
		}
		bestIdx := -1
		bestArea := 0
		for candidateIdx, candidate := range nodes {
			if candidateIdx == textIdx || used[candidateIdx] {
				continue
			}
			if !canPairAsContainedForeground(candidate, text) {
				continue
			}
			candidateArea := area(candidate.BBox)
			if bestIdx == -1 || candidateArea < bestArea {
				bestIdx = candidateIdx
				bestArea = candidateArea
			}
		}
		if bestIdx < 0 {
			continue
		}
		first := min(textIdx, bestIdx)
		children := []Node{nodes[bestIdx], text}
		pairsByFirst[first] = makeContainedForegroundGroup(children, counter)
		used[textIdx] = true
		used[bestIdx] = true
	}
	if len(pairsByFirst) == 0 {
		return nodes
	}
	out := make([]Node, 0, len(nodes)-len(used)+len(pairsByFirst))
	for i, node := range nodes {
		if pair, ok := pairsByFirst[i]; ok {
			out = append(out, pair)
			continue
		}
		if used[i] {
			continue
		}
		out = append(out, node)
	}
	return out
}

func groupContainedForegroundSlices(nodes []Node, counter *int) []Node {
	if len(nodes) < 3 {
		return nodes
	}
	usedText := map[int]bool{}
	groupsByFirst := map[int][]Node{}
	for imageIdx, imageNode := range nodes {
		if imageNode.Type != "Image" || imageNode.Meta.Synthetic || isThinLineNode(imageNode) {
			continue
		}
		textIndexes := containedSliceTextIndexes(imageNode, nodes, usedText)
		if len(textIndexes) < 2 {
			continue
		}
		groups := makeContainedSliceGroups(imageNode, textIndexes, nodes, counter)
		if len(groups) == 0 {
			continue
		}
		for _, idx := range textIndexes {
			usedText[idx] = true
		}
		insertAt := textIndexes[0]
		if imageIdx < insertAt {
			insertAt = imageIdx + 1
		}
		groupsByFirst[insertAt] = append(groupsByFirst[insertAt], groups...)
	}
	if len(groupsByFirst) == 0 {
		return nodes
	}
	out := make([]Node, 0, len(nodes)-len(usedText))
	for i, node := range nodes {
		if groups := groupsByFirst[i]; len(groups) > 0 {
			out = append(out, groups...)
		}
		if usedText[i] {
			continue
		}
		out = append(out, node)
	}
	return out
}

func containedSliceTextIndexes(imageNode Node, nodes []Node, usedText map[int]bool) []int {
	var indexes []int
	for i, node := range nodes {
		if usedText[i] || node.Type != "Text" || node.Meta.Synthetic {
			continue
		}
		if !bboxContains(imageNode.BBox, node.BBox, containmentTolerance) {
			continue
		}
		if centerY(node) < imageNode.BBox.Y+imageNode.BBox.Height/2 {
			continue
		}
		indexes = append(indexes, i)
	}
	if len(indexes) < 2 {
		return nil
	}
	sort.SliceStable(indexes, func(i, j int) bool {
		return centerX(nodes[indexes[i]]) < centerX(nodes[indexes[j]])
	})
	if !sameTextBaseline(indexes, nodes) {
		return nil
	}
	if !imageCanSplitByContainedText(imageNode, indexes, nodes) {
		return nil
	}
	return indexes
}

func centerX(node Node) int {
	return node.BBox.X + node.BBox.Width/2
}

func sameTextBaseline(indexes []int, nodes []Node) bool {
	minCenter := centerY(nodes[indexes[0]])
	maxCenter := minCenter
	medianHeightValues := make([]int, 0, len(indexes))
	for _, idx := range indexes {
		cy := centerY(nodes[idx])
		minCenter = min(minCenter, cy)
		maxCenter = max(maxCenter, cy)
		medianHeightValues = append(medianHeightValues, nodes[idx].BBox.Height)
	}
	return maxCenter-minCenter <= max(8, medianInt(medianHeightValues)/2)
}

func imageCanSplitByContainedText(imageNode Node, indexes []int, nodes []Node) bool {
	heights := make([]int, 0, len(indexes))
	maxTextWidth := 0
	for _, idx := range indexes {
		heights = append(heights, nodes[idx].BBox.Height)
		maxTextWidth = max(maxTextWidth, nodes[idx].BBox.Width)
	}
	medianHeight := max(1, medianInt(heights))
	if imageNode.BBox.Height > medianHeight*10 {
		return false
	}
	if imageNode.BBox.Width < maxTextWidth*2 {
		return false
	}
	return true
}

func makeContainedSliceGroups(imageNode Node, indexes []int, nodes []Node, counter *int) []Node {
	groups := make([]Node, 0, len(indexes))
	left := imageNode.BBox.X
	right := imageNode.BBox.X + imageNode.BBox.Width
	bounds := make([]int, len(indexes)+1)
	bounds[0] = left
	bounds[len(bounds)-1] = right
	for i := 0; i < len(indexes)-1; i++ {
		a := centerX(nodes[indexes[i]])
		b := centerX(nodes[indexes[i+1]])
		bounds[i+1] = (a + b) / 2
	}
	for i, idx := range indexes {
		if bounds[i+1] <= bounds[i] {
			continue
		}
		bg := makeBackgroundSliceNode(imageNode, contract.BBox{
			X:      bounds[i],
			Y:      imageNode.BBox.Y,
			Width:  bounds[i+1] - bounds[i],
			Height: imageNode.BBox.Height,
		}, counter)
		group := makeSpatialGroup([]Node{bg, nodes[idx]}, counter)
		group.Meta.GroupKind = "contained_slice_group"
		groups = append(groups, group)
	}
	return groups
}

func makeBackgroundSliceNode(source Node, box contract.BBox, counter *int) Node {
	id := fmt.Sprintf("slice_%04d", *counter)
	*counter = *counter + 1
	return Node{
		ID:   id,
		Type: "Image",
		Name: "Background / " + source.ID,
		BBox: box,
		Layout: Layout{
			Mode:     "absolute",
			Relative: true,
		},
		SourceRefs: SourceRefs{
			TokenIDs:      append([]string(nil), source.SourceRefs.TokenIDs...),
			BackgroundIDs: append([]string(nil), source.SourceRefs.TokenIDs...),
		},
		Meta: Meta{
			Synthetic:    true,
			GroupKind:    "background_leaf",
			ParentReason: "contained_foreground_slice",
		},
	}
}

func canPairAsContainedForeground(candidate Node, text Node) bool {
	if candidate.Type == "Text" || candidate.Meta.Synthetic || isThinLineNode(candidate) {
		return false
	}
	if !bboxContains(candidate.BBox, text.BBox, containmentTolerance) {
		return false
	}
	textArea := area(text.BBox)
	candidateArea := area(candidate.BBox)
	if textArea == 0 || candidateArea <= textArea {
		return false
	}
	if candidateArea > textArea*14 {
		return false
	}
	if canPairAsCompactBackground(candidate, text) {
		return true
	}
	return canPairAsContainedTile(candidate, text)
}

func canPairAsCompactBackground(candidate Node, text Node) bool {
	if candidate.BBox.Height > text.BBox.Height*4 {
		return false
	}
	if candidate.BBox.Width > text.BBox.Width+text.BBox.Height*3 {
		return false
	}
	return true
}

func canPairAsContainedTile(candidate Node, text Node) bool {
	if candidate.Type != "Image" {
		return false
	}
	if candidate.BBox.Height <= text.BBox.Height*4 {
		return false
	}
	if candidate.BBox.Width < text.BBox.Width {
		return false
	}
	textBottom := text.BBox.Y + text.BBox.Height
	candidateBottom := candidate.BBox.Y + candidate.BBox.Height
	if textBottom < candidate.BBox.Y+candidate.BBox.Height/2 {
		return false
	}
	if candidateBottom-textBottom > max(text.BBox.Height, candidate.BBox.Height/4) {
		return false
	}
	textCenter := text.BBox.X + text.BBox.Width/2
	candidateCenter := candidate.BBox.X + candidate.BBox.Width/2
	if abs(textCenter-candidateCenter) > max(candidate.BBox.Width/3, text.BBox.Width) {
		return false
	}
	return true
}

func makeContainedForegroundGroup(children []Node, counter *int) Node {
	sort.SliceStable(children, func(i, j int) bool {
		if children[i].Type != children[j].Type {
			return children[i].Type != "Text"
		}
		return lessNode(children[i], children[j])
	})
	group := makeSpatialGroup(children, counter)
	if len(children) == 2 && children[0].Type == "Image" && canPairAsContainedTile(children[0], children[1]) {
		group.Meta.GroupKind = "contained_foreground_group"
	} else {
		group.Meta.GroupKind = "contained_pair_group"
	}
	return group
}

func isAtomicSpatialGroup(node Node) bool {
	return node.Meta.Synthetic && (node.Meta.GroupKind == "contained_pair_group" || node.Meta.GroupKind == "contained_foreground_group" || node.Meta.GroupKind == "contained_slice_group" || node.Meta.GroupKind == "text_background_group" || node.Meta.GroupKind == "vertical_pair_group")
}

func pairTextBackedForeground(nodes []Node, counter *int) []Node {
	if len(nodes) == 0 {
		return nodes
	}
	out := make([]Node, 0, len(nodes))
	for _, node := range nodes {
		if canUseTextBBoxAsBackground(node) {
			out = append(out, makeTextBackgroundGroup(node, counter))
			continue
		}
		out = append(out, node)
	}
	return out
}

func canUseTextBBoxAsBackground(node Node) bool {
	if node.Type != "Text" || node.Meta.Synthetic || node.BBox.Height <= 0 {
		return false
	}
	// 纯相对判据:宽高比 >= 2.5(短宽型,像按钮/标签)
	if node.BBox.Width*2 < node.BBox.Height*5 {
		return false
	}
	return true
}

func makeTextBackgroundGroup(text Node, counter *int) Node {
	bg := Node{
		ID:   fmt.Sprintf("tbg_%04d", *counter),
		Type: "Image",
		Name: "Background / " + text.ID,
		BBox: text.BBox,
		Layout: Layout{
			Mode:     "absolute",
			Relative: true,
		},
		Meta: Meta{
			Synthetic:    true,
			GroupKind:    "background_leaf",
			ParentReason: "text_bbox_background",
		},
	}
	group := makeSpatialGroup([]Node{bg, text}, counter)
	group.Meta.GroupKind = "text_background_group"
	return group
}

func pairVerticalForeground(nodes []Node, counter *int) []Node {
	if len(nodes) < 2 {
		return nodes
	}
	used := map[int]bool{}
	pairsByFirst := map[int]Node{}
	for topIdx, top := range nodes {
		if used[topIdx] || top.Type == "Text" || top.Meta.Synthetic || isThinLineNode(top) {
			continue
		}
		bestIdx := -1
		bestGap := 0
		for textIdx, text := range nodes {
			if used[textIdx] || textIdx == topIdx || text.Type != "Text" {
				continue
			}
			if !isVerticalLabelPair(top, text) {
				continue
			}
			gap := text.BBox.Y - (top.BBox.Y + top.BBox.Height)
			if bestIdx == -1 || gap < bestGap {
				bestIdx = textIdx
				bestGap = gap
			}
		}
		if bestIdx < 0 {
			continue
		}
		first := min(topIdx, bestIdx)
		children := []Node{top, nodes[bestIdx]}
		group := makeSpatialGroup(children, counter)
		group.Meta.GroupKind = "vertical_pair_group"
		pairsByFirst[first] = group
		used[topIdx] = true
		used[bestIdx] = true
	}
	if len(pairsByFirst) == 0 {
		return nodes
	}
	out := make([]Node, 0, len(nodes)-len(used)+len(pairsByFirst))
	for i, node := range nodes {
		if pair, ok := pairsByFirst[i]; ok {
			out = append(out, pair)
			continue
		}
		if used[i] {
			continue
		}
		out = append(out, node)
	}
	return out
}

func isVerticalLabelPair(top Node, text Node) bool {
	if text.BBox.Y < top.BBox.Y {
		return false
	}
	gap := text.BBox.Y - (top.BBox.Y + top.BBox.Height)
	local := max(1, min(top.BBox.Height, text.BBox.Height))
	if gap < -local/2 || gap > max(8, local) {
		return false
	}
	overlap := min(top.BBox.X+top.BBox.Width, text.BBox.X+text.BBox.Width) - max(top.BBox.X, text.BBox.X)
	if overlap <= 0 {
		centerDelta := abs((top.BBox.X + top.BBox.Width/2) - (text.BBox.X + text.BBox.Width/2))
		if centerDelta > max(top.BBox.Width, text.BBox.Width)/2 {
			return false
		}
		return true
	}
	return overlap*2 >= min(top.BBox.Width, text.BBox.Width)
}

// xycut 对一组节点递归做 XY 切分。返回切分后的节点列表(可能含新建的 synthetic 容器)。
// depth 防止极端情况下无限递归。
// xycut 对一组兄弟节点做一层 XY 切分,返回切分后的顶层成员列表。
// 每个能被进一步细分或本身就是紧密簇的多元素子簇,会被递归地包成 synthetic 容器。
// 顶层若整体切不开(就是一个紧密簇),返回原列表(由调用方 regroupChildren 决定不再加层)。
func xycut(nodes []Node, counter *int, depth int) []Node {
	if len(nodes) <= 1 || depth > 12 {
		return nodes
	}

	clustersY, gapY := splitAxis(nodes, true)  // 按 Y 分行
	clustersX, gapX := splitAxis(nodes, false) // 按 X 分列

	if len(clustersY) < 2 && len(clustersX) < 2 {
		// 两个轴都切不开(投影互相重叠)。退一步用"邻近连通分量"兜底:
		// 按元素之间的边缘间距建图,把空间上分离的连通块分开。
		// 这能处理"投影重叠但实际分簇"的情况(如交错排列的卡片)。
		comps := neighborComponents(nodes)
		if len(comps) >= 2 {
			out := make([]Node, 0, len(comps))
			for _, comp := range comps {
				out = append(out, groupCluster(comp, counter, depth+1))
			}
			return out
		}
		// 仍是单一连通块:这批节点是一个紧密簇,无法再分,原样返回
		return nodes
	}

	// 选间隙更显著的轴先切(XY-cut 经典:每层选更干净的切分)
	var clusters [][]Node
	if gapY >= gapX && len(clustersY) >= 2 {
		clusters = clustersY
	} else if len(clustersX) >= 2 {
		clusters = clustersX
	} else {
		clusters = clustersY
	}

	out := make([]Node, 0, len(clusters))
	for _, cluster := range clusters {
		out = append(out, groupCluster(cluster, counter, depth+1))
	}
	return out
}

// absorbStragglers 把孤立的小叶子节点吸收进相邻的组。
// 动机:XY-cut 把所有超过阈值的间隙都切开,导致紧邻大组的小元素(如底部指示条、
// 分隔线)被单独切出。Codia 会把它们归入相邻的大组。
// 判据:孤立叶子与相邻组的间隙 < 相邻组在该轴上尺寸的 50%。纯相对,无像素阈值。
func absorbStragglers(nodes []Node, counter *int) []Node {
	if len(nodes) < 3 {
		return nodes
	}
	absorbed := map[int]int{} // straggler index -> target group index
	for i, node := range nodes {
		if !isStraggler(node) {
			continue
		}
		bestTarget := -1
		bestGap := 0
		for j, other := range nodes {
			if j == i || isStraggler(other) {
				continue
			}
			gap := nodeGap(node, other)
			limit := max(other.BBox.Height, other.BBox.Width) / 2
			if gap >= 0 && gap < limit {
				if bestTarget == -1 || gap < bestGap {
					bestTarget = j
					bestGap = gap
				}
			}
		}
		if bestTarget >= 0 {
			absorbed[i] = bestTarget
		}
	}
	if len(absorbed) == 0 {
		return nodes
	}
	// 把被吸收的叶子加入目标组的 children
	extras := map[int][]Node{}
	for si, ti := range absorbed {
		extras[ti] = append(extras[ti], nodes[si])
	}
	out := make([]Node, 0, len(nodes)-len(absorbed))
	for i, node := range nodes {
		if _, ok := absorbed[i]; ok {
			continue
		}
		if ex, ok := extras[i]; ok {
			if node.Meta.Synthetic && len(node.Children) > 0 {
				node.Children = append(node.Children, ex...)
				node.BBox = unionNodeBBox(node.Children)
				refreshChildLayouts(&node)
			} else {
				all := append([]Node{node}, ex...)
				node = makeSpatialGroup(all, counter)
			}
		}
		out = append(out, node)
	}
	return out
}

func isStraggler(node Node) bool {
	return !node.Meta.Synthetic && len(node.Children) == 0
}

func nodeGap(a, b Node) int {
	gx := axisGap(a.BBox.X, a.BBox.X+a.BBox.Width, b.BBox.X, b.BBox.X+b.BBox.Width)
	gy := axisGap(a.BBox.Y, a.BBox.Y+a.BBox.Height, b.BBox.Y, b.BBox.Y+b.BBox.Height)
	if gx == 0 && gy == 0 {
		return 0
	}
	if gx == 0 {
		return gy
	}
	if gy == 0 {
		return gx
	}
	return gx + gy
}

// groupCluster 把一个簇收敛成【单个】节点:
//   - 单元素:返回该元素本身
//   - 多元素:递归 xycut 继续细分;无论细分出多个子项、还是整簇切不开,
//     都包成一个 synthetic 容器(对标 Codia "紧密一组 = 一个 Groups")
func groupCluster(cluster []Node, counter *int, depth int) Node {
	if len(cluster) == 1 {
		return cluster[0]
	}
	sub := xycut(cluster, counter, depth)
	return makeSpatialGroup(sub, counter)
}

// splitAxis 把 nodes 沿给定轴(vertical=true 表示沿 Y 轴分行)按空白带切成多个簇。
// 返回簇列表 和 最大相对间隙(间隙/中位尺寸,用于跨轴比较哪个切分更干净)。
//
// 算法(投影空白带 / projection profile cut):
//  1. 把每个节点在该轴上投影成 [start,end] 区间,按 start 排序;
//  2. 用扫描线合并所有重叠/接触的区间,得到若干"占用块";占用块之间的空隙即候选切缝;
//  3. 只在"足够大"的空隙处切(空隙 >= 中位元素尺寸 * ratio),把节点按所属占用块分簇。
//
// 关键:簇内节点保持输入(阅读)顺序,排序只用于找切缝,不改变输出顺序。
//
// 为什么用相对判据:一行紧密排列的元素(导航文字、价格数字)缝隙远小于元素本身,
// 不应被切散;而区块之间的结构性留白通常和元素尺寸同量级或更大。无绝对像素阈值,按内容自适应。
func splitAxis(nodes []Node, vertical bool) ([][]Node, float64) {
	n := len(nodes)
	starts := make([]int, n)
	ends := make([]int, n)
	sizes := make([]int, n)
	for i, nd := range nodes {
		if vertical {
			starts[i], ends[i], sizes[i] = nd.BBox.Y, nd.BBox.Y+nd.BBox.Height, nd.BBox.Height
		} else {
			starts[i], ends[i], sizes[i] = nd.BBox.X, nd.BBox.X+nd.BBox.Width, nd.BBox.Width
		}
	}

	order := make([]int, n)
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(a, b int) bool {
		if starts[order[a]] != starts[order[b]] {
			return starts[order[a]] < starts[order[b]]
		}
		return ends[order[a]] < ends[order[b]]
	})

	medianSize := medianInt(sizes)
	minGap := 1
	if medianSize > 0 {
		minGap = max(minGap, int(float64(medianSize)*spatialGapRatio))
	}

	// 沿排序后的占用区间找切缝,给每个节点打"簇编号"
	clusterOf := make([]int, n)
	cluster := 0
	curEnd := ends[order[0]]
	clusterOf[order[0]] = 0
	maxGap := 0
	for k := 1; k < n; k++ {
		idx := order[k]
		gap := starts[idx] - curEnd
		if gap >= minGap {
			if gap > maxGap {
				maxGap = gap
			}
			cluster++
		}
		clusterOf[idx] = cluster
		if ends[idx] > curEnd {
			curEnd = ends[idx]
		}
	}

	clusterCount := cluster + 1
	clusters := make([][]Node, clusterCount)
	// 按【原始输入顺序】填充,保持阅读顺序
	for i := range n {
		c := clusterOf[i]
		clusters[c] = append(clusters[c], nodes[i])
	}

	relGap := 0.0
	if medianSize > 0 {
		relGap = float64(maxGap) / float64(medianSize)
	}
	return clusters, relGap
}

// neighborComponents 按"边缘间距"把节点分成空间连通分量(并查集)。
// 两个节点相连的条件:在一个轴上投影重叠,且另一轴的间距 <= 邻近阈值。
// 阈值 = 这批节点中位尺寸 * spatialGapRatio(与切分判据同源,自适应)。
//
// 用途:当投影空白切分切不开(两轴投影都重叠)时,用它把实际分离的簇分开;
// 若整批是一个连通块,说明它们紧密相邻,应作为一个组。
func neighborComponents(nodes []Node) [][]Node {
	n := len(nodes)
	if n <= 1 {
		return [][]Node{nodes}
	}
	sizes := make([]int, 0, 2*n)
	for _, nd := range nodes {
		sizes = append(sizes, nd.BBox.Width, nd.BBox.Height)
	}
	med := medianInt(sizes)
	maxGap := 1
	if med > 0 {
		maxGap = max(maxGap, int(float64(med)*spatialGapRatio))
	}

	parent := make([]int, n)
	for i := range parent {
		parent[i] = i
	}
	var find func(int) int
	find = func(x int) int {
		for parent[x] != x {
			parent[x] = parent[parent[x]]
			x = parent[x]
		}
		return x
	}
	union := func(a, b int) {
		ra, rb := find(a), find(b)
		if ra != rb {
			parent[ra] = rb
		}
	}

	for i := range n {
		a := nodes[i].BBox
		for j := i + 1; j < n; j++ {
			b := nodes[j].BBox
			overlapX := min(a.X+a.Width, b.X+b.Width) - max(a.X, b.X)
			overlapY := min(a.Y+a.Height, b.Y+b.Height) - max(a.Y, b.Y)
			gx := axisGap(a.X, a.X+a.Width, b.X, b.X+b.Width)
			gy := axisGap(a.Y, a.Y+a.Height, b.Y, b.Y+b.Height)
			connected := false
			if overlapX > 0 && gy <= maxGap {
				connected = true
			} else if overlapY > 0 && gx <= maxGap {
				connected = true
			}
			if connected {
				union(i, j)
			}
		}
	}

	groups := map[int][]Node{}
	for i := range n {
		r := find(i)
		groups[r] = append(groups[r], nodes[i])
	}
	out := make([][]Node, 0, len(groups))
	for _, g := range groups {
		out = append(out, g)
	}
	// 按位置稳定排序(上->下, 左->右)
	sort.SliceStable(out, func(i, j int) bool {
		bi, bj := unionNodeBBox(out[i]), unionNodeBBox(out[j])
		if bi.Y != bj.Y {
			return bi.Y < bj.Y
		}
		return bi.X < bj.X
	})
	return out
}

// axisGap 返回两个区间在某轴上的正间距;若重叠返回 0。
func axisGap(a1, a2, b1, b2 int) int {
	if a2 < b1 {
		return b1 - a2
	}
	if b2 < a1 {
		return a1 - b2
	}
	return 0
}

// makeSpatialGroup 用一组子节点包一个 synthetic 容器(对标 Codia 的 Groups FRAME)。
func makeSpatialGroup(children []Node, counter *int) Node {
	id := fmt.Sprintf("sgroup_%04d", *counter)
	*counter = *counter + 1
	box := unionNodeBBox(children)
	// 子节点按阅读顺序(上->下, 左->右)排好
	sort.SliceStable(children, func(i, j int) bool { return lessNode(children[i], children[j]) })
	node := Node{
		ID:   id,
		Type: "Layer",
		Name: "Groups / " + id,
		BBox: box,
		Layout: Layout{
			Mode:     "absolute",
			X:        box.X,
			Y:        box.Y,
			Width:    box.Width,
			Height:   box.Height,
			Relative: true,
		},
		Meta: Meta{
			Synthetic: true,
			GroupKind: "spatial_group",
		},
		Children: children,
	}
	refreshChildLayouts(&node)
	return node
}
