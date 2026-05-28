package pipeline

import (
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func TestRunWritesPhysicalEvidenceForSimpleRectAndLine(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeSyntheticPNG(t, input, false)

	doc, err := Run(Options{InputPath: input, OutputDir: filepath.Join(tmp, "out")})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if doc.SchemaName != "M29PhysicalEvidence" {
		t.Fatalf("unexpected schema name %q", doc.SchemaName)
	}
	if doc.OCR.Provided {
		t.Fatalf("OCR should not be marked provided")
	}
	if len(doc.Primitives) == 0 {
		t.Fatalf("expected primitives")
	}
	if !hasPrimitiveType(doc.Primitives, "rect") {
		t.Fatalf("expected rect primitive, got %#v", primitiveTypes(doc.Primitives))
	}
	if !hasPrimitiveType(doc.Primitives, "line") {
		t.Fatalf("expected line primitive, got %#v", primitiveTypes(doc.Primitives))
	}
	assertFileExists(t, filepath.Join(tmp, "out", "m29_physical_evidence.v1.json"))
	assertFileExists(t, filepath.Join(tmp, "out", "debug_overlay.png"))
	assertFileExists(t, filepath.Join(tmp, "out", "preview_sheet.png"))
}

func TestRunUsesOCRAsTextMaskOnly(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeSyntheticPNG(t, input, true)
	ocrPath := filepath.Join(tmp, "ocr.json")
	ocrDoc := map[string]any{
		"image": map[string]any{"width": 120, "height": 80},
		"blocks": []map[string]any{
			{
				"id":   "ocr_0001",
				"text": "Allow",
				"bbox": map[string]any{"x": 12, "y": 12, "width": 32, "height": 16},
			},
		},
	}
	data, err := json.Marshal(ocrDoc)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(ocrPath, data, 0o644); err != nil {
		t.Fatal(err)
	}

	doc, err := Run(Options{InputPath: input, OCRPath: ocrPath, OutputDir: filepath.Join(tmp, "out")})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if !doc.OCR.Provided || doc.OCR.BlockCount != 1 {
		t.Fatalf("unexpected OCR info: %#v", doc.OCR)
	}
	if !hasPrimitiveType(doc.Primitives, "text_region") {
		t.Fatalf("expected text_region primitive")
	}
	for _, p := range doc.Primitives {
		if p.PrimitiveType == "text_region" && p.Source.Kind != "ocr" {
			t.Fatalf("text_region should keep OCR source, got %#v", p.Source)
		}
	}
	if doc.Diagnostics.TextMaskPixelCount == 0 {
		t.Fatalf("expected text mask pixels")
	}
}

func TestRunEmitsOCRAnchoredSurfaceRegion(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeSurfacePNG(t, input)
	ocrPath := filepath.Join(tmp, "ocr.json")
	ocrDoc := map[string]any{
		"image": map[string]any{"width": 220, "height": 120},
		"blocks": []map[string]any{
			{
				"id":   "ocr_0001",
				"text": "Search",
				"bbox": map[string]any{"x": 52, "y": 48, "width": 58, "height": 18},
			},
		},
	}
	data, err := json.Marshal(ocrDoc)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(ocrPath, data, 0o644); err != nil {
		t.Fatal(err)
	}

	doc, err := Run(Options{InputPath: input, OCRPath: ocrPath, OutputDir: filepath.Join(tmp, "out")})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	var surface *contract.Primitive
	for i := range doc.Primitives {
		if doc.Primitives[i].PrimitiveType == "surface_region" {
			surface = &doc.Primitives[i]
			break
		}
	}
	if surface == nil {
		t.Fatalf("expected surface_region, got %#v", primitiveTypes(doc.Primitives))
	}
	textBox := contract.BBox{X: 52, Y: 48, Width: 58, Height: 18}
	if !contains(surface.BBox, textBox, 4) {
		t.Fatalf("surface should contain OCR text, surface=%#v text=%#v", surface.BBox, textBox)
	}
	if !surface.CompileHints.CanContainForeground || !surface.CompileHints.HasStableRectGeometry {
		t.Fatalf("surface should be foreground-capable stable geometry: %#v", surface.CompileHints)
	}
}

func writeSyntheticPNG(t *testing.T, path string, withTextLikePixels bool) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 120, 80))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 245, G: 245, B: 245, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(56, 20, 104, 48), &image.Uniform{C: color.RGBA{R: 40, G: 120, B: 220, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(8, 64, 110, 66), &image.Uniform{C: color.RGBA{R: 30, G: 30, B: 30, A: 255}}, image.Point{}, draw.Src)
	if withTextLikePixels {
		draw.Draw(img, image.Rect(12, 12, 44, 16), &image.Uniform{C: color.RGBA{R: 20, G: 20, B: 20, A: 255}}, image.Point{}, draw.Src)
		draw.Draw(img, image.Rect(12, 20, 38, 24), &image.Uniform{C: color.RGBA{R: 20, G: 20, B: 20, A: 255}}, image.Point{}, draw.Src)
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatal(err)
	}
}

func writeSurfacePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 220, 120))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 42, G: 128, B: 240, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(30, 36, 190, 78), &image.Uniform{C: color.RGBA{R: 248, G: 248, B: 250, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(52, 48, 110, 52), &image.Uniform{C: color.RGBA{R: 130, G: 136, B: 148, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(52, 58, 96, 62), &image.Uniform{C: color.RGBA{R: 130, G: 136, B: 148, A: 255}}, image.Point{}, draw.Src)
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatal(err)
	}
}

func hasPrimitiveType(primitives []contract.Primitive, primitiveType string) bool {
	for _, p := range primitives {
		if p.PrimitiveType == primitiveType {
			return true
		}
	}
	return false
}

func primitiveTypes(primitives []contract.Primitive) []string {
	out := make([]string, 0, len(primitives))
	for _, p := range primitives {
		out = append(out, p.PrimitiveType)
	}
	return out
}

func assertFileExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
}
