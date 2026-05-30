package dsl02

import (
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestExportConvertsFigmaLikeTreeToRuntimeDSL(t *testing.T) {
	doc := sampleFigmaLikeTree()
	out, err := Export("task_test", doc)
	if err != nil {
		t.Fatalf("Export() error = %v", err)
	}
	if out.Version != "0.2" {
		t.Fatalf("version = %q", out.Version)
	}
	if out.Kind != "codia_runtime" {
		t.Fatalf("kind = %q", out.Kind)
	}
	if out.TaskID != "task_test" {
		t.Fatalf("taskId = %q", out.TaskID)
	}
	if out.Page.Width != 390 || out.Page.Height != 844 {
		t.Fatalf("page size = %+v", out.Page)
	}
	if out.Root.Role != "Root" || out.Root.Type != "frame" {
		t.Fatalf("root = role %q type %q", out.Root.Role, out.Root.Type)
	}
	if len(out.Root.Children) != 3 {
		t.Fatalf("root children = %d", len(out.Root.Children))
	}
	text := out.Root.Children[0]
	if text.Role != "TextView" || text.Type != "text" || text.Text == nil || text.Text.Characters != "首页" {
		t.Fatalf("text child = %+v", text)
	}
	if text.BBox.X != 16 || text.BBox.Y != 24 {
		t.Fatalf("text bbox should be parent-local, got %+v", text.BBox)
	}
	if text.Style["color"] != "#111827" {
		t.Fatalf("text color = %#v", text.Style["color"])
	}
	image := out.Root.Children[1]
	if image.Role != "ImageView" || image.Type != "image" {
		t.Fatalf("image child = role %q type %q", image.Role, image.Type)
	}
	if image.Image != nil {
		t.Fatalf("image without fetchable asset should remain placeholder, got %+v", image.Image)
	}
	if image.Meta["asset"] == nil {
		t.Fatalf("image asset provenance missing")
	}
	button := out.Root.Children[2]
	if button.Children[0].Role != "bg_Button" || button.Children[0].Type != "shape" {
		t.Fatalf("button background = %+v", button.Children[0])
	}
	if button.Children[0].Style["radius"] != 8.0 {
		t.Fatalf("button bg radius = %#v", button.Children[0].Style["radius"])
	}
}

func TestExportWithAssetsCropsImageNodes(t *testing.T) {
	tmp := t.TempDir()
	sourcePath := filepath.Join(tmp, "source.png")
	writeTestSourcePNG(t, sourcePath)

	out, err := ExportWithAssets(ExportAssetOptions{
		TaskID:          "task_test",
		Document:        sampleFigmaLikeTree(),
		SourceImagePath: sourcePath,
		OutputDir:       tmp,
	})
	if err != nil {
		t.Fatalf("ExportWithAssets() error = %v", err)
	}
	if len(out.Assets) != 1 {
		t.Fatalf("assets = %d, want 1", len(out.Assets))
	}
	asset := out.Assets[0]
	if asset.AssetID != "asset_image_1" || asset.URL != "assets/asset_image_1.png" || asset.Width != 120 || asset.Height != 80 {
		t.Fatalf("unexpected asset: %+v", asset)
	}
	imageNode := out.Root.Children[1]
	if imageNode.Image == nil || imageNode.Image.AssetID != asset.AssetID {
		t.Fatalf("image node missing asset reference: %+v", imageNode.Image)
	}
	file, err := os.Open(filepath.Join(tmp, asset.URL))
	if err != nil {
		t.Fatalf("open cropped asset: %v", err)
	}
	defer file.Close()
	crop, err := png.Decode(file)
	if err != nil {
		t.Fatalf("decode cropped asset: %v", err)
	}
	bounds := crop.Bounds()
	if bounds.Dx() != 120 || bounds.Dy() != 80 {
		t.Fatalf("crop size = %dx%d", bounds.Dx(), bounds.Dy())
	}
	got := color.RGBAModel.Convert(crop.At(0, 0)).(color.RGBA)
	if got.R != 220 || got.G != 40 || got.B != 80 {
		t.Fatalf("crop pixel = %+v", got)
	}
}

func TestExportWithAssetsInfersMissingRuntimeTextStyle(t *testing.T) {
	tmp := t.TempDir()
	sourcePath := filepath.Join(tmp, "source.png")
	writeTextStyleSourcePNG(t, sourcePath)
	doc := sampleFigmaLikeTree()
	doc.Root.Children[0].Style = ir.Style{Visible: true, Opacity: 1}
	doc.Root.Children[0].SourceBBox = ir.BBox{X: 16, Y: 24, Width: 96, Height: 32}
	doc.Root.Children[0].FigmaBBox = doc.Root.Children[0].SourceBBox
	doc.Root.Children[0].RelativeBBox = doc.Root.Children[0].SourceBBox

	out, err := ExportWithAssets(ExportAssetOptions{
		TaskID:          "task_test",
		Document:        doc,
		SourceImagePath: sourcePath,
		OutputDir:       tmp,
	})
	if err != nil {
		t.Fatalf("ExportWithAssets() error = %v", err)
	}
	text := out.Root.Children[0]
	if text.Style["fontFamily"] != "Inter" {
		t.Fatalf("font family = %#v", text.Style["fontFamily"])
	}
	if text.Style["fontSize"] != 25 {
		t.Fatalf("font size = %#v", text.Style["fontSize"])
	}
	if text.Style["lineHeight"] != 32 {
		t.Fatalf("line height = %#v", text.Style["lineHeight"])
	}
	if text.Style["color"] != "#FFFFFF" {
		t.Fatalf("text color = %#v", text.Style["color"])
	}
}

func TestWriteArtifact(t *testing.T) {
	tmp := t.TempDir()
	out, err := Export("task_test", sampleFigmaLikeTree())
	if err != nil {
		t.Fatalf("Export() error = %v", err)
	}
	if err := WriteArtifact(tmp, out); err != nil {
		t.Fatalf("WriteArtifact() error = %v", err)
	}
	data, err := os.ReadFile(filepath.Join(tmp, ArtifactName))
	if err != nil {
		t.Fatalf("read artifact: %v", err)
	}
	var decoded Document
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("decode artifact: %v", err)
	}
	if decoded.Version != "0.2" || decoded.Kind != "codia_runtime" {
		t.Fatalf("decoded artifact = %+v", decoded)
	}
}

func writeTextStyleSourcePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 390, 844))
	for y := 0; y < 844; y++ {
		for x := 0; x < 390; x++ {
			img.SetRGBA(x, y, color.RGBA{R: 74, G: 162, B: 87, A: 255})
		}
	}
	for y := 31; y < 49; y++ {
		for x := 28; x < 98; x++ {
			img.SetRGBA(x, y, color.RGBA{R: 255, G: 255, B: 255, A: 255})
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create source png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode source png: %v", err)
	}
}

func writeTestSourcePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 390, 844))
	for y := 0; y < 844; y++ {
		for x := 0; x < 390; x++ {
			img.SetRGBA(x, y, color.RGBA{R: 245, G: 245, B: 245, A: 255})
		}
	}
	for y := 80; y < 160; y++ {
		for x := 20; x < 140; x++ {
			img.SetRGBA(x, y, color.RGBA{R: 220, G: 40, B: 80, A: 255})
		}
	}
	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create source png: %v", err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode source png: %v", err)
	}
}

func sampleFigmaLikeTree() emitter.Document {
	return emitter.Document{
		SchemaName: emitter.SchemaName,
		Version:    emitter.Version,
		Source: emitter.Source{
			IRSchemaName: ir.SchemaName,
			IRVersion:    ir.Version,
			InputPath:    "/tmp/input.png",
		},
		Root: emitter.Node{
			ID:           "root",
			Type:         ir.FigmaFrame,
			Name:         "Root",
			Role:         ir.RoleRoot,
			SchemaID:     "schema_root",
			Seq:          1,
			SourceBBox:   ir.BBox{X: 0, Y: 0, Width: 390, Height: 844},
			FigmaBBox:    ir.BBox{X: 0, Y: 0, Width: 390, Height: 844},
			RelativeBBox: ir.BBox{X: 0, Y: 0, Width: 390, Height: 844},
			Style: ir.Style{
				Visible: true,
				FillPaints: []ir.Paint{{
					Type:  "SOLID",
					Color: &ir.Color{R: 1, G: 1, B: 1, A: 1},
				}},
			},
			Children: []emitter.Node{
				{
					ID:           "text_1",
					Type:         ir.FigmaText,
					Name:         "首页",
					Role:         ir.RoleTextView,
					SchemaID:     "schema_text_1",
					Seq:          2,
					SourceBBox:   ir.BBox{X: 16, Y: 24, Width: 64, Height: 20},
					FigmaBBox:    ir.BBox{X: 16, Y: 24, Width: 64, Height: 20},
					RelativeBBox: ir.BBox{X: 16, Y: 24, Width: 64, Height: 20},
					Text:         &ir.Text{Characters: "首页"},
					Style: ir.Style{
						Visible: true,
						FillPaints: []ir.Paint{{
							Type:  "SOLID",
							Color: &ir.Color{R: 17.0 / 255.0, G: 24.0 / 255.0, B: 39.0 / 255.0, A: 1},
						}},
						Font:       &ir.Font{Family: "Inter", Size: 16},
						LineHeight: &ir.LineHeight{Value: 20, Units: "PIXELS"},
					},
				},
				{
					ID:           "image_1",
					Type:         ir.FigmaRoundedRectangle,
					Name:         "Image",
					Role:         ir.RoleImageView,
					SchemaID:     "schema_image_1",
					Seq:          3,
					SourceBBox:   ir.BBox{X: 20, Y: 80, Width: 120, Height: 80},
					FigmaBBox:    ir.BBox{X: 20, Y: 80, Width: 120, Height: 80},
					RelativeBBox: ir.BBox{X: 20, Y: 80, Width: 120, Height: 80},
					Asset:        &ir.Asset{Kind: "image", Hash: "hash_1"},
					Style:        ir.Style{Visible: true},
				},
				{
					ID:           "button_1",
					Type:         ir.FigmaFrame,
					Name:         "Button",
					Role:         ir.RoleButton,
					SchemaID:     "schema_button_1",
					Seq:          4,
					SourceBBox:   ir.BBox{X: 16, Y: 180, Width: 140, Height: 44},
					FigmaBBox:    ir.BBox{X: 16, Y: 180, Width: 140, Height: 44},
					RelativeBBox: ir.BBox{X: 16, Y: 180, Width: 140, Height: 44},
					Style:        ir.Style{Visible: true},
					Children: []emitter.Node{
						{
							ID:           "button_bg",
							Type:         ir.FigmaRoundedRectangle,
							Name:         "Background",
							Role:         ir.RoleBgButton,
							SchemaID:     "schema_button_bg",
							Seq:          5,
							SourceBBox:   ir.BBox{X: 16, Y: 180, Width: 140, Height: 44},
							FigmaBBox:    ir.BBox{X: 16, Y: 180, Width: 140, Height: 44},
							RelativeBBox: ir.BBox{X: 0, Y: 0, Width: 140, Height: 44},
							Style: ir.Style{
								Visible: true,
								FillPaints: []ir.Paint{{
									Type:  "SOLID",
									Color: &ir.Color{R: 37.0 / 255.0, G: 99.0 / 255.0, B: 235.0 / 255.0, A: 1},
								}},
								CornerRadius: &ir.CornerRadius{TopLeft: 8, TopRight: 8, BottomRight: 8, BottomLeft: 8},
							},
						},
					},
				},
			},
		},
		Summary: emitter.Summary{
			NodeCount:  5,
			MaxDepth:   3,
			RoleCounts: map[string]int{"TextView": 1},
		},
	}
}
