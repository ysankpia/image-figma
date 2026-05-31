package layoutcompile

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestRunWritesStageOneArtifacts(t *testing.T) {
	dir := t.TempDir()
	input := filepath.Join(dir, "source.png")
	writeTestPNG(t, input, 17, 23)

	out := filepath.Join(dir, "out")
	result, err := Run(Options{
		InputPath: input,
		OutputDir: out,
		TaskID:    "task_test",
	})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if result.Document.Version != contract.Version {
		t.Fatalf("version = %q, want %q", result.Document.Version, contract.Version)
	}
	if result.Document.SourceImage.Width != 17 || result.Document.SourceImage.Height != 23 {
		t.Fatalf("source image size = %dx%d", result.Document.SourceImage.Width, result.Document.SourceImage.Height)
	}
	if result.Document.Root.Type != contract.NodePage {
		t.Fatalf("root type = %q, want page", result.Document.Root.Type)
	}
	if result.Validation.ErrorCount != 0 {
		t.Fatalf("validation errors = %+v", result.Validation.Findings)
	}
	for _, path := range []string{result.Artifacts.LayoutIR, result.Artifacts.ValidationReport, result.Artifacts.CompileReport} {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("expected artifact %s: %v", path, err)
		}
	}
}

func writeTestPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.Set(x, y, color.RGBA{R: uint8(x), G: uint8(y), B: 40, A: 255})
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create test png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode test png: %v", err)
	}
}
