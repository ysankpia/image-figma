package components

import (
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/contract"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/mask"
)

type Component struct {
	ID     int
	BBox   contract.BBox
	Area   int
	Pixels []Point
}

type Point struct {
	X int
	Y int
}

func ConnectedComponents(fg mask.Mask, minArea int, maxAreaRatio float64) []Component {
	visited := make([]bool, len(fg.Data))
	var out []Component
	maxArea := int(float64(fg.Width*fg.Height) * maxAreaRatio)
	nextID := 1
	for y := 0; y < fg.Height; y++ {
		for x := 0; x < fg.Width; x++ {
			idx := y*fg.Width + x
			if visited[idx] || !fg.Data[idx] {
				continue
			}
			component := flood(nextID, fg, visited, x, y)
			if component.Area >= minArea && (maxArea <= 0 || component.Area <= maxArea) {
				out = append(out, component)
				nextID++
			}
		}
	}
	return out
}

func flood(id int, fg mask.Mask, visited []bool, sx, sy int) Component {
	queue := []Point{{X: sx, Y: sy}}
	visited[sy*fg.Width+sx] = true
	minX, maxX := sx, sx
	minY, maxY := sy, sy
	pixels := make([]Point, 0, 128)
	for len(queue) > 0 {
		p := queue[0]
		queue = queue[1:]
		pixels = append(pixels, p)
		if p.X < minX {
			minX = p.X
		}
		if p.X > maxX {
			maxX = p.X
		}
		if p.Y < minY {
			minY = p.Y
		}
		if p.Y > maxY {
			maxY = p.Y
		}
		for _, next := range [...]Point{{p.X + 1, p.Y}, {p.X - 1, p.Y}, {p.X, p.Y + 1}, {p.X, p.Y - 1}} {
			if !fg.InBounds(next.X, next.Y) {
				continue
			}
			idx := next.Y*fg.Width + next.X
			if visited[idx] || !fg.Data[idx] {
				continue
			}
			visited[idx] = true
			queue = append(queue, next)
		}
	}
	return Component{
		ID:     id,
		Area:   len(pixels),
		Pixels: pixels,
		BBox: contract.BBox{
			X:      minX,
			Y:      minY,
			Width:  maxX - minX + 1,
			Height: maxY - minY + 1,
		},
	}
}
