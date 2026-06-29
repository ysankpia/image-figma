package primitive

import (
	"fmt"
	"image"
	"math"
	"sort"

	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/components"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/contract"
)

type RGB struct {
	R uint8
	G uint8
	B uint8
}

func EstimateBackground(img image.Image) (RGB, float64) {
	b := img.Bounds()
	samples := make([]RGB, 0, b.Dx()*2+b.Dy()*2)
	step := max(1, min(b.Dx(), b.Dy())/160)
	for x := b.Min.X; x < b.Max.X; x += step {
		samples = append(samples, rgbAt(img, x, b.Min.Y), rgbAt(img, x, b.Max.Y-1))
	}
	for y := b.Min.Y; y < b.Max.Y; y += step {
		samples = append(samples, rgbAt(img, b.Min.X, y), rgbAt(img, b.Max.X-1, y))
	}
	bg := medianRGB(samples)
	distances := make([]float64, 0, len(samples))
	for _, sample := range samples {
		distances = append(distances, ColorDistance(sample, bg))
	}
	sort.Float64s(distances)
	p95 := percentile(distances, 0.95)
	threshold := clampFloat(maxFloat(18, p95*2.2), 18, 52)
	return bg, threshold
}

func MeasureComponent(img image.Image, component components.Component, bg RGB) contract.Measurements {
	bboxArea := component.BBox.Width * component.BBox.Height
	fill := 0.0
	if bboxArea > 0 {
		fill = float64(component.Area) / float64(bboxArea)
	}
	sumR, sumG, sumB := 0, 0, 0
	colors := map[string]struct{}{}
	for _, p := range component.Pixels {
		rgb := rgbAt(img, p.X, p.Y)
		sumR += int(rgb.R)
		sumG += int(rgb.G)
		sumB += int(rgb.B)
		colors[quantizedColorKey(rgb)] = struct{}{}
	}
	mean := RGB{}
	if component.Area > 0 {
		mean = RGB{R: uint8(sumR / component.Area), G: uint8(sumG / component.Area), B: uint8(sumB / component.Area)}
	}
	edgeDensity := EdgeDensity(img, component.BBox)
	colorCount := len(colors)
	texture := clampFloat(edgeDensity+float64(colorCount)/96.0, 0, 1)
	return contract.Measurements{
		Area:                 component.Area,
		FillRatio:            round4(fill),
		MeanColor:            Hex(mean),
		ColorCount:           colorCount,
		EdgeDensity:          round4(edgeDensity),
		TextureScore:         round4(texture),
		LocalContrast:        round2(ColorDistance(mean, bg)),
		CornerRadiusEstimate: 0,
	}
}

func EdgeDensity(img image.Image, bbox contract.BBox) float64 {
	if bbox.Width <= 2 || bbox.Height <= 2 {
		return 0
	}
	total := 0
	edge := 0
	for y := bbox.Y + 1; y < bbox.Y+bbox.Height-1; y++ {
		for x := bbox.X + 1; x < bbox.X+bbox.Width-1; x++ {
			gx := math.Abs(grayAt(img, x+1, y) - grayAt(img, x-1, y))
			gy := math.Abs(grayAt(img, x, y+1) - grayAt(img, x, y-1))
			total++
			if gx+gy > 48 {
				edge++
			}
		}
	}
	if total == 0 {
		return 0
	}
	return float64(edge) / float64(total)
}

func ColorDistance(a, b RGB) float64 {
	dr := float64(a.R) - float64(b.R)
	dg := float64(a.G) - float64(b.G)
	db := float64(a.B) - float64(b.B)
	return math.Sqrt(dr*dr + dg*dg + db*db)
}

func Hex(c RGB) string {
	return fmt.Sprintf("#%02x%02x%02x", c.R, c.G, c.B)
}

func RGBAt(img image.Image, x, y int) RGB {
	return rgbAt(img, x, y)
}

func rgbAt(img image.Image, x, y int) RGB {
	r, g, b, _ := img.At(x, y).RGBA()
	return RGB{R: uint8(r >> 8), G: uint8(g >> 8), B: uint8(b >> 8)}
}

func grayAt(img image.Image, x, y int) float64 {
	c := rgbAt(img, x, y)
	return 0.299*float64(c.R) + 0.587*float64(c.G) + 0.114*float64(c.B)
}

func medianRGB(samples []RGB) RGB {
	if len(samples) == 0 {
		return RGB{R: 255, G: 255, B: 255}
	}
	rs := make([]int, len(samples))
	gs := make([]int, len(samples))
	bs := make([]int, len(samples))
	for i, sample := range samples {
		rs[i] = int(sample.R)
		gs[i] = int(sample.G)
		bs[i] = int(sample.B)
	}
	sort.Ints(rs)
	sort.Ints(gs)
	sort.Ints(bs)
	mid := len(samples) / 2
	return RGB{R: uint8(rs[mid]), G: uint8(gs[mid]), B: uint8(bs[mid])}
}

func percentile(values []float64, p float64) float64 {
	if len(values) == 0 {
		return 0
	}
	idx := int(math.Round(float64(len(values)-1) * p))
	if idx < 0 {
		idx = 0
	}
	if idx >= len(values) {
		idx = len(values) - 1
	}
	return values[idx]
}

func quantizedColorKey(c RGB) string {
	return string([]byte{c.R >> 4, c.G >> 4, c.B >> 4})
}

func round2(v float64) float64 {
	return math.Round(v*100) / 100
}

func round4(v float64) float64 {
	return math.Round(v*10000) / 10000
}

func clampFloat(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func maxFloat(a, b float64) float64 {
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

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
