package visualtree

import (
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func applyAxisProjectionGroups(node *Node, counter *int) {
	for i := range node.Children {
		applyAxisProjectionGroups(&node.Children[i], counter)
	}
	if len(node.Children) < 2 {
		return
	}
	groups := axisProjectionGroups(node.Children, node.BBox, node.Type == "Body")
	if len(groups) == 0 {
		return
	}
	childByID := map[string]Node{}
	for _, child := range node.Children {
		childByID[child.ID] = child
	}
	used := map[string]bool{}
	selected := make([]visualGroup, 0, len(groups))
	for _, group := range groups {
		conflict := false
		for _, id := range group.memberIDs {
			if used[id] {
				conflict = true
				break
			}
		}
		if conflict {
			continue
		}
		for _, id := range group.memberIDs {
			used[id] = true
		}
		selected = append(selected, group)
	}
	if len(selected) == 0 {
		return
	}
	groupByFirstID := map[string]visualGroup{}
	for _, group := range selected {
		sort.SliceStable(group.memberIDs, func(i, j int) bool {
			return lessNode(childByID[group.memberIDs[i]], childByID[group.memberIDs[j]])
		})
		groupByFirstID[group.memberIDs[0]] = group
	}
	nextChildren := make([]Node, 0, len(node.Children))
	for _, child := range node.Children {
		if group, ok := groupByFirstID[child.ID]; ok {
			nextChildren = append(nextChildren, buildGroupNode(group, childByID, counter))
			continue
		}
		if used[child.ID] {
			continue
		}
		nextChildren = append(nextChildren, child)
	}
	node.Children = nextChildren
	refreshChildLayouts(node)
}

type axisRowBucket struct {
	nodes []Node
	box   contract.BBox
}

func axisProjectionGroups(children []Node, parentBox contract.BBox, parentIsBody bool) []visualGroup {
	candidates := axisProjectionCandidates(children)
	if axisNodeEffectiveMemberCount(candidates) < 4 {
		return nil
	}
	sort.SliceStable(candidates, func(i, j int) bool {
		if centerY(candidates[i]) != centerY(candidates[j]) {
			return centerY(candidates[i]) < centerY(candidates[j])
		}
		if candidates[i].BBox.X != candidates[j].BBox.X {
			return candidates[i].BBox.X < candidates[j].BBox.X
		}
		return candidates[i].ID < candidates[j].ID
	})
	rows := axisRowBuckets(candidates)
	if len(rows) < 2 {
		return nil
	}

	var groups []visualGroup
	for start := 0; start < len(rows); start++ {
		for end := len(rows) - 1; end > start; end-- {
			window := rows[start : end+1]
			if !validAxisProjectionWindow(window, parentBox, parentIsBody) {
				continue
			}
			memberIDs := axisWindowMemberIDs(window)
			groups = append(groups, visualGroup{
				kind:      "axis_projection_group",
				memberIDs: memberIDs,
				score:     groupScore("axis_projection_group"),
			})
			start = end
			break
		}
	}
	sort.SliceStable(groups, func(i, j int) bool {
		if groups[i].score != groups[j].score {
			return groups[i].score > groups[j].score
		}
		if len(groups[i].memberIDs) != len(groups[j].memberIDs) {
			return len(groups[i].memberIDs) > len(groups[j].memberIDs)
		}
		return groups[i].memberIDs[0] < groups[j].memberIDs[0]
	})
	return groups
}

func axisProjectionCandidates(children []Node) []Node {
	out := make([]Node, 0, len(children))
	for _, child := range children {
		if child.BBox.Width <= 0 || child.BBox.Height <= 0 || child.Type == "Body" {
			continue
		}
		if child.Meta.Synthetic {
			if child.Meta.GroupKind == "row_group" {
				out = append(out, child)
			}
			continue
		}
		if child.Type == "Text" {
			out = append(out, child)
			continue
		}
		if child.Type == "Image" && !isThinLineNode(child) {
			out = append(out, child)
		}
	}
	return out
}

func axisRowBuckets(nodes []Node) []axisRowBucket {
	var rows []axisRowBucket
	for _, node := range nodes {
		placed := false
		for i := range rows {
			if abs(centerY(node)-centerYOfBox(rows[i].box)) <= axisRowTolerance(rows[i], node) {
				rows[i].nodes = append(rows[i].nodes, node)
				rows[i].box = unionNodeBBox(rows[i].nodes)
				placed = true
				break
			}
		}
		if !placed {
			rows = append(rows, axisRowBucket{
				nodes: []Node{node},
				box:   node.BBox,
			})
		}
	}
	for i := range rows {
		sort.SliceStable(rows[i].nodes, func(a, b int) bool {
			if rows[i].nodes[a].BBox.X != rows[i].nodes[b].BBox.X {
				return rows[i].nodes[a].BBox.X < rows[i].nodes[b].BBox.X
			}
			return rows[i].nodes[a].ID < rows[i].nodes[b].ID
		})
		rows[i].box = unionNodeBBox(rows[i].nodes)
	}
	sort.SliceStable(rows, func(i, j int) bool {
		if centerYOfBox(rows[i].box) != centerYOfBox(rows[j].box) {
			return centerYOfBox(rows[i].box) < centerYOfBox(rows[j].box)
		}
		return rows[i].box.X < rows[j].box.X
	})
	return rows
}

func axisRowTolerance(row axisRowBucket, node Node) int {
	return max(8, int(float64(max(row.box.Height, node.BBox.Height))*0.55))
}

func validAxisProjectionWindow(rows []axisRowBucket, parentBox contract.BBox, parentIsBody bool) bool {
	if len(rows) < 2 {
		return false
	}
	memberCount := 0
	largeRasterCount := 0
	var allNodes []Node
	for _, row := range rows {
		if len(row.nodes) < 2 && !singleRowGroupBucket(row) {
			return false
		}
		for _, node := range row.nodes {
			memberCount += axisEffectiveMemberCount(node)
		}
		allNodes = append(allNodes, row.nodes...)
	}
	if memberCount < 4 || allThinLineNodes(allNodes) {
		return false
	}
	box := unionNodeBBox(allNodes)
	for _, node := range allNodes {
		if parentIsBody && axisDominantRawImage(node, box) {
			return false
		}
		if axisLargeRasterLikeNode(node, box) {
			largeRasterCount++
		}
		if axisLargeRasterLikeNode(node, box) && area(node.BBox) >= max(1, area(box)*45/100) {
			return false
		}
	}
	if largeRasterCount > 2 {
		return false
	}
	if parentIsBody {
		if parentBox.Height > 0 && box.Height > max(1, parentBox.Height*28/100) {
			return false
		}
		if parentBox.Width > 0 && box.Width > max(1, parentBox.Width*96/100) &&
			parentBox.Height > 0 && box.Height > max(1, parentBox.Height*12/100) {
			return false
		}
	}
	if !axisRowsAreContinuous(rows) {
		return false
	}
	if repeatedXLaneCount(rows) < 2 && !rowsHaveSimilarSpan(rows) {
		return false
	}
	return true
}

func singleRowGroupBucket(row axisRowBucket) bool {
	return len(row.nodes) == 1 && row.nodes[0].Meta.Synthetic && row.nodes[0].Meta.GroupKind == "row_group"
}

func axisEffectiveMemberCount(node Node) int {
	if node.Meta.Synthetic && node.Meta.GroupKind == "row_group" && len(node.Children) > 0 {
		return len(node.Children)
	}
	return 1
}

func axisNodeEffectiveMemberCount(nodes []Node) int {
	count := 0
	for _, node := range nodes {
		count += axisEffectiveMemberCount(node)
	}
	return count
}

func axisRowsAreContinuous(rows []axisRowBucket) bool {
	if len(rows) < 2 {
		return false
	}
	gaps := make([]int, 0, len(rows)-1)
	for i := 1; i < len(rows); i++ {
		gap := rows[i].box.Y - (rows[i-1].box.Y + rows[i-1].box.Height)
		gaps = append(gaps, max(0, gap))
	}
	medianGap := medianInt(gaps)
	maxRowHeight := 1
	for _, row := range rows {
		maxRowHeight = max(maxRowHeight, row.box.Height)
	}
	limit := max(maxRowHeight*3, medianGap*3+16)
	for _, gap := range gaps {
		if gap > limit {
			return false
		}
	}
	return true
}

func repeatedXLaneCount(rows []axisRowBucket) int {
	laneCounts := map[int]int{}
	for _, row := range rows {
		seen := map[int]bool{}
		for _, node := range axisLaneNodes(row) {
			lane := quantizeLane(centerX(node))
			seen[lane] = true
		}
		for lane := range seen {
			laneCounts[lane]++
		}
	}
	repeated := 0
	for _, count := range laneCounts {
		if count >= 2 {
			repeated++
		}
	}
	return repeated
}

func axisLaneNodes(row axisRowBucket) []Node {
	var out []Node
	for _, node := range row.nodes {
		if node.Meta.Synthetic && node.Meta.GroupKind == "row_group" && len(node.Children) > 0 {
			out = append(out, node.Children...)
			continue
		}
		out = append(out, node)
	}
	return out
}

func rowsHaveSimilarSpan(rows []axisRowBucket) bool {
	if len(rows) < 2 {
		return false
	}
	base := rows[0].box
	tolerance := max(12, base.Width/8)
	matches := 1
	for _, row := range rows[1:] {
		if abs(row.box.X-base.X) <= tolerance &&
			abs((row.box.X+row.box.Width)-(base.X+base.Width)) <= tolerance {
			matches++
		}
	}
	return matches >= 2
}

func axisWindowMemberIDs(rows []axisRowBucket) []string {
	ids := map[string]bool{}
	for _, row := range rows {
		for _, node := range row.nodes {
			ids[node.ID] = true
		}
	}
	return sortedKeys(ids)
}

func centerX(node Node) int {
	return node.BBox.X + node.BBox.Width/2
}

func centerYOfBox(box contract.BBox) int {
	return box.Y + box.Height/2
}

func quantizeLane(value int) int {
	return int(float64(value)/24.0 + 0.5)
}

func axisLargeRasterLikeNode(node Node, groupBox contract.BBox) bool {
	if node.Meta.Synthetic {
		return false
	}
	return isLargeRasterLikeNode(node, groupBox)
}

func axisDominantRawImage(node Node, groupBox contract.BBox) bool {
	if node.Meta.Synthetic || node.Type != "Image" {
		return false
	}
	groupArea := max(1, area(groupBox))
	if area(node.BBox) >= groupArea*25/100 {
		return true
	}
	return node.BBox.Height >= max(1, groupBox.Height*60/100) &&
		node.BBox.Width >= max(1, groupBox.Width*30/100)
}
