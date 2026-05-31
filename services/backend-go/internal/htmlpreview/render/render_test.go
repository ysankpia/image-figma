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
	if artifacts.AssetCount != 2 {
		t.Fatalf("asset count = %d, want 2", artifacts.AssetCount)
	}
	if _, err := os.Stat(filepath.Join(out, PreviewAssetsDir, "asset_node_image_1.png")); err != nil {
		t.Fatalf("expected node image crop: %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	if !strings.Contains(html, "preview_assets/asset_node_image_1.png") {
		t.Fatalf("preview html should reference local node crop asset")
	}
	if !strings.Contains(html, "Hello") {
		t.Fatalf("preview html should render text node")
	}
	if strings.Contains(html, `data-evidence-id=`) {
		t.Fatalf("normal preview must not render raw evidence")
	}
	debugHTML := readString(t, artifacts.DebugHTML)
	if !strings.Contains(debugHTML, `data-evidence-id="evidence_image_1"`) {
		t.Fatalf("debug preview should render raw evidence")
	}
}

func TestWritePaintsTextAboveRasterNodes(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 80, 60)

	artifacts, err := Write(previewDoc(source), Options{OutputDir: filepath.Join(dir, "out")})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	imageIndex := strings.Index(html, `data-node-id="node_image_1"`)
	textIndex := strings.Index(html, `data-node-id="node_text_1"`)
	if imageIndex < 0 || textIndex < 0 {
		t.Fatalf("expected image and text nodes in html: image=%d text=%d", imageIndex, textIndex)
	}
	if imageIndex > textIndex {
		t.Fatalf("image node should be emitted before text node so text paints above it when z-index ties are absent")
	}
	if !strings.Contains(tagAround(html, imageIndex), "--z:22") {
		t.Fatalf("image node should use raster z-index 22")
	}
	if !strings.Contains(tagAround(html, textIndex), "--z:44") {
		t.Fatalf("text node should use text z-index 44")
	}
}

func TestWriteRendersUnifiedVisionTextStyleMeta(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 80, 60)

	doc := previewDoc(source)
	doc.Root.Children[1].Style.Fill = "#123456"
	doc.Root.Children[1].Meta = map[string]string{
		"fontSize":    "18",
		"fontWeight":  "700",
		"styleSource": "unified_vision",
	}
	artifacts, err := Write(doc, Options{OutputDir: filepath.Join(dir, "out")})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	textIndex := strings.Index(html, `data-node-id="node_text_1"`)
	if textIndex < 0 {
		t.Fatalf("expected text node in html")
	}
	tag := tagAround(html, textIndex)
	for _, want := range []string{"--fill:#123456", "--font:18px", "--weight:700"} {
		if !strings.Contains(tag, want) {
			t.Fatalf("text style tag missing %q: %s", want, tag)
		}
	}
}

func TestWriteUsesNodeFillAndTextEraserLayer(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 80, 60)

	doc := previewDoc(source)
	doc.Root.Style.Fill = "#202020"
	doc.Root.Children = append(doc.Root.Children, contract.Node{
		ID:             "node_eraser_1",
		Type:           contract.NodeShape,
		BBox:           geometry.Rect{X: 10, Y: 12, Width: 30, Height: 10},
		Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
		Style:          contract.Style{Fill: "#333333"},
		SourceRefs:     []contract.SourceRef{{Kind: "layout_evidence", ID: "evidence_text_1"}},
		Confidence:     0.8,
		FallbackPolicy: "substrate_text_eraser",
		Meta:           map[string]string{"zLayer": "text_eraser"},
	})

	artifacts, err := Write(doc, Options{OutputDir: filepath.Join(dir, "out")})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	if !strings.Contains(html, `<main class="page" style="width:80px;height:60px;background:#202020"`) {
		t.Fatalf("page should use root fill: %s", html)
	}
	eraserIndex := strings.Index(html, `data-node-id="node_eraser_1"`)
	if eraserIndex < 0 {
		t.Fatalf("expected eraser node in html")
	}
	eraserTag := tagAround(html, eraserIndex)
	if !strings.Contains(eraserTag, "--fill:#333333") {
		t.Fatalf("eraser should carry fill style: %s", eraserTag)
	}
	if !strings.Contains(eraserTag, "--z:36") {
		t.Fatalf("eraser should render above crops and below text: %s", eraserTag)
	}
}

