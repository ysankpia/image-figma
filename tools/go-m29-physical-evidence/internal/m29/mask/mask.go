package mask

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
