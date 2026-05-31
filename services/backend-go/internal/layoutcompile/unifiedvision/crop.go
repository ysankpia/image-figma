package unifiedvision

import (
	"image"
	"image/draw"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

func cropImage(src image.Image, box geometry.Rect) image.Image {
	if src == nil || box.Empty() {
		return image.NewRGBA(image.Rect(0, 0, 1, 1))
	}
	bounds := src.Bounds()
	clamped := geometry.Clamp(box, geometry.Rect{Width: bounds.Dx(), Height: bounds.Dy()})
	if clamped.Empty() {
		return image.NewRGBA(image.Rect(0, 0, 1, 1))
	}
	out := image.NewRGBA(image.Rect(0, 0, clamped.Width, clamped.Height))
	draw.Draw(out, out.Bounds(), src, image.Point{X: bounds.Min.X + clamped.X, Y: bounds.Min.Y + clamped.Y}, draw.Src)
	return out
}
