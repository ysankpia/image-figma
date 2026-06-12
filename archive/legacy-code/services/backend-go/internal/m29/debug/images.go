package debug

import (
	"image"
	"image/color"
	"image/draw"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/mask"
)

func WriteMaskPNG(path string, m mask.Mask) error {
	img := image.NewGray(image.Rect(0, 0, m.Width, m.Height))
	for y := 0; y < m.Height; y++ {
		for x := 0; x < m.Width; x++ {
			if m.Get(x, y) {
				img.SetGray(x, y, color.Gray{Y: 255})
			}
		}
	}
	return imageio.WritePNG(path, img)
}

func WriteOverlay(path string, src image.Image, primitives []contract.Primitive) error {
	b := src.Bounds()
	out := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(out, out.Bounds(), src, b.Min, draw.Src)
	for _, p := range primitives {
		drawBBox(out, p.BBox, colorForType(p.PrimitiveType))
	}
	return imageio.WritePNG(path, out)
}

func WritePreviewSheet(path string, src image.Image, overlayPath string) error {
	overlay, err := imageio.ReadPNG(overlayPath)
	if err != nil {
		return err
	}
	srcBounds := src.Bounds()
	overlayBounds := overlay.Bounds()
	width := srcBounds.Dx() + overlayBounds.Dx()
	height := max(srcBounds.Dy(), overlayBounds.Dy())
	out := image.NewRGBA(image.Rect(0, 0, width, height))
	draw.Draw(out, image.Rect(0, 0, srcBounds.Dx(), srcBounds.Dy()), src, srcBounds.Min, draw.Src)
	draw.Draw(out, image.Rect(srcBounds.Dx(), 0, width, overlayBounds.Dy()), overlay, overlayBounds.Min, draw.Src)
	return imageio.WritePNG(path, out)
}

func drawBBox(img *image.RGBA, bbox contract.BBox, c color.RGBA) {
	x1 := max(0, bbox.X)
	y1 := max(0, bbox.Y)
	x2 := min(img.Bounds().Dx()-1, bbox.X+bbox.Width-1)
	y2 := min(img.Bounds().Dy()-1, bbox.Y+bbox.Height-1)
	if x2 < x1 || y2 < y1 {
		return
	}
	for x := x1; x <= x2; x++ {
		img.SetRGBA(x, y1, c)
		img.SetRGBA(x, y2, c)
	}
	for y := y1; y <= y2; y++ {
		img.SetRGBA(x1, y, c)
		img.SetRGBA(x2, y, c)
	}
}

func colorForType(kind string) color.RGBA {
	switch kind {
	case "text_region":
		return color.RGBA{R: 40, G: 110, B: 255, A: 255}
	case "rect":
		return color.RGBA{R: 20, G: 180, B: 80, A: 255}
	case "surface_region":
		return color.RGBA{R: 40, G: 210, B: 170, A: 255}
	case "line":
		return color.RGBA{R: 255, G: 160, B: 0, A: 255}
	case "image_region":
		return color.RGBA{R: 230, G: 60, B: 60, A: 255}
	case "symbol_region":
		return color.RGBA{R: 150, G: 60, B: 210, A: 255}
	default:
		return color.RGBA{R: 120, G: 120, B: 120, A: 255}
	}
}
