package batch

import (
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"testing"
)

func TestRunWritesSummaryAndReview(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	inputDir := filepath.Join(tmp, "inputs")
	if err := os.MkdirAll(inputDir, 0o755); err != nil {
		t.Fatal(err)
	}
	writePNG(t, filepath.Join(inputDir, "a.png"))
	writePNG(t, filepath.Join(inputDir, "b.png"))
	out := filepath.Join(tmp, "out")

	summary, err := Run(Options{InputDir: inputDir, OutputDir: out, Limit: 1})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if summary.CaseCount != 1 || summary.CompletedCount != 1 || summary.FailedCount != 0 {
		t.Fatalf("unexpected summary: %#v", summary)
	}
	assertExists(t, filepath.Join(out, "summary.json"))
	assertExists(t, filepath.Join(out, "review.md"))
	assertExists(t, filepath.Join(summary.Cases[0].OutputDir, "m29_physical_evidence.v1.json"))
	assertExists(t, filepath.Join(summary.Cases[0].OutputDir, "preview_sheet.png"))
}

func writePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 80, 60))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 250, G: 250, B: 250, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(10, 10, 50, 30), &image.Uniform{C: color.RGBA{R: 20, G: 80, B: 160, A: 255}}, image.Point{}, draw.Src)
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatal(err)
	}
}

func assertExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
}
