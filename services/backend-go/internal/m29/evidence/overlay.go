package evidence

import (
	"image"
	"image/color"
	"image/draw"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func writeTokenArtifacts(outputDir string, sourcePath string, tokens []Token) error {
	if sourcePath == "" {
		return nil
	}
	img, err := imageio.ReadPNG(sourcePath)
	if err != nil {
		return err
	}
	overlayPath := filepath.Join(outputDir, "token_overlay.png")
	if err := WriteTokenOverlay(overlayPath, img, tokens); err != nil {
		return err
	}
	return writeTokenPreviewSheet(filepath.Join(outputDir, "token_preview_sheet.png"), img, overlayPath)
}

func WriteTokenOverlay(path string, src image.Image, tokens []Token) error {
	b := src.Bounds()
	out := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(out, out.Bounds(), src, b.Min, draw.Src)
	for _, token := range tokens {
		if token.Disposition == "suppressed" {
			continue
		}
		drawBBox(out, token.BBox, colorForToken(token))
	}
	return imageio.WritePNG(path, out)
}

func writeTokenPreviewSheet(path string, src image.Image, overlayPath string) error {
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

func colorForToken(token Token) color.RGBA {
	if token.Disposition == "review" {
		return color.RGBA{R: 145, G: 145, B: 145, A: 255}
	}
	switch token.TokenType {
	case "text_token":
		return color.RGBA{R: 20, G: 110, B: 255, A: 255}
	case "layer_background_token":
		return color.RGBA{R: 20, G: 190, B: 90, A: 255}
	case "surface_region_token":
		return color.RGBA{R: 40, G: 210, B: 170, A: 255}
	case "raster_region_token":
		return color.RGBA{R: 230, G: 60, B: 60, A: 255}
	case "symbol_cluster_token":
		return color.RGBA{R: 165, G: 65, B: 225, A: 255}
	case "line_token":
		return color.RGBA{R: 255, G: 170, B: 0, A: 255}
	case "unknown_token":
		return color.RGBA{R: 120, G: 120, B: 120, A: 255}
	default:
		return color.RGBA{R: 255, G: 255, B: 255, A: 255}
	}
}
