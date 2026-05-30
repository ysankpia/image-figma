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
				"text": "Label",
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

func TestRunEmitsTightControlSurfaceRegion(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeTightControlSurfacePNG(t, input)
	ocrPath := filepath.Join(tmp, "ocr.json")
	ocrDoc := map[string]any{
		"image": map[string]any{"width": 220, "height": 120},
		"blocks": []map[string]any{
			{
				"id":   "ocr_0001",
				"text": "uinotes.com",
				"bbox": map[string]any{"x": 38, "y": 43, "width": 126, "height": 34},
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
	textBox := contract.BBox{X: 38, Y: 43, Width: 126, Height: 34}
	for _, p := range doc.Primitives {
		if p.PrimitiveType != "surface_region" {
			continue
		}
		if contains(p.BBox, textBox, 4) && hasReason(p.CompileHints.Reasons, "control_surface_component") {
			return
		}
	}
	t.Fatalf("expected tight control surface_region around %#v, got %#v", textBox, doc.Primitives)
}

func TestRunEmitsContrastControlSurfaceRegion(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeContrastControlSurfacePNG(t, input)
	ocrPath := filepath.Join(tmp, "ocr.json")
	ocrDoc := map[string]any{
		"image": map[string]any{"width": 220, "height": 120},
		"blocks": []map[string]any{
			{
				"id":   "ocr_0001",
				"text": "Pay now",
				"bbox": map[string]any{"x": 74, "y": 49, "width": 72, "height": 20},
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
	textBox := contract.BBox{X: 74, Y: 49, Width: 72, Height: 20}
	for _, p := range doc.Primitives {
		if p.PrimitiveType != "surface_region" {
			continue
		}
		if contains(p.BBox, textBox, 4) && p.BBox.Width >= textBox.Width+24 {
			return
		}
	}
	t.Fatalf("expected contrast control surface_region around %#v, got %#v", textBox, doc.Primitives)
}

func TestTightNumericGlyphSurface(t *testing.T) {
	if !tightNumericGlyphSurface("04", contract.BBox{X: 10, Y: 10, Width: 42, Height: 40}, contract.BBox{X: 10, Y: 10, Width: 41, Height: 39}) {
		t.Fatalf("expected tight numeric glyph surface to be rejected")
	}
	if tightNumericGlyphSurface("回归签到", contract.BBox{X: 10, Y: 10, Width: 96, Height: 30}, contract.BBox{X: 20, Y: 12, Width: 72, Height: 20}) {
		t.Fatalf("non-numeric CTA text should not be rejected as numeric glyph")
	}
}

func TestRunAllowsEdgeAnchoredSurfaceRegion(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeEdgeAnchoredSurfacePNG(t, input)
	ocrPath := filepath.Join(tmp, "ocr.json")
	ocrDoc := map[string]any{
		"image": map[string]any{"width": 220, "height": 120},
		"blocks": []map[string]any{
			{
				"id":   "ocr_0001",
				"text": "Mine",
				"bbox": map[string]any{"x": 84, "y": 98, "width": 42, "height": 14},
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
	var anchored *contract.Primitive
	for i := range doc.Primitives {
		p := &doc.Primitives[i]
		if p.PrimitiveType == "surface_region" && p.BBox.Y+p.BBox.Height >= 119 {
			anchored = p
			break
		}
	}
	if anchored == nil {
		t.Fatalf("expected edge-anchored surface_region, got %#v", primitiveTypes(doc.Primitives))
	}
	textBox := contract.BBox{X: 84, Y: 98, Width: 42, Height: 14}
	if !contains(anchored.BBox, textBox, 4) {
		t.Fatalf("edge surface should contain OCR text, surface=%#v text=%#v", anchored.BBox, textBox)
	}
	if !anchored.CompileHints.CanContainForeground {
		t.Fatalf("edge surface should keep foreground containment capability: %#v", anchored.CompileHints)
	}
}

func TestRunExtractsSurfaceLocalForegroundComponents(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeSurfaceForegroundPNG(t, input)
	ocrPath := filepath.Join(tmp, "ocr.json")
	ocrDoc := map[string]any{
		"image": map[string]any{"width": 220, "height": 140},
		"blocks": []map[string]any{
			{
				"id":   "ocr_0001",
				"text": "Label",
				"bbox": map[string]any{"x": 52, "y": 56, "width": 58, "height": 18},
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
	iconBox := contract.BBox{X: 148, Y: 58, Width: 16, Height: 16}
	for _, p := range doc.Primitives {
		if p.PrimitiveType != "text_region" && contains(inflateBBox(iconBox, 2, 2, 220, 140), p.BBox, 0) {
			return
		}
	}
	t.Fatalf("expected surface-local foreground primitive near %#v, got %#v", iconBox, doc.Primitives)
}

func TestRunEmitsInternalRasterCropCandidatesForRepeatedSlots(t *testing.T) {
	t.Setenv("OCR_PROVIDER", "fake")
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writeRepeatedRasterSlotsPNG(t, input)

	doc, err := Run(Options{InputPath: input, OutputDir: filepath.Join(tmp, "out")})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}

	count := 0
	sideRail := 0
	for _, p := range doc.Primitives {
		if p.PrimitiveType != "image_region" || !hasReason(p.CompileHints.Reasons, "internal_raster_crop_candidate") {
			continue
		}
		count++
		if hasReason(p.CompileHints.Reasons, "side_rail_crop_candidate") {
			sideRail++
		}
		assertFileExists(t, filepath.Join(tmp, "out", p.CropRef))
	}
	if count < 4 {
		t.Fatalf("expected repeated internal raster crops, got %d primitives: %#v", count, doc.Primitives)
	}
	if sideRail < 2 {
		t.Fatalf("expected repeated side-rail raster crops, got sideRail=%d primitives=%#v", sideRail, doc.Primitives)
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

func writeRepeatedRasterSlotsPNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 320, 320))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 246, G: 246, B: 246, A: 255}}, image.Point{}, draw.Src)
	parent := image.Rect(20, 30, 300, 280)
	for y := parent.Min.Y; y < parent.Max.Y; y++ {
		for x := parent.Min.X; x < parent.Max.X; x++ {
			shadeX := uint8((x - parent.Min.X) * 150 / max(1, parent.Dx()-1))
			shadeY := uint8((y - parent.Min.Y) * 90 / max(1, parent.Dy()-1))
			img.SetRGBA(x, y, color.RGBA{R: 56 + shadeX, G: 72 + shadeY, B: 104 + shadeX/2, A: 255})
		}
	}
	rows := []int{42, 124, 206}
	for _, y := range rows {
		drawTexturedSlot(img, image.Rect(34, y, 112, y+48), color.RGBA{R: 194, G: 72, B: 82, A: 255})
		drawTexturedSlot(img, image.Rect(262, y, 292, y+70), color.RGBA{R: 82, G: 112, B: 198, A: 255})
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

func drawTexturedSlot(img *image.RGBA, rect image.Rectangle, base color.RGBA) {
	draw.Draw(img, rect, &image.Uniform{C: base}, image.Point{}, draw.Src)
	for y := rect.Min.Y; y < rect.Max.Y; y++ {
		for x := rect.Min.X; x < rect.Max.X; x++ {
			r := uint8((int(base.R) + (x-rect.Min.X)*5 + (y-rect.Min.Y)*3) % 256)
			g := uint8((int(base.G) + (x-rect.Min.X)*2 + (y-rect.Min.Y)*7) % 256)
			b := uint8((int(base.B) + (x-rect.Min.X)*4 + (y-rect.Min.Y)*5) % 256)
			img.SetRGBA(x, y, color.RGBA{R: r, G: g, B: b, A: 255})
		}
	}
	for y := rect.Min.Y; y < rect.Max.Y; y += 6 {
		shade := uint8(24 + (y-rect.Min.Y)%18)
		draw.Draw(img, image.Rect(rect.Min.X, y, rect.Max.X, min(rect.Max.Y, y+2)), &image.Uniform{C: color.RGBA{R: base.R + shade/3, G: base.G + shade/4, B: base.B + shade/5, A: 255}}, image.Point{}, draw.Src)
	}
	for x := rect.Min.X; x < rect.Max.X; x += 9 {
		draw.Draw(img, image.Rect(x, rect.Min.Y, min(rect.Max.X, x+2), rect.Max.Y), &image.Uniform{C: color.RGBA{R: base.R / 2, G: base.G / 2, B: base.B / 2, A: 255}}, image.Point{}, draw.Src)
	}
}

func writeEdgeAnchoredSurfacePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 220, 120))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 38, G: 116, B: 224, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(0, 88, 220, 120), &image.Uniform{C: color.RGBA{R: 250, G: 250, B: 252, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(84, 100, 126, 104), &image.Uniform{C: color.RGBA{R: 90, G: 96, B: 110, A: 255}}, image.Point{}, draw.Src)
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatal(err)
	}
}

func writeSurfaceForegroundPNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 220, 140))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 42, G: 128, B: 240, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(30, 36, 190, 96), &image.Uniform{C: color.RGBA{R: 248, G: 248, B: 250, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(52, 58, 110, 62), &image.Uniform{C: color.RGBA{R: 130, G: 136, B: 148, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(52, 68, 96, 72), &image.Uniform{C: color.RGBA{R: 130, G: 136, B: 148, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(148, 58, 164, 74), &image.Uniform{C: color.RGBA{R: 210, G: 78, B: 82, A: 255}}, image.Point{}, draw.Src)
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

func writeTightControlSurfacePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 220, 120))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 46, G: 122, B: 230, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(30, 36, 168, 80), &image.Uniform{C: color.RGBA{R: 246, G: 246, B: 246, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(38, 50, 164, 56), &image.Uniform{C: color.RGBA{R: 128, G: 132, B: 140, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(38, 64, 154, 70), &image.Uniform{C: color.RGBA{R: 128, G: 132, B: 140, A: 255}}, image.Point{}, draw.Src)
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatal(err)
	}
}

func writeContrastControlSurfacePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 220, 120))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 255, G: 255, B: 255, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(55, 42, 165, 78), &image.Uniform{C: color.RGBA{R: 236, G: 168, B: 92, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(74, 50, 146, 68), &image.Uniform{C: color.RGBA{R: 252, G: 252, B: 252, A: 255}}, image.Point{}, draw.Src)
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

func hasReason(reasons []string, reason string) bool {
	for _, item := range reasons {
		if item == reason {
			return true
		}
	}
	return false
}

func assertFileExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
}
