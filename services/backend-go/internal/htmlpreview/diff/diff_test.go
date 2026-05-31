package diff

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRunWritesDiffAndReport(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	screenshot := filepath.Join(dir, "screenshot.png")
	preview := filepath.Join(dir, "preview.html")
	writeSolidPNG(t, source, color.RGBA{R: 10, G: 20, B: 30, A: 255})
	writeSolidPNG(t, screenshot, color.RGBA{R: 15, G: 25, B: 35, A: 255})
	if err := os.WriteFile(preview, []byte(`<img src="assets/missing.png">`), 0o644); err != nil {
		t.Fatalf("write preview: %v", err)
	}

	result, err := Run(Options{
		SourcePath:     source,
		ScreenshotPath: screenshot,
		PreviewHTML:    preview,
		OutputDir:      filepath.Join(dir, "out"),
	})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if result.Metrics.MeanChannelDiff <= 0 {
		t.Fatalf("expected non-zero diff, got %+v", result.Metrics)
	}
	if result.Metrics.ReferencedAssetCount != 1 || result.Metrics.MissingAssetCount != 1 {
		t.Fatalf("unexpected asset metrics: %+v", result.Metrics)
	}
	for _, path := range []string{result.DiffPNG, result.Report} {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("expected artifact %s: %v", path, err)
		}
	}
	report := readString(t, result.Report)
	if !strings.Contains(report, ReportVersion) || !strings.Contains(report, "missing assets") {
		t.Fatalf("report missing expected content: %s", report)
	}
}

func writeSolidPNG(t *testing.T, path string, c color.Color) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 4, 3))
	for y := 0; y < 3; y++ {
		for x := 0; x < 4; x++ {
			img.Set(x, y, c)
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
}

func readString(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(data)
}