func TestWriteRendersRowLayoutAndReportsStructuralHealth(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 160, 80)

	doc := previewDoc(source)
	row := contract.Node{
		ID:   "row_1",
		Type: contract.NodeRow,
		BBox: geometry.Rect{X: 8, Y: 10, Width: 120, Height: 36},
		Layout: contract.Layout{
			Mode: contract.LayoutRow,
			Gap:  8,
			Padding: contract.Insets{
				Top:  4,
				Left: 6,
			},
			Align: "center",
		},
		Meta: map[string]string{"gapVariance": "0"},
		Children: []contract.Node{
			{
				ID:             "row_text_1",
				Type:           contract.NodeText,
				BBox:           geometry.Rect{X: 14, Y: 14, Width: 36, Height: 16},
				Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
				FallbackPolicy: "editable_text",
				Text:           &contract.Text{Characters: "A"},
			},
			{
				ID:             "row_icon_1",
				Type:           contract.NodeIcon,
				BBox:           geometry.Rect{X: 58, Y: 14, Width: 16, Height: 16},
				Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
				FallbackPolicy: "crop_asset",
				AssetRef:       &contract.AssetRef{AssetID: "asset_row_icon_1"},
			},
			{
				ID:             "row_bg_1",
				Type:           contract.NodeShape,
				BBox:           geometry.Rect{X: 8, Y: 10, Width: 120, Height: 36},
				Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
				Style:          contract.Style{Fill: "#eeeeee"},
				FallbackPolicy: "vector_shape",
			},
		},
	}
	doc.Root.Children = []contract.Node{row}
	doc.Assets = append(doc.Assets, contract.Asset{
		ID:     "asset_row_icon_1",
		Type:   "image",
		Format: "png",
		BBox:   geometry.Rect{X: 58, Y: 14, Width: 16, Height: 16},
		Width:  16,
		Height: 16,
	})

	artifacts, err := Write(doc, Options{OutputDir: filepath.Join(dir, "out")})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	for _, want := range []string{
		`class="node node-row layout-row"`,
		`data-layout-mode="row"`,
		`--gap:8px`,
		`--pt:4px`,
		`class="flow-node node-text"`,
		`class="flow-node node-icon"`,
		`data-node-id="row_bg_1"`,
	} {
		if !strings.Contains(html, want) {
			t.Fatalf("preview html missing %q:\n%s", want, html)
		}
	}
	report := readString(t, artifacts.PreviewReport)
	for _, want := range []string{
		"- row layout nodes: `1`",
		"- visible leaf nodes: `3`",
		"- flex-covered leaf nodes: `2`",
		"- auto layout coverage: `0.6667`",
		"- absolute fallback ratio: `0.3333`",
		"- zero-flow row count: `0`",
		"- high-gap row count: `0`",
		"- mean gap variance: `0.00`",
	} {
		if !strings.Contains(report, want) {
			t.Fatalf("preview report missing %q:\n%s", want, report)
		}
	}
}

func TestWriteRendersColumnLayout(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "source.png")
	writePreviewTestPNG(t, source, 120, 120)

	doc := previewDoc(source)
	column := contract.Node{
		ID:     "column_1",
		Type:   contract.NodeColumn,
		BBox:   geometry.Rect{X: 10, Y: 10, Width: 80, Height: 70},
		Layout: contract.Layout{Mode: contract.LayoutColumn, Gap: 6},
		Children: []contract.Node{
			{
				ID:     "column_text_1",
				Type:   contract.NodeText,
				BBox:   geometry.Rect{X: 12, Y: 12, Width: 50, Height: 16},
				Layout: contract.Layout{Mode: contract.LayoutAbsolute},
				Text:   &contract.Text{Characters: "Top"},
			},
			{
				ID:     "column_text_2",
				Type:   contract.NodeText,
				BBox:   geometry.Rect{X: 12, Y: 34, Width: 50, Height: 16},
				Layout: contract.Layout{Mode: contract.LayoutAbsolute},
				Text:   &contract.Text{Characters: "Bottom"},
			},
		},
	}
	doc.Root.Children = []contract.Node{column}

	artifacts, err := Write(doc, Options{OutputDir: filepath.Join(dir, "out")})
	if err != nil {
		t.Fatalf("Write() error = %v", err)
	}
	html := readString(t, artifacts.PreviewHTML)
	for _, want := range []string{
		`class="node node-column layout-column"`,
		`data-layout-mode="column"`,
		`--gap:6px`,
		`data-node-id="column_text_1"`,
		`data-node-id="column_text_2"`,
	} {
		if !strings.Contains(html, want) {
			t.Fatalf("preview html missing %q:\n%s", want, html)
		}
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
			Children: []contract.Node{
				{
					ID:             "node_image_1",
					Type:           contract.NodeImage,
					BBox:           geometry.Rect{X: 8, Y: 10, Width: 50, Height: 30},
					Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
					SourceRefs:     []contract.SourceRef{{Kind: "layout_evidence", ID: "evidence_image_1"}},
					Confidence:     0.9,
					FallbackPolicy: "crop_asset",
					AssetRef:       &contract.AssetRef{AssetID: "asset_node_image_1"},
				},
				{
					ID:             "node_text_1",
					Type:           contract.NodeText,
					BBox:           geometry.Rect{X: 12, Y: 16, Width: 34, Height: 14},
					Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
					SourceRefs:     []contract.SourceRef{{Kind: "layout_evidence", ID: "evidence_text_1"}},
					Confidence:     1,
					FallbackPolicy: "editable_text",
					Text:           &contract.Text{Characters: "Hello"},
				},
			},
		},
		Assets: []contract.Asset{
			{
				ID:         "asset_node_image_1",
				Type:       "image",
				Format:     "png",
				BBox:       geometry.Rect{X: 8, Y: 10, Width: 50, Height: 30},
				Width:      50,
				Height:     30,
				SourceRefs: []contract.SourceRef{{Kind: "layout_evidence", ID: "evidence_image_1"}},
			},
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
