package render

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestWriteCreatesPreviewArtifacts(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 80, 60)

	out := filepath.Join(dir, "out")
	artifacts, err := Write(previewDoc(source), Options{OutputDir: out})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	for _, path := range []string{artifacts.PreviewHTML, artifacts.DebugHTML, artifacts.PreviewReport} {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("expected artifact %s: %v", path, err)
		}
	}
	if artifacts.AssetCount != 1 {
		t.Fatalf("asset count = %d, want 1", artifacts.AssetCount)
	}
	if _, err := os.Stat(filepath.Join(out, PreviewAssetsDir, "evidence_image_1.png")); err != nil {
		t.Fatalf("expected image evidence crop: %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	if !strings.Contains(html, "preview_assets/evidence_image_1.png") {
		t.Fatalf("preview html should reference local crop asset")
	}
	if !strings.Contains(html, "Hello") {
		t.Fatalf("preview html should render text evidence")
	}
}

func TestWritePaintsTextAboveRasterEvidence(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 80, 60)

	artifacts, err := Write(previewDoc(source), Options{OutputDir: filepath.Join(dir, "out")})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	imageIndex := strings.Index(html, `data-evidence-id="evidence_image_1"`)
	textIndex := strings.Index(html, `data-evidence-id="evidence_text_1"`)
	if imageIndex < 0 || textIndex < 0 {
		t.Fatalf("expected image and text evidence in html: image=%d text=%d", imageIndex, textIndex)
	}
	if imageIndex > textIndex {
		t.Fatalf("image evidence should be emitted before text evidence so text paints above it when z-index ties are absent")
	}
	if !strings.Contains(tagAround(html, imageIndex), "--z:20") {
		t.Fatalf("image evidence should use raster z-index 20")
	}
	if !strings.Contains(tagAround(html, textIndex), "--z:40") {
		t.Fatalf("text evidence should use text z-index 40")
	}
}

func previewDoc(source string) contract.Document {
	return contract.Document{
		Version: contract.Version,
		SourceImage: contract.ImageMeta{
			Path:   source,
			Width:  80,
			Height: 60,
		},
		Root: contract.Node{
			ID:   "node_0001",
			Type: contract.NodePage,
			BBox: geometry.Rect{Width: 80, Height: 60},
			Layout: contract.Layout{
				Mode: contract.LayoutColumn,
			},
			SourceRefs: []contract.SourceRef{{Kind: "source_image", ID: "source_image"}},
		},
		Evidence: []contract.Evidence{
			{
				ID:         "evidence_image_1",
				Kind:       "m29_token",
				RoleHint:   "image",
				BBox:       geometry.Rect{X: 8, Y: 10, Width: 50, Height: 30},
				Source:     "m29",
				Confidence: 0.9,
				SourceRefs: []contract.SourceRef{{Kind: "m29_token", ID: "token_image"}},
			},
			{
				ID:         "evidence_text_1",
				Kind:       "m29_token",
				RoleHint:   "text",
				BBox:       geometry.Rect{X: 12, Y: 16, Width: 34, Height: 14},
				Source:     "m29",
				Confidence: 1,
				SourceRefs: []contract.SourceRef{{Kind: "m29_token", ID: "token_text"}},
				Meta:       map[string]string{"text": "Hello"},
			},
		},
	}
}

func writePreviewTestPNG(t *testing.T, path string, width int, height int) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.Set(x, y, color.RGBA{R: uint8(x * 3), G: uint8(y * 3), B: 100, A: 255})
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

func tagAround(value string, index int) string {
	start := strings.LastIndex(value[:index], "<div")
	end := strings.Index(value[index:], ">")
	if start < 0 || end < 0 {
		return ""
	}
	return value[start : index+end+1]
}
