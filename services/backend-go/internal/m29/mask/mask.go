package mask

import "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"

type Mask struct {
	Width  int
	Height int
	Data   []bool
}

func New(width, height int) Mask {
	return Mask{Width: width, Height: height, Data: make([]bool, width*height)}
}

func (m Mask) InBounds(x, y int) bool {
	return x >= 0 && y >= 0 && x < m.Width && y < m.Height
}

func (m Mask) Get(x, y int) bool {
	if !m.InBounds(x, y) {
		return false
	}
	return m.Data[y*m.Width+x]
}

func (m Mask) Set(x, y int, value bool) {
	if m.InBounds(x, y) {
		m.Data[y*m.Width+x] = value
	}
}

func (m Mask) Count() int {
	total := 0
	for _, value := range m.Data {
		if value {
			total++
		}
	}
	return total
}

func FillBBox(m Mask, bbox contract.BBox, padding int) {
	x1 := max(0, bbox.X-padding)
	y1 := max(0, bbox.Y-padding)
	x2 := min(m.Width, bbox.X+bbox.Width+padding)
	y2 := min(m.Height, bbox.Y+bbox.Height+padding)
	for y := y1; y < y2; y++ {
		for x := x1; x < x2; x++ {
			m.Set(x, y, true)
		}
	}
}

func BBoxMask(width, height int, bbox contract.BBox) Mask {
	m := New(width, height)
	FillBBox(m, bbox, 0)
	return m
}
