package evidence

import (
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func TestWriteTokenOverlayDrawsReviewTokensGrayAndSkipsSuppressed(t *testing.T) {
	tmp := t.TempDir()
	src := image.NewRGBA(image.Rect(0, 0, 40, 30))
	draw.Draw(src, src.Bounds(), &image.Uniform{C: color.RGBA{R: 250, G: 250, B: 250, A: 255}}, image.Point{}, draw.Src)
	outPath := filepath.Join(tmp, "overlay.png")

	err := WriteTokenOverlay(outPath, src, []Token{
		{TokenType: "symbol_cluster_token", Disposition: "main", BBox: contract.BBox{X: 2, Y: 2, Width: 10, Height: 8}},
		{TokenType: "symbol_cluster_token", Disposition: "review", BBox: contract.BBox{X: 15, Y: 2, Width: 10, Height: 8}},
		{TokenType: "symbol_cluster_token", Disposition: "suppressed", BBox: contract.BBox{X: 28, Y: 2, Width: 8, Height: 8}},
	})
	if err != nil {
		t.Fatalf("WriteTokenOverlay() error = %v", err)
	}

	file, err := os.Open(outPath)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	img, err := png.Decode(file)
	if err != nil {
		t.Fatal(err)
	}
	assertPixel(t, img, 2, 2, color.RGBA{R: 165, G: 65, B: 225, A: 255})
	assertPixel(t, img, 15, 2, color.RGBA{R: 145, G: 145, B: 145, A: 255})
	assertPixel(t, img, 28, 2, color.RGBA{R: 250, G: 250, B: 250, A: 255})
}

func assertPixel(t *testing.T, img image.Image, x int, y int, expected color.RGBA) {
	t.Helper()
	got := color.RGBAModel.Convert(img.At(x, y)).(color.RGBA)
	if got != expected {
		t.Fatalf("pixel (%d,%d) = %#v, expected %#v", x, y, got, expected)
	}
}
