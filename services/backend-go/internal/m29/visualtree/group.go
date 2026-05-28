package visualtree

import (
	"fmt"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/relation"
)

func applyVisualGroups(node *Node, relations []relation.Relation, counter *int) {
	for i := range node.Children {
		applyVisualGroups(&node.Children[i], relations, counter)
	}
	if len(node.Children) < 3 {
		return
	}
	childIDs := map[string]bool{}
	for _, child := range node.Children {
		if child.Meta.Synthetic {
			continue
		}
		childIDs[child.ID] = true
	}
	if len(childIDs) < 3 {
		return
	}
	groups := candidateGroups(node.Children, childIDs, relations, node.BBox)
	if len(groups) == 0 {
		return
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
	childByID := map[string]Node{}
	for _, child := range node.Children {
		childByID[child.ID] = child
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

type visualGroup struct {
	kind        string
	memberIDs   []string
	relationIDs []string
	score       int
}

func candidateGroups(children []Node, childIDs map[string]bool, relations []relation.Relation, parentBox contract.BBox) []visualGroup {
	edges := map[string][]relation.Relation{}
	for _, rel := range relations {
		if rel.Strength == "weak" {
			continue
		}
		if !childIDs[rel.FromID] || !childIDs[rel.ToID] {
			continue
		}
		if !groupableRelation(rel.RelationType) {
			continue
		}
		edges[rel.RelationType] = append(edges[rel.RelationType], rel)
	}
	var groups []visualGroup
	groups = append(groups, connectedGroups("raster_parts_same_region", "raster_parts_group", edges["raster_parts_same_region"])...)
	groups = append(groups, connectedGroups("same_band", "band_group", edges["same_band"])...)
	groups = append(groups, rowProjectionGroups(children, parentBox)...)
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

func groupableRelation(relationType string) bool {
	switch relationType {
	case "same_band", "raster_parts_same_region":
		return true
	default:
		return false
	}
}

func rowProjectionGroups(children []Node, parentBox contract.BBox) []visualGroup {
	candidates := make([]Node, 0, len(children))
	for _, child := range children {
		if child.Meta.Synthetic || child.BBox.Width <= 0 || child.BBox.Height <= 0 {
			continue
		}
		if isThinLineNode(child) {
			continue
		}
		candidates = append(candidates, child)
	}
	if len(candidates) < 3 {
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

	used := map[string]bool{}
	var groups []visualGroup
	for i := range candidates {
		if used[candidates[i].ID] {
			continue
		}
		group := []Node{candidates[i]}
		baseline := centerY(candidates[i])
		tolerance := rowCenterTolerance(candidates[i].BBox.Height)
		for j := i + 1; j < len(candidates); j++ {
			if used[candidates[j].ID] {
				continue
			}
			if abs(centerY(candidates[j])-baseline) > tolerance {
				if centerY(candidates[j]) > baseline+tolerance {
					break
				}
				continue
			}
			group = append(group, candidates[j])
			tolerance = max(tolerance, rowCenterTolerance(candidates[j].BBox.Height))
		}
		if !validRowProjectionGroup(group, parentBox) {
			continue
		}
		memberIDs := make([]string, 0, len(group))
		for _, member := range group {
			memberIDs = append(memberIDs, member.ID)
			used[member.ID] = true
		}
		sort.Strings(memberIDs)
		groups = append(groups, visualGroup{
			kind:      "row_group",
			memberIDs: memberIDs,
			score:     groupScore("row_group"),
		})
	}
	return groups
}

func validRowProjectionGroup(nodes []Node, parentBox contract.BBox) bool {
	if len(nodes) < 3 {
		return false
	}
	box := unionNodeBBox(nodes)
	maxHeight := 0
	heights := make([]int, 0, len(nodes))
	minCenter := centerY(nodes[0])
	maxCenter := minCenter
	largeRasterCount := 0
	for _, node := range nodes {
		maxHeight = max(maxHeight, node.BBox.Height)
		heights = append(heights, node.BBox.Height)
		minCenter = min(minCenter, centerY(node))
		maxCenter = max(maxCenter, centerY(node))
		if isLargeRasterLikeNode(node, box) {
			largeRasterCount++
		}
	}
	if maxCenter-minCenter > max(8, int(float64(maxHeight)*0.45)) {
		return false
	}
	if box.Height > int(float64(maxHeight)*1.8) {
		return false
	}
	medianHeight := medianInt(heights)
	if maxHeight > 64 && medianHeight > 0 && maxHeight > int(float64(medianHeight)*3.0) {
		return false
	}
	if parentBox.Height > 0 && box.Height > max(1, parentBox.Height*8/100) {
		return false
	}
	if largeRasterCount >= 2 {
		return false
	}
	if allThinLineNodes(nodes) {
		return false
	}
	return true
}

func rowCenterTolerance(height int) int {
	return max(8, int(float64(height)*0.45))
}

func centerY(node Node) int {
	return node.BBox.Y + node.BBox.Height/2
}

func isLargeRasterLikeNode(node Node, groupBox contract.BBox) bool {
	if node.Type != "Image" && node.Type != "Layer" {
		return false
	}
	groupArea := max(1, area(groupBox))
	return area(node.BBox) >= groupArea/4 || node.BBox.Height >= max(1, groupBox.Height*3/4)
}

func isThinLineNode(node Node) bool {
	return node.BBox.Height <= 2 || node.BBox.Width <= 2
}

func allThinLineNodes(nodes []Node) bool {
	for _, node := range nodes {
		if !isThinLineNode(node) {
			return false
		}
	}
	return true
}

func abs(value int) int {
	if value < 0 {
		return -value
	}
	return value
}

func medianInt(values []int) int {
	if len(values) == 0 {
		return 0
	}
	sorted := append([]int(nil), values...)
	sort.Ints(sorted)
	return sorted[len(sorted)/2]
}

func connectedGroups(relationType string, kind string, relations []relation.Relation) []visualGroup {
	if len(relations) == 0 {
		return nil
	}
	neighbors := map[string]map[string]bool{}
	relationIDs := map[string][]string{}
	for _, rel := range relations {
		if rel.RelationType != relationType {
			continue
		}
		if neighbors[rel.FromID] == nil {
			neighbors[rel.FromID] = map[string]bool{}
		}
		if neighbors[rel.ToID] == nil {
			neighbors[rel.ToID] = map[string]bool{}
		}
		neighbors[rel.FromID][rel.ToID] = true
		neighbors[rel.ToID][rel.FromID] = true
		relationIDs[rel.FromID] = append(relationIDs[rel.FromID], rel.ID)
		relationIDs[rel.ToID] = append(relationIDs[rel.ToID], rel.ID)
	}
	visited := map[string]bool{}
	var groups []visualGroup
	for id := range neighbors {
		if visited[id] {
			continue
		}
		stack := []string{id}
		visited[id] = true
		var members []string
		relIDs := map[string]bool{}
		for len(stack) > 0 {
			last := len(stack) - 1
			current := stack[last]
			stack = stack[:last]
			members = append(members, current)
			for _, relID := range relationIDs[current] {
				relIDs[relID] = true
			}
			for next := range neighbors[current] {
				if visited[next] {
					continue
				}
				visited[next] = true
				stack = append(stack, next)
			}
		}
		if len(members) < 3 {
			continue
		}
		sort.Strings(members)
		groups = append(groups, visualGroup{
			kind:        kind,
			memberIDs:   members,
			relationIDs: sortedKeys(relIDs),
			score:       groupScore(kind),
		})
	}
	return groups
}

func buildGroupNode(group visualGroup, childByID map[string]Node, counter *int) Node {
	id := fmt.Sprintf("group_%04d", *counter)
	*counter = *counter + 1
	children := make([]Node, 0, len(group.memberIDs))
	for _, memberID := range group.memberIDs {
		children = append(children, childByID[memberID])
	}
	box := unionNodeBBox(children)
	node := Node{
		ID:   id,
		Type: "Layer",
		Name: "Layer / " + id,
		BBox: box,
		Layout: Layout{
			Mode:     "absolute",
			X:        box.X,
			Y:        box.Y,
			Width:    box.Width,
			Height:   box.Height,
			Relative: true,
		},
		SourceRefs: SourceRefs{
			TokenIDs:    group.memberIDs,
			RelationIDs: group.relationIDs,
		},
		Meta: Meta{
			Synthetic: true,
			GroupKind: group.kind,
		},
		Children: children,
	}
	refreshChildLayouts(&node)
	return node
}

func refreshChildLayouts(parent *Node) {
	for i := range parent.Children {
		child := &parent.Children[i]
		child.Layout.X = child.BBox.X - parent.BBox.X
		child.Layout.Y = child.BBox.Y - parent.BBox.Y
		child.Layout.Width = child.BBox.Width
		child.Layout.Height = child.BBox.Height
		child.Layout.Relative = parent.Type != "Body"
	}
}

func unionNodeBBox(nodes []Node) contract.BBox {
	if len(nodes) == 0 {
		return contract.BBox{}
	}
	x1 := nodes[0].BBox.X
	y1 := nodes[0].BBox.Y
	x2 := nodes[0].BBox.X + nodes[0].BBox.Width
	y2 := nodes[0].BBox.Y + nodes[0].BBox.Height
	for _, node := range nodes[1:] {
		x1 = min(x1, node.BBox.X)
		y1 = min(y1, node.BBox.Y)
		x2 = max(x2, node.BBox.X+node.BBox.Width)
		y2 = max(y2, node.BBox.Y+node.BBox.Height)
	}
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func lessNode(a Node, b Node) bool {
	if a.BBox.Y != b.BBox.Y {
		return a.BBox.Y < b.BBox.Y
	}
	if a.BBox.X != b.BBox.X {
		return a.BBox.X < b.BBox.X
	}
	return a.ID < b.ID
}

func sortedKeys(values map[string]bool) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func groupScore(kind string) int {
	switch kind {
	case "raster_parts_group":
		return 400
	case "band_group":
		return 300
	case "row_group":
		return 200
	default:
		return 100
	}
}
