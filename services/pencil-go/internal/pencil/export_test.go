package pencil

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/contract"
)

func TestExportModesPreserveTextContracts(t *testing.T) {
	tmp := t.TempDir()
	m29Dir := filepath.Join(tmp, "m29")
	if err := os.MkdirAll(filepath.Join(m29Dir, "crops"), 0o755); err != nil {
		t.Fatal(err)
	}
	writeSolidPNG(t, filepath.Join(m29Dir, "crops", "text.png"), 40, 16, color.RGBA{R: 10, G: 20, B: 30, A: 255})
	writeSolidPNG(t, filepath.Join(m29Dir, "crops", "surface.png"), 80, 32, color.RGBA{R: 30, G: 90, B: 200, A: 255})
	doc := contract.Document{
		Image:       contract.ImageInfo{Width: 100, Height: 80, SourcePath: "source.png"},
		Diagnostics: contract.Diagnostics{BackgroundColor: "#FFFFFF"},
		Primitives: []contract.Primitive{
			{ID: "prim_0001", PrimitiveType: "surface_region", BBox: contract.BBox{X: 0, Y: 0, Width: 80, Height: 32}, CropRef: "crops/surface.png"},
			{ID: "prim_0002", PrimitiveType: "text_region", BBox: contract.BBox{X: 10, Y: 8, Width: 40, Height: 16}, CropRef: "crops/text.png", Source: contract.Source{Kind: "ocr", Text: "提交"}},
		},
	}
	for _, tc := range []struct {
		mode      Mode
		textNodes int
		cropText  int
	}{
		{ModeCleanEditable, 1, 0},
		{ModeVisualFidelity, 0, 1},
		{ModeVisualOCR, 1, 1},
	} {
		result, err := ExportMode(ExportOptions{InputDir: m29Dir, OutputDir: filepath.Join(tmp, string(tc.mode)), Name: string(tc.mode), IDPrefix: "page_0001", AssetPageDir: "page_0001"}, doc, tc.mode)
		if err != nil {
			t.Fatalf("%s export: %v", tc.mode, err)
		}
		if result.Manifest.TextNodes != tc.textNodes || result.Manifest.CropTextNodes != tc.cropText {
			t.Fatalf("%s counts text=%d cropText=%d", tc.mode, result.Manifest.TextNodes, result.Manifest.CropTextNodes)
		}
		if len(result.Document.Children) != 1 {
			t.Fatalf("%s frame count = %d", tc.mode, len(result.Document.Children))
		}
	}
}

func TestDilateMaskCanWriteFutureRows(t *testing.T) {
	mask := [][]bool{
		{false, true, false},
		{false, false, false},
		{false, false, false},
	}
	out := dilateMask(mask)
	if !out[1][1] {
		t.Fatalf("expected dilation into next row")
	}
}

func writeSolidPNG(t *testing.T, path string, w, h int, c color.RGBA) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			img.SetRGBA(x, y, c)
		}
	}
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := png.Encode(f, img); err != nil {
		t.Fatal(err)
	}
}
