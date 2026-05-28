package relation

import "math"

func area(b bbox) int {
	return max(0, b.Width) * max(0, b.Height)
}

func intersection(a, b bbox) int {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	return area(bbox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1})
}

func iou(a, b bbox) float64 {
	inter := intersection(a, b)
	if inter == 0 {
		return 0
	}
	union := area(a) + area(b) - inter
	if union <= 0 {
		return 0
	}
	return round4(float64(inter) / float64(union))
}

func childCoverage(parent, child bbox) float64 {
	childArea := area(child)
	if childArea == 0 {
		return 0
	}
	return round4(float64(intersection(parent, child)) / float64(childArea))
}

func parentCoverage(parent, child bbox) float64 {
	parentArea := area(parent)
	if parentArea == 0 {
		return 0
	}
	return round4(float64(intersection(parent, child)) / float64(parentArea))
}

func contains(parent, child bbox, tolerance int) bool {
	return parent.X-tolerance <= child.X &&
		parent.Y-tolerance <= child.Y &&
		parent.X+parent.Width+tolerance >= child.X+child.Width &&
		parent.Y+parent.Height+tolerance >= child.Y+child.Height
}

func horizontalOverlapRatio(a, b bbox) float64 {
	left := max(a.X, b.X)
	right := min(a.X+a.Width, b.X+b.Width)
	overlap := max(0, right-left)
	base := min(a.Width, b.Width)
	if base <= 0 {
		return 0
	}
	return round4(float64(overlap) / float64(base))
}

func verticalOverlapRatio(a, b bbox) float64 {
	top := max(a.Y, b.Y)
	bottom := min(a.Y+a.Height, b.Y+b.Height)
	overlap := max(0, bottom-top)
	base := min(a.Height, b.Height)
	if base <= 0 {
		return 0
	}
	return round4(float64(overlap) / float64(base))
}

func edgeGapX(a, b bbox) int {
	a2 := a.X + a.Width
	b2 := b.X + b.Width
	if a2 < b.X {
		return b.X - a2
	}
	if b2 < a.X {
		return a.X - b2
	}
	return 0
}

func edgeGapY(a, b bbox) int {
	a2 := a.Y + a.Height
	b2 := b.Y + b.Height
	if a2 < b.Y {
		return b.Y - a2
	}
	if b2 < a.Y {
		return a.Y - b2
	}
	return 0
}

func centerDistance(a, b bbox) float64 {
	ax := float64(a.X) + float64(a.Width)/2
	ay := float64(a.Y) + float64(a.Height)/2
	bx := float64(b.X) + float64(b.Width)/2
	by := float64(b.Y) + float64(b.Height)/2
	return round2(math.Sqrt((ax-bx)*(ax-bx) + (ay-by)*(ay-by)))
}

func areaRatio(a, b bbox) float64 {
	aa := area(a)
	ba := area(b)
	if aa == 0 || ba == 0 {
		return 0
	}
	smaller := min(aa, ba)
	larger := max(aa, ba)
	return round4(float64(smaller) / float64(larger))
}

func relationMetrics(a, b bbox) Metrics {
	inter := intersection(a, b)
	intersectionRatio := 0.0
	smaller := min(area(a), area(b))
	if smaller > 0 {
		intersectionRatio = round4(float64(inter) / float64(smaller))
	}
	return Metrics{
		IntersectionRatio:      intersectionRatio,
		IoU:                    iou(a, b),
		ChildCoverage:          childCoverage(a, b),
		ParentCoverage:         parentCoverage(a, b),
		HorizontalOverlapRatio: horizontalOverlapRatio(a, b),
		VerticalOverlapRatio:   verticalOverlapRatio(a, b),
		GapX:                   edgeGapX(a, b),
		GapY:                   edgeGapY(a, b),
		CenterDistance:         centerDistance(a, b),
		AreaRatio:              areaRatio(a, b),
	}
}

func round2(value float64) float64 {
	return math.Round(value*100) / 100
}

func round4(value float64) float64 {
	return math.Round(value*10000) / 10000
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
