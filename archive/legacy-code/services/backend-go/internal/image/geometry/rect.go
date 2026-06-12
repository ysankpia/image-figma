package geometry

type Rect struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

func (r Rect) Right() int {
	return r.X + r.Width
}

func (r Rect) Bottom() int {
	return r.Y + r.Height
}

func (r Rect) Area() int {
	if r.Width <= 0 || r.Height <= 0 {
		return 0
	}
	return r.Width * r.Height
}

func (r Rect) Empty() bool {
	return r.Area() == 0
}

func (r Rect) Intersect(other Rect) Rect {
	x1 := max(r.X, other.X)
	y1 := max(r.Y, other.Y)
	x2 := min(r.Right(), other.Right())
	y2 := min(r.Bottom(), other.Bottom())
	if x2 <= x1 || y2 <= y1 {
		return Rect{}
	}
	return Rect{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func (r Rect) Union(other Rect) Rect {
	if r.Empty() {
		return other
	}
	if other.Empty() {
		return r
	}
	x1 := min(r.X, other.X)
	y1 := min(r.Y, other.Y)
	x2 := max(r.Right(), other.Right())
	y2 := max(r.Bottom(), other.Bottom())
	return Rect{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func IoU(a, b Rect) float64 {
	intersection := a.Intersect(b).Area()
	if intersection == 0 {
		return 0
	}
	union := a.Area() + b.Area() - intersection
	if union <= 0 {
		return 0
	}
	return float64(intersection) / float64(union)
}

func IoA(anchor, container Rect) float64 {
	area := anchor.Area()
	if area <= 0 {
		return 0
	}
	return float64(anchor.Intersect(container).Area()) / float64(area)
}

func Contains(container, child Rect) bool {
	return child.Area() > 0 && IoA(child, container) >= 1
}

func Clamp(r Rect, bounds Rect) Rect {
	return r.Intersect(bounds)
}
