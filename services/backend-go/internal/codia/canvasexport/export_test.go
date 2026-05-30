package canvasexport

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/canvas"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestExportProducesAnalyzableCodiaCanvas(t *testing.T) {
	doc := fixtureIR()
	result, err := Export(doc)
	if err != nil {
		t.Fatalf("Export() error = %v", err)
	}
	analysis, err := canvas.Analyze(canvas.CanvasDocument{Version: result.Document.Version, Root: result.Document.Root}, "generated.canvas.json", "")
	if err != nil {
		t.Fatalf("generated canvas should analyze: %v", err)
	}
	if analysis.CanvasVersion != 101 {
		t.Fatalf("unexpected canvas version: %d", analysis.CanvasVersion)
	}
	if analysis.DesignFrameName != "Figma design - source.png" {
		t.Fatalf("unexpected design frame name: %q", analysis.DesignFrameName)
	}
	if analysis.RootName != "Root" || analysis.RoleCounts["root"] != 1 {
		t.Fatalf("expected Root role, analysis=%#v", analysis)
	}
	if analysis.RoleCounts["TextView"] != 1 || analysis.Text.NameCharacterMatch != 1 {
		t.Fatalf("expected TextView to round-trip, text=%#v roles=%#v", analysis.Text, analysis.RoleCounts)
	}
	if analysis.RoleCounts["ImageView"] != 1 || analysis.ImageFills.ImageFillCount != 1 {
		t.Fatalf("expected ImageView image fill, image=%#v roles=%#v", analysis.ImageFills, analysis.RoleCounts)
	}
	if len(analysis.RoleMappingViolations) != 0 {
		t.Fatalf("expected role mapping clean, got %#v", analysis.RoleMappingViolations)
	}
	if len(result.Report.UnsupportedNotes) == 0 {
		t.Fatalf("expected unsupported notes in report")
	}
}

func fixtureIR() ir.Document {
	rootBox := ir.BBox{X: 0, Y: 0, Width: 120, Height: 80}
	textBox := ir.BBox{X: 10, Y: 10, Width: 40, Height: 18}
	imageBox := ir.BBox{X: 60, Y: 12, Width: 40, Height: 32}
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  rootBox,
		FigmaBBox:   rootBox,
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		SchemaID:    "root_0",
		Seq:         0,
		HasSeq:      true,
		Style:       ir.Style{Visible: true, Opacity: 1},
		Children: []ir.Node{
			{
				ID:          "text_1",
				Role:        ir.RoleTextView,
				SourceBBox:  textBox,
				FigmaBBox:   textBox,
				FigmaType:   ir.FigmaText,
				VisibleName: "Hi",
				SchemaID:    "TextView_10_10_1",
				Seq:         1,
				HasSeq:      true,
				Text:        &ir.Text{Characters: "Hi"},
				Style:       ir.Style{Visible: true, Opacity: 1},
			},
			{
				ID:          "image_1",
				Role:        ir.RoleImageView,
				SourceBBox:  imageBox,
				FigmaBBox:   imageBox,
				FigmaType:   ir.FigmaRoundedRectangle,
				VisibleName: "Image",
				SchemaID:    "ImageView_60_12_2",
				Seq:         2,
				HasSeq:      true,
				Asset:       &ir.Asset{Kind: "crop", Hash: "image_1"},
				Style: ir.Style{Visible: true, Opacity: 1, FillPaints: []ir.Paint{{
					Type: "IMAGE",
				}}},
			},
		},
	}
	return ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Source:     ir.Source{InputPath: "/tmp/source.png"},
		Root:       root,
		Summary: ir.Summary{
			NodeCount:       3,
			MaxDepth:        1,
			RoleCounts:      map[string]int{"root": 1, "TextView": 1, "ImageView": 1},
			FigmaTypeCounts: map[string]int{"FRAME": 1, "TEXT": 1, "ROUNDED_RECTANGLE": 1},
		},
	}
}
