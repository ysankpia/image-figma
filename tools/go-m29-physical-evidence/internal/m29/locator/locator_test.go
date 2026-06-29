package locator

import (
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/contract"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/imageio"
)

func TestRunWritesLocationJsonAndCrops(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	img := image.NewRGBA(image.Rect(0, 0, 80, 60))
	draw.Draw(img, img.Bounds(), image.NewUniform(color.White), image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(10, 12, 30, 26), image.NewUniform(color.Black), image.Point{}, draw.Src)
	if err := imageio.WritePNG(input, img); err != nil {
		t.Fatal(err)
	}

	doc, err := Run(Options{InputPath: input, OutputDir: filepath.Join(tmp, "out")})
	if err != nil {
		t.Fatal(err)
	}
	if doc.SchemaName != "M29Locations" {
		t.Fatalf("schema = %q", doc.SchemaName)
	}
	if len(doc.Items) != 1 {
		t.Fatalf("item count = %d", len(doc.Items))
	}
	want := contract.BBox{X: 10, Y: 12, Width: 20, Height: 14}
	if doc.Items[0].BBox != want {
		t.Fatalf("bbox = %#v, want %#v", doc.Items[0].BBox, want)
	}
	if _, err := os.Stat(filepath.Join(tmp, "out", doc.Items[0].CropPath)); err != nil {
		t.Fatalf("crop missing: %v", err)
	}

	data, err := os.ReadFile(filepath.Join(tmp, "out", OutputName))
	if err != nil {
		t.Fatal(err)
	}
	var disk contract.Document
	if err := json.Unmarshal(data, &disk); err != nil {
		t.Fatal(err)
	}
	if len(disk.Items) != 1 || disk.Items[0].BBox != want {
		t.Fatalf("disk bbox = %#v", disk.Items)
	}
}
