package visualtree

import (
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

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

func isThinLineNode(node Node) bool {
	return node.BBox.Height <= 2 || node.BBox.Width <= 2
}

func centerY(node Node) int {
	return node.BBox.Y + node.BBox.Height/2
}

func medianInt(values []int) int {
	if len(values) == 0 {
		return 0
	}
	sorted := append([]int(nil), values...)
	sort.Ints(sorted)
	return sorted[len(sorted)/2]
}

func sortedKeys(values map[string]bool) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func abs(value int) int {
	if value < 0 {
		return -value
	}
	return value
}
