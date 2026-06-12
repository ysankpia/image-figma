package pipeline

import (
	"fmt"
	"math"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func buildRelations(primitives []contract.Primitive) []contract.PhysicalRelation {
	var out []contract.PhysicalRelation
	nextID := 1
	for i := range primitives {
		for j := range primitives {
			if i == j {
				continue
			}
			a := primitives[i]
			b := primitives[j]
			if contains(a.BBox, b.BBox, 2) && area(a.BBox) > area(b.BBox) {
				out = append(out, contract.PhysicalRelation{
					ID:     fmt.Sprintf("rel_%04d", nextID),
					Kind:   "contains_bbox",
					FromID: a.ID,
					ToID:   b.ID,
					Ratio:  intersectionRatio(a.BBox, b.BBox),
				})
				nextID++
				continue
			}
			if a.PrimitiveType != "text_region" && b.PrimitiveType == "text_region" {
				d := bboxDistance(a.BBox, b.BBox)
				if d <= 12 {
					out = append(out, contract.PhysicalRelation{
						ID:       fmt.Sprintf("rel_%04d", nextID),
						Kind:     "near_text",
						FromID:   a.ID,
						ToID:     b.ID,
						Distance: d,
					})
					nextID++
				}
			}
		}
	}
	return out
}

func contains(parent, child contract.BBox, tolerance int) bool {
	return parent.X-tolerance <= child.X &&
		parent.Y-tolerance <= child.Y &&
		parent.X+parent.Width+tolerance >= child.X+child.Width &&
		parent.Y+parent.Height+tolerance >= child.Y+child.Height
}

func area(b contract.BBox) int {
	return max(0, b.Width) * max(0, b.Height)
}

func intersectionRatio(a, b contract.BBox) float64 {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	inter := area(contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1})
	if area(b) == 0 {
		return 0
	}
	return math.Round(float64(inter)/float64(area(b))*10000) / 10000
}

func bboxDistance(a, b contract.BBox) float64 {
	ax2, ay2 := a.X+a.Width, a.Y+a.Height
	bx2, by2 := b.X+b.Width, b.Y+b.Height
	dx := max(max(b.X-ax2, a.X-bx2), 0)
	dy := max(max(b.Y-ay2, a.Y-by2), 0)
	return math.Round(math.Sqrt(float64(dx*dx+dy*dy))*100) / 100
}
