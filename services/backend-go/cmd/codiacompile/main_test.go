package main

import (
	"image"
	"image/color"
	"image/draw"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func TestCodiaCompileCLIWritesEndToEndArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	ocrPath := filepath.Join(tmp, "ocr.json")
	out := filepath.Join(tmp, "out")
	writeCompilePNG(t, input)
	if err := os.WriteFile(ocrPath, []byte(`{"image":{"width":160,"height":120},"blocks":[{"id":"ocr_1","text":"Pay","bbox":{"x":48,"y":45,"width":48,"height":20},"confidence":1}]}`), 0o644); err != nil {
		t.Fatalf("write ocr fixture: %v", err)
	}

	cmd := exec.Command("go", "run", ".", "-input", input, "-ocr", ocrPath, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "codia_tree_ir.v1.json") {
		t.Fatalf("unexpected CLI output: %s", string(data))
	}
	for _, name := range []string{
		filepath.Join("extract", "m29_physical_evidence.v1.json"),
		filepath.Join("tokens", "evidence_tokens.v1.json"),
		filepath.Join("leaves", "codia_leaf_ir.v1.json"),
		filepath.Join("controls", "codia_control_ir.v1.json"),
		"codia_tree_ir.v1.json",
		"codia_figma_like_tree.v1.json",
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func writeCompilePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 160, 120))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 245, G: 245, B: 245, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(32, 36, 116, 76), &image.Uniform{C: color.RGBA{R: 40, G: 110, B: 220, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(54, 48, 92, 62), &image.Uniform{C: color.RGBA{R: 255, G: 255, B: 255, A: 255}}, image.Point{}, draw.Src)
	if err := imageio.WritePNG(path, img); err != nil {
		t.Fatalf("write png fixture: %v", err)
	}
}
