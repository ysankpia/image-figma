package unifiedvision

import (
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func flowRole(role string) bool {
	switch strings.ToLower(strings.TrimSpace(role)) {
	case "text", "textview", "icon", "image", "imageview":
		return true
	default:
		return false
	}
}

func textRole(role string) bool {
	switch strings.ToLower(strings.TrimSpace(role)) {
	case "text", "textview":
		return true
	default:
		return false
	}
}

func centerInside(container geometry.Rect, child geometry.Rect) bool {
	if container.Empty() || child.Empty() {
		return false
	}
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return cx >= container.X && cx <= container.Right() && cy >= container.Y && cy <= container.Bottom()
}

func clamp(box geometry.Rect, bounds geometry.Rect) geometry.Rect {
	return geometry.Clamp(box, bounds)
}

func expand(box geometry.Rect, n int) geometry.Rect {
	return geometry.Rect{X: box.X - n, Y: box.Y - n, Width: box.Width + n*2, Height: box.Height + n*2}
}

func localBBox(box geometry.Rect, crop geometry.Rect) geometry.Rect {
	return geometry.Rect{X: box.X - crop.X, Y: box.Y - crop.Y, Width: box.Width, Height: box.Height}
}

func sortEvidence(items []EvidenceItem) {
	sort.SliceStable(items, func(i, j int) bool {
		a, b := items[i].BBox, items[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return items[i].ID < items[j].ID
	})
}

func sortNodes(nodes []contract.Node) {
	sort.SliceStable(nodes, func(i, j int) bool {
		a, b := nodes[i].BBox, nodes[j].BBox
		if a.X != b.X {
			return a.X < b.X
		}
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		return nodes[i].ID < nodes[j].ID
	})
}

func median(values []int) int {
	if len(values) == 0 {
		return 0
	}
	out := append([]int(nil), values...)
	sort.Ints(out)
	mid := len(out) / 2
	if len(out)%2 == 1 {
		return out[mid]
	}
	return (out[mid-1] + out[mid]) / 2
}

func variance(values []int) int {
	if len(values) <= 1 {
		return 0
	}
	mean := 0
	for _, value := range values {
		mean += value
	}
	mean /= len(values)
	total := 0
	for _, value := range values {
		delta := value - mean
		total += delta * delta
	}
	return total / len(values)
}

func maxInt(a int, b int) int {
	if a > b {
		return a
	}
	return b
}

func minInt(a int, b int) int {
	if a < b {
		return a
	}
	return b
}

func unionEvidence(items []EvidenceItem) geometry.Rect {
	var out geometry.Rect
	for _, item := range items {
		out = out.Union(item.BBox)
	}
	return out
}

func unionNodes(nodes []contract.Node) geometry.Rect {
	var out geometry.Rect
	for _, node := range nodes {
		out = out.Union(node.BBox)
	}
	return out
}

func normalizedIDs(ids []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		value := strings.TrimSpace(id)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func intMeta(node contract.Node, key string) int {
	if node.Meta == nil {
		return 0
	}
	value := strings.TrimSpace(node.Meta[key])
	if value == "" {
		return 0
	}
	out, err := strconv.Atoi(value)
	if err != nil {
		return 0
	}
	return out
}

func sourceRefs(ids []string, role string) []contract.SourceRef {
	refs := make([]contract.SourceRef, 0, len(ids))
	for _, id := range ids {
		refs = append(refs, contract.SourceRef{Kind: "layout_evidence", ID: id, Role: role})
	}
	return refs
}

func groupID(batchID string, index int, value string) string {
	value = strings.TrimSpace(value)
	if value != "" {
		return value
	}
	return fmt.Sprintf("%s_group_%04d", batchID, index+1)
}

func validHexColor(value string) bool {
	value = strings.TrimSpace(value)
	if len(value) != 7 || value[0] != '#' {
		return false
	}
	for _, r := range value[1:] {
		if (r >= '0' && r <= '9') || (r >= 'a' && r <= 'f') || (r >= 'A' && r <= 'F') {
			continue
		}
		return false
	}
	return true
}
